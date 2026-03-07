# USER-001 — 用户手册

> **文档编号**: USER-001  
> **版本**: v1.1  
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

### 3.3 先理解“你到底要给平台什么”

如果你还是不确定怎么用，可以先把平台理解成：

- **你提供**：一个真实项目目录 + 一组需求/设计/Sprint 文档；
- **平台负责**：读取这些文档，拆任务，分发到机器，做 Review，跑测试，产出报告。

也就是说，这个平台的输入不是一句话，而是一个**已经有文档的项目目录**。

一个最小例子：

```text
/Users/you/projects/crm-system/
├── docs/
│   ├── 01-基础功能需求.md
│   ├── 04-系统概要设计.md
│   ├── 05-测试方案与计划.md
│   ├── 06-总体开发计划.md
│   └── 07-Sprint任务卡.md
├── contracts/
├── src/
└── tests/
```

然后，你让 AutoDev Pipeline 去处理这个 `crm-system` 项目。

---

## §4 典型使用流程

下面给一个**完整可照抄的示例**。假设你的目标项目是：

- 项目名：`crm-system`
- 本地路径：`/Users/you/projects/crm-system`
- Git 仓库：`git@github.com:your-org/crm-system.git`
- 有两台执行机器：`mac-mini-dev` 和 `linux-worker-01`

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

例如你可以这样填写 `.env`：

```dotenv
OPENAI_API_BASE=https://your-llm-gateway.example.com/v1
OPENAI_API_KEY=sk-xxxxxxxx
AIDER_MODEL=openai/gpt-4.1

DINGTALK_WEBHOOK_URL=
DINGTALK_WEBHOOK_SECRET=
```

### 步骤 3：编辑配置

重点填写：

- LLM 地址与密钥
- 目标项目路径
- Git 仓库地址
- Worker 机器信息
- 文档匹配规则

一个可以直接参考的 `orchestrator/config.yaml` 片段：

```yaml
project:
  name: crm-system
  path: /Users/you/projects/crm-system
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
    display_name: "My MacBook"
    host: 127.0.0.1
    port: 22
    user: you
    work_dir: /Users/you/projects/crm-system
    tags: [python, orchestrator, testing]
    aider_prefix: 'export PATH="$HOME/.local/bin:$PATH"'

  - machine_id: mac-mini-dev
    display_name: "Mac Mini Dev"
    host: 192.168.1.20
    port: 22
    user: dev
    work_dir: /Users/dev/projects/crm-system
    tags: [python, backend, macos]
    aider_prefix: 'export PATH="$HOME/.local/bin:$PATH"'

  - machine_id: linux-worker-01
    display_name: "Linux Worker"
    host: 192.168.1.30
    port: 22
    user: dev
    work_dir: /home/dev/crm-system
    tags: [python, api, linux]
    aider_prefix: 'export PATH="$HOME/.local/bin:$PATH"'
```

上面这段配置的意思很简单：

- `project.path` 是你的目标项目目录；
- `doc_set` 告诉系统去哪找文档；
- `machines` 告诉系统有哪些机器可用、每台机器擅长什么任务。

### 步骤 4：先干跑

```bash
python -m orchestrator.main --config orchestrator/config.yaml --dry-run
```

干跑只解析文档和任务，不会真正执行编码。

如果你是第一次接入项目，建议这样执行：

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/projects/crm-system \
  --sprint-id sprint-001 \
  --dry-run
```

你可以把它理解成：

- 读取 `crm-system/docs/` 下的文档；
- 让 AI 拆出本轮 Sprint 的任务；
- 只展示和验证，不真的下发到机器。

一个典型的干跑结果会类似这样：

```text
[INFO] loaded documents: requirements=1 design=1 task_card=1 test_plan=1
[INFO] sprint_id=sprint-001
[INFO] decomposed tasks: 6
[INFO] task=T001 desc="实现用户登录接口"
[INFO] task=T002 desc="补充登录接口单元测试"
[INFO] task=T003 desc="新增登录页面表单"
[INFO] dry-run complete
```

如果你看到了类似“loaded documents”和“decomposed tasks”，就说明平台已经读懂了你的项目文档。

### 步骤 5：执行单轮 Sprint

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --sprint-id sprint-001 \
  --mode sprint
```

把上面的路径换成真实项目后，一个实际例子是：

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/projects/crm-system \
  --sprint-id sprint-001 \
  --mode sprint
```

这一条命令执行后，平台会按顺序做这些事：

1. 读取 `crm-system/docs/`；
2. 生成本轮任务；
3. 按 tags 选择机器；
4. 下发编码任务；
5. 自动 Review；
6. 自动测试；
7. 生成报告。

你可以把它理解为“自动跑完一次开发迭代”。

### 步骤 6：查看结果

- Dashboard：`/api/status`
- 报告目录：`reports/`
- 日志目录：`logs/`

例如：

- 看状态：`curl http://localhost:8080/api/status`
- 看机器：`curl http://localhost:8080/api/machines`
- 看任务：`curl http://localhost:8080/api/tasks`

一个典型的状态返回可能像这样：

```json
{
  "sprint_id": "sprint-001",
  "queued": 0,
  "in_progress": 1,
  "passed": 4,
  "failed": 1,
  "escalated": 0
}
```

这表示本轮 Sprint 一共已经完成了 5 个任务，其中 4 个通过，1 个失败，当前还有 1 个在执行。

`reports/` 里通常会有类似这样的文件：

```text
reports/
├── sprint_report_sprint-001.md
└── test_report_sprint-001.json
```

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

例如：

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/projects/crm-system \
  --sprint-id sprint-002 \
  --mode sprint
```

### 持续运行

```bash
python -m orchestrator.main --config orchestrator/config.yaml --mode continuous
```

例如：

```bash
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/projects/crm-system \
  --mode continuous
```

这个模式适合长时间运行，让系统持续轮询和处理新的 Sprint 或任务。

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

如果你只想快速判断这一轮有没有跑成功，先看这两个地方：

1. `curl http://localhost:8080/api/status`
2. `reports/sprint_report_*.md`

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

### Q5：如果我是第一次接入，最小操作步骤是什么？

最小步骤只有 3 个：

1. 准备目标项目文档；
2. 填好 `.env` 和 `orchestrator/config.yaml`；
3. 先跑 `--dry-run`，确认成功后再跑 `--mode sprint`。

可以直接照抄：

```bash
cp .env.example .env
cp configs/config.example.yaml orchestrator/config.yaml

python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/projects/crm-system \
  --sprint-id sprint-001 \
  --dry-run

python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /Users/you/projects/crm-system \
  --sprint-id sprint-001 \
  --mode sprint
```

---

## §9 参考入口

- 项目入口：`README.md`
- 部署说明：`docs/09-operations/OPS-002-部署手册-Deployment.md`
- 运维手册：`docs/09-operations/OPS-001-运维手册-Runbook.md`
- 测试报告：`reports/TEST-REPORT-v3.0.0.md`
- 发布说明：`release/RELEASE_NOTES-v3.0.0.md`
