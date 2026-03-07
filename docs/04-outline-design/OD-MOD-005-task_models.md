# OD-MOD-005 — TaskModels 模块概要设计

> **文档编号**: OD-MOD-005  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/task_models.py` (202 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-006](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-005](../05-detail-design/DD-MOD-005-task_models.md) · [OD-002](OD-002-数据模型设计.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-005 |
| **核心类** | `CodingTask`, `TaskResult`, `ReviewResult`, `TestResult`, `MachineInfo` |
| **核心枚举** | `TaskStatus` (11 态), `MachineStatus` (4 态), `ReviewLayer` (3 层) |
| **ARCH 组件** | ARCH-006 状态管理组件 (数据层) |
| **关联 FR** | FR-003, FR-014 (支撑所有模块数据结构) |
| **对外接口** | 纯数据定义，无行为接口 |
| **依赖** | 无 (最底层模块) |

## 职责

定义全系统数据类型和枚举。是所有其他模块的共享数据基础，无外部依赖。

## 数据结构一览

| 类型 | 名称 | 字段数 | 说明 |
|------|------|--------|------|
| Enum | `TaskStatus` | 11 值 | CREATED→QUEUED→DISPATCHED→CODING_DONE→REVIEW→TESTING→JUDGING→PASSED/FAILED/RETRY/ESCALATED |
| Enum | `MachineStatus` | 4 值 | OFFLINE, IDLE, BUSY, ERROR |
| Enum | `ReviewLayer` | 3 值 | L1_STATIC, L2_CONTRACT, L3_DESIGN |
| Dataclass | `CodingTask` | ~15 字段 | 核心任务模型，含 v2/v3 兼容字段 |
| Dataclass | `TaskResult` | ~6 字段 | aider 执行结果 |
| Dataclass | `ReviewResult` | ~5 字段 | 审查结果 |
| Dataclass | `TestResult` | ~7 字段 | 测试结果 |
| Dataclass | `MachineInfo` | ~10 字段 | 机器信息 |

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **纯 dataclass** | 不使用 Pydantic/attrs，保持零依赖 |
| **v2/v3 兼容** | `CodingTask` 同时支持 `target_machine` (v2) 和 `tags` + `assigned_machine` (v3) |
| **effective_machine 属性** | 优先返回 `assigned_machine`，回退到 `target_machine`，统一外部访问 |
| **序列化** | `to_dict()` / `from_dict()` 方法支持 JSON 持久化 |
| **11 态枚举** | 终态: PASSED, ESCALATED；可重试态: FAILED, RETRY |

## 详细模型设计

→ 详见 [OD-002 数据模型设计](OD-002-数据模型设计.md)

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.5 提取并扩充 |
