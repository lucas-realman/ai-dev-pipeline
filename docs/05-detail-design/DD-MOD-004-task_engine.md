# DD-MOD-004 — TaskEngine 模块详细设计

> **文档编号**: DD-MOD-004  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/task_engine.py` (254 行)  
> **上游文档**: [OD-MOD-004](../04-outline-design/OD-MOD-004-task_engine.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌────────────────────────────────────────────────────────────┐
│                       TaskEngine                           │
├────────────────────────────────────────────────────────────┤
│ + max_retries       : int                                  │
│ + max_concurrent    : int                                  │
│ + registry          : MachineRegistry                      │
│ - _tasks            : OrderedDict[str, (CodingTask, TSM)]  │
│ - _lock             : threading.Lock                       │
│ + total_dispatched  : int                                  │
│ + total_passed      : int                                  │
│ + total_failed      : int                                  │
│ + total_escalated   : int                                  │
├────────────────────────────────────────────────────────────┤
│ + __init__(max_retries=3, max_concurrent=4,                │
│            machine_registry=None)                          │
│ + enqueue(tasks: List[CodingTask]) → None                  │
│ + enqueue_single(task: CodingTask) → None                  │
│ + next_batch() → List[CodingTask]                          │
│ + mark_dispatched(task_id: str) → None                     │
│ + handle_coding_done(task_id, result) → None               │
│ + handle_review_done(task_id, review) → None               │
│ + handle_test_done(task_id, test_result) → None            │
│ + all_done() → bool                                        │
│ + get_status_summary() → Dict[str, int]                    │
│ + get_task(task_id) → Optional[CodingTask]                 │
│ + get_all_tasks() → List[CodingTask]                       │
│ + get_tasks_in_status(status) → List[CodingTask]           │
│ + get_escalated_tasks() → List[CodingTask]                 │
│ «property» total_tasks → int                               │
│ «property» completed_count → int                           │
│ «property» in_progress_count → int                         │
│ - _get(task_id) → tuple                                    │
│ - _completed_task_ids() → Set[str]                         │
└────────────────────────────────────────────────────────────┘
         ▲ 组合            ▲ 组合
         │                  │
  ┌──────┴──────┐   ┌──────┴──────────────┐
  │ MachineReg. │   │ TaskStateMachine     │
  │ (MOD-003)   │   │ (MOD-006)           │
  └─────────────┘   └─────────────────────┘
```

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self, max_retries=3, max_concurrent=4, machine_registry=None)` |
| **职责** | 初始化任务引擎，创建 OrderedDict 存储和 Lock |
| **数据结构** | `_tasks: OrderedDict[str, (CodingTask, TaskStateMachine)]` — 保持插入顺序 |
| **默认值** | 未传 registry 时自动创建空 `MachineRegistry()` |

### 2.2 `enqueue`

| 项目 | 内容 |
|------|------|
| **签名** | `enqueue(self, tasks: List[CodingTask]) → None` |
| **职责** | 批量入队任务，创建关联的 StateMachine |
| **算法** | ALG-009 |
| **线程安全** | `with self._lock` |

#### ALG-009: 任务入队

```
function enqueue(tasks):
    with _lock:
        for task in tasks:
            if task.task_id in _tasks:
                log.warning("任务已存在, 跳过"); continue
            
            sm = TaskStateMachine(task, max_retries)
            sm.enqueue()                    # CREATED → QUEUED
            _tasks[task.task_id] = (task, sm)
            log.info("入队: %s", task.task_id)
```

### 2.3 `next_batch` ★

| 项目 | 内容 |
|------|------|
| **签名** | `next_batch(self) → List[CodingTask]` |
| **职责** | 取出下一批可并行执行的任务，依赖感知 + 机器动态分配 |
| **算法** | ALG-010 |
| **线程安全** | `with self._lock` |
| **返回** | 最多 `max_concurrent` 个可分发的 CodingTask |

#### ALG-010: 依赖感知批次调度

```
function next_batch():
    with _lock:
        completed_ids = _completed_task_ids()     # 所有 PASSED 的 task_id
        idle_machines = registry.get_idle_machines()
        
        batch = []
        used_machine_ids = set()
        
        for (task, sm) in _tasks (按插入顺序):
            if not sm.can_dispatch: continue      # 非 QUEUED 跳过
            
            # 依赖检查: 所有前置任务已 PASSED
            if task.depends_on:
                if not all(dep in completed_ids for dep in task.depends_on):
                    continue
            
            # 机器匹配
            available = [m for m in idle_machines 
                         if m.id not in used_machine_ids]
            
            if task.assigned_machine:
                # v3: 指定机器
                matched = find(available, id==task.assigned_machine)
            elif task.target_machine:
                # v2 兼容: target_machine
                matched = find(available, id==task.target_machine)
            else:
                # v3 动态: tags 匹配
                matched = registry.match_machine(task.tags, available)
            
            if not matched: continue
            
            task.assigned_machine = matched.machine_id
            batch.append(task)
            used_machine_ids.add(matched.machine_id)
            
            if len(batch) >= max_concurrent: break
        
        return batch
```

**关键特性**:
- OrderedDict 保证 FIFO 公平调度
- 依赖拓扑: 前置任务必须 PASSED
- 机器互斥: 同一批里每台机器只分配一个任务
- v2/v3 兼容: 优先 `assigned_machine` → `target_machine` → tags 匹配

### 2.4 `mark_dispatched`

| 项目 | 内容 |
|------|------|
| **签名** | `mark_dispatched(self, task_id: str) → None` |
| **职责** | 确认任务已分发 |
| **算法** | `sm.dispatch()` (QUEUED→DISPATCHED) + `registry.set_busy(machine_id, task_id)` |
| **副作用** | `total_dispatched += 1` |

### 2.5 `handle_coding_done`

| 项目 | 内容 |
|------|------|
| **签名** | `handle_coding_done(self, task_id: str, result: TaskResult) → None` |
| **职责** | 处理编码完成事件 |
| **算法** | 释放机器 (`set_idle`) → `sm.coding_done(result)` → 失败可重试则 `sm.requeue()` |

### 2.6 `handle_review_done`

| 项目 | 内容 |
|------|------|
| **签名** | `handle_review_done(self, task_id: str, review: ReviewResult) → None` |
| **职责** | 处理 Review 完成事件 |
| **算法** | `sm.start_review()` → `sm.review_done(review)` → 失败且可重试 → `sm.requeue()`；不可重试 → ESCALATED |

### 2.7 `handle_test_done`

| 项目 | 内容 |
|------|------|
| **签名** | `handle_test_done(self, task_id: str, test_result: TestResult) → None` |
| **职责** | 处理测试完成事件 |
| **算法** | ALG-011 |

#### ALG-011: 测试结果处理

```
function handle_test_done(task_id, test_result):
    with _lock:
        (task, sm) = _get(task_id)
        sm.test_done(test_result)              # → JUDGING
        sm.judge(test_result)                  # → PASSED or FAILED
        
        if task.status == PASSED:
            total_passed += 1
        elif task.status == FAILED:
            sm.handle_failure()                # 设置 fix_instruction
            if sm.is_retryable:
                sm.requeue()                   # RETRY → QUEUED
            else:
                total_escalated += 1           # 升级人工
```

### 2.8 状态查询方法

| 方法 | 返回 | 说明 |
|------|------|------|
| `all_done()` | `bool` | 所有任务是否终态 (PASSED/ESCALATED) |
| `get_status_summary()` | `Dict[str, int]` | 各状态的任务计数 |
| `get_task(id)` | `Optional[CodingTask]` | 按 ID 查询 |
| `get_all_tasks()` | `List[CodingTask]` | 全量任务列表 |
| `get_tasks_in_status(status)` | `List[CodingTask]` | 按状态过滤 |
| `get_escalated_tasks()` | `List[CodingTask]` | 快捷: 获取所有升级任务 |

### 2.9 属性

| 属性 | 类型 | 计算方式 |
|------|------|---------|
| `total_tasks` | `int` | `len(self._tasks)` |
| `completed_count` | `int` | `total_passed + total_escalated` |
| `in_progress_count` | `int` | 状态为 DISPATCHED/CODING_DONE/REVIEW/TESTING/JUDGING 的计数 |

---

## §3 序列图

### SEQ-004: 任务生命周期管理

```
Orchestrator      TaskEngine       StateMachine     MachineReg.
    │                │                  │                │
    │ enqueue(tasks) │                  │                │
    │───────────────>│  sm.enqueue()    │                │
    │                │─────────────────>│                │
    │                │                  │ CREATED→QUEUED │
    │                │                  │                │
    │ next_batch()   │                  │                │
    │───────────────>│ can_dispatch?    │                │
    │                │─────────────────>│ return QUEUED  │
    │                │  check deps     │<────────────── │
    │                │                  │                │
    │                │ get_idle_machines│                │
    │                │─────────────────────────────────>│
    │                │ match_machine    │                │
    │                │─────────────────────────────────>│
    │ batch          │                  │                │
    │<───────────────│                  │                │
    │                │                  │                │
    │ mark_dispatched│                  │                │
    │───────────────>│ sm.dispatch()    │                │
    │                │─────────────────>│ QUEUED→DISP.  │
    │                │ set_busy()       │                │
    │                │─────────────────────────────────>│
    │                │                  │                │
    │ handle_test_   │                  │                │
    │  done()        │                  │                │
    │───────────────>│ sm.judge()       │                │
    │                │─────────────────>│→PASSED/FAILED │
    │                │                  │                │
```

---

## §4 数据结构

### 4.1 _tasks 内部结构

```python
_tasks: OrderedDict[str, tuple[CodingTask, TaskStateMachine]] = {
    "S1_T1": (CodingTask(...), TaskStateMachine(task, max_retries=3)),
    "S1_T2": (CodingTask(...), TaskStateMachine(task, max_retries=3)),
    ...
}
```

**选择 OrderedDict 的理由**:
- 保持任务插入顺序（FIFO 调度）
- O(1) 键查找
- Python 3.7+ dict 已有序，OrderedDict 语义更明确

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §4 提取并扩充，形成独立模块详述 |
