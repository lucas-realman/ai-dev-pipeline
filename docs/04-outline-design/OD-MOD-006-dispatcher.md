# OD-MOD-006 — Dispatcher 模块概要设计

> **文档编号**: OD-MOD-006  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/dispatcher.py` (326 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-003](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-006](../05-detail-design/DD-MOD-006-dispatcher.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-006 |
| **核心类** | `Dispatcher` |
| **ARCH 组件** | ARCH-003 任务调度组件 (执行端) |
| **关联 FR** | FR-006 SSH 分发, FR-008 aider 远程执行 |
| **对外接口** | IF-006 `dispatch_task()`, IF-007 `dispatch_batch()` |
| **依赖** | MOD-012 (config), MOD-003 (machine_registry), MOD-005 (task_models), asyncio |

## 职责

SSH 连接远程机器 → SCP 任务指令 → 执行 aider → 收集结果。自动检测本机 IP，本地机器走 subprocess，远程机器走 SSH。

## 核心流程

```
dispatch_task(task) → TaskResult
    │
    ├── _build_instruction(task)          ← Markdown 格式指令，含约束
    │       └── 含 fix_instruction (重试时)
    ├── 获取 MachineInfo from registry
    ├── _scp_content(machine, instruction)
    │       ├── 本地: 直接写 tempfile
    │       └── 远程: scp 到 /tmp/aider_msg_{task_id}
    ├── _build_ssh_script(task, machine)
    │       ├── cd work_dir
    │       ├── git reset --hard && git pull
    │       ├── aider --message-file ...
    │       └── git push (3 次重试)
    ├── _ssh_exec(machine, script)
    │       ├── 本地: bash -c
    │       └── 远程: ssh user@host
    ├── _parse_changed_files(stdout)      ← 解析 "Wrote" 和 "create mode"
    └── return TaskResult(success, files, stdout, stderr)

dispatch_batch(tasks) → List[TaskResult]
    └── asyncio.gather(*[dispatch_task(t) for t in tasks])  ← 并行分发
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **本地/远程自动检测** | `__init__` 获取本机 IP 列表，匹配则走 subprocess |
| **指令文件传输** | SCP 写到 `/tmp/aider_msg_{task_id}`，避免命令行长度限制 |
| **Git push 3 次重试** | 脚本内置重试循环，应对网络抖动 |
| **并行分发** | `dispatch_batch` 使用 `asyncio.gather` 并行执行 |
| **fallback_machines** | 配置兜底机器列表，registry 匹配失败时使用 |
| **超时控制** | 通过 config 的 `single_task_timeout` 控制 SSH 执行超时 |

## 错误处理策略

| 场景 | 处理 |
|------|------|
| SSH 连接失败 | TaskResult(success=False)，上层触发重试/升级 |
| SCP 传输失败 | 异常捕获，warning 日志 |
| aider 执行超时 | asyncio timeout，进程 kill |
| Git push 失败 | 脚本内 3 次重试后返回非零退出码 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.6 提取并扩充 |
