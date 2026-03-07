# OD-MOD-007 — AutoReviewer 模块概要设计

> **文档编号**: OD-MOD-007  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/reviewer.py` (263 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-004](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-007](../05-detail-design/DD-MOD-007-reviewer.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-007 |
| **核心类** | `AutoReviewer` |
| **ARCH 组件** | ARCH-004 审查组件 |
| **关联 FR** | FR-009 L1 静态检查, FR-010 L2 契约对齐, FR-011 L3 设计符合度 |
| **对外接口** | IF-008 `review(task, result) → ReviewResult` |
| **依赖** | MOD-012 (config), MOD-005 (task_models), httpx |

## 职责

三层自动代码审查：L1 静态检查 → L2 LLM 契约对齐 → L3 LLM 设计评分。每层独立可跳过，LLM 层降级容忍。

## 三层审查策略

| 层 | 名称 | 工具 | 成本 | 检查内容 | 降级策略 |
|----|------|------|------|---------|---------|
| L1 | 静态检查 | py_compile + ruff | 0 (本地) | 语法错误 + 严重 lint (E9,F8,F6,F4) | 不降级，失败即返回 |
| L2 | 契约对齐 | LLM (Claude) | API 调用 | 代码 vs contracts/ 目录内容 | LLM 失败 → score=4.0, passed=True |
| L3 | 设计符合度 | LLM (Claude) | API 调用 | 5 维度评分 (功能/接口/错误/质量/可运行) | LLM 失败 → score=4.0, passed=True |

## 核心流程

```
review(task, result) → ReviewResult
    │
    ├── L1: _static_check(changed_files)
    │       ├── py_compile.compile(file) → SyntaxError?
    │       ├── ruff check --select E9,F8,F6,F4
    │       └── 失败 → return ReviewResult(passed=False, layer=L1)
    │
    ├── L2: _contract_check(task, changed_files)
    │       ├── 读取 contracts/ 目录内容
    │       ├── LLM prompt: "对比代码与契约，判断是否对齐"
    │       ├── _parse_json_response() → {passed, reasons}
    │       └── LLM异常 → 降级 score=4.0, passed=True
    │
    └── L3: _design_check(task, changed_files)
            ├── LLM prompt: "5 维度评分"
            ├── _parse_json_response() → {score, details}
            ├── score >= threshold → passed=True
            └── LLM异常 → 降级 score=4.0, passed=True
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **3 层 pipeline** | L1→L2→L3 顺序执行，任何层失败可提前返回 |
| **ruff 限定规则** | 只检查 E9, F8, F6, F4 (严重错误)，避免风格误判 |
| **LLM 温度 0.1** | 比 doc_analyzer 更低，追求一致性 |
| **优雅降级** | LLM 调用失败时给默认通过 (score=4.0)，不阻塞流水线 |
| **阈值可配** | `pass_threshold` 从 config 读取，默认 4.0 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.7 提取并扩充 |
