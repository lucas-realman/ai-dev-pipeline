# v3.0 ACTION-ITEMS — 跨模块一致性修复清单

> **评审编号**: REVIEW-v3.0-ACT  
> **生成日期**: 2026-03-07  
> **总工时**: ~8h (P0: 2h + P1: 3h + P2: 2h + P3: 1h)  
> **总条目**: 29 项 (P0×2 + P1×6 + P2×13 + P3×8)  
> **修复原则**: 全部为文档级变更，不涉及代码修改  
> **符号说明**: ⬜ 未开始 | 🔵 进行中 | ✅ 已完成

---

## §1 P0 — 阻塞实现 (2 项 | ~2h)

### A-001 Orchestrator ↔ TaskEngine 方法名对齐 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-001 |
| **严重度** | 🔴 P0 |
| **定义侧** | DD-MOD-004 §2: `handle_coding_done()`, `handle_review_done()`, `handle_test_done()` |
| **调用侧** | DD-MOD-013 ALG-031: `handle_coding_failed()`, `handle_review_failed()`, `handle_review_passed()`, `handle_test_failed()`, `handle_test_passed()`, `mark_done()` |
| **影响范围** | DD-MOD-004 / DD-MOD-013 / CONTRACT-002 (可能) |
| **修复方案** | **方案 A (推荐)**: DD-MOD-004 拆分 `handle_xxx_done()` 为 `handle_xxx_passed()` + `handle_xxx_failed()` + `mark_done()`，提供更细粒度的状态处理。同步更新 DD-MOD-004 §1 类图、§2 算法伪代码 |
| **修复方案** | **方案 B**: DD-MOD-013 ALG-031 对齐到 DD-MOD-004 现有 `handle_xxx_done(success: bool)` 风格 |
| **估时** | 1h |
| **涉及文件** | DD-MOD-004, DD-MOD-013, CONTRACT-002 |

### A-002 StateMachine 转换表增加 CREATED→ESCALATED ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-002 |
| **严重度** | 🔴 P0 |
| **问题位置** | DD-MOD-006 §2.1 `_TRANSITIONS` |
| **调用方** | DD-MOD-004 ALG-009: 循环依赖检测后调用 `sm.escalate()` (此时 task 处于 CREATED 状态) |
| **修复方案** | DD-MOD-006 §2.1 `_TRANSITIONS[CREATED]` 增加 `ESCALATED`；在 §2 增加 Note 说明场景；同步检查 DD-MOD-006 状态图 (mermaid) |
| **估时** | 1h |
| **涉及文件** | DD-MOD-006, DD-MOD-004 (确认 ALG-009 描述) |

---

## §2 P1 — 一致性缺陷 (6 项 | ~3h)

### A-003 CodingTask 增加 `module_name` 字段 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-003 |
| **严重度** | 🟡 P1 |
| **问题位置** | DD-MOD-005 §2.1 CodingTask |
| **引用方** | DD-MOD-009 ALG-018 (`task.module_name`) |
| **修复方案** | DD-MOD-005 CodingTask 字段表增加 `module_name: str`，加入「映射说明」指出 DocAnalyzer 产出中的模块名如何赋值 |
| **估时** | 20min |
| **涉及文件** | DD-MOD-005 |

### A-004 MachineInfo 增加 `busy_since` 字段 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-004 |
| **严重度** | 🟡 P1 |
| **问题位置** | DD-MOD-005 §2.3 MachineInfo |
| **引用方** | DD-MOD-013 ALG-030b (stale-busy 检测) |
| **修复方案** | DD-MOD-005 MachineInfo 字段表增加 `busy_since: Optional[datetime]`，注明在 Dispatcher 分配任务时写入 |
| **估时** | 20min |
| **涉及文件** | DD-MOD-005 |

### A-005 TestResult 增加 `pass_rate` / `reason` / `skipped_count` ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-005 |
| **严重度** | 🟡 P1 |
| **问题位置** | DD-MOD-005 §2.5 TestResult |
| **引用方** | DD-MOD-009 ALG-018/020 |
| **修复方案** | DD-MOD-005 TestResult 字段表增加: `pass_rate: float`, `reason: str`, `skipped_count: int`；注明 TestRunner 执行后填充 |
| **估时** | 20min |
| **涉及文件** | DD-MOD-005 |

### A-006 降级 score=4.0→3.5 全文传播 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-006 |
| **严重度** | 🟡 P1 |
| **已修改** | DD-MOD-008 §2.4 ✅, DD-SYS-001 §2.4 ✅ |
| **未修改** | REQ-001 (2 处: §FR-008 描述 + §NFR-005 质量门), DD-SYS-001 SEQ-SYS-003 mermaid 图, OD-003 §MOD-007 (4 处: SSH + review + quality_score 接口描述) |
| **修复方案** | `grep -rn "score=4\.0\|score = 4\.0\|4\.0/5\.0\|≥4\.0\|>=4\.0\|4\.0 分" docs/` → 逐一修改为 3.5 |
| **估时** | 30min |
| **涉及文件** | REQ-001, DD-SYS-001, OD-003 |

### A-007 MachineRegistry 增加 `get_busy_machines()` / `set_offline()` ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-007 |
| **严重度** | 🟡 P1 |
| **问题位置** | DD-MOD-003 §1 公开方法 |
| **引用方** | DD-MOD-013 ALG-030b (`registry.get_busy_machines()`), DD-MOD-007 ALG-013 (`registry.set_offline()`) |
| **修复方案** | DD-MOD-003 §1 类图增加两个方法签名；§2 增加对应简短算法描述 (ALG-XXX) |
| **估时** | 40min |
| **涉及文件** | DD-MOD-003 |

### A-008 Reporter 增加 `notify_shutdown()` ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-008 |
| **严重度** | 🟡 P1 |
| **问题位置** | DD-MOD-010 公开接口 |
| **引用方** | DD-MOD-013 ALG-030a (信号处理时调用) |
| **修复方案** | DD-MOD-010 §1 类图增加 `notify_shutdown() → None`；§2 增加算法 (发送 shutdown event, 刷新 pending reports) |
| **估时** | 30min |
| **涉及文件** | DD-MOD-010 |

---

## §3 P2 — 跨模块引用修正 (13 项 | ~2h)

### A-009 ReviewLayer 枚举命名统一 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-009 |
| **修复方案** | 以 DD-MOD-005 为权威；DD-MOD-008 §1 的 `L1_STATIC/L2_CONTRACT/L3_QUALITY` 改为 `STATIC/CONTRACT/DESIGN` 或反之 (确定一种)。建议保留带前缀版本 (更清晰)，则 DD-MOD-005 对齐到 MOD-008 |
| **估时** | 10min |
| **涉及文件** | DD-MOD-005 或 DD-MOD-008 |

### A-010 ReviewResult 字段名统一 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-010 |
| **修复方案** | 以 CONTRACT-003 YAML 为权威 (`issues`)；DD-MOD-008 §2 中 `comments` → `issues` |
| **估时** | 10min |
| **涉及文件** | DD-MOD-008 |

### A-011 DD-MOD-007 补充 `_ssh_exec_simple` 定义 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-011 |
| **修复方案** | DD-MOD-007 §2 增加 `_ssh_exec_simple` 私有方法签名及说明 (与 `_ssh_exec` 区别: 不带输出捕获) |
| **估时** | 10min |
| **涉及文件** | DD-MOD-007 |

### A-012 Config Schema 增加 `per_machine_branch` ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-012 |
| **修复方案** | DD-MOD-012 §3 Schema 表增加 `per_machine_branch: bool (default: false)` |
| **估时** | 10min |
| **涉及文件** | DD-MOD-012 |

### A-013 DD-MOD-013 `engine.get_all_results()` → `get_all_tasks()` ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-013 |
| **修复方案** | DD-MOD-013 中 `engine.get_all_results()` 改为 `engine.get_all_tasks()` 以对齐 DD-MOD-004 |
| **估时** | 5min |
| **涉及文件** | DD-MOD-013 |

### A-014 CONTRACT-001 `call()` 签名对齐设计文档 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-014 |
| **修复方案** | 以 DD-SYS-001 §4.2 (LLM 抽象层详细设计) 为权威；CONTRACT-001 `call()` 参数改为 `prompt: str, …` 或在 DD-SYS-001 中增加 `messages` 一致性映射 |
| **估时** | 15min |
| **涉及文件** | CONTRACT-001 或 DD-SYS-001 |

### A-015 CONTRACT-002 ALG 编号修正 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-015 |
| **修复方案** | CONTRACT-002 SSH 预检引用从 ALG-012 改为 ALG-013a |
| **估时** | 5min |
| **涉及文件** | CONTRACT-002 |

### A-016 CONTRACT-003 ALG 编号修正 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-016 |
| **修复方案** | CONTRACT-003 `review()` 引用从 ALG-010 改为 ALG-015 |
| **估时** | 5min |
| **涉及文件** | CONTRACT-003 |

### A-017 DD-MOD-005 §3.3 重复编号修正 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-017 |
| **修复方案** | 第二个 §3.3 改为 §3.4，后续章节依次后移 |
| **估时** | 5min |
| **涉及文件** | DD-MOD-005 |

### A-018 DD-MOD-004 变更记录 §4a → §4.2 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-018 |
| **修复方案** | DD-MOD-004 §5 变更记录中 "§4a" 改为 "§4.2" |
| **估时** | 5min |
| **涉及文件** | DD-MOD-004 |

### A-019 DD-MOD-011 公开方法数修正 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-019 |
| **修复方案** | DD-MOD-011 §1 重新计数并修正 "10 个公开方法" 为实际数量 |
| **估时** | 5min |
| **涉及文件** | DD-MOD-011 |

### A-020 DD-MOD-013 §5a 编号规范化 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-020 |
| **修复方案** | DD-MOD-013 §5a 改为 §5.1 或调整为独立 §6 |
| **估时** | 5min |
| **涉及文件** | DD-MOD-013 |

### A-021 DD-MOD-005 版本号补 v1.1 变更记录 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-021 |
| **修复方案** | DD-MOD-005 变更记录中 v1.0→v1.2 之间插入 v1.1 条目，说明中间变更 |
| **估时** | 5min |
| **涉及文件** | DD-MOD-005 |

---

## §4 P3 — 文档质量 (8 项 | ~1h)

### A-022 OD-003 文档头版本号更新 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-022 |
| **修复方案** | OD-003 文档头版本从 v1.0 改为 v1.1 |
| **估时** | 5min |
| **涉及文件** | OD-003 |

### A-023 REQ-001 默认 LLM 模型对齐 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-023 |
| **修复方案** | REQ-001 中 LLM 默认模型描述改为可配置 (default 由 Config 指定)，移除硬编码 `gpt-4` |
| **估时** | 10min |
| **涉及文件** | REQ-001 |

### A-024 v2.1 ACTION-ITEMS 工时不一致 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-024 |
| **修复方案** | v2.1 ACTION-ITEMS 文档头工时改为与 §6 汇总一致 (~64h) 或校正 §6 计算 |
| **估时** | 5min |
| **涉及文件** | docs/12-review/v2.1/ACTION-ITEMS.md |

### A-025 00-navigator 补充评审目录链接 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-025 |
| **修复方案** | 00-navigator.md 目录结构中增加 v2.0、v2.1、v3.0 评审目录及文件链接 |
| **估时** | 10min |
| **涉及文件** | docs/00-navigator.md |

### A-026 TRACE-001 CON-002 增加 Dispatcher 影响范围 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-026 |
| **修复方案** | TRACE-001 §3 CON-002 asyncio 约束影响模块列表增加 Dispatcher |
| **估时** | 5min |
| **涉及文件** | TRACE-001 |

### A-027 DD-MOD-004 ALG-009a 清理编辑痕迹 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-027 |
| **修复方案** | DD-MOD-004 §2.2 ALG-009a 统一入度计算写法，删除重复/冲突的伪代码行 |
| **估时** | 10min |
| **涉及文件** | DD-MOD-004 |

### A-028 DD-MOD-011 §1 类图补充 `_push_count` ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-028 |
| **修复方案** | DD-MOD-011 §1 类结构/类图中增加 `_push_count: int` 私有属性 |
| **估时** | 5min |
| **涉及文件** | DD-MOD-011 |

### A-029 历史 ACTION-ITEMS 跨版本重复标注 ⬜

| 属性 | 值 |
|------|-----|
| **评审发现** | F-029 |
| **修复方案** | v1.0 A-009/A-018 和 v2.0 A-004/A-005 增加跨版本关联标注 (如 "→ 同 v2.0 A-004")，避免重复跟踪 |
| **估时** | 10min |
| **涉及文件** | v1.0/ACTION-ITEMS.md, v2.0/ACTION-ITEMS.md |

---

## §5 工作量汇总

| 优先级 | 条目数 | 估时 | 涉及文件数 |
|--------|--------|------|-----------|
| P0 | 2 | 2h | 3 |
| P1 | 6 | 3h | 6 |
| P2 | 13 | ~1.5h | 11 |
| P3 | 8 | ~1h | 8 |
| **合计** | **29** | **~8h** | **~15 个文件** |

> **建议执行顺序**: P0 → P1 → P2 → P3，逐批提交。  
> **阻塞关系**: P0-A001/A002 不解决 → 后续实现阶段接口对不上。

---

## §6 依赖关系图

```
A-001 (方法名对齐) ─────┐
                         ├──→ 进入代码实现阶段
A-002 (状态转换表) ──────┘
                         
A-003~A-005 (字段补全) ──→ A-006 (score 传播) ──→ 全文一致性校验

A-009 (枚举统一) ──→ A-010 (字段统一) ──→ CONTRACT-003 对齐

A-015/A-016 (ALG 编号) ──→ 独立

A-025 (navigator) ──→ 在所有修改完成后最后更新
```

---

## 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-07 | 初始版本: v3.0 评审 29 项 ACTION-ITEMS | AutoDev Pipeline |
