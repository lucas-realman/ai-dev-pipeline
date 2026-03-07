# AutoDev Pipeline — 全流程实施计划 v2.0

> **文档编号**: PMO-PLAN-002  
> **版本**: v2.0  
> **创建日期**: 2026-03-08  
> **对齐基线**: docs/ 设计文档体系 (REQ-001 v2.0, TEST-001 v1.3, ITER-001 v1.1)  
> **代码基线**: coding-v1.0 (commit d0455a7) — 13 模块已实现, 14 冒烟测试通过  
> **目标**: 从"设计文档完成 → 开发 → 测试 → 集成 → 验收 → 功能具备"的全生命周期计划

---

## §0 现状评估 (As-Is)

### 0.1 代码完成度

| 维度 | 数据 |
|------|------|
| 已实现模块 | 13/13 (orchestrator/ 全部有实质代码) |
| 代码总行数 | ~3,800 行 / 15 Python 文件 |
| 代码完成度 | ~97% (对齐 DD-MOD-001~013 详细设计) |
| 已知 Bug | **2 处** (BUG-1: reviewer.py, BUG-2: test_runner.py) |
| 入口可用性 | `autodev` CLI 可调用, --help 正常输出 |

### 0.2 测试完成度

| 维度 | 数据 | 目标 (TEST-001) |
|------|------|----------------|
| L1 冒烟测试 | 14 TC (4/13 模块) | TC-001~TC-005, 100% pass ✅ |
| L2 组件测试 | **0 TC** | TC-010~TC-102 (~35 TC), ≥90% pass ❌ |
| L3 集成测试 | **0 TC** | TC-110~TC-120 (11 TC), ≥85% pass ❌ |
| L4 验收测试 | **0 TC** | TC-121~TC-127 (7 TC), 人工验收 ❌ |
| conftest.py | **不存在** | pytest markers 注册 ❌ |
| tests/fixtures/ | **不存在** | 测试数据管理 ❌ |

### 0.3 基础设施完成度

| 维度 | 状态 |
|------|------|
| GitHub Actions CI/CD | **不存在** (.github/ 仅有 copilot-instructions.md) |
| Dockerfile | **不存在** |
| conftest.py (pytest) | **不存在** |
| tests/fixtures/ | **不存在** |
| Dashboard API (NFR-015) | **未实现** (fastapi 已声明为依赖) |

### 0.4 已知 Bug 清单

| Bug ID | 位置 | 描述 | 严重度 |
|--------|------|------|--------|
| BUG-1 | reviewer.py AutoReviewer | `self._LLM_MAX_RETRIES` / `self._LLM_BACKOFF_BASE` 被引用但未定义为类属性 | P0 (运行时崩溃) |
| BUG-2 | test_runner.py TestRunner | `run_tests()` 调用 `self._exec(cmd, task)` 但方法实际名为 `_run_pytest()` | P0 (运行时崩溃) |

---

## §1 里程碑体系 (对齐 ITER-001)

> 在已有 coding-v1.0 代码基线上，重新定义从"补全 → 测试 → 集成 → 验收"的里程碑。

| 里程碑 | 名称 | 目标 | 判定标准 | 预计达成 |
|--------|------|------|---------|---------|
| **M0.5** | Bug修复 + 测试基建 | 修复已知 Bug, 建立测试基础设施 | BUG-1/2 修复, conftest.py 就绪, CI 绿灯 | Sprint 0.5 末 |
| **M1** | L2 组件测试全覆盖 | 13 模块全部有组件测试 | TC-010~TC-102 ≥90% pass, 行覆盖≥70% | Sprint 1 末 |
| **M2** | L3 集成测试通过 | 11 条端到端链路测试 | TC-110~TC-120 ≥85% pass | Sprint 2 末 |
| **M3** | 生产就绪 + 验收 | CI/CD + Docker + L4 验收 | TC-121~TC-127 全部 P0 pass, 文档定稿 | Sprint 3 末 |

---

## §2 Sprint 详细规划

### Sprint 0.5 — Bug 修复 + 测试基建 (1 周)

> **对应里程碑**: M0.5  
> **目标**: 消灭运行时 Bug, 建立完整测试基础设施, 让后续所有 Sprint 可在 CI 中自动验证

#### 2.1.1 开发任务

| # | 任务 | 关联文档 | 优先级 | 预估 |
|---|------|---------|--------|------|
| S0.5-01 | 修复 BUG-1: reviewer.py 添加 `_LLM_MAX_RETRIES=3` / `_LLM_BACKOFF_BASE=2.0` 类属性 | DD-MOD-008 | P0 | 0.5h |
| S0.5-02 | 修复 BUG-2: test_runner.py `self._exec()` → `self._run_pytest()` | DD-MOD-009 | P0 | 0.5h |
| S0.5-03 | 创建 `tests/conftest.py`: 注册 4 个 pytest 标记 (smoke/component/integration/acceptance) | TEST-001 §3.2 | P0 | 1h |
| S0.5-04 | 创建 `tests/fixtures/` 目录: config_valid.yaml, config_invalid.yaml, sample_tasks.json, mock_doc_set/ | TEST-001 §3.4 | P0 | 2h |
| S0.5-05 | 创建 `.github/workflows/ci.yml`: L1+L2 自动测试 | ITER-001 S0-04 | P1 | 2h |
| S0.5-06 | 更新 `pyproject.toml` [tool.pytest.ini_options] 添加 markers 配置 | TEST-001 §3.2 | P1 | 0.5h |
| S0.5-07 | 现有 test_smoke.py 14 个测试添加 `@pytest.mark.smoke` 标记 | TEST-001 §3.2 | P1 | 0.5h |

#### 2.1.2 测试要求

| 测试层 | 测试内容 | 通过标准 |
|--------|---------|---------|
| L1 冒烟 | 修复后全部 14 TC 通过 | 100% pass |
| 回归 | BUG-1 修复后 reviewer.review_task() 不抛 AttributeError | pass |
| 回归 | BUG-2 修复后 test_runner.run_tests() 不抛 AttributeError | pass |
| CI | GitHub Actions 首次成功执行 | 绿灯 |

#### 2.1.3 准出标准 (Exit Criteria)

- [ ] BUG-1, BUG-2 已修复并有对应回归测试
- [ ] `pytest -m smoke` 14/14 pass
- [ ] `tests/conftest.py` 存在, 4 个 marker 已注册
- [ ] `tests/fixtures/` 至少包含 config_valid.yaml, config_invalid.yaml, sample_tasks.json
- [ ] `.github/workflows/ci.yml` 存在, push 触发 CI 绿灯
- [ ] Git tag: `testing-v0.5`

---

### Sprint 1 — L2 组件测试全覆盖 (2 周)

> **对应里程碑**: M1  
> **目标**: 为全部 13 个模块编写 L2 组件测试, 覆盖 TEST-001 §2.2~§2.3 定义的 ~35 个 TC

#### 2.2.1 Week 1: 核心模块组件测试 (无外部依赖)

| # | 测试文件 | 覆盖模块 | 覆盖 TC | 预估 |
|---|---------|---------|--------|------|
| S1-01 | `tests/test_state_machine.py` | MOD-009 状态机 | TC-010~TC-015 (6 TC) | 3h |
| S1-02 | `tests/test_machine_registry.py` | MOD-003 机器注册表 | TC-020~TC-024 (5 TC) | 3h |
| S1-03 | `tests/test_task_engine.py` | MOD-004 任务引擎 | TC-030~TC-035 (6 TC) | 4h |
| S1-04 | `tests/test_config.py` | MOD-012 配置 | TC-040~TC-043 (4 TC) | 2h |
| S1-05 | `tests/test_task_models.py` | MOD-005 数据模型 | TC-003~TC-005 (补全) | 2h |

**Week 1 小计**: 5 个测试文件, 21+ TC, ~14h

#### 2.2.2 Week 2: 外部交互模块组件测试 (需 Mock)

| # | 测试文件 | 覆盖模块 | 覆盖 TC | Mock 策略 | 预估 |
|---|---------|---------|--------|----------|------|
| S1-06 | `tests/test_doc_analyzer.py` | MOD-001 文档分析器 | TC-050~TC-055 (6 TC) | mock httpx → LLM JSON 响应 | 4h |
| S1-07 | `tests/test_dispatcher.py` | MOD-006 分发器 | TC-060~TC-063 (4 TC) | mock subprocess (SSH) | 4h |
| S1-08 | `tests/test_reviewer.py` | MOD-007 审查器 | TC-070~TC-073 (4 TC) | mock LLM + 临时 .py 文件 | 3h |
| S1-09 | `tests/test_test_runner.py` | MOD-008 测试运行器 | TC-080~TC-083 (4 TC) | mock pytest JSON report | 3h |
| S1-10 | `tests/test_reporter.py` | MOD-010 报告器 | TC-090~TC-094 (5 TC) | mock httpx.post (钉钉) | 3h |
| S1-11 | `tests/test_git_ops.py` | MOD-011 Git 操作 | TC-100~TC-102 (3 TC) | mock subprocess (git) | 2h |
| S1-12 | `tests/test_doc_parser.py` | MOD-002 文档解析器 | TC 追加 (2 TC) | 临时 .md 文件 | 1h |
| S1-13 | `tests/test_main.py` | MOD-013 主编排器 | TC 追加 (3 TC) | mock all modules | 3h |

**Week 2 小计**: 8 个测试文件, 27+ TC, ~23h

#### 2.2.3 测试要求

| 测试层 | 测试内容 | 通过标准 |
|--------|---------|---------|
| L1 冒烟 | 全部 14 TC | 100% pass |
| L2 组件 | TC-010~TC-102 全量 | ≥90% pass (允许 ≤3 个失败) |
| 覆盖率 | `pytest --cov=orchestrator` | 行覆盖 ≥70% |

#### 2.2.4 准出标准 (Exit Criteria)

- [ ] 13 个模块各有独立测试文件 (`tests/test_<module>.py`)
- [ ] `pytest -m component` ≥90% pass
- [ ] `pytest --cov=orchestrator --cov-report=term-missing` 行覆盖 ≥70%
- [ ] 所有 L2 TC (TC-010~TC-102) 有对应测试函数
- [ ] CI Pipeline L1+L2 阶段全绿
- [ ] Git tag: `testing-v1.0`

#### 2.2.5 需求追溯

| FR | 覆盖 TC | 验证方式 |
|----|--------|---------|
| FR-001 (文档加载) | TC-050, TC-051 | test_doc_analyzer.py |
| FR-002 (LLM 拆解) | TC-052, TC-053 | test_doc_analyzer.py |
| FR-003 (CodingTask) | TC-054, TC-055 | test_doc_analyzer.py |
| FR-004 (机器池管理) | TC-020, TC-021, TC-022 | test_machine_registry.py |
| FR-005 (标签匹配) | TC-023, TC-024 | test_machine_registry.py |
| FR-006 (任务编排) | TC-030, TC-032, TC-033 | test_task_engine.py |
| FR-007 (负载分发) | TC-031 | test_task_engine.py |
| FR-008 (SSH 执行) | TC-060, TC-061, TC-062, TC-063 | test_dispatcher.py |
| FR-009 (L1 静态) | TC-070, TC-071 | test_reviewer.py |
| FR-010 (L2 契约) | TC-072 | test_reviewer.py |
| FR-011 (L3 设计) | TC-073 | test_reviewer.py |
| FR-012 (自动测试) | TC-080, TC-081 | test_test_runner.py |
| FR-013 (测试阈值) | TC-082, TC-083 | test_test_runner.py |
| FR-014 (11状态机) | TC-010, TC-014, TC-015 | test_state_machine.py |
| FR-015 (非法转换) | TC-011, TC-012, TC-013 | test_state_machine.py |
| FR-016 (钉钉通知) | TC-090, TC-091 | test_reporter.py |
| FR-017 (报告生成) | TC-092 | test_reporter.py |
| FR-018 (Sprint报告) | TC-093, TC-094 | test_reporter.py |
| FR-019 (Git 同步) | TC-100, TC-102 | test_git_ops.py |
| FR-020 (Git tag) | TC-101 | test_git_ops.py |
| FR-023 (Bug修复注入) | TC-034, TC-035 | test_task_engine.py |

---

### Sprint 2 — L3 集成测试 + 集成修复 (2 周)

> **对应里程碑**: M2  
> **目标**: 实现 TEST-001 §2.4 定义的 11 条 L3 集成测试链路, 验证模块间接口 (IF-001~IF-012)

#### 2.3.1 Week 1: 核心集成链路

| # | 测试文件/函数 | 覆盖 TC | 覆盖 IF | 场景描述 | 预估 |
|---|-------------|--------|--------|---------|------|
| S2-01 | `tests/test_integration.py::test_happy_path` | TC-110 | IF-001~012 | Happy Path 全链路: load_doc → decompose → enqueue → dispatch → review → test → judge → report → git tag | 6h |
| S2-02 | `tests/test_integration.py::test_retry_path` | TC-111 | IF-006,008,010 | 重试链路: dispatch → review fail → retry → dispatch → review pass → test → pass | 3h |
| S2-03 | `tests/test_integration.py::test_escalation_path` | TC-112 | IF-006,008,010,011 | 升级链路: dispatch → review fail ×4 → ESCALATED → notify_task_escalated | 3h |
| S2-04 | `tests/test_integration.py::test_empty_sprint` | TC-113 | IF-002,003 | 空 Sprint: 文档无任务卡 → 空列表 → sprint_summary(0 tasks) | 1h |
| S2-05 | `tests/test_integration.py::test_all_machines_offline` | TC-114 | IF-004,005 | 机器全离线: registry 全 ERROR → next_batch 返回空 → 等待 | 2h |

**Week 1 小计**: 5 条集成链路, ~15h

#### 2.3.2 Week 2: 高级集成链路 (★v1.2)

| # | 测试文件/函数 | 覆盖 TC | 覆盖 IF | 场景描述 | 预估 |
|---|-------------|--------|--------|---------|------|
| S2-06 | `test_integration.py::test_cycle_detection` | TC-115 | IF-003 | 循环依赖: enqueue([A→B, B→C, C→A]) → DependencyCycleError | 2h |
| S2-07 | `test_integration.py::test_snapshot_recovery` | TC-116 | IF-003,004 | 快照恢复: 执行至 3/5 → 模拟崩溃 → snapshot 恢复 → DISPATCHED→RETRY, PASSED 保持 | 4h |
| S2-08 | `test_integration.py::test_llm_degradation` | TC-117 | IF-002,008 | LLM 降级: mock LLM 超时 ×3 → DocAnalyzer 降级 DocParser, Reviewer 自动 3.5 分通过 | 3h |
| S2-09 | `test_integration.py::test_sandbox_violation` | TC-118 | IF-006,010 | 沙箱违规: exit_code=99 → 直接 ESCALATED (不重试), 钉钉含 "沙箱违规" | 2h |
| S2-10 | `test_integration.py::test_ssh_precheck_elimination` | TC-119 | IF-004,005,006 | SSH 预检淘汰: 3 台机器, 1 台失败 → OFFLINE → 只分配 2 台 | 2h |
| S2-11 | `test_integration.py::test_json_structured_logging` | TC-120 | IF-001~012 | JSON 日志: 执行 1 Sprint → 每行 json.loads(), 含 event/task_id/sprint_id | 2h |

**Week 2 小计**: 6 条集成链路, ~15h

#### 2.3.3 集成修复阶段

> 集成测试过程中大概率会发现模块间契约不一致的问题。预留 **2 天** 用于修复。

| # | 预期修复类型 | 预估 |
|---|------------|------|
| FIX-01 | 接口参数/返回值不匹配 (IF-xxx 契约偏差) | 4h |
| FIX-02 | 异步调用链 (asyncio) 死锁/竞态 | 4h |
| FIX-03 | Mock 环境与真实环境行为差异 | 2h |
| FIX-04 | 状态机转换路径遗漏 | 2h |

#### 2.3.4 测试要求

| 测试层 | 测试内容 | 通过标准 |
|--------|---------|---------|
| L1 冒烟 | 全部 14 TC | 100% pass |
| L2 组件 | 全部 ~35 TC | ≥90% pass |
| L3 集成 | TC-110~TC-120 (11 TC) | ≥85% pass (允许 ≤1 个失败) |
| 覆盖率 | `pytest --cov=orchestrator` | 行覆盖 ≥80% |

#### 2.3.5 准出标准 (Exit Criteria)

- [ ] `tests/test_integration.py` 存在, 包含 11 个测试函数
- [ ] `pytest -m integration` ≥85% pass (≥10/11)
- [ ] `pytest -m "smoke or component or integration"` 全量执行无崩溃
- [ ] `pytest --cov=orchestrator` 行覆盖 ≥80%
- [ ] 所有集成修复 (FIX-01~04) 有对应回归测试
- [ ] CI Pipeline L1+L2+L3 阶段全绿
- [ ] Git tag: `testing-v2.0`

#### 2.3.6 需求追溯

| TC | 覆盖 FR | 覆盖 IF |
|----|--------|--------|
| TC-110 Happy Path | FR-001~023 全量 | IF-001~012 全量 |
| TC-111 重试链路 | FR-015 (重试), FR-008 (分发) | IF-006, IF-008, IF-010 |
| TC-112 升级链路 | FR-015 (ESCALATED), FR-016 (通知) | IF-006, IF-008, IF-010, IF-011 |
| TC-113 空 Sprint | FR-002 (拆解), FR-017 (报告) | IF-002, IF-003 |
| TC-114 机器离线 | FR-004 (机器池), FR-007 (匹配) | IF-004, IF-005 |
| TC-115 循环依赖 | FR-006 (拓扑排序) | IF-003 |
| TC-116 快照恢复 | FR-006 (任务队列), NFR-005 (崩溃恢复) | IF-003, IF-004 |
| TC-117 LLM 降级 | FR-002 (拆解), FR-011 (Review) | IF-002, IF-008 |
| TC-118 沙箱违规 | FR-008 (SSH 执行), FR-016 (通知) | IF-006, IF-010 |
| TC-119 SSH 预检 | FR-004 (机器管理), FR-008 (SSH) | IF-004, IF-005, IF-006 |
| TC-120 JSON 日志 | NFR-013 (统一日志) | IF-001~012 |

---

### Sprint 3 — 生产就绪 + L4 验收 (2 周)

> **对应里程碑**: M3  
> **目标**: CI/CD 完善, Docker 容器化, L4 验收测试, 文档定稿, 达到功能具备 (Feature Complete)

#### 2.4.1 Week 1: 生产基础设施

| # | 任务 | 关联需求 | 优先级 | 预估 |
|---|------|---------|--------|------|
| S3-01 | 完善 CI/CD: 增加 L3 集成测试阶段, coverage badge, 制品上传 | NFR-008, ITER-001 S0-04 | P0 | 4h |
| S3-02 | 创建 Dockerfile: 多阶段构建, Python 3.10-slim, 非 root 运行 | OPS-001 §2, ARCH-002 | P0 | 3h |
| S3-03 | 创建 docker-compose.yml: orchestrator + 测试环境 | OPS-001 §2 | P1 | 2h |
| S3-04 | NFR-015 Dashboard API: FastAPI /api/status 端点 (机器/任务/测试状态查询) | NFR-015 | P1 | 6h |
| S3-05 | 性能基线测试: 单任务 SSH 分发延迟 <5s 验证脚手架 | NFR-001, NFR-002 | P1 | 3h |
| S3-06 | 日志标准化: 统一 `[module] level message` 格式, JSON 日志模式 | NFR-013, TC-120 | P1 | 2h |

#### 2.4.2 Week 2: L4 验收测试 + 文档定稿

| # | 测试文件/函数 | 覆盖 TC | 验收方式 | 预估 |
|---|-------------|--------|---------|------|
| S3-07 | `tests/test_acceptance.py::test_single_sprint_e2e` | TC-121 | 真实 5 台机器执行 1 个 Sprint (或等效 mock 环境) | 6h |
| S3-08 | `tests/test_acceptance.py::test_doc_driven_accuracy` | TC-122 | 人工对比 LLM 拆解结果 vs 文档原文 | 2h |
| S3-09 | `tests/test_acceptance.py::test_report_readability` | TC-123 | 人工验证钉钉报告可读性 | 1h |
| S3-10 | `tests/test_acceptance.py::test_performance_baseline` | TC-124 | 单任务 SSH 分发延迟 <5s, Sprint <30min | 2h |
| S3-11 | `tests/test_acceptance.py::test_ssh_key_auth` | TC-125 | SSH ed25519 密钥验证 | 1h |
| S3-12 | `tests/test_acceptance.py::test_no_secrets_in_repo` | TC-126 | `git grep -i "private\|secret\|password"` 无匹配 | 0.5h |
| S3-13 | `tests/test_acceptance.py::test_new_module_onboarding` | TC-127 | 新模块骨架 <1h 接入验证 | 2h |

#### 2.4.3 文档定稿任务

| # | 文档 | 任务 | 预估 |
|---|------|------|------|
| S3-14 | TRACE-001 追溯矩阵 | 终审: FR→SYS→ARCH→MOD→TC 全链路无断链 | 3h |
| S3-15 | OPS-001 运维手册 | 更新: Dockerfile 操作, CI/CD 流程, 新增故障场景 | 2h |
| S3-16 | TEST-001 测试方案 | 更新: 实际 TC 执行结果回填, 覆盖率数据 | 1h |
| S3-17 | ITER-001 迭代计划 | 标记所有 Sprint Backlog 状态: Done / Deferred | 1h |
| S3-18 | README.md | 更新: 快速开始, 测试命令, Docker 部署 | 1h |

#### 2.4.4 测试要求

| 测试层 | 测试内容 | 通过标准 |
|--------|---------|---------|
| L1 冒烟 | 全部 14 TC | 100% pass |
| L2 组件 | 全部 ~35 TC | ≥90% pass |
| L3 集成 | TC-110~TC-120 (11 TC) | ≥85% pass |
| L4 验收 | TC-121~TC-127 (7 TC) | **全部 P0 pass** |
| 覆盖率 | `pytest --cov=orchestrator` | 行覆盖 **≥85%** |

#### 2.4.5 准出标准 (Exit Criteria)

- [ ] `pytest -m acceptance` 全部 P0 TC pass
- [ ] `pytest --cov=orchestrator` 行覆盖 ≥85%
- [ ] Dockerfile 构建成功, `docker run` 可启动
- [ ] CI Pipeline 全 4 层 (L1→L2→L3→L4) 通过
- [ ] Dashboard `/api/status` 返回有效 JSON
- [ ] TRACE-001 追溯矩阵终审通过, 无断链
- [ ] 全量文档已更新到最新状态
- [ ] Git tag: `v3.0.0-rc1`
- [ ] **功能具备 (Feature Complete) 宣告**

---

## §3 测试策略总览 (对齐 TEST-001)

### 3.1 测试金字塔

```
                ┌──────────┐
                │ L4 验收   │  7 TC  (TC-121~127)  人工+LLM Judge
                │ Sprint 3  │
                └────┬─────┘
              ┌──────┴───────┐
              │ L3 集成       │  11 TC (TC-110~120)  pytest -m integration
              │ Sprint 2      │
              └──────┬───────┘
          ┌──────────┴──────────┐
          │ L2 组件              │  ~35 TC (TC-010~102)  pytest -m component
          │ Sprint 1             │
          └──────────┬──────────┘
      ┌──────────────┴──────────────┐
      │ L1 冒烟                      │  14 TC (TC-001~005+)  pytest -m smoke
      │ Sprint 0.5 (已有)            │
      └─────────────────────────────┘
```

### 3.2 pytest 命令速查

```bash
# L1 — 每次 commit (CI 自动)
pytest -m smoke --tb=short -q

# L2 — 每次 Sprint (CI 自动)
pytest -m component --tb=long --json-report

# L3 — 每次 Sprint (CI 自动)
pytest -m integration --tb=long --json-report

# L4 — 里程碑节点 (人工触发)
pytest -m acceptance -s -v

# 全量
pytest -m "smoke or component or integration" --cov=orchestrator --cov-report=html

# 覆盖率检查
pytest --cov=orchestrator --cov-fail-under=70
```

### 3.3 通过/回退标准 (对齐 TEST-001 §3.3)

| 阶段 | 通过标准 | 回退动作 |
|------|---------|---------|
| L1 冒烟 | **100% pass** | 中断流水线, 拒绝进入 L2 |
| L2 组件 | **≥90% pass** | 失败用例生成 fix_instruction → 自动重试 |
| L3 集成 | **≥85% pass** | 失败链路升级为人工排查 |
| L4 验收 | **全部 P0 pass** | 阻塞发布 |

### 3.4 测试文件结构

```
tests/
├── __init__.py                 # (已有)
├── conftest.py                 # NEW: pytest markers + 共享 fixtures
├── test_smoke.py               # (已有, 14 TC) — L1
├── fixtures/                   # NEW: 测试数据目录
│   ├── config_valid.yaml       # 合法配置
│   ├── config_invalid.yaml     # 非法配置 (缺必填项)
│   ├── config_bad_schema.yaml  # Schema 错误配置
│   ├── sample_tasks.json       # 预定义任务列表
│   └── mock_doc_set/           # 模拟文档集
│       ├── requirements.md
│       ├── system_design.md
│       └── architecture.md
├── test_task_models.py         # L2 — MOD-005
├── test_config.py              # L2 — MOD-012
├── test_machine_registry.py    # L2 — MOD-003
├── test_state_machine.py       # L2 — MOD-009
├── test_task_engine.py         # L2 — MOD-004
├── test_doc_analyzer.py        # L2 — MOD-001
├── test_doc_parser.py          # L2 — MOD-002
├── test_dispatcher.py          # L2 — MOD-006
├── test_reviewer.py            # L2 — MOD-007
├── test_test_runner.py         # L2 — MOD-008
├── test_reporter.py            # L2 — MOD-010
├── test_git_ops.py             # L2 — MOD-011
├── test_main.py                # L2 — MOD-013
├── test_integration.py         # L3 — 11 条集成链路
└── test_acceptance.py          # L4 — 7 条验收测试
```

---

## §4 CI/CD 流水线设计

### 4.1 GitHub Actions 工作流

```yaml
# .github/workflows/ci.yml

name: CI Pipeline
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install ruff && ruff check orchestrator/

  test-l1:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -e ".[dev]"
      - run: pytest -m smoke --tb=short -q

  test-l2:
    needs: test-l1
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -e ".[dev]"
      - run: pytest -m component --tb=long --json-report --cov=orchestrator --cov-fail-under=70

  test-l3:
    needs: test-l2
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -e ".[dev]"
      - run: pytest -m integration --tb=long --json-report
```

### 4.2 短路机制

```
Lint ──▶ L1 Smoke ──▶ L2 Component ──▶ L3 Integration
  ❌        ❌            ❌               ❌
  停止      停止          停止             停止
```

任一阶段失败 → 后续阶段不执行 → CI 红灯。

---

## §5 全量需求追溯矩阵

> 验证每个 FR/NFR 在哪个 Sprint 被覆盖, 通过哪些 TC 验证。

### 5.1 功能需求覆盖 (FR-001~FR-023)

| FR | 描述 | 优先级 | Sprint | 验证 TC | 测试文件 |
|----|------|--------|--------|--------|---------|
| FR-001 | 文档集加载 | P0 | S1 | TC-050, TC-051 | test_doc_analyzer.py |
| FR-002 | LLM 任务拆解 | P0 | S1 | TC-052, TC-053 | test_doc_analyzer.py |
| FR-003 | CodingTask 完整性 | P0 | S1 | TC-054, TC-055 | test_doc_analyzer.py |
| FR-004 | 机器池管理 | P0 | S1 | TC-020, TC-021, TC-022 | test_machine_registry.py |
| FR-005 | 标签匹配/负载均衡 | P1 | S1 | TC-023, TC-024 | test_machine_registry.py |
| FR-006 | 任务拓扑排序 | P0 | S1 | TC-030, TC-031, TC-032, TC-033 | test_task_engine.py |
| FR-007 | 均衡分发 | P0 | S1 | TC-031 | test_task_engine.py |
| FR-008 | SSH aider 执行 | P0 | S1 | TC-060~TC-063 | test_dispatcher.py |
| FR-009 | L1 静态检查 | P0 | S1 | TC-070, TC-071 | test_reviewer.py |
| FR-010 | L2 契约检查 | P0 | S1 | TC-072 | test_reviewer.py |
| FR-011 | L3 设计符合度 | P1 | S1 | TC-073 | test_reviewer.py |
| FR-012 | 自动 pytest | P0 | S1 | TC-080, TC-081 | test_test_runner.py |
| FR-013 | 测试阈值 | P1 | S1 | TC-082, TC-083 | test_test_runner.py |
| FR-014 | 11 状态机 | P0 | S1 | TC-010, TC-014, TC-015 | test_state_machine.py |
| FR-015 | 非法转换拒绝 | P0 | S1 | TC-011, TC-012, TC-013 | test_state_machine.py |
| FR-016 | 钉钉通知 | P0 | S1 | TC-090, TC-091 | test_reporter.py |
| FR-017 | 报告生成 | P1 | S1 | TC-092 | test_reporter.py |
| FR-018 | Sprint 报告 | P1 | S1 | TC-093, TC-094 | test_reporter.py |
| FR-019 | Git 同步 | P0 | S1 | TC-100, TC-102 | test_git_ops.py |
| FR-020 | Git tag | P0 | S1 | TC-101 | test_git_ops.py |
| FR-021 | 人工反馈 | P1 | S2 | TC-111, TC-112 | test_integration.py |
| FR-022 | AI Bug 分类 | P2 | S3 | TC-122 | test_acceptance.py |
| FR-023 | 修复任务注入 | P2 | S1 | TC-034, TC-035 | test_task_engine.py |

### 5.2 非功能需求覆盖 (NFR-001~NFR-015)

| NFR | 描述 | Sprint | 验证方式 |
|-----|------|--------|---------|
| NFR-001 | 任务延迟 ≤10min | S3 | TC-124 性能基线 |
| NFR-002 | 调度延迟 ≤5s | S3 | TC-124 性能基线 |
| NFR-003 | 日产 ≥50 任务 | S3 | TC-121 全链路 |
| NFR-004 | SSH 重试 3 次 | S1 | TC-062 |
| NFR-005 | 崩溃恢复 | S2 | TC-116 快照恢复 |
| NFR-006 | 重试 3 次 + 升级 | S1+S2 | TC-012, TC-013, TC-112 |
| NFR-007 | 动态扩缩容 | S3 | TC-127 新模块接入 |
| NFR-008 | 零项目假设 | S0.5 | CI lint + code review |
| NFR-009 | 多项目 (v3.1) | — | 路线图, 不在本期 |
| NFR-010 | SSH 密钥认证 | S3 | TC-125 |
| NFR-011 | 密钥不入库 | S3 | TC-126 |
| NFR-012 | 频率限制 | S3 | code review |
| NFR-013 | 统一日志 | S2 | TC-120 JSON 日志 |
| NFR-014 | 状态时间戳 | S1 | TC-010 全路径验证 |
| NFR-015 | Dashboard API | S3 | S3-04 /api/status 端点 |

---

## §6 风险识别 (对齐 OPS-003)

| 风险 ID | 描述 | 影响 | 缓解措施 |
|---------|------|------|---------|
| RISK-R01 | L2 组件测试发现深层 Bug 需要大幅重构 | Sprint 1 延期 | 预留 1 天缓冲; 非核心功能降级 |
| RISK-R02 | L3 集成测试中 asyncio 链路死锁 | Sprint 2 延期 | 使用 pytest-asyncio + 超时限制; 降级为同步测试 |
| RISK-R03 | Mock 与真实 LLM/SSH 行为差异导致 L4 失败 | Sprint 3 阻塞 | L3 阶段引入半真实环境测试; L4 前做冒烟预检 |
| RISK-R04 | CI 环境与本地环境差异 | 全 Sprint | 使用 Docker 统一环境; CI 与本地同 Python 版本 |
| RISK-R05 | test_runner.py BUG-2 修复后影响链路 | Sprint 0.5 | 先修 Bug, 后写回归测试, 确认无副作用 |

---

## §7 总工时与里程碑甘特图

### 7.1 工时汇总

| Sprint | 持续时间 | 开发工时 | 测试工时 | 缓冲 | 合计 |
|--------|---------|---------|---------|------|------|
| Sprint 0.5 | 1 周 | 4h | 3h | 1d | ~2d |
| Sprint 1 | 2 周 | 14h | 23h | 1d | ~6d |
| Sprint 2 | 2 周 | 12h | 18h + 集成修复 12h | 1d | ~7d |
| Sprint 3 | 2 周 | 20h | 14.5h + 文档 8h | 1d | ~7d |
| **合计** | **~7 周** | **~50h** | **~58.5h** | **4d** | **~22d** |

### 7.2 关键路径

```
Sprint 0.5 (1w)          Sprint 1 (2w)                Sprint 2 (2w)           Sprint 3 (2w)
┌───────────────┐  ┌───────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Bug Fix       │  │ W1: 核心模块 L2 测试   │  │ W1: 核心集成链路      │  │ W1: CI/CD + Docker   │
│ conftest.py   │→ │   state_machine       │→ │   TC-110 Happy Path  │→ │   Dashboard API      │
│ fixtures/     │  │   machine_registry    │  │   TC-111 重试链路     │  │   性能基线            │
│ CI Pipeline   │  │   task_engine         │  │   TC-112 升级链路     │  │                      │
│               │  │   config              │  │   TC-113 空 Sprint    │  │ W2: L4 验收测试       │
│ Tag:          │  │   task_models         │  │   TC-114 机器离线     │  │   TC-121~TC-127      │
│ testing-v0.5  │  │                       │  │                      │  │   文档定稿            │
│               │  │ W2: 外部交互 L2 测试   │  │ W2: 高级集成链路      │  │   追溯矩阵终审       │
│               │  │   doc_analyzer(mock)  │  │   TC-115~TC-120      │  │                      │
│               │  │   dispatcher(mock)    │  │   + 集成修复          │  │ Tag: v3.0.0-rc1      │
│               │  │   reviewer(mock)      │  │                      │  │ ★ Feature Complete    │
│               │  │   test_runner(mock)   │  │ Tag: testing-v2.0    │  │                      │
│               │  │   reporter(mock)      │  │                      │  │                      │
│               │  │   git_ops(mock)       │  │                      │  │                      │
│               │  │                       │  │                      │  │                      │
│               │  │ Tag: testing-v1.0     │  │                      │  │                      │
└───────────────┘  └───────────────────────┘  └──────────────────────┘  └──────────────────────┘

  M0.5 ✓              M1 ✓                        M2 ✓                      M3 ✓
```

### 7.3 关键依赖链

**关键路径**: Bug Fix → conftest.py → L2 核心测试 → L2 Mock 测试 → L3 Happy Path → L3 高级链路 → L4 验收 → Feature Complete

延迟影响: 任一环节延迟 → 后续全部推迟。最大风险节点为 **Sprint 2 Week 1 (L3 Happy Path)** — 首次全链路集成, 极可能暴露深层问题。

---

## §8 DoD (Definition of Done) (对齐 ITER-001 §5)

### 8.1 通用 DoD (每个 Sprint)

| # | 检查项 | 验证方式 |
|---|--------|---------|
| DoD-G1 | 所有代码已合并到 `main` | Git log |
| DoD-G2 | 单元测试覆盖率按目标达成 | `pytest --cov` |
| DoD-G3 | 无 P0 级 Bug 遗留 | Issue tracker |
| DoD-G4 | 相关文档已同步更新 | 文档 diff |
| DoD-G5 | CI Pipeline 绿灯 | GitHub Actions |

### 8.2 Sprint 专属 DoD

| Sprint | 额外 DoD | 数值目标 |
|--------|---------|---------|
| Sprint 0.5 | BUG-1/2 已修, conftest.py + CI 就绪 | L1 14/14 pass |
| Sprint 1 | 13 个模块各有测试文件, L2 全量 pass | L2 ≥90%, cov ≥70% |
| Sprint 2 | 11 条集成链路 pass, 集成修复完成 | L3 ≥85%, cov ≥80% |
| Sprint 3 | 全部 P0 验收通过, 文档定稿, Docker 可用 | L4 P0 100%, cov ≥85% |

---

## §9 交付物清单

| 交付物 | Sprint | 状态 |
|--------|--------|------|
| BUG-1/BUG-2 修复 + 回归测试 | S0.5 | ⬜ |
| tests/conftest.py | S0.5 | ⬜ |
| tests/fixtures/ (4+ 文件) | S0.5 | ⬜ |
| .github/workflows/ci.yml | S0.5 | ⬜ |
| tests/test_state_machine.py (TC-010~015) | S1 | ⬜ |
| tests/test_machine_registry.py (TC-020~024) | S1 | ⬜ |
| tests/test_task_engine.py (TC-030~035) | S1 | ⬜ |
| tests/test_config.py (TC-040~043) | S1 | ⬜ |
| tests/test_task_models.py (补全) | S1 | ⬜ |
| tests/test_doc_analyzer.py (TC-050~055) | S1 | ⬜ |
| tests/test_dispatcher.py (TC-060~063) | S1 | ⬜ |
| tests/test_reviewer.py (TC-070~073) | S1 | ⬜ |
| tests/test_test_runner.py (TC-080~083) | S1 | ⬜ |
| tests/test_reporter.py (TC-090~094) | S1 | ⬜ |
| tests/test_git_ops.py (TC-100~102) | S1 | ⬜ |
| tests/test_doc_parser.py (补充) | S1 | ⬜ |
| tests/test_main.py (补充) | S1 | ⬜ |
| tests/test_integration.py (TC-110~120) | S2 | ⬜ |
| 集成修复补丁 (FIX-01~04) | S2 | ⬜ |
| .github/workflows/ci.yml 完善版 | S3 | ⬜ |
| Dockerfile | S3 | ⬜ |
| docker-compose.yml | S3 | ⬜ |
| Dashboard API (/api/status) | S3 | ⬜ |
| tests/test_acceptance.py (TC-121~127) | S3 | ⬜ |
| 文档定稿 (TRACE-001, OPS-001, TEST-001 等) | S3 | ⬜ |
| README.md 更新 | S3 | ⬜ |
| Git tag: v3.0.0-rc1 | S3 | ⬜ |

---

## §10 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 初版: 编码实施计划 (P1~P5 修复+补全) |
| **v2.0** | **2026-03-08** | **重构为全流程实施计划: 4 里程碑 + 4 Sprint + 完整测试策略 + 需求追溯矩阵 + CI/CD + Docker** |
