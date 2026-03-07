# DD-MOD-001 — DocAnalyzer 模块详细设计

> **文档编号**: DD-MOD-001  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/doc_analyzer.py` (291 行)  
> **上游文档**: [OD-MOD-001](../04-outline-design/OD-MOD-001-doc_analyzer.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                     DocAnalyzer                          │
├──────────────────────────────────────────────────────────┤
│ - project_path      : Path                               │
│ - doc_set_config    : Dict[str, str]                     │
│ - llm_base          : str                                │
│ - llm_key           : str                                │
│ - llm_model         : str                                │
├──────────────────────────────────────────────────────────┤
│ + __init__(project_path, doc_set_config,                 │
│            llm_base, llm_key, llm_model)                 │
│ + load_doc_set() → Dict[str, str]                        │
│ + analyze_and_decompose(sprint?, extra_context?)         │
│                        → List[CodingTask]    «async»     │
│ + get_doc_set_summary() → Dict[str, int]                 │
│ - _build_decompose_prompt(doc_set, sprint,               │
│                           extra_context) → str           │
│ - _call_llm(prompt) → str               «async»         │
│ - _parse_tasks_from_llm(response) → List[CodingTask]    │
│ - _extract_json(text) → Any             «static»        │
└──────────────────────────────────────────────────────────┘
         ▲ 使用                  ▲ 使用
         │                       │
  ┌──────┴──────┐      ┌────────┴────────┐
  │  CodingTask │      │  httpx.AsyncClient│
  │ (task_models)│      │ (外部依赖)        │
  └─────────────┘      └─────────────────┘
```

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self, project_path: str, doc_set_config: Dict[str, str], llm_base: str = "", llm_key: str = "", llm_model: str = "")` |
| **职责** | 初始化分析器，存储项目路径和 LLM 配置 |
| **算法** | 直接赋值，`project_path` 转为 `Path` 对象 |
| **异常** | 无 (延迟校验) |

### 2.2 `load_doc_set`

| 项目 | 内容 |
|------|------|
| **签名** | `load_doc_set(self) → Dict[str, str]` |
| **职责** | 按 glob 模式加载项目文档集 |
| **输入** | 无参数 (使用 `self.doc_set_config`) |
| **输出** | `{doc_type: combined_content}`，每个 key 是文档类型，value 是拼合后的全部文件内容 |
| **算法** | ALG-001 |
| **异常** | 文件读取失败 → 打 warning 跳过；空 pattern → 跳过 |

#### ALG-001: 文档集加载算法

```
function load_doc_set():
    result = {}
    for (doc_type, pattern) in doc_set_config:
        if pattern is empty: continue
        
        full_pattern = is_absolute(pattern) ? pattern : project_path / pattern
        matched_files = sorted(glob(full_pattern, recursive=True))
        
        if matched_files is empty:
            log.warning("未匹配到文件: %s", pattern)
            continue
        
        parts = []
        for filepath in matched_files:
            try:
                content = read_text(filepath, utf-8)
                rel_path = relative_to(filepath, project_path)
                parts.append("=== {rel_path} ===\n{content}")
            except Exception:
                log.warning("读取失败: %s", filepath)
        
        if parts is not empty:
            result[doc_type] = join(parts, "\n\n")
            log.info("加载 %d 个文件 for '%s'", len(parts), doc_type)
    
    return result
```

**复杂度**: O(F) 其中 F 为总匹配文件数

### 2.3 `analyze_and_decompose`

| 项目 | 内容 |
|------|------|
| **签名** | `async analyze_and_decompose(self, sprint: Optional[int] = None, extra_context: str = "") → List[CodingTask]` |
| **职责** | 调用 LLM 将文档集自动分解为编码任务列表 |
| **输入** | `sprint` — 可选 Sprint 编号过滤；`extra_context` — 补充说明 |
| **输出** | `List[CodingTask]`，失败时返回空列表 |
| **算法** | ALG-002 |
| **异常** | LLM 调用/解析异常 → catch + 返回 `[]` |

#### ALG-002: 任务分解主流程

```
async function analyze_and_decompose(sprint, extra_context):
    doc_set = self.load_doc_set()
    if doc_set is empty:
        log.error("文档集为空")
        return []
    
    prompt = _build_decompose_prompt(doc_set, sprint, extra_context)
    
    try:
        response = await _call_llm(prompt)
        tasks = _parse_tasks_from_llm(response)
        log.info("分解出 %d 个任务", len(tasks))
        return tasks
    except Exception as e:
        log.error("LLM 任务分解失败: %s", e)
        return []
```

### 2.4 `_build_decompose_prompt`

| 项目 | 内容 |
|------|------|
| **签名** | `_build_decompose_prompt(self, doc_set: Dict[str,str], sprint: Optional[int], extra_context: str) → str` |
| **职责** | 构建发送给 LLM 的系统分解 prompt |
| **算法** | ALG-003 |
| **约束** | 单文档截断阈值 `MAX_DOC_LEN = 6000` 字符 |

#### ALG-003: Prompt 构建算法 (含智能截断 ★v1.2)

```
function _build_decompose_prompt(doc_set, sprint, extra_context):
    # ★v1.2 A-126: 从配置读取，默认 6000
    MAX_DOC_LEN = config.get("llm.doc_max_len", 6000)
    
    doc_sections = []
    
    # ★v1.2: 智能截断优先级 — 确保高价值文档类型获得更多空间
    PRIORITY_ORDER = [
        "requirements",    # 需求文档最优先
        "contracts",       # 接口契约次优先
        "sprint_cards",    # Sprint 任务卡
        "design",          # 设计文档
    ]
    # 未在优先级列表中的文档类型，获得较短的截断额度
    sorted_doc_types = []
    for dt in PRIORITY_ORDER:
        if dt in doc_set:
            sorted_doc_types.append(dt)
    for dt in doc_set:
        if dt not in sorted_doc_types:
            sorted_doc_types.append(dt)
    
    for doc_type in sorted_doc_types:
        content = doc_set[doc_type]
        truncated = content[:MAX_DOC_LEN]
        if len(content) > MAX_DOC_LEN:
            truncated += f"\n\n... (截断, 原文 {len(content)} 字符)"
        doc_sections.append(f"## {doc_type}\n{truncated}")
    
    docs_text = join(doc_sections, "\n\n---\n\n")
    sprint_hint = sprint ? "注意: 只分解 Sprint {sprint}" : ""
    extra_hint = extra_context ? "## 补充说明\n{extra_context}" : ""
    
    return PROMPT_TEMPLATE.format(docs_text, sprint_hint, extra_hint)
```

**★v1.2 变更说明**:
- `MAX_DOC_LEN` 从硬编码 6000 改为通过 `config.get("llm.doc_max_len", 6000)` 读取，支持运维按照 LLM 上下文窗口大小调整
- 智能截断优先级: requirements > contracts > sprint_cards > design > 其他，确保高价值文档优先被包含

**Prompt 模板包含**:
- 角色定义（任务分解引擎）
- 文档集内容（截断后）
- 输出 JSON schema 示例
- 7 条分解规则（task_id 格式、tags 必填、target_dir、acceptance 等）

### 2.5 `_call_llm` (含重试机制 ★v1.1)

| 项目 | 内容 |
|------|------|
| **签名** | `async _call_llm(self, prompt: str) → str` |
| **职责** | 通过 OpenAI-compatible API 调用 LLM，内置指数退避重试 |
| **依赖** | `httpx.AsyncClient` |
| **参数** | `temperature=0.2`, `max_tokens=4096`, `timeout=180s` |
| **重试策略** | 最多 3 次，指数退避 1s→2s→4s |
| **异常** | 未配置 API → `RuntimeError`；重试耗尽 → `LLMConnectionError` (ERR-009) |

**请求结构**:
```json
{
    "model": "{self.llm_model or 'gpt-4'}",
    "messages": [{"role": "user", "content": "{prompt}"}],
    "temperature": 0.2,
    "max_tokens": 4096
}
```

#### ALG-005: LLM 调用与指数退避重试 ★v1.1

```
async function _call_llm(prompt):
    if not self.llm_base or not self.llm_key:
        raise RuntimeError("LLM 未配置")
    
    MAX_RETRIES = 3
    BACKOFF_BASE = 1      # 秒
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{self.llm_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.llm_key}"},
                    json={"model": model, "temperature": 0.2,
                          "max_tokens": 4096,
                          "messages": [{"role": "user", "content": prompt}]}
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                # 429 速率限制: 优先读取 Retry-After 头
                retry_after = int(e.response.headers.get("Retry-After", 
                                  BACKOFF_BASE * (2 ** (attempt - 1))))
                log.warning("LLM 429 速率限制, 等待 %ds (第 %d/%d 次)",
                            retry_after, attempt, MAX_RETRIES)
                await asyncio.sleep(retry_after)
            elif e.response.status_code >= 500:
                # 5xx 服务端错误: 标准退避
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                log.warning("LLM %d 错误, 退避 %ds (第 %d/%d 次)",
                            e.response.status_code, wait, attempt, MAX_RETRIES)
                await asyncio.sleep(wait)
            else:
                # 4xx (非 429): 不可重试
                raise
        
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning("LLM 连接/超时错误, 退避 %ds (第 %d/%d 次)",
                        wait, attempt, MAX_RETRIES)
            await asyncio.sleep(wait)
    
    # 重试耗尽
    log.error("LLM 调用失败, 已重试 %d 次: %s", MAX_RETRIES, last_error)
    raise LLMConnectionError(f"LLM 重试耗尽: {last_error}")   # ERR-009
```

**重试决策矩阵**:

| HTTP 状态 | 是否重试 | 退避策略 | 说明 |
|-----------|---------|---------|------|
| 429 | ✅ | `Retry-After` 头优先 | 速率限制 (ERR-026) |
| 500~599 | ✅ | 指数退避 1s→2s→4s | 服务端临时故障 |
| 400~499 (非429) | ❌ | 立即抛出 | 请求本身有误，重试无意义 |
| 连接超时 | ✅ | 指数退避 1s→2s→4s | 网络问题 |
| 重试耗尽 | — | 抛 `LLMConnectionError` | 上游 `analyze_and_decompose` catch 后返回 `[]` |

### 2.5a LLM 审计日志 ★v1.2

> 对应 ACTION-ITEM v2.1 A-125: 记录每次 LLM 调用的请求/响应，支撑质量追溯和成本分析

每次 `_call_llm` 调用成功后，将请求与响应存储白到审计日志目录。

**存储结构**:
```
logs/llm_audit/
├── 2026-03-07/
│   ├── 143201_doc_analyzer_req.json
│   ├── 143201_doc_analyzer_resp.json
│   ├── 143512_reviewer_l2_req.json
│   ├── 143512_reviewer_l2_resp.json
│   └── ...
└── 2026-03-08/
    └── ...
```

**审计记录格式**:
```json
// *_req.json
{
  "timestamp": "2026-03-07T14:32:01",
  "module": "doc_analyzer",
  "model": "claude-sonnet-4-6",
  "temperature": 0.2,
  "max_tokens": 4096,
  "prompt_chars": 12345,
  "prompt_preview": "(前 200 字符)..."
}

// *_resp.json
{
  "timestamp": "2026-03-07T14:32:08",
  "module": "doc_analyzer",
  "status": "success",
  "response_chars": 3456,
  "latency_ms": 7200,
  "retry_count": 0,
  "response_preview": "(前 200 字符)..."
}
```

**设计决策**:
| 决策 | 说明 |
|------|------|
| 分日子目录 | 方便按日期清理和归档 |
| 只存 preview | 完整 prompt/response 可能包含敏感信息，仅存前 200 字符摘要 |
| 不阻塞主流程 | 审计写入失败仅 WARNING，不影响 LLM 调用结果 |
| 复用设计 | DocAnalyzer 和 AutoReviewer (DD-MOD-008) 共享相同审计格式，通过 `module` 字段区分来源 |

### 2.6 `_parse_tasks_from_llm`

| 项目 | 内容 |
|------|------|
| **签名** | `_parse_tasks_from_llm(self, response: str) → List[CodingTask]` |
| **职责** | 将 LLM 文本回复解析为 CodingTask 列表，含字段类型校验 |
| **算法** | 调用 `_extract_json` → 遍历数组 → 字段校验 → 构造 CodingTask |
| **异常** | 非数组 → `ValueError` |

#### ALG-006: 任务解析与字段校验 ★v1.2

> 对应 ACTION-ITEM v2.1 A-128: 防止 LLM 返回类型不匹配的字段值

```
function _parse_tasks_from_llm(response):
    data = _extract_json(response)
    if not isinstance(data, list):
        raise ValueError("期望 JSON 数组, 实际类型: " + type(data).__name__)
    
    tasks = []
    for i, item in enumerate(data):
        # ★v1.2: 字段类型校验 & 清洗
        errors = []
        
        # task_id: 必填, str, 非空
        task_id = item.get("task_id")
        if not task_id or not isinstance(task_id, str):
            errors.append(f"task_id 缺失或非字符串")
        
        # description: 必填, str, 非空
        description = item.get("description")
        if not description or not isinstance(description, str):
            errors.append(f"description 缺失或非字符串")
        
        # estimated_minutes: int, >0
        est = item.get("estimated_minutes", 30)
        if not isinstance(est, (int, float)) or est <= 0:
            log.warning("任务[%d] estimated_minutes 无效(%s), 回退默认 30", i, est)
            item["estimated_minutes"] = 30
        else:
            item["estimated_minutes"] = int(est)  # float → int
        
        # tags: list of str
        tags = item.get("tags", [])
        if not isinstance(tags, list):
            log.warning("任务[%d] tags 非数组(%s), 回退空列表", i, type(tags).__name__)
            item["tags"] = []
        else:
            item["tags"] = [str(t) for t in tags]  # 确保全为 str
        
        # depends_on: list of str
        deps = item.get("depends_on", [])
        if not isinstance(deps, list):
            log.warning("任务[%d] depends_on 非数组, 回退空列表", i)
            item["depends_on"] = []
        
        # 必填字段缺失则跳过该任务
        if errors:
            log.error("跳过无效任务[%d]: %s", i, "; ".join(errors))
            continue
        
        tasks.append(CodingTask(**{
            k: v for k, v in item.items()
            if k in CodingTask.__dataclass_fields__
        }))
    
    log.info("解析出 %d 个有效任务 (原始 %d 项)", len(tasks), len(data))
    return tasks
```

**校验规则汇总**:

| 字段 | 类型要求 | 失败策略 | 说明 |
|------|---------|---------|------|
| `task_id` | str, 非空 | 跳过该任务 | 必填标识，无法回退 |
| `description` | str, 非空 | 跳过该任务 | 必填描述，无法回退 |
| `estimated_minutes` | int, >0 | 回退 30 | LLM 可能返回字符串或负数 |
| `tags` | List[str] | 回退 [] | LLM 可能返回字符串 |
| `depends_on` | List[str] | 回退 [] | LLM 可能返回单值 |

> 与 DD-MOD-005 §3.2 `__post_init__` 形成双层防御: §2.6 做类型清洗, `__post_init__` 做格式校验

### 2.7 `_extract_json` (静态方法)

| 项目 | 内容 |
|------|------|
| **签名** | `@staticmethod _extract_json(text: str) → Any` |
| **职责** | 从 LLM 回复中提取 JSON |
| **算法** | ALG-004 |

#### ALG-004: JSON 三级回退提取

```
function _extract_json(text):
    text = text.strip()
    
    # Level 1: 直接解析
    if text.startswith("[") or text.startswith("{"):
        try: return json.loads(text)
        except: pass
    
    # Level 2: ```json``` 代码块提取
    match = regex.search(r"```(?:json)?\s*\n(.*?)\n```", text, DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except: pass
    
    # Level 3: 搜索第一个 [ 到最后一个 ]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try: return json.loads(text[start:end+1])
        except: pass
    
    raise ValueError("无法解析 JSON")
```

### 2.8 `get_doc_set_summary`

| 项目 | 内容 |
|------|------|
| **签名** | `get_doc_set_summary(self) → Dict[str, int]` |
| **职责** | 返回文档集统计：`{doc_type: 文件数}` |
| **算法** | 遍历 `doc_set_config`，对每个 pattern 执行 glob 计数 |

---

## §3 序列图

### SEQ-001: 文档分析完整流程

```
Orchestrator          DocAnalyzer          LLM API          CodingTask
    │                     │                   │                  │
    │  analyze_and_       │                   │                  │
    │  decompose(sprint)  │                   │                  │
    │────────────────────>│                   │                  │
    │                     │  load_doc_set()   │                  │
    │                     │──────┐            │                  │
    │                     │      │ glob + read│                  │
    │                     │<─────┘            │                  │
    │                     │                   │                  │
    │                     │ _build_prompt()   │                  │
    │                     │──────┐            │                  │
    │                     │      │ 截断+模板  │                  │
    │                     │<─────┘            │                  │
    │                     │                   │                  │
    │                     │  POST /chat/      │                  │
    │                     │  completions      │                  │
    │                     │──────────────────>│                  │
    │                     │                   │                  │
    │                     │  JSON response    │                  │
    │                     │<──────────────────│                  │
    │                     │                   │                  │
    │                     │ _extract_json()   │                  │
    │                     │──────┐            │                  │
    │                     │      │ 3级回退    │                  │
    │                     │<─────┘            │                  │
    │                     │                   │                  │
    │                     │                   │    new CodingTask│
    │                     │──────────────────────────────────────>
    │                     │                   │                  │
    │  List[CodingTask]   │                   │                  │
    │<────────────────────│                   │                  │
```

---

## §4 数据结构

### 4.1 doc_set_config 格式

```yaml
# config.yaml → doc_set 节
doc_set:
  requirements: "docs/01-requirements/**/*.md"
  design: "docs/04-outline-design/*.md"
  contracts: "contracts/*.yaml"
```

### 4.2 LLM 输出 JSON Schema

```json
[
  {
    "task_id": "S1_T1",           // string, 必填
    "description": "...",          // string, 必填
    "tags": ["python", "web"],     // List[str], 必填
    "target_dir": "src/auth/",     // string, 可选
    "acceptance": ["..."],         // List[str], 可选
    "depends_on": [],              // List[str], 可选
    "estimated_minutes": 30,       // int, 可选 (默认 30)
    "context_files": ["..."]       // List[str], 可选
  }
]
```

---

## §5 配置与常量

| 常量/配置 | 值 | 说明 |
|-----------|---|------|
| `MAX_DOC_LEN` | `config.get("llm.doc_max_len", 6000)` | 单文档截断阈值 (字符数) ★v1.2: 可配置 |
| `temperature` | 0.2 | LLM 调用温度 |
| `max_tokens` | 4096 | LLM 最大回复 token 数 |
| `timeout` | 180s | httpx 客户端超时 |

---

## §6 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §1 提取并扩充，形成独立模块详述 |
| v1.1 | 2026-03-07 | `_call_llm` 增加 3× 指数退避重试 (ALG-005); 新增重试决策矩阵 |
| v1.2 | 2026-03-07 | §2.5a LLM 审计日志; §2.6 字段类型校验 (A-125/A-128); MAX_DOC_LEN 可配置化 (A-126) |
