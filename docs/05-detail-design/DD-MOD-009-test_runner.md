# DD-MOD-009 — TestRunner 模块详细设计

> **文档编号**: DD-MOD-009  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/test_runner.py` (342 行)  
> **上游文档**: [OD-MOD-009](../04-outline-design/OD-MOD-009-test_runner.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                      TestRunner                          │
├──────────────────────────────────────────────────────────┤
│ + config         : Config                                │
│ + timeout        : int                                   │
├──────────────────────────────────────────────────────────┤
│ + __init__(config)                                       │
│ + run_tests(task, result) → TestResult       «async»     │
│ - _discover_test_files(task) → List[str]                 │
│ - _run_pytest(test_files) → (int, str, str)  «async»     │
│ - _parse_json_report(report_path) → TestResult           │
│ - _parse_pytest_output(stdout, stderr) → TestResult      │
│ - _apply_fallback_threshold(test_result, task) → None    │
│ - _build_acceptance_criteria(task) → List[AcceptanceCriterion] │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│               AcceptanceCriterion (dataclass)             │
├──────────────────────────────────────────────────────────┤
│ + description  : str                                     │
│ + test_pattern : str          # 测试文件名 glob          │
│ + threshold    : float        # 通过率阈值 (0.0-1.0)     │
│ + weight       : float        # 权重 (默认 1.0)          │
└──────────────────────────────────────────────────────────┘
```

---

## §2 核心函数设计

### 2.1 `run_tests` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async run_tests(self, task: CodingTask, result: TaskResult) → TestResult` |
| **职责** | 执行测试并返回结构化结果 |
| **算法** | ALG-017 |

#### ALG-017: 测试执行主流程

```
async function run_tests(task, result):
    # 1. 发现测试文件
    test_files = _discover_test_files(task)
    if not test_files:
        return TestResult(passed=True, reason="无可用测试文件")
    
    # 2. 执行 pytest (JSON 报告模式)
    report_path = f"/tmp/pytest_report_{task.task_id}.json"
    exit_code, stdout, stderr = await _run_pytest(
        test_files, report_path
    )
    
    # 3. 解析结果 (双路径)
    if os.path.exists(report_path):
        test_result = _parse_json_report(report_path)
    else:
        test_result = _parse_pytest_output(stdout, stderr)
    
    # 4. Bug17 修复: 回退阈值判定
    _apply_fallback_threshold(test_result, task)
    
    # 5. 关联元数据
    test_result.task_id = task.task_id
    test_result.exit_code = exit_code
    
    return test_result
```

### 2.2 `_discover_test_files`

| 项目 | 内容 |
|------|------|
| **签名** | `_discover_test_files(self, task: CodingTask) → List[str]` |
| **职责** | 三层策略发现测试文件 |
| **算法** | ALG-018 |

#### ALG-018: 三层测试发现策略

```
function _discover_test_files(task):
    candidates = []
    
    # Tier 1: 精确匹配
    # tests/test_{task_id}.py 或 tests/{target_module}_test.py
    exact_patterns = [
        f"tests/test_{task.task_id}.py",
        f"tests/test_{task.module_name}.py",
    ]
    for pattern in exact_patterns:
        if os.path.exists(pattern):
            candidates.append(pattern)
    
    if candidates:
        return candidates
    
    # Tier 2: 目录扫描
    test_dir = f"tests/{task.target_dir}"
    if os.path.isdir(test_dir):
        for f in glob.glob(f"{test_dir}/test_*.py"):
            candidates.append(f)
    
    if candidates:
        return candidates
    
    # Tier 3: 宽泛模式
    for f in glob.glob("tests/**/test_*.py", recursive=True):
        if task.module_name in f or task.target_dir in f:
            candidates.append(f)
    
    return candidates
```

### 2.3 `_run_pytest`

| 项目 | 内容 |
|------|------|
| **签名** | `async _run_pytest(self, test_files, report_path) → Tuple[int, str, str]` |
| **命令** | `pytest {files} --json-report --json-report-file={path} -v --tb=short -q` |
| **超时** | `config.test_timeout` (默认 300s) |
| **实现** | `asyncio.create_subprocess_exec` |

### 2.4 `_parse_json_report`

| 项目 | 内容 |
|------|------|
| **签名** | `_parse_json_report(self, report_path: str) → TestResult` |
| **输入** | pytest-json-report 生成的 JSON 文件 |
| **算法** | ALG-019 |

#### ALG-019: JSON 报告解析

```
function _parse_json_report(report_path):
    data = json.load(open(report_path))
    summary = data.get("summary", {})
    
    total   = summary.get("total", 0)
    passed  = summary.get("passed", 0)
    failed  = summary.get("failed", 0)
    errors  = summary.get("error", 0)
    skipped = summary.get("skipped", 0)
    
    pass_rate = passed / total if total > 0 else 0.0
    
    # 提取失败详情
    failures = []
    for test in data.get("tests", []):
        if test["outcome"] in ("failed", "error"):
            failures.append({
                "nodeid": test["nodeid"],
                "message": test.get("call", {}).get("longrepr", "")[:500]
            })
    
    return TestResult(
        total=total,
        passed_count=passed,
        failed_count=failed + errors,
        skipped_count=skipped,
        pass_rate=pass_rate,
        failures=failures,
        passed=(failed + errors == 0)
    )
```

### 2.5 `_parse_pytest_output` (回退解析)

| 项目 | 内容 |
|------|------|
| **签名** | `_parse_pytest_output(self, stdout: str, stderr: str) → TestResult` |
| **职责** | JSON 报告不可用时的正则回退 |
| **正则** | `(\d+) passed`, `(\d+) failed`, `(\d+) error` |

### 2.6 `_apply_fallback_threshold` ★ (Bug17 修复)

| 项目 | 内容 |
|------|------|
| **签名** | `_apply_fallback_threshold(self, test_result: TestResult, task: CodingTask) → None` |
| **算法** | ALG-020 |

#### ALG-020: 回退阈值判定 (Bug17)

```
function _apply_fallback_threshold(test_result, task):
    """
    Bug17: 原始逻辑仅看 failed_count == 0 判 passed。
    修复后: 如果通过率 >= task 阈值，也判为通过。
    """
    if test_result.passed:
        return   # 已通过不再处理
    
    threshold = task.pass_threshold   # 默认 0.8
    if test_result.total > 0 and test_result.pass_rate >= threshold:
        test_result.passed = True
        test_result.reason = (
            f"部分通过: {test_result.pass_rate:.0%} >= "
            f"阈值 {threshold:.0%}"
        )
```

**设计动机**: 真实场景中 AI 生成的测试用例可能包含边界 case 未能完全通过，但核心功能已实现。通过阈值机制避免无限重试。

---

## §3 序列图

### SEQ-009: 测试执行与结果解析

```
Orchestrator    TestRunner        pytest          JSON Report
    │               │               │               │
    │ run_tests     │               │               │
    │──────────────>│               │               │
    │               │               │               │
    │               │ discover      │               │
    │               │ test files    │               │
    │               │───┐           │               │
    │               │<──┘           │               │
    │               │               │               │
    │               │ run pytest    │               │
    │               │──────────────>│               │
    │               │               │ write report  │
    │               │               │──────────────>│
    │               │  exit_code    │               │
    │               │<──────────────│               │
    │               │               │               │
    │               │ parse report  │               │
    │               │──────────────────────────────>│
    │               │  TestResult   │               │
    │               │<──────────────────────────────│
    │               │               │               │
    │               │ apply_fallback│               │
    │               │ _threshold    │               │
    │               │───┐           │               │
    │               │<──┘           │               │
    │               │               │               │
    │  TestResult   │               │               │
    │<──────────────│               │               │
```

---

## §4 配置参数

| 配置路径 | 类型 | 默认值 | 说明 |
|----------|------|--------|------|
| `task.test_timeout` | int | 300 | pytest 超时秒数 |
| `task.pass_threshold` | float | 0.8 | 回退通过率阈值 |

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §9 提取并扩充，包含 Bug17 修复算法 |
