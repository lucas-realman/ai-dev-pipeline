# OD-MOD-009 — TaskStateMachine 模块概要设计

> **文档编号**: OD-MOD-009  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/state_machine.py` (148 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-006](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-009](../05-detail-design/DD-MOD-009-state_machine.md) · [OD-002](OD-002-数据模型设计.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-009 |
| **核心类** | `TaskStateMachine`, `StateMachineError` |
| **ARCH 组件** | ARCH-006 状态管理组件 |
| **关联 FR** | FR-014 状态转换, FR-015 重试+升级 |
| **对外接口** | IF-010 `enqueue()`, `dispatch()`, `coding_done()`, `review_done()`, `test_done()`, `judge()`, `handle_failure()`, `requeue()` |
| **依赖** | MOD-005 (task_models: `CodingTask`, `TaskStatus`) |

## 职责

管理 `CodingTask` 的 11 态状态机，严格转换规则。非法转换抛出 `StateMachineError`。

## 状态转换图

```
CREATED ──enqueue()──→ QUEUED ──dispatch()──→ DISPATCHED
                         ▲                       │
                         │                  coding_done()
                    requeue()                    │
                         │              ┌────────┴────────┐
                         │              ▼                  ▼
                       RETRY ←── FAILED   CODING_DONE
                         │                       │
                         │              start_review()
                         │                       │
                         │                       ▼
                         ├──────────── REVIEW
                         │                       │
                         │              review_done()
                         │              ┌────┴────┐
                         │              ▼         ▼
                         ├──── (fail) RETRY    TESTING
                         │                       │
                         │                test_done()
                         │              ┌────┴────┐
                         │              ▼         ▼
                         ├──── (fail) RETRY   JUDGING
                         │                       │
                         │                  judge()
                         │              ┌────┴────┐
                         │              ▼         ▼
                         └──────── FAILED    ✅ PASSED
                                     │
                              handle_failure()
                              ┌────┴────┐
                              ▼         ▼
                           RETRY    ❌ ESCALATED
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **`_TRANSITIONS` 表** | 静态 dict 定义所有合法转换，未列出的转换均非法 |
| **严格校验** | `_transit()` 校验 new_status 是否在当前状态的允许列表中 |
| **重试计数** | `coding_done` 失败 → `retry_count++`；`review_done` 失败 → `review_retry++` |
| **升级阈值** | 超过 `max_retries` (config) 时转入 ESCALATED 终态 |
| **属性快捷** | `is_terminal`, `is_retryable`, `can_dispatch` 等布尔属性 |
| **fix_instruction** | `handle_failure()` 构建修复指令，携带失败原因供重试使用 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.9 提取并扩充 |
