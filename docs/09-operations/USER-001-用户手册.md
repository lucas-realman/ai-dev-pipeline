# USER-001 — 用户手册

> **文档编号**: USER-001  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **适用对象**: 项目负责人、交付负责人、运维负责人、独立开发者

---

## §1 产品是什么

AutoDev Pipeline 是一套自动化开发流水线平台。

它做的事情是：

1. 读取目标项目的需求/设计/Sprint 文档；
2. 让 AI 把文档拆成可执行的编码任务；
3. 根据机器标签把任务分发到不同 Worker；
4. 自动进行 Review、测试、结果判定；
5. 输出 Sprint 报告、测试报告和状态数据。

---

## §2 适合谁用

适合以下场景：

- 已经有规范设计文档，希望自动生成开发任务；
- 有 1 台以上开发机，希望并行执行编码任务；
- 希望把“开发、审查、测试、报告”串成统一流水线；
- 希望降低人工调度成本。

---

## §3 使用前准备

### 3.1 准备目标项目

目标项目至少应包含：

- 需求文档
- 概要/详细设计文档
- Sprint 任务卡
- 测试计划
- 开发计划

### 3.2 准备运行环境

- 安装 Python 3.10+
- 准备 OpenAI 兼容 API
- 配置 SSH 免密登录到 Worker 机器
- 准备可读写的 Git 仓库

---

## §4 典型使用流程

### 步骤 1：安装平台

```bash
git clone git@github-lucas:lucas-realman/ai-dev-pipeline.git
cd ai-dev-pipeline
pip install -e ".[dev]"
```

### 步骤 2：复制模板

```bash
cp .env.example .env
cp configs/config.example.yaml orchestrator/config.yaml
```

### 步骤 3：编辑配置

重点填写：

- LLM 地址与密钥
- 目标项目路径
- Git 仓库地址
- Worker 机器信息
- 文档匹配规则

### 步骤 4：先干跑

```bash
python -m orchestrator.main --config orchestrator/config.yaml --dry-run
```

干跑只解析文档和任务，不会真正执行编码。

### 步骤 5：执行单轮 Sprint

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --sprint-id sprint-001 \
  --mode sprint
```

### 步骤 6：查看结果

- Dashboard：`/api/status`
- 报告目录：`reports/`
- 日志目录：`logs/`

---

## §5 常用命令

### 查看帮助

```bash
python -m orchestrator.main --help
```

### 干跑

```bash
python -m orchestrator.main --config orchestrator/config.yaml --dry-run
```

### 单轮运行

```bash
python -m orchestrator.main --config orchestrator/config.yaml --mode sprint
```

### 持续运行

```bash
python -m orchestrator.main --config orchestrator/config.yaml --mode continuous
```

### 测试平台本身

```bash
pytest -m "smoke or component or integration or acceptance" --cov=orchestrator
```

---

## §6 运行结果怎么看

### 6.1 Dashboard API

| 接口 | 说明 |
|------|------|
| `/api/health` | 健康检查 |
| `/api/status` | 总体状态汇总 |
| `/api/machines` | 机器池状态 |
| `/api/tasks` | 任务详情 |

### 6.2 报告

- `reports/`：保存 Sprint 报告、测试报告
- `release/`：保存版本发布说明

### 6.3 日志

- 标准日志：便于快速排查
- JSON 日志：便于机器采集和分析

---

## §7 最佳实践

- 第一次接入新项目时先用 `--dry-run`
- 先用 1~2 台机器验证，再扩到完整机器池
- 保持目标项目文档结构稳定
- 每次 Sprint 结束保存 `reports/` 产物
- 配置变更后先跑 `pytest -m smoke`

---

## §8 常见问题

### Q1：平台是直接替代开发者吗？

不是。平台负责自动编排与自动化执行，仍建议保留人工抽检和关键节点审批。

### Q2：没有多台机器能用吗？

可以。单机也可以运行，只是吞吐较低。

### Q3：必须使用 Docker 吗？

不是。可以本地 Python 直接运行。

### Q4：怎样知道系统是否正常？

先看 `/api/health`，再看 `/api/status` 和 `reports/`。

---

## §9 参考入口

- 项目入口：`README.md`
- 部署说明：`docs/09-operations/OPS-002-部署手册-Deployment.md`
- 运维手册：`docs/09-operations/OPS-001-运维手册-Runbook.md`
- 测试报告：`reports/TEST-REPORT-v3.0.0.md`
- 发布说明：`release/RELEASE_NOTES-v3.0.0.md`
