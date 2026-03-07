# OD-MOD-001 — DocAnalyzer 模块概要设计

> **文档编号**: OD-MOD-001  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/doc_analyzer.py` (292 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-001](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-001](../05-detail-design/DD-MOD-001-doc_analyzer.md) · [OD-003 IF-001/IF-002](OD-003-接口契约设计.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-001 |
| **核心类** | `DocAnalyzer` |
| **ARCH 组件** | ARCH-001 文档解析组件 |
| **关联 FR** | FR-001 文档集加载, FR-002 AI 自动拆解, FR-003 结构化任务输出 |
| **对外接口** | IF-001 `load_doc_set()`, IF-002 `analyze_and_decompose()` |
| **依赖** | MOD-012 (config), MOD-005 (task_models), httpx |

## 职责

按 `doc_set` 配置的 glob 模式加载项目文档 → 调用云端 LLM 进行自动任务分解 → 输出结构化 `List[CodingTask]`。

## 核心流程

```
load_doc_set()                    analyze_and_decompose()
    │                                    │
    ├── 遍历 doc_set_config              ├── load_doc_set()
    ├── glob 匹配文件                    ├── _build_decompose_prompt()
    ├── 读取文件内容                     │       └── MAX_DOC_LEN=6000 截断
    └── return Dict[str, str]            ├── _call_llm()
                                         │       ├── httpx async POST
                                         │       ├── OpenAI-compatible API
                                         │       └── temp=0.2, max_tokens=4096
                                         ├── _parse_tasks_from_llm()
                                         │       └── _extract_json() (3 级回退)
                                         └── return List[CodingTask]
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **glob 加载** | 支持绝对/相对路径，按 doc_set 配置的 key→pattern 映射加载 |
| **LLM 截断** | 单个文档超过 MAX_DOC_LEN=6000 字符时截断，防止 token 溢出 |
| **JSON 3 级回退** | 直接解析 → ` ```json``` ` 代码块提取 → 搜索 `[` 到 `]` 范围 |
| **温度 0.2** | 低温度确保输出稳定性，max_tokens=4096 足够覆盖任务列表 |

## 错误处理策略

| 场景 | 处理 |
|------|------|
| 项目路径不存在 | 抛出 `FileNotFoundError` |
| glob 无匹配 | warning 日志，跳过该 doc_type |
| LLM 调用超时 | httpx timeout，抛出异常由上层捕获 |
| JSON 解析失败 | 3 级回退后仍失败时返回空列表 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.1 提取并扩充，形成独立模块概要 |
