# ACTION-ITEMS — v6.0

> **评审版本**: v6.0  
> **生成日期**: 2026-03-07  
> **范围**: 代码评审新增问题跟踪  
> **合计**: 6 项 (P0×0 / P1×2 / P2×4 / P3×0)  
> **预估总工时**: ~4.5h

---

## 状态说明

| 图标 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🔧 | 进行中 |
| ✅ | 已完成 |
| ❌ | 已取消 |

---

## P1 — 高优先级 (2 项)

| A-ID | 问题描述 | 涉及文件 | 修改内容 | 预估 | 状态 |
|------|---------|---------|---------|------|------|
| A-001 | Dashboard 运行时未形成与 Orchestrator 的明确集成闭环 | `orchestrator/main.py`, `orchestrator/dashboard.py`, `Dockerfile`, `docker-compose.yml`, `README.md`, `docs/09-operations/*.md` | 明确并实现 Dashboard 联动方案，或在文档中清楚说明当前仅支持独立模式 | 2.0h | ⬜ |
| A-002 | 运维手册 CLI 示例仍使用旧式子命令 | `docs/09-operations/OPS-001-运维手册-Runbook.md` | 将 `autodev sprint --sprint 1` / `autodev dry-run --sprint 1` 改为真实参数形式 | 0.5h | ⬜ |

## P2 — 中优先级 (4 项)

| A-ID | 问题描述 | 涉及文件 | 修改内容 | 预估 | 状态 |
|------|---------|---------|---------|------|------|
| A-003 | `/api/health` 示例返回值与真实实现不一致 | `README.md`, `docs/09-operations/OPS-002-部署手册-Deployment.md`, `orchestrator/dashboard.py` | 统一示例为真实返回格式，必要时补充字段说明 | 0.5h | ⬜ |
| A-004 | `config.example.yaml` 使用 `$USER`，与实现支持的 `${VAR}` 不一致 | `configs/config.example.yaml`, `orchestrator/config.py` | 修改示例或增强解析兼容性 | 0.5h | ⬜ |
| A-005 | 缺少“主流程 + Dashboard”联动集成测试 | `tests/` | 新增一条验证 Dashboard 真实状态注入的集成测试 | 0.75h | ⬜ |
| A-006 | 缺少“文档示例命令 / 配置样例”自动化回归校验 | `tests/`, `README.md`, `docs/09-operations/*.md`, `configs/config.example.yaml` | 增加文档示例与示例配置校验测试 | 0.75h | ⬜ |

---

## 修复建议顺序

1. **先修 P1**：A-001, A-002
2. **再修文档一致性**：A-003, A-004
3. **最后补回归测试**：A-005, A-006

---

## 修复完成判定

- [ ] Dashboard 运行模式已明确且文档一致
- [ ] 运维手册命令可直接执行
- [ ] 健康检查返回示例与真实接口一致
- [ ] 示例配置与解析规则一致
- [ ] Dashboard 联动测试已补充
- [ ] 文档示例回归检查已补充
