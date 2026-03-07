# 系统设计文档 (模拟)

## 1. 系统架构

AutoDev Pipeline 采用 **文档驱动 + AI-Native** 架构:

```
文档集 → DocAnalyzer (LLM) → CodingTask[] → TaskEngine
→ Dispatcher (SSH) → AutoReviewer (3层) → TestRunner → Reporter
```

## 2. 核心模块

| 模块 | 职责 |
|------|------|
| DocAnalyzer | 文档集加载 + LLM 任务拆解 |
| TaskEngine | 任务队列管理 + 拓扑排序 |
| Dispatcher | SSH 远程执行 aider |
| AutoReviewer | 三层代码审查 |
| TestRunner | pytest 测试执行 |
| Reporter | 钉钉通知 + 报告生成 |

## 3. 接口契约

所有模块通过 `CodingTask` / `TaskResult` / `ReviewResult` / `TestResult` 数据模型交互。
