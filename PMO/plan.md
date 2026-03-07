# AutoDev Pipeline — 编码实施计划 (v1.0 — 已归档)

> **版本**: v1.0 (已归档)  
> **创建日期**: 2026-03-07  
> **状态**: ✅ 已完成 (coding-v1.0, commit d0455a7)  
> **后续计划**: → [plan-v2.md](./plan-v2.md) (全流程实施计划 v2.0)  
> **基线**: review-v5.1 (文档评审通过, 4.3/5)  
> **代码基线**: 现有 3175 行 (13 模块 + 1 冒烟测试)  
> **目标**: 将现有代码与 DD-MOD-001~013 详细设计规格对齐

---

## 现状评估

| 维度 | 数据 |
|------|------|
| 现有代码量 | 3175 行 / 14 文件 |
| 运行时崩溃 Bug | **9 处** (main.py 调用不存在的枚举/方法) |
| 设计规格缺失功能 | **~20 项** (缺方法、缺字段、缺算法) |
| 命名/规范偏差 | **~15 处** (方法名、枚举名、降级分) |
| 测试覆盖 | 1 个冒烟测试 (106 行) |

---

## Phase 1 — 修复崩溃级 Bug (优先级: P0)

> **目标**: 修复所有 TypeError / AttributeError，确保代码可运行  
> **预估**: ~2h  
> **涉及文件**: 6 个

### 1.1 task_models.py — 数据模型修复

| # | 修复项 | 原因 |
|---|--------|------|
| 1 | `ReviewLayer` 枚举: STATIC/CONTRACT/DESIGN → L1_STATIC/L2_CONTRACT/L3_QUALITY | 与 DD-MOD-005 §2.1 对齐 |
| 2 | `TestResult` 添加 `task_id: str`, `details: str = ""`, `pass_rate: float = 0.0`, `reason: str = ""`, `skipped_count: int = 0` | test_runner.py 构造时传了这些字段 |
| 3 | `ReviewResult.layer` 类型: `Optional[str]` → `ReviewLayer` | 类型安全 |
| 4 | `CodingTask` 添加 `module_name: str = ""` | DD-MOD-005 |
| 5 | `MachineInfo.current_task` → `current_task_id`, 添加 `busy_since: Optional[float] = None` | DD-MOD-003 |

### 1.2 doc_analyzer.py — 构造函数对齐

| # | 修复项 |
|---|--------|
| 6 | `__init__` 改为 `(self, config: Config)`, 从 config 中提取 project_path, doc_set, llm 参数 |

### 1.3 doc_parser.py — 构造函数对齐

| # | 修复项 |
|---|--------|
| 7 | `__init__` 改为 `(self, config: Config)`, 从 config 中提取 repo_path |

### 1.4 task_engine.py — 补充缺失方法

| # | 修复项 |
|---|--------|
| 8 | 添加 `add_task()` 方法 (委托给 `enqueue_single`) |

### 1.5 dispatcher.py — 补充缺失方法

| # | 修复项 |
|---|--------|
| 9 | 添加 `check_task_done()` 方法骨架 |

### 1.6 main.py — 修复所有调用不一致

| # | 修复项 |
|---|--------|
| 10 | `TaskStatus.CODING` → `TaskStatus.DISPATCHED` / `CODING_DONE` |
| 11 | `TaskStatus.CODED` → `TaskStatus.CODING_DONE` |
| 12 | `TaskStatus.REVIEWING` → `TaskStatus.REVIEW` |
| 13 | `self.engine.add_task(t)` → `self.engine.enqueue_single(t)` |
| 14 | `mark_dispatched(task)` → `mark_dispatched(task.task_id)` |
| 15 | `handle_coding_done(task)` → `handle_coding_done(task.task_id, result)` |
| 16 | `reviewer.review(task)` → `reviewer.review(task, result)` |
| 17 | `DocAnalyzer(self.config)` 构造签名已在 1.2 修复 |
| 18 | `DocParser(self.config)` 构造签名已在 1.3 修复 |

### 验收标准

- [ ] `python -c "from orchestrator.main import Orchestrator"` 无报错
- [ ] `pytest tests/test_smoke.py` 全部通过

---

## Phase 2 — 补齐设计规格功能 (优先级: P1)

> **目标**: 实现 DD-MOD 规格中的缺失算法和功能  
> **预估**: ~4h  
> **涉及文件**: 8 个

### 2.1 config.py — Schema 验证 (ALG-025a)

| # | 功能 |
|---|------|
| 1 | `ConfigSchemaError` 异常类 |
| 2 | `_validate_schema()` 方法: 校验必填字段、类型、范围 |
| 3 | `__init__` 中调用 `_validate_schema()` |

### 2.2 task_models.py — 安全校验

| # | 功能 |
|---|------|
| 4 | `CodingTask.__post_init__()`: task_id / target_dir 白名单校验 |

### 2.3 task_engine.py — 核心算法

| # | 功能 | 算法 |
|---|------|------|
| 5 | `enqueue()` 环检测 (Kahn 拓扑排序) | ALG-009, ALG-009a |
| 6 | `_save_snapshot()` / `_load_snapshot()` 持久化 | ALG-009b |

### 2.4 state_machine.py — 状态扩展

| # | 功能 |
|---|------|
| 7 | `_TRANSITIONS[CREATED]` 补充 `→ ESCALATED` |
| 8 | `on_state_change` 回调支持 |

### 2.5 dispatcher.py — SSH 安全

| # | 功能 | 算法 |
|---|------|------|
| 9 | `_ssh_exec_simple()` 辅助方法 | — |
| 10 | `_ssh_pre_check()` SSH 预检 | ALG-013a |
| 11 | `_check_aider_version()` 版本检查 | ALG-013b |
| 12 | 沙箱安全: exit_code=99, ulimit, 目录逃逸检测 | DD-MOD-007 §3a |

### 2.6 doc_analyzer.py — LLM 健壮性

| # | 功能 | 算法 |
|---|------|------|
| 13 | `_call_llm()` 指数退避重试 (3 次) | ALG-032 |
| 14 | `_build_decompose_prompt()` 优先级截断 | ALG-003 |
| 15 | `get_doc_set_summary()` 方法 | DD-MOD-001 |
| 16 | LLM 审计日志 | DD-MOD-001 ★v1.2 |

### 2.7 reviewer.py — LLM 重试 + 降级

| # | 功能 |
|---|------|
| 17 | `_call_llm()` 3 次重试 + 指数退避 |
| 18 | L3 降级分: 4.0 → 3.5 |

### 2.8 main.py — 生产级特性

| # | 功能 | 算法 |
|---|------|------|
| 19 | SIGTERM/SIGINT 信号处理 | ALG-030a |
| 20 | stale-busy 检测与恢复 | ALG-030b |

### 验收标准

- [ ] Config 加载非法 YAML 时抛出 `ConfigSchemaError`
- [ ] 循环依赖任务入队时抛出异常
- [ ] SSH 预检超时时返回明确错误
- [ ] `pytest tests/` 全部通过

---

## Phase 3 — 命名规范对齐 (优先级: P2)

> **目标**: 方法名、参数名与设计文档完全一致  
> **预估**: ~1.5h  
> **涉及文件**: 5 个

### 3.1 reviewer.py — 方法重命名

| 旧名称 | 新名称 |
|--------|--------|
| `review()` | `review_task()` |
| `_static_check()` | `_run_l1_static()` |
| `_contract_check()` | `_run_l2_contract()` |
| `_design_check()` | `_run_l3_quality()` |
| `_read_contracts_for_task()` | `_read_contracts()` |
| `_read_files()` | `_build_code_snippet()` |

### 3.2 test_runner.py — 方法重命名 + 签名修复

| 旧名称 | 新名称 |
|--------|--------|
| `run_tests(task)` | `run_tests(task, result)` |
| `_find_tests_for_task()` | `_discover_test_files()` |
| `_exec()` | `_run_pytest()` |

### 3.3 reporter.py — 补充 + 重命名

| # | 修复项 |
|---|--------|
| 1 | 添加 `notify_shutdown()` 方法 |
| 2 | `save_sprint_report()` → `generate_report()` |
| 3 | `_compute_sign()` 提取为 `@staticmethod` |

### 3.4 git_ops.py — 签名对齐

| # | 修复项 |
|---|--------|
| 4 | `commit(message, add_all=True)` → `commit(message, paths=None)` |
| 5 | 添加 push 计数追踪属性 `push_count` |

### 3.5 machine_registry.py — 方法补充

| # | 修复项 |
|---|--------|
| 6 | 添加 `get_busy_machines()` 方法 |
| 7 | 添加 `set_offline(machine_id)` 方法 |

### 验收标准

- [ ] 所有公开方法名与 DD-MOD 设计文档一致
- [ ] `pytest tests/test_smoke.py` 红灯 → 修复后全绿

---

## Phase 4 — 单元测试补全 (优先级: P1)

> **目标**: 每个模块一个测试文件, 覆盖核心路径  
> **预估**: ~3h  
> **涉及文件**: 13 个新测试文件

| 测试文件 | 覆盖模块 | 关键 TC |
|---------|---------|--------|
| `test_task_models.py` | MOD-005 | 枚举值、dataclass 构造、__post_init__ 校验 |
| `test_config.py` | MOD-012 | 加载 YAML、环境变量展开、Schema 验证 |
| `test_machine_registry.py` | MOD-003 | 注册/注销、标签匹配、busy/idle 切换 |
| `test_state_machine.py` | MOD-006 | 全状态链路、非法转换拒绝、回调触发 |
| `test_task_engine.py` | MOD-004 | 入队、批次取出、环检测、持久化 |
| `test_doc_analyzer.py` | MOD-001 | Mock LLM、加载文档集、任务分解 |
| `test_doc_parser.py` | MOD-002 | 解析任务卡片、合约读取 |
| `test_dispatcher.py` | MOD-007 | SSH 预检 mock、沙箱检查、版本检查 |
| `test_reviewer.py` | MOD-008 | L1/L2/L3 通过/失败路径、降级分 |
| `test_test_runner.py` | MOD-009 | pytest 报告解析、fallback 阈值 |
| `test_reporter.py` | MOD-010 | 签名计算、通知发送 mock |
| `test_git_ops.py` | MOD-011 | commit/push/tag mock |
| `test_main.py` | MOD-013 | 信号处理、stale-busy、CLI 参数 |

### 验收标准

- [ ] `pytest tests/ -v` 全部通过
- [ ] `pytest --cov=orchestrator` 行覆盖 ≥ 70%

---

## Phase 5 — 集成验证 (优先级: P2)

> **目标**: 端到端功能验证  
> **预估**: ~2h

| # | 验证项 |
|---|--------|
| 1 | `python -m orchestrator.main --mode sprint --dry-run` 正常运行 |
| 2 | Config 加载 config.yaml 无警告 |
| 3 | 任务拆解 → 分发 → 编码 → 评审 → 测试 全链路 (mock SSH) |
| 4 | 信号处理: 发送 SIGTERM 后优雅退出 |
| 5 | 钉钉通知 mock 验证 |

---

## 总工时估算

| Phase | 工时 | 累计 |
|-------|------|------|
| Phase 1: 修复崩溃 | ~2h | 2h |
| Phase 2: 补齐功能 | ~4h | 6h |
| Phase 3: 命名对齐 | ~1.5h | 7.5h |
| Phase 4: 单元测试 | ~3h | 10.5h |
| Phase 5: 集成验证 | ~2h | 12.5h |
| **合计** | **~12.5h** | |

---

## 执行策略

1. **Phase 1 + 2 + 3 合并执行**: 按模块而非按 Phase 修改，减少来回切换
2. **修改顺序**: task_models → config → machine_registry → state_machine → task_engine → doc_parser → doc_analyzer → dispatcher → reviewer → test_runner → reporter → git_ops → main
3. **每模块完成后**: 运行现有测试确保无回归
4. **Phase 4 紧跟**: 每修完一个模块立即写测试
5. **Git 策略**: 每完成一个 Phase 提交一次, tag: `code-v0.1` / `code-v0.2` ...
