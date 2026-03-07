# DD-MOD-004 — TaskEngine 模块详细设计

> **文档编号**: DD-MOD-004  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/task_engine.py` (253 行)  
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

#### ALG-009: 任务入队 (含循环依赖检测)

```
function enqueue(tasks):
    with _lock:
        # ──── Phase 1: 循环依赖检测 ────
        # 构建依赖图: task_id → depends_on 集
        dep_graph = {}
        for task in tasks:
            dep_graph[task.task_id] = set(task.depends_on or [])
        # 合并已有任务的依赖关系
        for tid, (existing_task, _) in _tasks.items():
            if tid not in dep_graph:
                dep_graph[tid] = set(existing_task.depends_on or [])
        
        # Kahn 拓扑排序检测环路
        cycle_tasks = _detect_cycles(dep_graph)
        if cycle_tasks:
            log.error("检测到循环依赖: %s", cycle_tasks)
            # 环路中的任务直接 ESCALATE, 其余正常入队
            for task in tasks:
                if task.task_id in cycle_tasks:
                    sm = TaskStateMachine(task, max_retries)
                    sm.escalate(reason="循环依赖")    # CREATED → ESCALATED
                    _tasks[task.task_id] = (task, sm)
                    total_escalated += 1
                    log.warning("循环依赖 ESCALATED: %s", task.task_id)
                    continue
                # 非环路任务正常入队（见下方）
        
        # ──── Phase 2: 正常入队 ────
        for task in tasks:
            if task.task_id in _tasks:
                log.warning("任务已存在, 跳过"); continue
            if task.task_id in (cycle_tasks or set()):
                continue  # 已在 Phase 1 处理
            
            sm = TaskStateMachine(task, max_retries)
            sm.enqueue()                    # CREATED → QUEUED
            _tasks[task.task_id] = (task, sm)
            log.info("入队: %s", task.task_id)
```

#### ALG-009a: 循环依赖检测 (Kahn 拓扑排序)

```
function _detect_cycles(dep_graph) → Set[str]:
    """
    基于 Kahn 算法检测有向图中的环路。
    
    输入: dep_graph = {task_id: {dep_task_id, ...}, ...}
    输出: 参与环路的 task_id 集合 (无环时返回空集)
    
    复杂度: O(V + E), V = 任务数, E = 依赖边数
    """
    # 1. 计算入度
    in_degree = {node: 0 for node in dep_graph}
    for node, deps in dep_graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] = in_degree.get(dep, 0)  # 已初始化
            in_degree[node] += sum(1 for d in deps if d in dep_graph)
    
    # 修正: 精确计算入度
    in_degree = {node: 0 for node in dep_graph}
    for node, deps in dep_graph.items():
        for dep in deps:
            if dep in in_degree:
                pass  # dep 被 node 依赖, 但入度是"被依赖的次数"
    # 反转: 入度 = 有多少节点依赖我 (即我是多少个 depends_on 的成员)
    in_degree = {node: 0 for node in dep_graph}
    for node, deps in dep_graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] += 1
    
    # 2. 初始队列: 入度为 0 (无前置依赖) 的节点
    queue = [n for n, d in in_degree.items() if d == 0]
    sorted_count = 0
    
    # 3. BFS 拓扑排序
    while queue:
        node = queue.pop(0)
        sorted_count += 1
        # node 的所有"被依赖者" (即 depends_on 包含 node 的任务)
        for other, deps in dep_graph.items():
            if node in deps:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)
    
    # 4. 未排序的节点即为环路参与者
    if sorted_count == len(dep_graph):
        return set()  # 无环
    
    cycle_nodes = {n for n, d in in_degree.items() if d > 0}
    return cycle_nodes
```

**设计决策**:
- **检测时机**: 在 `enqueue()` 入队前执行，而非在 `next_batch()` 调度时
- **环路处理**: 环路中所有任务直接 ESCALATED（需人工干预拆解依赖），非环路任务正常调度
- **增量检测**: 新任务的依赖图与已有 `_tasks` 合并后做全图检测
- **对应异常**: `DependencyCycleError` (ERR-020), 见 DD-SYS-001 §2

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

### 4.2 JSON 快照持久化 ★v1.1

> 对应 ACTION-ITEM v2.1 A-101: 每次状态变更时写入快照，启动时恢复

#### 设计目标

解决进程崩溃或 SIGTERM 终止后的任务状态丢失问题。通过 JSON 快照实现轻量级持久化，满足 < 100 任务的场景 (> 100 时迁移到 SQLite，见 P3 A-132)。

#### 快照文件路径

```
{config.reports_dir}/state_snapshot.json
```

#### 快照 JSON Schema

```json
{
  "version": "1.0",
  "timestamp": "2026-03-07T10:30:00Z",
  "sprint_id": "sprint-001",
  "engine_state": {
    "max_retries": 3,
    "max_concurrent": 4,
    "total_dispatched": 12,
    "total_passed": 8,
    "total_failed": 1,
    "total_escalated": 1
  },
  "tasks": [
    {
      "task_id": "S1_T1",
      "status": "PASSED",
      "retry_count": 0,
      "review_retry": 0,
      "test_retry": 0,
      "started_at": 1709800000.0,
      "finished_at": 1709800600.0,
      "last_error": null,
      "fix_instruction": null,
      "assigned_machine": "W1",
      "depends_on": [],
      "description": "...",
      "tags": ["python"],
      "target_dir": "src/"
    }
  ]
}
```

#### ALG-009b: 快照保存

```
function _save_snapshot():
    """每次状态变更后调用，写入 JSON 快照"""
    snapshot = {
        "version": "1.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "sprint_id": config.sprint_id,
        "engine_state": {
            "max_retries": max_retries,
            "max_concurrent": max_concurrent,
            "total_dispatched": total_dispatched,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_escalated": total_escalated,
        },
        "tasks": [
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "retry_count": task.retry_count,
                "review_retry": task.review_retry,
                "test_retry": task.test_retry,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "last_error": task.last_error,
                "fix_instruction": task.fix_instruction,
                "assigned_machine": task.assigned_machine,
                "depends_on": task.depends_on,
                "description": task.description,
                "tags": task.tags,
                "target_dir": task.target_dir,
            }
            for task, sm in _tasks.values()
        ],
    }
    
    # 原子写入: 先写临时文件再 rename，避免写入中断导致损坏
    tmp_path = snapshot_path + ".tmp"
    with open(tmp_path, 'w') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, snapshot_path)     # 原子操作
    log.debug("快照已保存: %d 个任务", len(snapshot["tasks"]))
```

#### ALG-009c: 快照恢复

```
function _load_snapshot() → bool:
    """启动时调用，从快照恢复状态。返回是否成功恢复。"""
    if not os.path.exists(snapshot_path):
        return False
    
    try:
        with open(snapshot_path) as f:
            snapshot = json.load(f)
        
        if snapshot.get("version") != "1.0":
            log.warning("快照版本不匹配, 忽略")
            return False
        
        # 恢复引擎统计
        es = snapshot["engine_state"]
        total_dispatched = es["total_dispatched"]
        total_passed = es["total_passed"]
        total_failed = es["total_failed"]
        total_escalated = es["total_escalated"]
        
        # 恢复任务
        for t in snapshot["tasks"]:
            task = CodingTask(
                task_id=t["task_id"],
                description=t["description"],
                tags=t["tags"],
                target_dir=t["target_dir"],
                depends_on=t["depends_on"],
                ...
            )
            task.status = TaskStatus(t["status"])
            task.retry_count = t["retry_count"]
            task.started_at = t["started_at"]
            task.finished_at = t["finished_at"]
            task.last_error = t["last_error"]
            task.fix_instruction = t["fix_instruction"]
            task.assigned_machine = t["assigned_machine"]
            
            sm = TaskStateMachine(task, max_retries)
            # 直接设置状态, 跳过转换校验 (恢复模式)
            sm._restore_state(task.status)
            _tasks[task.task_id] = (task, sm)
        
        log.info("从快照恢复 %d 个任务", len(snapshot["tasks"]))
        return True
        
    except (json.JSONDecodeError, KeyError) as e:
        log.error("快照损坏, 忽略: %s", e)
        return False
```

#### 触发时机

| 事件 | 触发方 | 说明 |
|------|--------|------|
| `enqueue()` 完毕 | TaskEngine | 新任务入队后保存 |
| `mark_dispatched()` | TaskEngine | 任务分发后保存 |
| `handle_coding_done()` | TaskEngine | 编码完成后保存 |
| `handle_review_done()` | TaskEngine | 审查完成后保存 |
| `handle_test_done()` | TaskEngine | 测试完成后保存 |
| `_transit()` | StateMachine | 每次状态转换后回调 (见 DD-MOD-006 §3.1) |

#### StateMachine 持久化回调

在 DD-MOD-006 `_transit()` 中新增回调钩子:

```
function _transit(new_status):
    old = task.status
    # ... 原有校验逻辑 ...
    task.status = new_status
    log.info("[%s] %s → %s", task_id, old, new_status)
    
    # ★v1.1: 持久化回调
    if self._on_state_change:
        self._on_state_change(task.task_id, old, new_status)
```

> `_on_state_change` 回调由 TaskEngine 在创建 StateMachine 时注入，指向 `_save_snapshot()`。

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §4 提取并扩充，形成独立模块详述 |
| v1.1 | 2026-03-07 | ALG-009 增加循环依赖检测 (Phase 1); 新增 ALG-009a 拓扑排序环检测; 新增 §4.2 快照持久化设计 |
