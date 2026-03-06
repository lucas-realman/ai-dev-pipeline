# AI Dev Pipeline

**通用 AI 自动化开发流水线平台** — 文档驱动任务拆解、动态机器池、零项目绑定。

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
cp orchestrator/config.example.yaml orchestrator/config.yaml
# 编辑 config.yaml: 填写项目路径、机器信息、LLM API 等

# 4. 设置环境变量
export OPENAI_API_BASE="your-api-base-url"
export OPENAI_API_KEY="your-api-key"

# 5. 运行
python -m orchestrator.main --config orchestrator/config.yaml
```

## 项目结构

```
ai-dev-pipeline/
├── orchestrator/                   ← 平台核心（通用，跨项目复用）
│   ├── main.py                     ← 主循环入口
│   ├── config.py                   ← 配置加载器
│   ├── config.yaml                 ← 运行配置
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
├── tests/                          ← 单元测试
├── docs/                           ← 平台文档
├── contracts/                      ← 接口契约模板
├── reports/                        ← 自动生成的报告
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

## 许可证

MIT
