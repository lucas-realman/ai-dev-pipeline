# OPS-002 — 部署手册 (Deployment Guide)

> **文档编号**: OPS-002  
> **版本**: v1.1  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **关联文档**: [OPS-001-运维手册-Runbook.md](OPS-001-运维手册-Runbook.md) · [USER-001-用户手册.md](USER-001-用户手册.md) · [../../README.md](../../README.md)

---

## §1 部署目标

本项目用于部署一套“文档驱动 → 任务拆解 → 多机分发 → 自动审查 → 自动测试 → 自动报告”的自动化开发流水线。

部署完成后，系统应提供两类能力：

1. **编排能力**：通过 `autodev` CLI 启动单轮或持续运行的 Sprint。
2. **观测能力**：通过 Dashboard API 查看系统状态、机器状态和任务状态。

---

## §2 部署前提

### 2.1 软件依赖

- Python 3.10+
- Git
- 可用的 OpenAI 兼容 API
- 至少 1 台可 SSH 访问的执行机器
- 可选：Docker / Docker Compose

### 2.2 网络与权限

- Orchestrator 到 Worker 机器的 SSH 连通
- Orchestrator 到 LLM API 的 HTTPS 连通
- 项目仓库具备 pull / push 权限
- 如启用通知，具备钉钉 Webhook 或企业应用凭据

---

## §3 目录准备

建议部署目录结构如下：

```text
ai-dev-pipeline/
├── configs/                     # 配置模板与环境配置
├── contracts/                   # 契约模板
├── docs/                        # 设计、运维、用户文档
├── orchestrator/                # 平台核心代码
├── release/                     # 发布说明
├── reports/                     # 测试报告、运行报告
├── tests/                       # 自动化测试
├── .env.example                 # 环境变量模板
├── docker-compose.yml           # 容器编排
├── Dockerfile                   # 容器镜像
└── README.md                    # 项目入口说明
```

一个实际例子：

```text
/Users/you/workspace/
├── ai-dev-pipeline/             # 平台自身
└── crm-system/                  # 被平台驱动的真实业务项目
  ├── docs/
  ├── contracts/
  ├── src/
  └── tests/
```

部署时你实际上会同时有两个目录：

- `ai-dev-pipeline/`：流水线平台；
- `crm-system/`：要被自动开发的目标项目。

---

## §4 本地部署

### 4.1 安装

```bash
git clone git@github-lucas:lucas-realman/ai-dev-pipeline.git
cd ai-dev-pipeline
pip install -e ".[dev]"
```

### 4.2 环境变量

```bash
cp .env.example .env
# 填写 OPENAI_API_BASE / OPENAI_API_KEY / AIDER_MODEL
```

例如：

```dotenv
OPENAI_API_BASE=https://your-llm-gateway.example.com/v1
OPENAI_API_KEY=sk-xxxxxxxx
AIDER_MODEL=openai/gpt-4.1
```

### 4.3 配置文件

```bash
cp configs/config.example.yaml orchestrator/config.yaml
# 按目标项目修改 project.path、repo_url、machines、doc_set
```

下面给一个**可运行示例**。假设：

- 平台目录：`/Users/you/workspace/ai-dev-pipeline`
- 目标项目：`/Users/you/workspace/crm-system`
- 一台本机 + 一台 Linux Worker

则 `orchestrator/config.yaml` 可以最少这样写：

```yaml
project:
  name: crm-system
  path: /Users/you/workspace/crm-system
  repo_url: git@github.com:your-org/crm-system.git
  branch: main

doc_set:
  requirements: "docs/*需求*.md"
  design: "docs/*设计*.md"
  task_card: "docs/*Sprint*任务卡*.md"
  test_plan: "docs/*测试*.md"
  dev_plan: "docs/*开发计划*.md"

machines:
  - machine_id: orchestrator
    display_name: "Local Mac"
    host: 127.0.0.1
    port: 22
    user: you
    work_dir: /Users/you/workspace/crm-system
    tags: [python, testing, orchestrator]
    aider_prefix: 'export PATH="$HOME/.local/bin:$PATH"'

  - machine_id: worker-linux-01
    display_name: "Linux Worker"
    host: 192.168.1.30
    port: 22
    user: dev
    work_dir: /home/dev/crm-system
    tags: [python, backend, linux]
    aider_prefix: 'export PATH="$HOME/.local/bin:$PATH"'
```

部署时最容易出错的就是这 3 项：

- `project.path` 写成了平台目录，而不是目标项目目录；
- `machines[*].work_dir` 与真实机器上的项目目录不一致；
- `doc_set.*` 匹配不到目标项目文档。

### 4.4 验证安装

```bash
python -m orchestrator.main --help
pytest -m smoke -q
```

如果都正常，下一步不要直接正式运行，先做一次干跑：

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/workspace/crm-system \
  --sprint-id sprint-001 \
  --dry-run
```

看到类似下面输出，就说明部署基本成功：

```text
[INFO] config loaded
[INFO] project=crm-system
[INFO] loaded documents: 5
[INFO] decomposed tasks: 6
[INFO] dry-run complete
```

---

## §5 Docker 部署

### 5.1 构建镜像

```bash
docker build -t ai-dev-pipeline:3.0.0 .
```

### 5.2 启动 Dashboard API

```bash
docker compose up -d orchestrator
```

### 5.3 运行容器内测试

```bash
docker compose --profile test run --rm test
```

### 5.4 健康检查

```bash
curl http://localhost:8080/api/health
curl http://localhost:8080/api/status
```

预期结果示例：

```json
{"status":"ok"}
```

以及：

```json
{
  "queued": 0,
  "in_progress": 0,
  "passed": 0,
  "failed": 0
}
```

如果 `/api/health` 通了，而 `/api/status` 也能返回 JSON，说明 Dashboard 这部分部署是正常的。

---

## §6 首次接入业务项目

### 6.1 业务项目需要准备的输入

目标项目应至少提供以下文档：

- 需求文档
- 设计文档
- Sprint 任务卡
- 测试计划
- 开发计划

### 6.2 配置映射

在 `orchestrator/config.yaml` 中重点修改：

- `project.name`
- `project.path`
- `project.repo_url`
- `doc_set.*`
- `machines[*].host/user/work_dir/tags`

### 6.3 干跑验证

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --sprint-id sprint-001 \
  --dry-run
```

若干跑成功，说明文档解析、配置加载、任务拆解链路正常。

这里给一个完整例子：

```bash
cd /Users/you/workspace/ai-dev-pipeline

python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/workspace/crm-system \
  --sprint-id sprint-001 \
  --dry-run
```

这个命令的含义是：

- 在 `ai-dev-pipeline` 平台里运行；
- 去处理 `/Users/you/workspace/crm-system` 这个业务项目；
- 当前处理的迭代编号叫 `sprint-001`；
- 只演练，不真正分发执行。

---

## §7 生产运行

### 7.1 单轮 Sprint

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --sprint-id sprint-001 \
  --mode sprint
```

一个实际命令示例：

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/workspace/crm-system \
  --sprint-id sprint-001 \
  --mode sprint
```

典型执行过程可以理解为：

1. 加载 `crm-system/docs/` 文档；
2. 生成任务；
3. 选择合适的机器；
4. 执行编码；
5. 自动 Review；
6. 自动测试；
7. 输出报告。

### 7.2 持续运行模式

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --mode continuous
```

适合长期运行在一台编排机上，持续接收新的 Sprint。

### 7.3 运行产物

- `reports/`：Sprint 报告、测试报告
- `logs/`：运行日志、JSON 结构化日志
- Dashboard API：状态查询

例如正式运行后，你可以这样检查：

```bash
curl http://localhost:8080/api/status
ls -la reports/
tail -f logs/orchestrator.log
```

如果 `reports/` 中已经生成 Sprint 报告，通常说明主流程已经跑通。

---

## §8 验收清单

部署完成后，至少确认以下事项：

- `python -m orchestrator.main --help` 正常
- `pytest -m "smoke or component or integration or acceptance" --cov=orchestrator` 通过
- `GET /api/health` 返回 200
- `GET /api/status` 返回有效 JSON
- 可成功完成一次 `--dry-run`
- 可成功完成一次真实 `--mode sprint`

建议按下面这个顺序验收，不容易乱：

1. `python -m orchestrator.main --help`
2. `pytest -m smoke -q`
3. `python -m orchestrator.main --dry-run`
4. `curl http://localhost:8080/api/health`
5. `python -m orchestrator.main --mode sprint`
6. 检查 `reports/` 是否生成报告

---

## §9 回滚建议

如部署失败，按以下顺序回滚：

1. 停止当前进程或容器
2. 回退 `orchestrator/config.yaml`
3. 回退 `.env`
4. 回退镜像或 Git commit/tag
5. 根据 [OPS-001-运维手册-Runbook.md](OPS-001-运维手册-Runbook.md) 执行故障排查
