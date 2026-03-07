# OD-MOD-010 — Reporter 模块概要设计

> **文档编号**: OD-MOD-010  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/reporter.py` (240 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-007](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-010](../05-detail-design/DD-MOD-010-reporter.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-010 |
| **核心类** | `Reporter` |
| **ARCH 组件** | ARCH-007 通知报告组件 |
| **关联 FR** | FR-016 钉钉 Webhook 通知, FR-017 Sprint 报告, FR-018 每日摘要 |
| **对外接口** | IF-011 `notify_sprint_start()`, `notify_task_dispatched()`, `notify_task_result()`, `notify_sprint_done()`, `save_sprint_report()` |
| **依赖** | MOD-012 (config), MOD-005 (task_models), httpx |

## 职责

钉钉通知 (Webhook / OpenAPI 两种模式) + 本地 Markdown 报告生成。

## 双通道通知架构

```
_send_dingtalk(title, markdown)
    │
    ├── 优先: Webhook 模式
    │       └── _send_via_webhook()
    │               ├── HMAC-SHA256 签名 (若配置 secret)
    │               ├── POST {msgtype: "markdown", markdown: {title, text}}
    │               └── 检查 errcode == 0
    │
    └── 备选: OpenAPI 模式
            └── _send_via_openapi()
                    ├── _get_access_token() (缓存 + 自动续期)
                    ├── POST robot/groupMessages/send
                    └── openConversationId + robotCode
```

## 通知事件矩阵

| 事件 | 方法 | Markdown 内容 |
|------|------|--------------|
| Sprint 开始 | `notify_sprint_start()` | 任务列表表格 + tags |
| 任务分发 | `notify_task_dispatched()` | 机器 + 目录 + 描述 |
| 任务结果 | `notify_task_result()` | 状态 + 审查 + 测试详情 |
| Sprint 完成 | `notify_sprint_done()` | 通过/失败统计 + 耗时 |
| 异常通知 | `notify_error()` | 错误消息 |
| 本地报告 | `save_sprint_report()` | 完整 Markdown 报告文件 |

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **双通道** | Webhook (简单推荐) 和 OpenAPI (企业内部应用) 两种模式 |
| **签名安全** | Webhook 支持 HMAC-SHA256 签名验证 |
| **Token 缓存** | OpenAPI access_token 缓存，过期前 60s 刷新 |
| **@人** | 支持 `at_mobiles` 和 `at_all` 配置 |
| **本地报告** | 报告保存到 `reports/sprint_{id}_{timestamp}.md` |
| **耗时格式** | `_elapsed()` 自动格式化为 `Xh Xm Xs` |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.10 提取并扩充 |
