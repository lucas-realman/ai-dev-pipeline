# OD-MOD-013 — Main / Orchestrator 模块概要设计

> **文档编号**: OD-MOD-013  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/main.py` (366 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-010](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-013](../05-detail-design/DD-MOD-013-main.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-013 |
| **核心类** | `Orchestrator` |
| **CLI 入口** | `build_parser()` + `main()` (autodev 命令) |
| **ARCH 组件** | ARCH-010 主循环入口 |
| **关联 FR** | 全部 (编排所有模块) |
| **对外接口** | `run_sprint(sprint_id)`, `run_continuous()`, CLI `autodev` |
| **依赖** | 所有其他模块 (MOD-001~012) |

## 职责

组装所有模块 → 执行 Sprint 主循环 (dispatch → wait → review → test → judge) → CLI 入口。

## Sprint 主循环流程

```
run_sprint(sprint_id)
    │
    ├── 1. 任务发现: _discover_tasks()
    │       ├── 优先: DocAnalyzer.analyze_and_decompose()
    │       └── 回退: DocParser.parse_task_card()
    │
    ├── 2. 注册: engine.add_task(task) for each task
    │
    ├── 3. 通知: reporter.notify_sprint_start()
    │
    ├── 4. 同步: git_ops.sync_nodes() (if configured)
    │
    ├── 5. 主循环 _main_loop() (MAX_ROUNDS=20)
    │       │
    │       ├── 5a. engine.next_batch() → 可调度任务
    │       ├── 5b. _dispatch_batch(batch) → 分发
    │       ├── 5c. _wait_for_coding(batch) → 轮询等待
    │       └── 5d. _process_task_result(task) for each
    │               ├── reviewer.review(task) → pass?
    │               ├── test_runner.run_tests(task) → pass?
    │               └── 判定: PASSED / QUEUED(重试) / ESCALATED
    │
    ├── 6. 收尾: reporter.save_sprint_report()
    ├── 7. 通知: reporter.notify_sprint_done()
    └── 8. Git: commit + push + tag_sprint()
```

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-c, --config` | 配置文件路径 | `orchestrator/config.yaml` |
| `--project-path` | 项目根目录 | config 中的值 |
| `--sprint-id` | Sprint ID | `auto-001` |
| `--mode` | sprint / continuous | `sprint` |
| `--dry-run` | 只解析任务不执行 | False |
| `-v, --verbose` | Debug 日志 | False |

## 运行模式

| 模式 | 方法 | 说明 |
|------|------|------|
| **sprint** | `run_sprint(id)` | 执行单轮 Sprint，完成后退出 |
| **continuous** | `run_continuous()` | 循环执行 sprint，无任务或异常时退出 |
| **dry-run** | `_dry_run_discover()` | 只解析任务列表，输出到 stdout |

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **MAX_ROUNDS=20** | 主循环最大轮次，防止死循环 |
| **轮询等待** | `_wait_for_coding` 通过 `poll_interval_sec` (默认 30s) 轮询 |
| **max_wait_sec** | 等待编码完成的最大时间，默认 1800s |
| **降级任务发现** | v3 DocAnalyzer 失败时回退到 v2 DocParser |
| **自动 Git 操作** | `auto_commit` 和 `sync_before_sprint` 可配置关闭 |
| **异常升级** | 主循环超时的任务强制设为 ESCALATED |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.13 提取并扩充 |
