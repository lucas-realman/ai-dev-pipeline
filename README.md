# AI Dev Pipeline

**通用 AI 自动化开发流水线平台** — 文档驱动任务拆解、动态机器池、零项目绑定。

> 当前状态：**v3.0.0 已完成交付**，云端 CI 已通过，可作为正式可用版本。

## 设计理念

| 维度 | 说明 |
|------|------|
| **文档驱动** | 标准化需求文档集（01-07 + contracts）经 AI 解析自动生成编码任务 |
| **动态机器池** | 开发机器可通过配置或 API 注册/注销，按能力标签 (tags) 自动匹配任务 |
| **零项目绑定** | 平台代码不包含任何项目特定的路径、模块名或业务逻辑 |

## 快速开始

```bash
# 1. 克隆
git clone git@github-lucas:lucas-realman/ai-dev-pipeline.git
cd ai-dev-pipeline

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 配置
cp .env.example .env
cp configs/config.example.yaml orchestrator/config.yaml
# 编辑 orchestrator/config.yaml: 填写项目路径、机器信息、LLM API 等

# 4. 设置环境变量
# 或直接在 .env 中填写
export OPENAI_API_BASE="your-api-base-url"
export OPENAI_API_KEY="your-api-key"
export AIDER_MODEL="your-model"

# 5. 先干跑验证
python -m orchestrator.main --config orchestrator/config.yaml --dry-run

# 6. 运行单轮 Sprint
python -m orchestrator.main --config orchestrator/config.yaml --mode sprint --sprint-id sprint-001
```

## 如何使用这套自动化开发流水线

使用顺序建议固定为 4 步：

1. **准备目标项目文档集**：需求、设计、测试计划、开发计划、Sprint 任务卡。
2. **配置流水线**：修改 `.env` 和 `orchestrator/config.yaml`，填入项目路径、仓库、机器池和 LLM。
3. **先执行干跑**：确认文档能被解析、任务能被拆解。
4. **再执行真实 Sprint**：让系统自动完成任务分发、Review、测试和报告生成。

最常用命令：

```bash
# 查看帮助
python -m orchestrator.main --help

# 干跑：只解析文档，不真正执行
python -m orchestrator.main --config orchestrator/config.yaml --dry-run

# 单轮 Sprint
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --sprint-id sprint-001 \
  --mode sprint

# 持续模式
python -m orchestrator.main \
  --config orchestrator/config.yaml \
  --project-path /absolute/path/to/your-project \
  --mode continuous
```

## 测试

```bash
# 运行全部测试 (281 tests, 4 层)
pytest -m "smoke or component or integration or acceptance"

# 按层级运行
pytest -m smoke       # L1 冒烟测试
pytest -m component   # L2 组件测试
pytest -m integration # L3 集成测试
pytest -m acceptance  # L4 验收测试 (29 tests)

# 覆盖率报告
pytest --cov=orchestrator --cov-report=term-missing
```

## Docker 部署

```bash
# 构建镜像
docker build -t ai-dev-pipeline:latest .

# 使用 docker-compose 启动
docker compose up -d

# 健康检查
curl http://localhost:8080/api/health

# 运行容器化测试
docker compose run --rm test
```

## Dashboard API

启动后可通过以下端点监控运行状态：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 任务状态汇总 (queued / in_progress / passed / failed) |
| `/api/machines` | GET | 机器池状态 (online / busy / offline) |
| `/api/tasks` | GET | 所有任务详情列表 |
| `/api/health` | GET | 健康检查 (返回 `{"status": "ok"}`) |

## CI/CD Pipeline

CI 采用 4 层测试金字塔：

```
L1 Smoke  →  L2 Unit  →  L3 Integration  →  L4 Acceptance
  (36)         (174)         (42)              (29)
```

- **L1**: 模块导入 + 基本创建，快速冒烟
- **L2**: 单元测试，覆盖纯函数与 mock 交互
- **L3**: 跨模块集成 (Engine→Dispatcher→Reviewer→TestRunner)
- **L4**: 端到端验收 (Dockerfile 可构建、Dashboard API、性能基线)
- 覆盖率门槛: L3 ≥80%, L4 ≥85%

## 项目结构

```
ai-dev-pipeline/
├── configs/                        ← 配置模板
├── orchestrator/                   ← 平台核心（通用，跨项目复用）
│   ├── main.py                     ← 主循环入口
│   ├── config.py                   ← 配置加载器
│   ├── config.yaml                 ← 运行配置
│   ├── dashboard.py                ← ★ Dashboard API (FastAPI)
│   ├── log_config.py               ← 日志标准化 (JSON/Standard)
│   ├── doc_analyzer.py             ← ★ 文档集解析 + AI 任务拆解器
│   ├── doc_parser.py               ← 向后兼容层（旧版解析器）
│   ├── machine_registry.py         ← ★ 动态机器池管理
│   ├── task_engine.py              ← 任务引擎（动态分配机器）
│   ├── task_models.py              ← 数据模型
│   ├── dispatcher.py               ← SSH 分发器
│   ├── reviewer.py                 ← 三层自动 Review
│   ├── reporter.py                 ← 钉钉通知 + 本地报告
│   ├── git_ops.py                  ← Git 自动化操作
│   ├── test_runner.py              ← 测试执行器
│   └── state_machine.py            ← 任务状态机
├── tests/                          ← 测试 (281 tests, 85% coverage)
├── docs/                           ← 平台文档
├── contracts/                      ← 接口契约模板
├── release/                        ← Release Notes
├── reports/                        ← 自动生成的报告
├── Dockerfile                      ← 多阶段构建 (python:3.10-slim)
├── docker-compose.yml              ← 编排 (orchestrator + test)
├── .github/workflows/ci.yml        ← CI 4 层测试金字塔
├── pyproject.toml                  ← 项目元数据
└── .env.example                    ← 环境变量模板
```

## 标准化需求文档集

接入本平台的项目需在 `docs/` 下提供以下标准文档：

| 文件 | 角色 | 必需 |
|------|------|------|
| `01-基础功能需求.md` | 功能需求表 | ✅ |
| `02-智能扩展需求.md` | AI/ML 需求 | 可选 |
| `03-硬件清单.md` | 可用资源 | 可选 |
| `04-系统概要设计.md` | 架构+模块设计 | ✅ |
| `05-测试方案与计划.md` | 测试策略 | ✅ |
| `06-总体开发计划.md` | Sprint 划分 | ✅ |
| `07-Sprint任务卡.md` | 逐日任务表 | ✅ |

## 交付文档入口

- [部署手册](docs/09-operations/OPS-002-%E9%83%A8%E7%BD%B2%E6%89%8B%E5%86%8C-Deployment.md)
- [运维手册](docs/09-operations/OPS-001-%E8%BF%90%E7%BB%B4%E6%89%8B%E5%86%8C-Runbook.md)
- [用户手册](docs/09-operations/USER-001-%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C.md)
- [测试报告](reports/TEST-REPORT-v3.0.0.md)
- [Release Notes](release/RELEASE_NOTES-v3.0.0.md)

## 许可证

MIT
