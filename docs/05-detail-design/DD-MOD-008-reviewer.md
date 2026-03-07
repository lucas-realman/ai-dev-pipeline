# DD-MOD-008 — AutoReviewer 模块详细设计

> **文档编号**: DD-MOD-008  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/reviewer.py` (263 行)  
> **上游文档**: [OD-MOD-008](../04-outline-design/OD-MOD-008-reviewer.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                     AutoReviewer                         │
├──────────────────────────────────────────────────────────┤
│ + config       : Config                                  │
│ + llm_url      : str                                     │
│ + llm_key      : str                                     │
│ + model        : str                                     │
├──────────────────────────────────────────────────────────┤
│ + __init__(config)                                       │
│ + review_task(task, result) → ReviewResult   «async»     │
│ - _run_l1_static(result) → (bool, str)                   │
│ - _run_l2_contract(task, result) → (bool, str) «async»   │
│ - _run_l3_quality(task, result) → (float, str) «async»   │
│ - _call_llm(system, user) → str             «async»      │
│ - _parse_json_response(text) → dict          «static»    │
│ - _read_contracts() → str                                │
│ - _build_code_snippet(result) → str                      │
└──────────────────────────────────────────────────────────┘
```

**ReviewLayer 枚举** (来自 task_models):
```
L1_STATIC   = "L1_static"      # py_compile + ruff
L2_CONTRACT = "L2_contract"    # LLM 契约检查
L3_QUALITY  = "L3_quality"     # LLM 5 维评分
```

---

## §2 核心函数设计

### 2.1 `review_task` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async review_task(self, task: CodingTask, result: TaskResult) → ReviewResult` |
| **职责** | 按层级执行代码审查，任一层失败即 early-return |
| **算法** | ALG-015 |

#### ALG-015: 三层审查流水线

```
async function review_task(task, result):
    # L1: 静态检查 (无 LLM)
    l1_pass, l1_msg = _run_l1_static(result)
    if not l1_pass:
        return ReviewResult(
            passed=False,
            layer=ReviewLayer.L1_STATIC,
            score=0.0,
            comments=l1_msg,
            fix_instruction="修复编译/lint 错误:\n" + l1_msg
        )
    
    # L2: 契约遵从 (LLM)
    l2_pass, l2_msg = await _run_l2_contract(task, result)
    if not l2_pass:
        return ReviewResult(
            passed=False,
            layer=ReviewLayer.L2_CONTRACT,
            score=2.0,
            comments=l2_msg,
            fix_instruction="契约违规需修复:\n" + l2_msg
        )
    
    # L3: 质量评分 (LLM)
    score, l3_msg = await _run_l3_quality(task, result)
    threshold = config.review_threshold   # 默认 3.5
    
    return ReviewResult(
        passed=(score >= threshold),
        layer=ReviewLayer.L3_QUALITY,
        score=score,
        comments=l3_msg,
        fix_instruction=l3_msg if score < threshold else ""
    )
```

---

### 2.2 `_run_l1_static`

| 项目 | 内容 |
|------|------|
| **签名** | `_run_l1_static(self, result: TaskResult) → Tuple[bool, str]` |
| **职责** | 对变更文件执行静态分析 |
| **算法** | ALG-016 |

#### ALG-016: L1 静态检查

```
function _run_l1_static(result):
    errors = []
    for file in result.files_changed:
        if not file.endswith('.py'):
            continue
        
        # 1. py_compile 语法检查
        try:
            py_compile.compile(file, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(e))
        
        # 2. ruff lint (选定规则)
        proc = subprocess.run(
            ['ruff', 'check', '--select', 'E9,F8,F6,F4', file],
            capture_output=True, text=True
        )
        if proc.returncode != 0:
            errors.append(proc.stdout)
    
    if errors:
        return (False, '\n'.join(errors))
    return (True, "L1 静态检查通过")
```

**ruff 规则选择**:

| 规则组 | 含义 |
|--------|------|
| E9 | 语法错误 (SyntaxError) |
| F8 | 未定义名称 (UndefinedName) |
| F6 | 重复键 |
| F4 | 重复导入 |

> 仅选严重问题，避免代码风格误报中断流水线。

---

### 2.3 `_run_l2_contract`

| 项目 | 内容 |
|------|------|
| **签名** | `async _run_l2_contract(self, task, result) → Tuple[bool, str]` |
| **职责** | 通过 LLM 校验代码是否遵从 contracts/*.yaml |
| **LLM 参数** | temp=0.1, max_tokens=2048 |

**System Prompt**:
```
你是代码审查专家。请判断以下代码是否违反了接口契约。
如果违反，给出具体违反的条目和修复建议。
返回 JSON: {"compliant": true/false, "violations": [...], "suggestions": "..."}
```

**User Prompt**: `契约内容 + 代码片段`

**降级策略**: LLM 重试耗尽 (3×) 后仍失败 → `(True, "L2 降级跳过")`, score 不影响

---

### 2.4 `_run_l3_quality`

| 项目 | 内容 |
|------|------|
| **签名** | `async _run_l3_quality(self, task, result) → Tuple[float, str]` |
| **职责** | LLM 5 维质量评分 |
| **LLM 参数** | temp=0.1, max_tokens=2048 |

**评分维度**:

| 维度 | 权重 | 说明 |
|------|------|------|
| 功能完整性 | 1/5 | 是否实现了 task.description 的全部需求 |
| 接口正确性 | 1/5 | 函数签名与契约是否一致 |
| 错误处理 | 1/5 | 异常处理的完备性 |
| 代码质量 | 1/5 | 命名、结构、可读性 |
| 可运行性 | 1/5 | 依赖完整、能直接执行 |

**System Prompt**:
```
你是代码质量评审专家。对以下代码从 5 个维度打分 (1-5)。
返回 JSON:
{
  "scores": {"功能完整性": N, "接口正确性": N, ...},
  "average": N.N,
  "comments": "..."
}
```

**降级策略**: LLM 重试耗尽 (3×) 后仍失败 → 返回 `(3.5, "L3 降级: 待人工审查")` ★v1.1

> **v1.1 变更**: 降级分从 4.0 调整为 3.5 (= `review_threshold`)。此时 `score >= threshold` 仍为 True (边界值视为通过)，但降级任务会在报告中标记为「降级通过」，提醒人工关注。
> 
> **设计理由**: 原 score=4.0 > threshold 导致降级审查静默通过，人工无感知。改为 3.5 (= threshold) 使其刚好通过但不遮蔽降级事实。

---

### 2.5 `_call_llm` (含重试机制 ★v1.1)

| 项目 | 内容 |
|------|------|
| **签名** | `async _call_llm(self, system_prompt: str, user_prompt: str) → str` |
| **HTTP** | POST `{llm_url}/chat/completions` |
| **参数** | `{"model": model, "temperature": 0.1, "max_tokens": 2048, "messages": [...]}` |
| **超时** | `aiohttp.ClientTimeout(total=120)` |
| **重试策略** | 最多 3 次，指数退避 1s→2s→4s (与 DocAnalyzer ALG-005 共享策略) |
| **返回** | `response.choices[0].message.content` |

#### 重试逻辑

AutoReviewer 的 `_call_llm` 采用与 DocAnalyzer ALG-005 相同的重试策略:
- 429 速率限制 → 读取 `Retry-After` 头优先
- 5xx 服务端错误 → 指数退避 1s→2s→4s
- 4xx (非 429) → 不重试, 立即抛出
- 连接/超时 → 指数退避 1s→2s→4s
- 重试耗尽 → 抛出 `LLMConnectionError` (ERR-009), 由 L2/L3 降级策略兜底

### 2.6 `_parse_json_response` (静态方法)

| 项目 | 内容 |
|------|------|
| **签名** | `@staticmethod _parse_json_response(text: str) → dict` |
| **算法** | 与 DocAnalyzer ALG-004 同源的三级回退 |

```
Level 1: json.loads(text)
Level 2: 正则提取 ```json ... ``` 块
Level 3: 正则提取 { ... } 最外层花括号
```

---

## §3 序列图

### SEQ-008: 三层审查流程

```
Orchestrator     AutoReviewer      subprocess       LLM API
    │                │                │               │
    │ review_task    │                │               │
    │───────────────>│                │               │
    │                │                │               │
    │                │ L1: py_compile │               │
    │                │───────────────>│               │
    │                │     ok         │               │
    │                │<───────────────│               │
    │                │ L1: ruff check │               │
    │                │───────────────>│               │
    │                │     ok         │               │
    │                │<───────────────│               │
    │                │                │               │
    │                │ L2: contract   │               │
    │                │ prompt         │               │
    │                │───────────────────────────────>│
    │                │     {"compliant": true}        │
    │                │<───────────────────────────────│
    │                │                │               │
    │                │ L3: quality    │               │
    │                │ prompt         │               │
    │                │───────────────────────────────>│
    │                │     {"average": 4.2}           │
    │                │<───────────────────────────────│
    │                │                │               │
    │  ReviewResult  │                │               │
    │  (passed=True, │                │               │
    │   score=4.2)   │                │               │
    │<───────────────│                │               │
```

---

## §4 异常与降级

| 场景 | 处理策略 | 错误码 |
|------|---------|--------|
| ruff 未安装 | 跳过 L1 lint, 仅 py_compile | — |
| LLM L2 超时/异常 (重试 3× 后) | 降级为 compliant=True | ERR-009/010 |
| LLM L3 超时/异常 (重试 3× 后) | 降级分 score=3.5 (= threshold) ★v1.1 | ERR-009/010 |
| JSON 解析失败 | 三级回退解析；全部失败则降级 | ERR-010 |

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §8 提取并扩充，形成独立模块详述 |
| v1.1 | 2026-03-07 | `_call_llm` 增加 3× 指数退避重试; L3 降级分从 4.0 调为 3.5 |
