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
| A-001 | Dashboard 运行时未形成与 Orchestrator 的明确集成闭环 | `orchestrator/main.py`, `orchestrator/dashboard.py`, `Dockerfile`, `docker-compose.yml`, `README.md`, `docs/09-operations/*.md` | 已增加 `--serve-dashboard` 联动模式，并在文档中区分本地联动 / Docker 独立两种运行模式 | 2.0h | ✅ |
| A-002 | 运维手册 CLI 示例仍使用旧式子命令 | `docs/09-operations/OPS-001-运维手册-Runbook.md` | 已统一为真实 CLI 参数形式 | 0.5h | ✅ |

## P2 — 中优先级 (4 项)

| A-ID | 问题描述 | 涉及文件 | 修改内容 | 预估 | 状态 |
|------|---------|---------|---------|------|------|
| A-003 | `/api/health` 示例返回值与真实实现不一致 | `README.md`, `docs/09-operations/OPS-002-部署手册-Deployment.md`, `orchestrator/dashboard.py` | 已统一示例为 `{"status": "healthy", "version": "3.0.0"}` | 0.5h | ✅ |
| A-004 | `config.example.yaml` 使用 `$USER`，与实现支持的 `${VAR}` 不一致 | `configs/config.example.yaml`, `orchestrator/config.py` | 已修改示例为 `${USER}` | 0.5h | ✅ |
| A-005 | 缺少“主流程 + Dashboard”联动集成测试 | `tests/` | 已补充 Dashboard 状态注入集成测试 | 0.75h | ✅ |
| A-006 | 缺少“文档示例命令 / 配置样例”自动化回归校验 | `tests/`, `README.md`, `docs/09-operations/*.md`, `configs/config.example.yaml` | 已新增文档与示例配置回归测试 | 0.75h | ✅ |

---

## 修复建议顺序

1. **先修 P1**：A-001, A-002
2. **再修文档一致性**：A-003, A-004
3. **最后补回归测试**：A-005, A-006

---

## 修复完成判定

- [x] Dashboard 运行模式已明确且文档一致
- [x] 运维手册命令可直接执行
- [x] 健康检查返回示例与真实接口一致
- [x] 示例配置与解析规则一致
- [x] Dashboard 联动测试已补充
- [x] 文档示例回归检查已补充
