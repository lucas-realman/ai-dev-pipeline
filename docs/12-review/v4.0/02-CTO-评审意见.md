# CTO 评审意见

> **评审版本**: v4.0  
> **评审日期**: 2026-03-07  
> **评审范围**: AI-Dev-Pipeline 全量文档体系 — 技术架构与实现可行性

---

## 总体评价

从技术战略角度，系统采用 **Python asyncio + Protocol/ABC 双层抽象** 的架构决策是正确的——兼顾了类型安全与运行时灵活性。13 模块的职责划分清晰，关键路径 (DocAnalyzer → TaskEngine → Dispatcher → AutoReviewer → TestRunner → Reporter) 形成完整的自动化闭环。

但当前文档暴露的 **接口一致性问题**是最大技术风险。尤其是 Orchestrator↔TaskEngine 的 7 个方法名不匹配 (P0) 以及 ALG 编号冲突 (P0-NEW)，这些问题如果带入代码阶段将导致集成测试全面失败。文档层面必须先对齐。

## 亮点

| # | 内容 | 技术评价 |
|---|------|---------|
| 1 | **Protocol + ABC 双层设计** (DD-SYS-001 §3) | 满足 SOLID 原则，支持未来 Provider 扩展 |
| 2 | **Token Bucket 令牌桶** (DD-SYS-001 §4.3 ★v1.2) | RPM/TPM 双维度限速，LLM 成本可控 |
| 3 | **指数退避重试** (DD-MOD-001 ALG-005) | 支持 jitter，适合对接不稳定的 LLM API |
| 4 | **Prometheus 指标** (DD-SYS-001 §9 ★v1.2) | 4 类 14 指标，运维可观测性完备 |
| 5 | **状态机驱动** (DD-MOD-006) | 7 态 13 转移，支持 ESCALATED 人工介入 |
| 6 | **持久化层** (DD-SYS-001 §10 ★v1.2) | async SQLite + WAL，单节点场景足够 |

## 问题与风险

### 🔴 P0 — 阻塞级

| # | 问题 | 详情 | 关联 |
|---|------|------|------|
| 1 | **Orchestrator↔TaskEngine 方法名断裂** | DD-MOD-013 ALG-031 调用 `handle_coding_failed/review_failed/review_passed/test_failed/test_passed/mark_done/get_all_results()`；DD-MOD-004 实际定义 `handle_coding_done/review_done/test_done/get_all_tasks()` — **7 处不匹配** | DD-MOD-004, DD-MOD-013 |
| 2 | **StateMachine CREATED→ESCALATED 非法转移** | `_TRANSITIONS[CREATED]=[QUEUED]` 但 ALG-009 从 CREATED 调用 `sm.escalate()` | DD-MOD-006, DD-MOD-004 |
| 3 | **ALG 编号冲突 (NEW)** | DD-MOD-001 ALG-005="LLM 指数退避重试"，DD-MOD-002/DD-001 ALG-005="任务卡解析主流程" — **4 个算法 ID 重复** | DD-MOD-001, DD-MOD-002, DD-001 |
| 4 | **构造函数参数断裂 (NEW)** | DD-MOD-001 DocAnalyzer `__init__(project_path, doc_set_config, llm_base, llm_key, llm_model)` vs DD-MOD-013 `DocAnalyzer(config)` 传入完整 Config 对象 | DD-MOD-001, DD-MOD-013 |

### 🟡 P1 — 需尽快修复

| # | 问题 | 详情 |
|---|------|------|
| 5 | **HTTP 客户端库不一致** | DocAnalyzer 使用 `httpx.AsyncClient`，AutoReviewer 使用 `aiohttp.ClientSession`；DD-SYS-001 §8.1 仅列 httpx |
| 6 | **asyncssh 矛盾** | OPS-003 RISK-002 提及 `asyncssh`，但 CON-003 明确禁止 |
| 7 | **数据模型字段缺失** | CodingTask 缺 `module_name`；MachineInfo 缺 `busy_since`；TestResult 缺 `pass_rate/reason/skipped_count` |
| 8 | **DD-MOD 编号与 MOD 编号映射错位** | DD-MOD-006=StateMachine(MOD-009), DD-MOD-007=Dispatcher(MOD-006) — 与 OD-MOD 上游引用不一致 |

## 具体建议

### 架构建议 1: ALG 编号重新分配
DD-MOD-001 的 ALG-005/006 应重新编号为 ALG-005a/005b 或分配新编号 (如 ALG-032/033)，避免与 DD-MOD-002 冲突。需同步更新 DD-001 索引页。

### 架构建议 2: 统一 HTTP 客户端
选择 `httpx` 作为唯一 HTTP 客户端库 (DD-SYS-001 §8.1 已列入)。AutoReviewer 的 `aiohttp.ClientSession` 应替换为 `httpx.AsyncClient`。

### 架构建议 3: 构造函数参数统一为 Config 注入
所有模块统一采用 `Config` 对象注入，DD-MOD-001/002 的构造函数签名应更新为 `__init__(config: Config)`，与 DD-MOD-013 Orchestrator 的调用方式一致。

### 架构建议 4: DD-MOD↔MOD 映射关系表
在 DD-001 索引页增加一张 DD-MOD-XXX ↔ MOD-XXX 映射表，消除编号混淆。

## 结论

- **评审结论**: ⚠️ 有条件通过
- **核心阻塞项**: P0 #1~#4 必须修复 — 预计 3~4h 文档对齐工作
- **技术可行性**: 架构设计合理，一旦接口对齐，代码实现无重大技术障碍
