# TEST-001 — 测试策略与方案

> **文档编号**: TEST-001  
> **版本**: v1.0  
> **状态**: 草稿  
> **更新日期**: 2026-03-06  
> **上游文档**: [REQ-001](../01-requirements/REQ-001-系统需求规格说明书.md) · [OD-001](../04-outline-design/OD-001-模块概要设计.md) · [OD-003](../04-outline-design/OD-003-接口契约设计.md)  
> **下游文档**: [TRACE-001](../06-traceability/TRACE-001-追溯矩阵.md)  
> **参考**: [05-测试方案与计划 (v0.5)](../11-references/migrated/05-测试方案与计划.md)

---

## §1 测试总则

### 1.1 测试理念

> **文档驱动 × AI-Native**：代码和测试由 aider 在同一个 Prompt 中同步生成；  
> 每次 Sprint 迭代自动 `pytest` → 评估 → 报告 → 钉钉通知，无"手动提测"环节。

| 原则 | 说明 |
|------|------|
| **代码与测试同源** | aider 写代码时同步生成测试；不存在"代码完成后补测试" |
| **30分钟迭代环** | 编码 10min → push + 自动评估 5min → Review 5min → 下一轮 10min |
| **三层自动审查** | L1 静态 (py_compile+ruff) → L2 契约 (LLM) → L3 设计 (LLM)，短路失败 |
| **红绿灯报告** | 每轮 Sprint 生成红/绿/黄 Markdown 摘要，推送钉钉 |
| **回归增量** | 只跑受影响模块的测试，未变更文件跳过 |

### 1.2 测试层级

```
┌─────────────────────────────────────────────────────────────┐
│                   测试金字塔 (V型映射)                       │
│                                                             │
│           ┌──────────────┐                                  │
│           │  L4 验收测试  │ ← FR 对齐 (人工复核)             │
│           └──────┬───────┘                                  │
│           ┌──────┴───────┐                                  │
│           │  L3 集成测试  │ ← 模块间接口 (IF-001~012)        │
│           └──────┬───────┘                                  │
│        ┌─────────┴──────────┐                               │
│        │  L2 模块/组件测试   │ ← 每个 MOD 的核心函数          │
│        └─────────┬──────────┘                               │
│    ┌─────────────┴──────────────┐                           │
│    │  L1 单元测试 + 冒烟测试    │ ← import / dataclass       │
│    └────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

| 层级 | 范围 | 执行频率 | 执行方式 | 通过标准 |
|------|------|---------|---------|---------|
| L1 单元/冒烟 | 全部 13 个 MOD 可导入 + dataclass 字段校验 | 每次 commit | pytest 本地 | 100% pass |
| L2 组件 | 每个 MOD 核心函数的输入/输出/异常 | 每次 Sprint | pytest 本地 | ≥90% pass |
| L3 集成 | IF-001~012 端到端调用链 | 每次 Sprint | pytest + mock/fixture | ≥85% pass |
| L4 验收 | FR 对齐度 + 人工 Review | 里程碑节点 | 人工 + LLM-as-Judge | 全部 P0 pass |

### 1.3 测试环境

| 环境 | 机器 | 用途 |
|------|------|------|
| **开发测试** | orchestrator (172.16.14.201) | pytest 本地执行，零网络延迟 |
| **推理后端** | 4090 (172.16.11.194:8000) | Agent 集成测试推理 (vLLM A)，内网 <1ms |
| **LLM Judge** | 云端 API | AutoReview L2/L3 用 `claude-opus-4-6` |

---

## §2 测试用例矩阵

> 映射规则: FR-xxx → MOD-xxx → TC-xxx

### 2.1 L1 冒烟测试

| TC 编号 | 测试目标 | 映射 FR/MOD | 输入 | 预期输出 | 优先级 |
|---------|---------|------------|------|---------|--------|
| TC-001 | 13 个模块全部可导入 | 全部 MOD | `importlib.import_module()` | 无 ImportError | P0 |
| TC-002 | 版本号一致 | — | `orchestrator.__version__` | `"3.0.0"` | P0 |
| TC-003 | CodingTask 默认值正确 | DM-004 | 构造最小字段 | status=QUEUED, retry_count=0 | P0 |
| TC-004 | MachineInfo 默认值正确 | DM-008 | 构造最小字段 | port=22, status=ONLINE, tags=[] | P0 |
| TC-005 | TaskStatus 枚举成员 11 个 | DM-001 | `len(TaskStatus)` | 11 | P0 |

### 2.2 L2 组件测试 — 核心模块

#### 2.2.1 状态机 (MOD-009)

| TC 编号 | 测试目标 | 映射 FR | 输入 | 预期输出 |
|---------|---------|--------|------|---------|
| TC-010 | 正常全路径 CREATED→PASSED | FR-014 | 依次调用 enqueue/dispatch/.../judge | status=PASSED |
| TC-011 | 非法转换抛异常 | FR-015 | QUEUED 直接调 judge() | StateMachineError |
| TC-012 | 重试计数 ≤3 触发 RETRY | FR-015 | review_done(failed) × 3 | retry_count=3, RETRY |
| TC-013 | 重试超限触发 ESCALATED | FR-015 | 第 4 次 handle_failure() | status=ESCALATED |
| TC-014 | is_terminal 属性 | FR-014 | PASSED / ESCALATED | True |
| TC-015 | can_dispatch 属性 | FR-014 | QUEUED | True; DISPATCHED → False |

#### 2.2.2 机器注册表 (MOD-003)

| TC 编号 | 测试目标 | 映射 FR | 输入 | 预期输出 |
|---------|---------|--------|------|---------|
| TC-020 | 注册/注销机器 | FR-004 | register + unregister | 数量增减正确 |
| TC-021 | 标签匹配 — 命中 | FR-005 | tags=["gpu"] | 返回含 gpu 标签的机器 |
| TC-022 | 标签匹配 — 空匹配 | FR-005 | tags=["nonexistent"] | 返回 None |
| TC-023 | 负载排序 | FR-005 | 3 台不同负载 | 返回最低负载 |
| TC-024 | 线程安全 | NFR-003 | 并发 register/set_busy | 无竞态异常 |

#### 2.2.3 任务引擎 (MOD-004)

| TC 编号 | 测试目标 | 映射 FR | 输入 | 预期输出 |
|---------|---------|--------|------|---------|
| TC-030 | 入队 + 拓扑排序 | FR-006 | 含依赖的 task 列表 | 依赖在前 |
| TC-031 | next_batch 遵循并发限制 | FR-007 | 5 tasks, limit=2 | 返回 2 个 |
| TC-032 | 依赖未满足不出队 | FR-006 | A→B 依赖, A 未完成 | B 不在 batch 中 |
| TC-033 | all_done 正确判定 | FR-006 | 全部 PASSED | True |
| TC-034 | Bug→修复任务注入 | FR-023 | confirmed bug report (BUG-001) | 生成 FIX-001 任务, priority=P0, 插入队列头部 |
| TC-035 | 修复任务依赖设置 | FR-023 | FIX-001 关联原始 task_id | depends_on 为空 (独立执行), tags 含 "hotfix" |

#### 2.2.4 配置 (MOD-012)

| TC 编号 | 测试目标 | 映射 FR | 输入 | 预期输出 |
|---------|---------|--------|------|---------|
| TC-040 | YAML 加载正确 | CON-001 | 合法 config.yaml | 属性可访问 |
| TC-041 | 环境变量展开 | CON-001 | `${HOME}` | 实际路径 |
| TC-042 | 缺少必选项报错 | CON-001 | 无 project_name | KeyError / ValueError |
| TC-043 | machines 列表解析 | FR-004 | 5 台机器配置 | len(get_machines()) == 5 |

### 2.3 L2 组件测试 — 外部交互模块

> 需要 mock 外部服务 (LLM API / SSH / 钉钉)

#### 2.3.1 文档分析器 (MOD-001)

| TC 编号 | 测试目标 | 映射 FR | Mock | 预期 |
|---------|---------|--------|------|------|
| TC-050 | load_doc_set 正常加载 | FR-001 | 临时 md 文件 | dict 非空 |
| TC-051 | load_doc_set 路径不存在 | FR-001 | 不存在路径 | FileNotFoundError |
| TC-052 | analyze_and_decompose 正常 | FR-002 | mock LLM → 合法 JSON | List[CodingTask] |
| TC-053 | LLM 返回非法 JSON | FR-002 | mock → `"not json"` | JSONDecodeError / 重试 |
| TC-054 | 任务字段完整性校验 | FR-003 | mock LLM → 合法 JSON | 每个 CodingTask 含 task_id, description, context_files, depends_on, acceptance, tags, estimated_minutes |
| TC-055 | 任务缺少必选字段 | FR-003 | mock → 缺 acceptance 的 JSON | ValidationError / 补全重试 |

#### 2.3.2 分发器 (MOD-006)

| TC 编号 | 测试目标 | 映射 FR | Mock | 预期 |
|---------|---------|--------|------|------|
| TC-060 | dispatch_task 本地执行 | FR-008 | mock subprocess | TaskResult, exit_code=0 |
| TC-061 | dispatch_task 远程 SSH | FR-008 | mock asyncssh | TaskResult |
| TC-062 | SSH 超时 | NFR-001 | mock 超时异常 | 机器标 ERROR, 任务迁移 |
| TC-063 | dispatch_batch 并行 | FR-008 | 3 tasks + mock | 3 个 TaskResult |

#### 2.3.3 审查器 (MOD-007)

| TC 编号 | 测试目标 | 映射 FR | Mock | 预期 |
|---------|---------|--------|------|------|
| TC-070 | L1 静态检查通过 | FR-009 | 合法 .py 文件 | layer=L1, passed=True |
| TC-071 | L1 语法错误短路 | FR-009 | 非法 .py | passed=False, 不进入 L2 |
| TC-072 | L2 契约检查 | FR-010 | mock LLM | ReviewResult, layer=L2 |
| TC-073 | L3 设计检查 | FR-011 | mock LLM | ReviewResult, layer=L3, 含 score |

#### 2.3.4 测试运行器 (MOD-008)

| TC 编号 | 测试目标 | 映射 FR | Mock | 预期 |
|---------|---------|--------|------|------|
| TC-080 | 找到测试文件并运行 | FR-012 | tmpdir + pytest json | TestResult, passed=True |
| TC-081 | 无测试文件 auto-pass | FR-012 | 空目录 | TestResult(passed=True) |
| TC-082 | 部分失败 + fallback | FR-013 | 3/4 pass, threshold=0.7 | passed=True |
| TC-083 | 低于 fallback 阈值 | FR-013 | 1/4 pass, threshold=0.7 | passed=False |

#### 2.3.5 报告器 (MOD-010)

| TC 编号 | 测试目标 | 映射 FR | Mock | 预期 |
|---------|---------|--------|------|------|
| TC-090 | 钉钉 webhook 发送 | FR-016 | mock httpx.post → 200 | 无异常 |
| TC-091 | 钉钉返回 errcode≠0 | FR-016 | mock → errcode=310000 | 日志 warning |
| TC-092 | sprint_summary Markdown | FR-017 | 5 tasks stats | 含红绿灯标记 |
| TC-093 | Sprint 报告含完整统计 | FR-018 | 10 tasks (8 pass, 1 fail, 1 escalated) | 报告含里程碑进度 + 全量统计表 + 遗留问题列表 |
| TC-094 | Sprint 报告零任务场景 | FR-018 | 0 tasks (空 Sprint) | 有效报告, 统计全零, 遗留问题为空 |

#### 2.3.6 Git 操作 (MOD-011)

| TC 编号 | 测试目标 | 映射 FR | Mock | 预期 |
|---------|---------|--------|------|------|
| TC-100 | commit + push | FR-019 | mock subprocess | True |
| TC-101 | tag_sprint | FR-020 | mock subprocess | True |
| TC-102 | sync_nodes 部分失败 | FR-021 | mock 2 ok + 1 fail | Dict{"m1":True, "m3":False} |

### 2.4 L3 集成测试

| TC 编号 | 测试目标 | 覆盖 IF | 场景描述 |
|---------|---------|--------|---------|
| TC-110 | Happy Path 全链路 | IF-001~012 | load_doc → decompose → enqueue → dispatch → review → test → judge → report → git tag |
| TC-111 | 重试链路 | IF-006,008,010 | dispatch → review fail → retry → dispatch → review pass → test → pass |
| TC-112 | 升级链路 | IF-006,008,010,011 | dispatch → review fail × 4 → ESCALATED → notify_task_escalated |
| TC-113 | 空 Sprint | IF-002,003 | 文档无任务卡 → 空列表 → sprint_summary(0 tasks) |
| TC-114 | 机器全离线 | IF-004,005 | registry 全 ERROR → next_batch 返回空 → 等待 |
| TC-115 | 循环依赖检测 ★v1.2 | IF-003 | enqueue([A→B, B→C, C→A]) → DependencyCycleError, 日志含环路径 |
| TC-116 | 快照恢复链路 ★v1.2 | IF-003,004 | 1) 执行至 3/5 任务 PASSED 2) 模拟崩溃 3) 从 snapshot 恢复 → DISPATCHED 任务变为 RETRY, PASSED 保持 |
| TC-117 | LLM 降级全链路 ★v1.2 | IF-002,008 | mock LLM 超时 3 次 → DocAnalyzer 降级到 DocParser, Reviewer L2/L3 自动 3.5 分通过, 报告标记 "LLM_DEGRADED" |
| TC-118 | 沙箱违规拦截 ★v1.2 | IF-006,010 | mock dispatch_task 返回 exit_code=99 → 任务直接 ESCALATED (不重试), 钉钉通知含 "沙箱违规" |
| TC-119 | SSH 预检 + 机器淘汰 ★v1.2 | IF-004,005,006 | 3 台机器, 1 台 SSH 预检失败 → 标记 OFFLINE → next_batch 只分配到 2 台 → 任务正常完成 |
| TC-11A | JSON 结构化日志链路 ★v1.2 | IF-001~012 | 开启 JSON 日志模式 → 执行 1 个 Sprint → 日志文件每行可 json.loads(), 含 event/task_id/sprint_id 字段 |

### 2.5 L4 验收测试

| TC 编号 | 验收目标 | 映射 FR | 验收方式 |
|---------|---------|--------|---------|
| TC-120 | 单 Sprint 端到端 | FR-001~023 | 真实 5 台机器执行 1 个 Sprint，全部任务 PASSED |
| TC-121 | 文档驱动正确性 | FR-001,002 | 人工对比：LLM 拆解结果 vs 文档任务卡原文 |
| TC-122 | 报告可读性 | FR-016,017 | 人工阅读钉钉收到的 Sprint 报告 |
| TC-123 | 性能基线 | NFR-001 | 单任务 SSH 分发延迟 <5s, 总 Sprint <30min |

---

## §3 自动化执行策略

### 3.1 执行流程

```
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐
│ git push │───▶│ pull 代码 │───▶│ L1 冒烟   │───▶│ L2 组件  │───▶│ L3 集成  │
│ (开发机) │    │ (orch)   │    │ pytest -m │    │ pytest -m│    │ pytest -m│
│          │    │          │    │ smoke     │    │ component│    │ integ    │
└─────────┘    └──────────┘    └─────┬─────┘    └────┬─────┘    └────┬─────┘
                                     │ fail ──▶ 中断                  │
                                                                      ▼
                                                              ┌──────────────┐
                                                              │ 生成报告     │
                                                              │ + 钉钉通知   │
                                                              └──────────────┘
```

### 3.2 pytest 标记约定

```python
# conftest.py 中注册标记
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: L1 冒烟测试")
    config.addinivalue_line("markers", "component: L2 组件测试")
    config.addinivalue_line("markers", "integration: L3 集成测试")
    config.addinivalue_line("markers", "acceptance: L4 验收测试")
```

**执行命令**:
```bash
# L1 — 每次 commit
pytest -m smoke --tb=short -q

# L2 — 每次 Sprint
pytest -m component --tb=long --json-report

# L3 — 每次 Sprint (需 fixture)
pytest -m integration --tb=long --json-report

# L4 — 里程碑 (真实环境)
pytest -m acceptance -s -v
```

### 3.3 通过/回退标准

| 阶段 | 通过标准 | 回退动作 |
|------|---------|---------|
| L1 冒烟 | 100% pass | 中断流水线，拒绝进入 L2 |
| L2 组件 | ≥90% pass | 失败用例生成 fix_instruction → 自动重试 |
| L3 集成 | ≥85% pass | 失败链路升级为人工排查 |
| L4 验收 | 全部 P0 pass | 阻塞发布 |

### 3.4 测试数据管理

| 数据类型 | 位置 | 管理方式 |
|----------|------|---------|
| 测试 fixture | `tests/fixtures/` | Git 版本控制 |
| mock 配置 | `tests/conftest.py` | 共享 fixture |
| 临时文件 | `pytest tmp_path` | 自动清理 |
| 测试报告 | `reports/` | `.gitignore`, 本地存档 |

---

## 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-06 | 初始版本：4 层测试策略 + 45 个 TC + 自动化执行 | AutoDev Pipeline |
| v1.1 | 2026-03-06 | 修正: MOD 编号与 OD-001 对齐, FR 映射修正 (A-002) | AutoDev Pipeline |
| v1.2 | 2026-03-06 | 新增: FR-003 (TC-054~055), FR-018 (TC-093~094), FR-023 (TC-034~035) 共 6 条测试用例 (A-008) | AutoDev Pipeline |
| v1.3 | 2026-03-07 | L3 集成测试补充 7 条 (TC-115~TC-11A): 循环依赖检测、快照恢复、LLM 降级、沙箱违规、SSH 预检、JSON 日志链路 (A-022/A-023) | AutoDev Pipeline |
