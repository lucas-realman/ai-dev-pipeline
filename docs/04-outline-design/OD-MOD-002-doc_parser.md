# OD-MOD-002 — DocParser 模块概要设计

> **文档编号**: OD-MOD-002  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/doc_parser.py` (194 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-001](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-002](../05-detail-design/DD-MOD-002-doc_parser.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-002 |
| **核心类** | `DocParser` |
| **ARCH 组件** | ARCH-001 文档解析组件 (v2 兼容层) |
| **关联 FR** | FR-001 (向后兼容 v2 格式) |
| **对外接口** | `parse_task_card(card_path) → List[CodingTask]` |
| **依赖** | MOD-005 (task_models) |

## 职责

解析 v2 格式 Sprint 任务卡表格 (`| **W1** | ... |` 格式) → 输出 `List[CodingTask]`。新项目建议直接用 MOD-001 (DocAnalyzer)，本模块保留为向后兼容层。

## 核心流程

```
parse_task_card(card_path, sprint)
    │
    ├── 读取 Markdown 文件
    ├── _extract_sprint_section(content, sprint)  ← regex 匹配 "## Sprint X"
    ├── _parse_tables(section)
    │       ├── 逐行匹配 "| **Wx** |" 格式
    │       ├── MACHINE_ALIAS 映射: W0→orchestrator, W1→4090, ...
    │       └── _expand_machine_range("W1-W3") → [W1, W2, W3]
    ├── _infer_target_dir(task)
    ├── _infer_context_files(task)
    └── return List[CodingTask]
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **MACHINE_ALIAS 硬编码** | v2 遗留，W0~W5 映射到具体机器名，v3 使用 tags 替代 |
| **MACHINE_DEFAULT_DIR** | 每台机器的默认工作目录，v3 由 config 配置 |
| **范围展开** | `W1-W3` 自动展开为 [W1, W2, W3]，支持连续分配 |
| **Sprint 段提取** | 正则匹配 `## Sprint {n}` 到下一个同级标题之间的内容 |

## 错误处理策略

| 场景 | 处理 |
|------|------|
| 任务卡文件不存在 | 抛出 `FileNotFoundError` |
| Sprint 段不存在 | 返回空列表 |
| 表格格式异常 | warning 日志，跳过无法解析的行 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.2 提取并扩充 |
