# OD-MOD-003 — MachineRegistry 模块概要设计

> **文档编号**: OD-MOD-003  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/machine_registry.py` (187 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-002](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-003](../05-detail-design/DD-MOD-003-machine_registry.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-003 |
| **核心类** | `MachineRegistry` |
| **ARCH 组件** | ARCH-002 机器池组件 |
| **关联 FR** | FR-004 动态注册/注销, FR-005 标签匹配+负载均衡 |
| **对外接口** | IF-005 `match_machine(tags, available)` |
| **依赖** | MOD-005 (task_models: `MachineInfo`, `MachineStatus`), threading |

## 职责

线程安全的机器池管理：注册/注销/状态更新/标签匹配/空闲查询/负载均衡。

## 核心流程

```
load_from_config(machines_list)           match_machine(task_tags, available)
    │                                          │
    ├── 遍历 config 列表                       ├── 过滤 available 中的 IDLE 机器
    ├── 构造 MachineInfo                       ├── Tier-1: exact tag match (全标签匹配)
    └── register(machine_info)                 ├── Tier-2: partial tag match (部分匹配)
         └── _machines[id] = info              ├── Tier-3: any idle machine (兜底)
                                               └── _pick_least_loaded() → min(cpu_percent)
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **线程安全** | 所有读写操作通过 `threading.Lock` 保护 |
| **3 层匹配策略** | 精确匹配 → 部分匹配 → 任意空闲，确保任务总能找到机器 |
| **负载排序** | 同层候选按 `cpu_percent` 升序，选负载最低的 |
| **动态注册** | 运行时可 register/unregister，支持机器热插拔 |

## 错误处理策略

| 场景 | 处理 |
|------|------|
| 注册重复 ID | 覆盖旧记录，warning 日志 |
| 注销不存在 ID | 忽略，debug 日志 |
| 无可用机器 | `match_machine()` 返回 `None`，上层等待重试 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.3 提取并扩充 |
