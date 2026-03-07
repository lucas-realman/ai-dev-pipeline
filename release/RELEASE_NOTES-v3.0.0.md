# Release Notes — v3.0.0

> 发布日期：2026-03-07  
> 发布类型：Release Candidate 完成并转正式交付  
> 对应标签：`v3.0.0-rc1`  
> 发布范围：AutoDev Pipeline 全功能版本

---

## 1. 发布摘要

v3.0.0 标志着 AutoDev Pipeline 达到“功能具备（Feature Complete）”状态。

本版本完成了从文档解析、任务拆解、任务调度、远程分发、自动审查、自动测试、状态跟踪、通知报告到容器化部署的全链路交付。

---

## 2. 核心新增能力

### 2.1 Sprint 3 生产就绪能力

- 完成 4 层测试金字塔 CI/CD
- 增加 Dockerfile 多阶段构建
- 增加 docker-compose 编排
- 实现 Dashboard API
- 实现日志标准化与 JSON 日志输出
- 完成 L4 验收测试

### 2.2 自动化开发流水线闭环

- 文档驱动任务拆解
- 基于标签的动态机器池分发
- 自动 Review（静态、契约、设计）
- 自动 pytest 执行与阈值判定
- Sprint 报告与钉钉通知
- Git 自动提交、同步和打标

---

## 3. 质量结果

- 总测试数：**281**
- 总覆盖率：**85%**
- L1 冒烟：通过
- L2 组件：通过
- L3 集成：通过
- L4 验收：通过
- 云端 CI：通过

---

## 4. 本版本修复

### 4.1 已修复问题

- 修复 `reviewer.py` 中 LLM 重试配置属性缺失问题
- 修复 `test_runner.py` 中错误调用 `_exec()` 的问题
- 修复 `pyproject.toml` 构建后端配置问题
- 修复 setuptools 多包自动发现导致的 CI 安装失败问题
- 修复 Ruff 代码风格与静态检查问题
- 修复 L3 阶段覆盖率门槛未达标问题，恢复并满足 `>=80%`

### 4.2 标签与交付

- `testing-v1.0`
- `testing-v2.0`
- `v3.0.0-rc1`

---

## 5. 交付物清单

- 核心代码：`orchestrator/`
- 自动化测试：`tests/`
- 设计文档：`docs/`
- 部署手册：`docs/09-operations/OPS-002-部署手册-Deployment.md`
- 运维手册：`docs/09-operations/OPS-001-运维手册-Runbook.md`
- 用户手册：`docs/09-operations/USER-001-用户手册.md`
- 测试报告：`reports/TEST-REPORT-v3.0.0.md`
- 配置模板：`configs/config.example.yaml`

---

## 6. 升级建议

如果从早期版本升级到 v3.0.0，建议按以下步骤执行：

1. 更新代码到 `main`
2. 重新安装依赖：`pip install -e ".[dev]"`
3. 重新比对 `orchestrator/config.yaml`
4. 补充 `.env` 中的 LLM/通知配置
5. 先执行 `--dry-run`
6. 再执行真实 Sprint

---

## 7. 已知事项

- 项目默认依赖“标准化文档集”输入，接入前需整理目标项目文档
- 多机并发收益取决于 SSH 稳定性、目标项目规模与 Worker 能力
- 钉钉通知、LLM API、Git 远端均属于外部依赖，应在部署前完成连通性验证
