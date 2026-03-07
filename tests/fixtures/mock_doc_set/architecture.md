# 系统架构文档 (模拟)

## 1. 部署架构

```
  ┌─────────────┐
  │ Orchestrator │ ← 主编排, 运行 TaskEngine + Reporter
  │ 172.16.14.201│
  └──────┬──────┘
         │ SSH
  ┌──────┼──────┬──────────┐
  │      │      │          │
  ▼      ▼      ▼          ▼
GPU-4090 Mac-Mini Gateway  DataCenter
(推理)   (前端)  (部署)    (数据)
```

## 2. 模块层级

- **L0 (入口)**: main.py - CLI 与 Orchestrator
- **L1 (核心)**: task_engine, state_machine, machine_registry
- **L2 (执行)**: dispatcher, reviewer, test_runner
- **L3 (辅助)**: doc_analyzer, doc_parser, reporter, git_ops, config
- **L4 (数据)**: task_models

## 3. 通信协议

- Orchestrator ↔ Worker: SSH + aider CLI
- Orchestrator → LLM: HTTP (OpenAI 兼容 API)
- Orchestrator → 钉钉: HTTPS Webhook
