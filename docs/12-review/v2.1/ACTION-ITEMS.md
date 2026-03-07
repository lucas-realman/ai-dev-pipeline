# v2.1 ACTION-ITEMS — 技术可行性改进项

> **评审版本**: v2.1  
> **创建日期**: 2026-03-07  
> **总 ACTION 项**: 24 项 (P0×3, P1×8, P2×9, P3×4)  
> **总工作量**: ~46h

---

## §1 P0 — 必须 (发布阻塞)

| ID | 来源 | 改进项 | 影响模块 | 工作量 | 期限 |
|----|------|--------|---------|--------|------|
| **A-100** | RISK-006, TF-001 | ✅ 实现循环依赖检测: `enqueue()` 中对 `depends_on` 关系做拓扑排序，发现环路时 ESCALATE 相关任务 | task_engine.py | 2h | v1.1 |
| **A-101** | RISK-001, TF-002 | ✅ 实现 JSON 快照持久化: 每次状态变更写入 `state_snapshot.json`，启动时加载恢复 | task_engine.py, state_machine.py | 4h | v1.1 |
| **A-102** | RISK-002, TF-003 | ✅ `_call_llm()` 增加重试: 3 次指数退避 (1s, 2s, 4s)，429 限流专门处理 | doc_analyzer.py, reviewer.py | 2h | v1.1 |

---

## §2 P1 — 应该 (质量提升)

| ID | 来源 | 改进项 | 影响模块 | 工作量 | 期限 |
|----|------|--------|---------|--------|------|
| **A-110** | 03-评审 ADR-003 | ✅ Reviewer 降级 score 从 4.0 调整为 3.5 (低于 pass_threshold)，避免审查静默跳过 | reviewer.py | 0.5h | Week 2 |
| **A-111** | TF-004 | ✅ Config 启动时 schema 校验: 必填字段检查 (llm.openai_api_key, machines 列表非空) | config.py | 2h | Week 2 |
| **A-112** | TF-005 | ✅ main.py 增加 SIGTERM/SIGINT 信号处理: 设置 shutdown 标志 → 等待当前 batch 完成 → 保存快照 → 退出 | main.py | 1h | Week 2 |
| **A-113** | RISK-003 | ✅ SSH 连接预检: dispatch 前执行 `ssh -o ConnectTimeout=5 {host} echo ok`，失败则标记机器 OFFLINE | dispatcher.py | 1h | Week 2 |
| **A-114** | RISK-008 | ✅ API Key 传递优化: 远程脚本使用 `export OPENAI_API_KEY` 而非内嵌值，或通过 SSH env 传递 | dispatcher.py | 1h | Week 2 |
| **A-115** | 02-评审 §5 | ✅ 统一接口参数名与设计文档: IF-002 sprint_id int→str, IF-005 required_tags→task_tags 等 | OD-003 文档 | 1h | Week 2 |
| **A-116** | RISK-005 | ✅ stale-busy 检测: main loop 中检查 BUSY 状态超过 2×single_task_timeout 的机器，强制 set_idle | main.py | 1h | Week 2 |
| **A-117** | RISK-004 | ✅ Git 推送策略增强: 当 push 次数 > 配置阈值进行告警; 支持 per-machine branch + 合并 | dispatcher.py, git_ops.py | 3h | Week 3 |

---

## §3 P2 — 可选 (健壮性增强)

| ID | 来源 | 改进项 | 影响模块 | 工作量 | 期限 |
|----|------|--------|---------|--------|------|
| **A-120** | RISK-007, TF-008 | task_id / target_dir 字符白名单校验 (只允许 `[a-zA-Z0-9_\-/.]`) | task_models.py | 0.5h | Week 3 |
| **A-121** | RISK-010 | aider 版本锁定: config.yaml 增加 `aider_version` 字段，dispatch 前检查 | config.py, dispatcher.py | 1h | Week 3 |
| **A-122** | RISK-013, v2.0 A-011 | JSON 结构化日志: loguru `serialize=True` + 统一字段 (task_id, module, level) | 所有模块 | 2h | Week 3 |
| **A-123** | RISK-014, v2.0 A-012 | Prometheus 指标暴露: 任务成功率, SSH 延迟 p99, LLM 调用耗时, 机器利用率 | main.py, 新模块 | 4h | Week 3-4 |
| **A-124** | 02-评审 §4 | contracts/ 接口契约文件: 至少编写 3 个核心接口的 YAML 契约 | contracts/ | 4h | Week 3-4 |
| **A-125** | RISK-011 | LLM 请求/响应日志: 保存到 logs/llm_audit/ 用于质量回溯 | doc_analyzer.py, reviewer.py | 2h | Week 3 |
| **A-126** | 01-评审 §2.1 | doc_analyzer MAX_DOC_LEN 可配置化 + 智能截断 (按优先级保留) | doc_analyzer.py | 1h | Week 3 |
| **A-127** | RISK-009 | 日志脱敏: access_token / api_key 在日志中 mask 后 8 位 | reporter.py, config.py | 0.5h | Week 3 |
| **A-128** | 01-评审 §2.1 | doc_analyzer._parse_tasks_from_llm 增加字段类型校验 (estimated_minutes 等) | doc_analyzer.py | 0.5h | Week 3 |

---

## §4 P3 — 远期 (架构演进)

| ID | 来源 | 改进项 | 影响模块 | 工作量 | 期限 |
|----|------|--------|---------|--------|------|
| **A-130** | 03-评审 §4 | CodingEngine 抽象接口: 支持 aider 以外的编码引擎 | dispatcher.py, 新接口 | 4h | v2.0 |
| **A-131** | 03-评审 ADR-001 | Agent 模式评估: 当机器数 > 20 时 PoC 轻量 Agent 替代 SSH | dispatcher.py, 新模块 | 16h | v2.0 |
| **A-132** | 03-评审 ADR-004 | SQLite 持久化迁移: 当任务数 > 100 时从 JSON 快照迁移到 SQLite | task_engine.py | 8h | v2.0 |
| **A-133** | RISK-015 | 部署脚本 rollback 命令: 支持 `./deploy.sh rollback v1.0` 快速回退 | deploy/ | 2h | v2.0 |

---

## §5 与 v2.0 ACTION-ITEMS 关系

| v2.0 项 | v2.1 对应项 | 关系 |
|---------|-----------|------|
| v2.0 A-004 (ERR 异常) | A-102 (LLM 重试) | 补充 — v2.1 给出具体重试策略 |
| v2.0 A-005 (LLM Provider) | A-102 | 部分覆盖 — 重试为 Provider 抽象的前置条件 |
| v2.0 A-006 (ALG-026 环路检测) | A-100 (循环依赖检测) | 完全对齐 |
| v2.0 A-011 (JSON 日志) | A-122 (JSON 结构化日志) | 完全对齐 |
| v2.0 A-012 (监控指标) | A-123 (Prometheus 指标) | 完全对齐 |
| v2.0 A-016 (Web UI) | — | 未覆盖 — 属于产品需求 |
| v2.0 A-017 (容器沙箱) | A-131 (Agent 模式) | 关联 — Agent 可封装沙箱执行 |

**新增技术项**: A-100 (持久化 P0), A-101 (配置校验), A-110~A-128 共 14 项新发现

---

## §6 工作量汇总

| 优先级 | 数量 | 工作量 | 建议时间窗 |
|--------|------|--------|-----------|
| P0 | 3 | 8h | Week 1 (v1.1 发布前) |
| P1 | 8 | 10.5h | Week 2 |
| P2 | 9 | 15.5h | Week 3-4 |
| P3 | 4 | 30h | v2.0 |
| **合计** | **24** | **~64h** | — |

---

## 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-07 | 初始版本: 24 项 ACTION-ITEMS | AutoDev Pipeline |
| v1.1 | 2026-03-07 | P0 全部完成 (3/3); P1 全部完成 (8/8); 均为文档级设计变更 | AutoDev Pipeline |
