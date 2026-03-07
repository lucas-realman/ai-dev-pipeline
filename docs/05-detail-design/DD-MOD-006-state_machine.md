# DD-MOD-006 — StateMachine 模块详细设计

> **文档编号**: DD-MOD-006  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/state_machine.py` (148 行)  
> **上游文档**: [OD-MOD-006](../04-outline-design/OD-MOD-006-state_machine.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                 StateMachineError                         │
│                  (Exception)                              │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                 TaskStateMachine                          │
├──────────────────────────────────────────────────────────┤
│ + task         : CodingTask                              │
│ + max_retries  : int                                     │
├──────────────────────────────────────────────────────────┤
│ + __init__(task, max_retries=3,                          │
│            on_state_change=None)                          │
│ + enqueue() → None                                       │
│ + dispatch() → None                                      │
│ + coding_done(result: TaskResult) → None                 │
│ + start_review() → None                                  │
│ + review_done(review: ReviewResult) → None               │
│ + start_testing() → None                                 │
│ + test_done(test_result: TestResult) → None              │
│ + judge(test_result: TestResult) → None                  │
│ + handle_failure() → None                                │
│ + requeue() → None                                       │
│ «property» is_terminal → bool                            │
│ «property» is_retryable → bool                           │
│ «property» is_waiting → bool                             │
│ «property» can_dispatch → bool                           │
│ «property» needs_review → bool                           │
│ «property» needs_testing → bool                          │
│ - _transit(new_status: TaskStatus) → None                │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ 模块级常量                                                │
│ _TRANSITIONS: Dict[TaskStatus, List[TaskStatus]]         │
└──────────────────────────────────────────────────────────┘
```

---

## §2 状态转换表

### 2.1 _TRANSITIONS 完整定义

```python
_TRANSITIONS = {
    TaskStatus.CREATED:     [TaskStatus.QUEUED],
    TaskStatus.QUEUED:      [TaskStatus.DISPATCHED],
    TaskStatus.DISPATCHED:  [TaskStatus.CODING_DONE, TaskStatus.RETRY, TaskStatus.ESCALATED],
    TaskStatus.CODING_DONE: [TaskStatus.REVIEW],
    TaskStatus.REVIEW:      [TaskStatus.TESTING, TaskStatus.RETRY, TaskStatus.ESCALATED],
    TaskStatus.TESTING:     [TaskStatus.JUDGING],
    TaskStatus.JUDGING:     [TaskStatus.PASSED, TaskStatus.FAILED],
    TaskStatus.FAILED:      [TaskStatus.RETRY, TaskStatus.ESCALATED],
    TaskStatus.RETRY:       [TaskStatus.QUEUED],
    TaskStatus.PASSED:      [],           # 终态
    TaskStatus.ESCALATED:   [],           # 终态
}
```

### 2.2 状态转换图

```
  CREATED ──────> QUEUED ──────> DISPATCHED
                    ▲                │
                    │          ┌─────┴─────┐
                  RETRY        │           │
                    ▲     CODING_DONE    RETRY/
                    │          │        ESCALATED
               ┌────┤     REVIEW
               │    │       │
            FAILED  │  ┌────┴────┐
               ▲    │  │         │
               │    │ TESTING  RETRY/
            JUDGING │    │     ESCALATED
               │    │ JUDGING
          ┌────┴────┘    │
          │         ┌────┴────┐
        PASSED    PASSED    FAILED
```

---

## §3 核心函数设计

### 3.1 `_transit` (核心)

| 项目 | 内容 |
|------|------|
| **签名** | `_transit(self, new_status: TaskStatus) → None` |
| **职责** | 执行状态转换，验证合法性 |
| **算法** | ALG-012 |

#### ALG-012: 合法转换校验 (含持久化回调)

```
function _transit(new_status):
    old = task.status
    allowed = _TRANSITIONS.get(old, [])
    
    if new_status not in allowed:
        raise StateMachineError(
            "[{task_id}] 非法: {old} → {new_status}"
            " (允许: {allowed})"
        )
    
    task.status = new_status
    log.info("[%s] %s → %s", task_id, old, new_status)
    
    # ★v1.1: 持久化回调 — 通知 TaskEngine 保存快照
    if self._on_state_change is not None:
        try:
            self._on_state_change(task.task_id, old, new_status)
        except Exception as e:
            log.warning("持久化回调失败: %s (不阻塞状态转换)", e)
```

> **设计决策**: 回调失败不阻塞状态转换——状态机的首要职责是状态管理，持久化是 best-effort。回调由 TaskEngine 在创建 `TaskStateMachine(task, max_retries, on_state_change=self._save_snapshot)` 时注入。

### 3.2 便捷转换方法

| 方法 | 转换 | 附加逻辑 |
|------|------|---------|
| `enqueue()` | → QUEUED | 无 |
| `dispatch()` | → DISPATCHED | `task.started_at = time.time()` |
| `coding_done(result)` | → CODING_DONE 或 RETRY/ESCALATED | 失败时判断重试次数 |
| `start_review()` | → REVIEW | 无 |
| `review_done(review)` | → TESTING 或 RETRY/ESCALATED | 失败时设置 fix_instruction |
| `start_testing()` | 空操作 | 无 (兼容预留) |
| `test_done(test_result)` | → JUDGING | 无 |
| `judge(test_result)` | → PASSED 或 FAILED | 通过时设置 `finished_at` |
| `handle_failure()` | → RETRY 或 ESCALATED | 设置 fix_instruction 含错误信息 |
| `requeue()` | → QUEUED | `retry_count += 1` |

### 3.3 `coding_done` 详细逻辑

```
function coding_done(result: TaskResult):
    if result.success:
        _transit(CODING_DONE)
    else:
        task.last_error = result.stderr or result.stdout
        if task.total_retries < max_retries:
            _transit(RETRY)
        else:
            _transit(ESCALATED)
```

### 3.4 `review_done` 详细逻辑

```
function review_done(review: ReviewResult):
    if review.passed:
        _transit(TESTING)
    else:
        task.last_error = join(review.issues, "; ")
        task.fix_instruction = review.fix_instruction
        task.review_retry += 1
        if task.total_retries < max_retries:
            _transit(RETRY)
        else:
            _transit(ESCALATED)
```

### 3.5 `handle_failure` 详细逻辑

```
function handle_failure():
    task.test_retry += 1
    task.fix_instruction = format(
        "测试失败 (第 {test_retry} 次)\n"
        "错误信息:\n{last_error}\n"
        "请根据以上修复代码。"
    )
    if task.total_retries < max_retries:
        _transit(RETRY)
    else:
        _transit(ESCALATED)
```

### 3.6 状态查询属性

| 属性 | 返回 | 条件 |
|------|------|------|
| `is_terminal` | `bool` | `status in (PASSED, ESCALATED)` |
| `is_retryable` | `bool` | `status == RETRY` |
| `is_waiting` | `bool` | `status == QUEUED` |
| `can_dispatch` | `bool` | `status == QUEUED` |
| `needs_review` | `bool` | `status == CODING_DONE` |
| `needs_testing` | `bool` | `status == TESTING` |

---

## §4 异常设计

### 4.1 StateMachineError

```python
class StateMachineError(Exception):
    pass
```

**触发条件**: 任何非 `_TRANSITIONS` 允许的状态跳转  
**信息格式**: `"[{task_id}] 非法状态转换: {old} → {new} (允许: {allowed})"`  
**对应 DD-SYS-001**: ERR-015

---

## §5 序列图

### SEQ-005: 典型任务状态流转

```
TaskEngine        StateMachine       CodingTask.status
    │                  │                    │
    │ enqueue()        │                    │
    │─────────────────>│ CREATED→QUEUED     │
    │                  │───────────────────>│
    │                  │                    │
    │ dispatch()       │                    │
    │─────────────────>│ QUEUED→DISPATCHED  │
    │                  │───────────────────>│
    │                  │ started_at=now()   │
    │                  │                    │
    │ coding_done(ok)  │                    │
    │─────────────────>│ DISP→CODING_DONE  │
    │                  │───────────────────>│
    │                  │                    │
    │ start_review()   │                    │
    │─────────────────>│ CODING→REVIEW     │
    │                  │───────────────────>│
    │                  │                    │
    │ review_done(ok)  │                    │
    │─────────────────>│ REVIEW→TESTING    │
    │                  │───────────────────>│
    │                  │                    │
    │ test_done()      │                    │
    │─────────────────>│ TESTING→JUDGING   │
    │                  │───────────────────>│
    │                  │                    │
    │ judge(ok)        │                    │
    │─────────────────>│ JUDGING→PASSED    │
    │                  │ finished_at=now()  │
    │                  │───────────────────>│
```

### SEQ-006: 失败重试流转

```
TaskEngine        StateMachine       CodingTask
    │                  │                 │
    │ judge(fail)      │                 │
    │─────────────────>│ JUDGING→FAILED  │
    │                  │                 │
    │ handle_failure() │                 │
    │─────────────────>│ FAILED→RETRY   │
    │                  │ fix_instruction │
    │                  │ = "测试失败..." │
    │                  │────────────────>│
    │                  │                 │
    │ requeue()        │                 │
    │─────────────────>│ RETRY→QUEUED   │
    │                  │ retry_count++   │
    │                  │────────────────>│
    │                  │                 │
    │ (下一轮 next_batch 再次调度)       │
```

---

## §6 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §6 提取并扩充，形成独立模块详述 |
| v1.1 | 2026-03-07 | `__init__` 增加 `on_state_change` 回调参数; ALG-012 `_transit()` 增加持久化回调 |
