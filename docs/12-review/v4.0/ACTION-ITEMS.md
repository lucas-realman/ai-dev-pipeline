# ACTION-ITEMS — v4.0

> **评审版本**: v4.0  
> **生成日期**: 2026-03-07  
> **合计**: 31 项 (P0×4, P1×9, P2×8, P3×10)  
> **预计总工作量**: 16h

---

## 状态说明

| 标记 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🔧 | 进行中 |
| ✅ | 已完成 |

---

## 🔴 Batch 1: P0 — Critical (4 项, 预计 4h)

> **Deadline**: Day 1 (修复后方可进入代码实现)

| ID | 问题 | 修复动作 | 涉及文档 | 工作量 | 状态 |
|----|------|---------|---------|--------|------|
| A-001 | Orchestrator↔TaskEngine 7 方法名不匹配 | 以 DD-MOD-004 为权威, 统一 DD-MOD-013 ALG-031 调用侧: `handle_coding_failed→handle_coding_done`; `handle_review_failed/passed→handle_review_done`; `handle_test_failed/passed→handle_test_done`; `mark_done→(移除或映射)`; `get_all_results→get_all_tasks`; 同步更新 SEQ-SYS-001 | DD-MOD-004, DD-MOD-013, SEQ-SYS-001 | 1h | ⬜ |
| A-002 | StateMachine CREATED→ESCALATED 非法转移 | 在 DD-MOD-006 `_TRANSITIONS[CREATED]` 中增加 `ESCALATED`; 更新 §2 转移表和 §4 状态图 | DD-MOD-006 | 0.5h | ⬜ |
| A-003 | ALG 编号冲突 (ALG-005/006 双重定义) | DD-MOD-001 的 ALG-005 重编号为 ALG-032 ("LLM 指数退避重试"); ALG-006 重编号为 ALG-033 ("请求解析与字段校验"); 更新 DD-001 索引页 ALG 注册表 | DD-MOD-001, DD-001 | 1h | ⬜ |
| A-004 | DocAnalyzer/DocParser 构造函数签名断裂 | DD-MOD-001 `__init__` 改为 `__init__(config: Config)`, 内部从 config 获取 project_path/llm_base 等; DD-MOD-002 同理改为 `__init__(config: Config)` | DD-MOD-001, DD-MOD-002, DD-MOD-013 | 1.5h | ⬜ |

---

## 🟡 Batch 2: P1 — High (9 项, 预计 5h)

> **Deadline**: Day 1-2

| ID | 问题 | 修复动作 | 涉及文档 | 工作量 | 状态 |
|----|------|---------|---------|--------|------|
| A-005 | 数据模型字段缺失 | DD-MOD-005 补充: `CodingTask.module_name: str`; `MachineInfo.busy_since: Optional[datetime]`; `TestResult.pass_rate: float`; `TestResult.reason: str`; `TestResult.skipped_count: int` | DD-MOD-005 | 1h | ⬜ |
| A-006 | httpx vs aiohttp 不统一 | DD-MOD-008 AutoReviewer 改用 `httpx.AsyncClient` (通过 LLMProvider 接口); 删除 pyproject.toml 中 aiohttp 依赖; DD-SYS-001 §8.1 确认仅列 httpx | DD-MOD-008, DD-SYS-001, pyproject.toml | 1h | ⬜ |
| A-007 | 降级分阈值 4.0→3.5 传播 | 全局替换: REQ-001 FR-010/FR-011 `4.0→3.5`; DD-SYS-001 SEQ-SYS-003 mermaid 图 `4.0→3.5`; OD-003 所有 `4.0→3.5` | REQ-001, DD-SYS-001, OD-003 | 0.5h | ⬜ |
| A-008 | MachineRegistry 缺失方法 | DD-MOD-005 MachineRegistry §3 补充: `get_busy_machines() → List[MachineInfo]`; `set_offline(machine_id: str) → None` | DD-MOD-005 | 0.5h | ⬜ |
| A-009 | Reporter 缺失 notify_shutdown() | DD-MOD-010 §3 公共方法表补充: `notify_shutdown(reason: str) → None` | DD-MOD-010 | 0.5h | ⬜ |
| A-010 | OPS-003 RISK-002 asyncssh 矛盾 | RISK-002 描述从 "asyncssh 连接" 改为 "subprocess SSH 连接"，风险描述改为进程管理风险而非库依赖风险 | OPS-003 | 0.5h | ⬜ |
| A-011 | DD-MOD↔OD-MOD 编号映射错误 | DD-MOD-006 上游引用改为 OD-MOD-009; DD-MOD-007→OD-MOD-006; DD-MOD-008→OD-MOD-007; DD-MOD-009→OD-MOD-008 | DD-MOD-006~009 | 0.5h | ⬜ |
| A-012 | TRACE-001 映射错误 | FR-016/017/018 → IF-011 (非 IF-010); CON-002 追溯链增加 MOD-006 (Dispatcher) | TRACE-001 | 0.5h | ⬜ |
| A-013 | MachineInfo.current_task vs current_task_id | DD-MOD-005 统一为 `current_task_id: Optional[str]`; DD-MOD-013 ALG-030b 相应更新 | DD-MOD-005, DD-MOD-013 | 0.5h | ⬜ |

---

## 🔵 Batch 3: P2 — Medium (8 项, 预计 4h)

> **Deadline**: Day 2-3

| ID | 问题 | 修复动作 | 涉及文档 | 工作量 | 状态 |
|----|------|---------|---------|--------|------|
| A-014 | ReviewLayer 枚举命名不一致 | DD-MOD-005 统一为 `L1_STATIC / L2_CONTRACT / L3_QUALITY` (以 DD-MOD-008 为准) | DD-MOD-005 | 0.5h | ⬜ |
| A-015 | ReviewResult 字段不一致 | DD-MOD-005 统一为 `issues: List[ReviewIssue]` (非 `comments`) | DD-MOD-005, DD-MOD-008 | 0.5h | ⬜ |
| A-016 | CONTRACT-001 参数签名不一致 | DD-SYS-001 `call(prompt: str)` 改为 `call(messages: List[Dict[str, str]])`, 以 CONTRACT-001 为权威 | DD-SYS-001 | 0.5h | ⬜ |
| A-017 | CONTRACT-002 ALG 引用错误 | SSH 预检引用 `ALG-012→ALG-013a` | CONTRACT-002 | 0.5h | ⬜ |
| A-018 | CONTRACT-003 ALG 引用错误 | `review()` 引用 `ALG-010→ALG-015` | CONTRACT-003 | 0.5h | ⬜ |
| A-019 | DD-MOD-007 _ssh_exec_simple 未定义 | 在 DD-MOD-007 §3 补充为私有辅助方法, 或在 §4 内部方法表中列出 | DD-MOD-007 | 0.5h | ⬜ |
| A-020 | Config Schema 缺 per_machine_branch | DD-MOD-012 Schema 补充 `per_machine_branch: bool (default: true)` | DD-MOD-012 | 0.5h | ⬜ |
| A-021 | Orchestrator get_all_results() 错误 | DD-MOD-013 ALG-031 中 `engine.get_all_results()→engine.get_all_tasks()` | DD-MOD-013 | 0.5h | ⬜ |

---

## 🟢 Batch 4: P3 — Low (10 项, 预计 3h)

> **Deadline**: 下一迭代

| ID | 问题 | 修复动作 | 涉及文档 | 状态 |
|----|------|---------|---------|------|
| A-022 | DD-MOD-005 §3.3 节号重复 | 重新编号 §3.3 以下小节 | DD-MOD-005 | ⬜ |
| A-023 | DD-MOD-005 版本跳跃 v1.0→v1.2 | 补充 v1.1 changelog 说明 | DD-MOD-005 | ⬜ |
| A-024 | DD-MOD-004 changelog "§4a" vs "§4.2" | 统一为 §4.2 | DD-MOD-004 | ⬜ |
| A-025 | DD-MOD-011 声称 10 方法实际 8-9 | 更正公共方法数量 | DD-MOD-011 | ⬜ |
| A-026 | DD-MOD-013 §5a 编号不连续 | 修正章节编号 | DD-MOD-013 | ⬜ |
| A-027 | OD-003 header v1.0 vs changelog v1.1 | header 更新为 v1.1 | OD-003 | ⬜ |
| A-028 | Navigator 缺 v2.0/v2.1/v3.0 目录 | 补充评审版本目录入口 | 00-navigator | ⬜ |
| A-029 | REQ-001 默认 gpt-4 vs OD-003 claude-opus-4-6 | 统一描述为"可配置 LLM", 默认值由 Config Schema 定义 | REQ-001, OD-003 | ⬜ |
| A-030 | TC 编号跳跃 (TC-001~123 仅 ~58 个) | 规范化 v1.2 新增 TC 编号 (TC-11A→TC-121) | TEST-001 | ⬜ |
| A-031 | NFR-007/010/011 无自动化 TC | 补充 TC-124 (SSH 延迟) / TC-125 (配置热加载) / TC-126 (日志 JSON 格式) | TEST-001, TRACE-001 | ⬜ |

---

## 进度追踪

| Batch | 总数 | ⬜ 未开始 | 🔧 进行中 | ✅ 已完成 | 进度 |
|-------|------|-----------|-----------|-----------|------|
| P0 | 4 | 4 | 0 | 0 | 0% |
| P1 | 9 | 9 | 0 | 0 | 0% |
| P2 | 8 | 8 | 0 | 0 | 0% |
| P3 | 10 | 10 | 0 | 0 | 0% |
| **合计** | **31** | **31** | **0** | **0** | **0%** |
