# ITER-001 — 迭代计划

> **文档编号**: ITER-001  
> **版本**: v1.0  
> **更新日期**: 2026-03-06  
> **上游**: [REQ-001](../01-requirements/REQ-001-系统需求规格说明书.md) · [ARCH-002](../03-architecture/ARCH-002-部署架构.md)

---

## §1 里程碑定义

| 里程碑 | 目标 | 交付物 | 判定标准 |
|--------|------|--------|---------|
| **M0 — 骨架可运行** | CLI 可调用，空 Sprint 跑通 | orchestrator v3.0 + 全模块导入 + 冒烟测试 | TC-001~005 全 pass |
| **M1 — 单机端到端** | 单台 orchestrator 本地完成 1 个 Sprint | doc_analyzer → task_engine → dispatcher(local) → reviewer → test_runner → reporter | TC-110 pass (mock LLM) |
| **M2 — 多机分发** | 5 台机器并行分发 + SSH | dispatcher remote + machine_registry + git sync | TC-060~063, TC-102 pass |
| **M3 — 生产就绪** | 全链路 + 重试/升级 + 钉钉通知 | 全部 L3 集成测试 + L4 验收 | TC-120~123 pass |

## §2 Sprint 节奏

| Sprint | 持续时间 | 聚焦模块 | 对应里程碑 |
|--------|---------|---------|-----------|
| Sprint 0 | 1 周 | 项目骨架 + CI + 文档体系 | M0 |
| Sprint 1 | 2 周 | MOD-001,004,005,006,007 | M1 |
| Sprint 2 | 2 周 | MOD-003,008 + SSH 分发 | M2 |
| Sprint 3 | 2 周 | MOD-009,010,011,012 | M3 |
| Sprint 4 | 1 周 | 全链路验收 + 文档定稿 | M3 验收 |

## §3 风险时间缓冲

每个 Sprint 末留 **1 天缓冲**，用于：
- 重试失败任务的人工排查
- 文档修订与交叉审查
- 下一 Sprint 任务预分析

---

## 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-06 | 初始版本 | AutoDev Pipeline |
