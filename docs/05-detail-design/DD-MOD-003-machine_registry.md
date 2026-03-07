# DD-MOD-003 — MachineRegistry 模块详细设计

> **文档编号**: DD-MOD-003  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/machine_registry.py` (187 行)  
> **上游文档**: [OD-MOD-003](../04-outline-design/OD-MOD-003-machine_registry.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                   MachineRegistry                        │
├──────────────────────────────────────────────────────────┤
│ - _machines : Dict[str, MachineInfo]                     │
│ - _lock     : threading.Lock                             │
├──────────────────────────────────────────────────────────┤
│ + __init__()                                             │
│ + register(machine: MachineInfo) → None                  │
│ + unregister(machine_id: str) → bool                     │
│ + load_from_config(machines_config: list) → None         │
│ + get_machine(machine_id) → Optional[MachineInfo]        │
│ + get_all_machines() → List[MachineInfo]                 │
│ + get_online_machines() → List[MachineInfo]              │
│ + get_idle_machines() → List[MachineInfo]                │
│ + get_online_count() → int                               │
│ + match_machine(task_tags, available?) → Optional[MI]    │
│ + set_status(machine_id, status) → None                  │
│ + set_busy(machine_id, task_id) → None                   │
│ + set_idle(machine_id) → None                            │
│ + update_load(machine_id, load) → None                   │
│ - _pick_least_loaded(machines) → MachineInfo  «static»   │
│ + __len__() → int                                        │
│ + __repr__() → str                                       │
└──────────────────────────────────────────────────────────┘
         ▲ 使用
         │
  ┌──────┴──────────┐
  │  MachineInfo     │
  │  MachineStatus   │
  │ (task_models)    │
  └─────────────────┘
```

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self)` |
| **职责** | 初始化空机器池和线程锁 |
| **线程安全** | `threading.Lock` 保护 `_machines` 字典 |

### 2.2 `register` / `unregister`

| 项目 | register | unregister |
|------|----------|-----------|
| **签名** | `register(machine: MachineInfo) → None` | `unregister(machine_id: str) → bool` |
| **线程安全** | 加锁写入 | 加锁删除 |
| **返回** | 无 | `True` 已存在并删除, `False` 不存在 |
| **日志** | info: 机器注册 | info: 机器注销 |

### 2.3 `load_from_config`

| 项目 | 内容 |
|------|------|
| **签名** | `load_from_config(self, machines_config: list) → None` |
| **职责** | 从 config.yaml 的 machines 列表批量加载机器 |
| **算法** | 遍历 config → 构造 MachineInfo → 调用 `register()` |

**字段映射**:

| config 键 | MachineInfo 属性 | 默认值 |
|-----------|-----------------|--------|
| `machine_id` | machine_id | 必填 |
| `display_name` | display_name | = machine_id |
| `host` | host | 必填 |
| `port` | port | 22 |
| `user` | user | 必填 |
| `work_dir` | work_dir | `~/projects` |
| `tags` | tags | `[]` |
| `aider_prefix` | aider_prefix | `""` |
| `aider_model` | aider_model | `""` |

### 2.4 查询方法组

| 方法 | 过滤条件 | 线程安全 |
|------|---------|---------|
| `get_machine(id)` | 精确 ID 匹配 | `with self._lock` |
| `get_all_machines()` | 无过滤 | `with self._lock` |
| `get_online_machines()` | `status == ONLINE` | `with self._lock` |
| `get_idle_machines()` | `status == ONLINE and current_task is None` | `with self._lock` |
| `get_online_count()` | `status in (ONLINE, BUSY)` | `with self._lock` |

### 2.5 `match_machine`

| 项目 | 内容 |
|------|------|
| **签名** | `match_machine(self, task_tags: List[str], available: Optional[List[MachineInfo]] = None) → Optional[MachineInfo]` |
| **职责** | 基于 tags 能力匹配 + 负载均衡选择最佳机器 |
| **算法** | ALG-008 |
| **返回** | 匹配的 MachineInfo 或 `None` (需排队等待) |

#### ALG-008: 三层匹配算法

```
function match_machine(task_tags, available):
    if available is None:
        available = get_idle_machines()
    if available is empty:
        return None
    
    task_tags_set = set(task_tags) if task_tags else set()
    
    # Layer 1: 完全覆盖匹配 (tags ⊆ machine.tags)
    if task_tags_set:
        candidates = [m for m in available
                      if task_tags_set.issubset(set(m.tags))]
        if candidates:
            return _pick_least_loaded(candidates)
    
    # Layer 2: 部分匹配降级 (按交集大小排序)
    if task_tags_set:
        scored = sorted(available,
                        key=λ m: len(task_tags_set & set(m.tags)),
                        reverse=True)
        return scored[0]
    
    # Layer 3: 无 tags 要求 → 最空闲
    return _pick_least_loaded(available)
```

**匹配优先级**:

| 层级 | 策略 | 说明 |
|------|------|------|
| L1 | 完全覆盖 | `task_tags ⊆ machine.tags`，且选负载最低者 |
| L2 | 部分匹配 | 按 `|task_tags ∩ machine.tags|` 降序，取第一个 |
| L3 | 无约束 | 任务无 tags 要求，选负载最低的空闲机器 |

### 2.6 状态管理方法组

| 方法 | 设置内容 | 线程安全 |
|------|---------|---------|
| `set_status(id, status)` | `machine.status = status` | `with self._lock` |
| `set_busy(id, task_id)` | `status = BUSY`, `current_task = task_id` | `with self._lock` |
| `set_idle(id)` | `status = ONLINE`, `current_task = None` | `with self._lock` |
| `update_load(id, load)` | `machine.load.update(load)` | `with self._lock` |

### 2.7 `_pick_least_loaded` (静态方法)

| 项目 | 内容 |
|------|------|
| **签名** | `@staticmethod _pick_least_loaded(machines: List[MachineInfo]) → MachineInfo` |
| **职责** | 从候选列表中选择 CPU 负载最低的机器 |
| **算法** | `min(machines, key=λ m: m.load.get("cpu_percent", 0.0))` |

---

## §3 线程安全设计

```
┌─────────────────────────────────────────────┐
│           MachineRegistry 并发模型           │
├─────────────────────────────────────────────┤
│                                             │
│  Thread-1 (TaskEngine.next_batch)           │
│    │  with self._lock:                      │
│    │    get_idle_machines()                  │
│    │                                        │
│  Thread-2 (TaskEngine.mark_dispatched)      │
│    │  with self._lock:                      │
│    │    set_busy(machine_id)                │
│    │                                        │
│  Thread-3 (TaskEngine.handle_coding_done)   │
│    │  with self._lock:                      │
│    │    set_idle(machine_id)                │
│                                             │
│  所有公共方法均使用 self._lock 保护          │
│  _pick_least_loaded 是无状态静态方法，无需锁 │
└─────────────────────────────────────────────┘
```

---

## §4 序列图

### SEQ-003: 机器匹配与分配流程

```
TaskEngine       MachineRegistry       MachineInfo
    │                  │                    │
    │ get_idle_        │                    │
    │  machines()      │                    │
    │─────────────────>│                    │
    │                  │ with _lock:        │
    │                  │  filter ONLINE     │
    │                  │  & no current_task │
    │ List[MachineInfo]│                    │
    │<─────────────────│                    │
    │                  │                    │
    │ match_machine    │                    │
    │  (tags, avail)   │                    │
    │─────────────────>│                    │
    │                  │ L1: subset check   │
    │                  │ L2: intersection   │
    │                  │ L3: least_loaded   │
    │ MachineInfo      │                    │
    │<─────────────────│                    │
    │                  │                    │
    │ set_busy(id, tid)│                    │
    │─────────────────>│                    │
    │                  │ with _lock:        │
    │                  │  status=BUSY       │
    │                  │  current_task=tid  │
    │                  │─────────────────>  │
    │         ok       │                    │
    │<─────────────────│                    │
```

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §3 提取并扩充，形成独立模块详述 |
