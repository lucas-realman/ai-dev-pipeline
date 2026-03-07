# OD-MOD-004 — TaskEngine 模块概要设计

> **文档编号**: OD-MOD-004  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/task_engine.py` (254 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-003](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-004](../05-detail-design/DD-MOD-004-task_engine.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-004 |
| **核心类** | `TaskEngine` |
| **ARCH 组件** | ARCH-003 任务调度组件 |
| **关联 FR** | FR-006 任务入队, FR-007 依赖排序, FR-008 动态分配 |
| **对外接口** | IF-003 `enqueue()`, IF-004 `next_batch()` |
| **依赖** | MOD-012 (config), MOD-005 (task_models), MOD-003 (machine_registry), MOD-009 (state_machine) |

## 职责

任务队列管理：入队 → 依赖检查 → 取下一批可调度任务（考虑依赖完成+空闲机器）→ 处理编码/审查/测试结果。

## 核心流程

```
enqueue(tasks)                         next_batch()
    │                                      │
    ├── 遍历任务列表                       ├── 过滤 QUEUED 状态任务
    ├── 为每个任务创建 TaskStateMachine     ├── 检查 depends_on 是否全部完成
    └── _tasks[id] = (task, sm)            ├── v2 兼容: target_machine 直接分配
                                           ├── v3: match_machine(tags) 匹配
                                           └── return List[CodingTask]

handle_coding_done(task)    handle_review_done(task, review)    handle_test_done(task, test)
    │                            │                                    │
    ├── sm.coding_done()         ├── sm.review_done(passed)           ├── sm.test_done(passed)
    └── 更新统计                 └── 更新统计                         └── 更新统计
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **OrderedDict** | `_tasks` 使用 `OrderedDict` 保持入队顺序 |
| **线程安全** | 所有操作通过 `threading.Lock` 保护 |
| **依赖检查** | `next_batch()` 检查 `depends_on` 列表中所有任务是否已达终态 |
| **v2/v3 兼容** | v2 `target_machine` 直接分配，v3 `tags` 通过 registry 匹配 |
| **状态机委托** | 状态转换委托给 `TaskStateMachine`，引擎只做调度决策 |

## 错误处理策略

| 场景 | 处理 |
|------|------|
| 重复 task_id 入队 | 覆盖旧任务，warning 日志 |
| 无可调度任务 | `next_batch()` 返回空列表 |
| 状态转换非法 | `StateMachineError` 由状态机抛出，引擎记录日志 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.4 提取并扩充 |
