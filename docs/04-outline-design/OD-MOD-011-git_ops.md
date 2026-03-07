# OD-MOD-011 — GitOps 模块概要设计

> **文档编号**: OD-MOD-011  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/git_ops.py` (137 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-008](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-011](../05-detail-design/DD-MOD-011-git_ops.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-011 |
| **核心类** | `GitOps` |
| **ARCH 组件** | ARCH-008 Git 自动化组件 |
| **关联 FR** | FR-019 pull/push 自动化, FR-020 Sprint tag |
| **对外接口** | IF-012 `pull()`, `commit()`, `push()`, `tag_sprint()`, `sync_nodes()` |
| **依赖** | MOD-012 (config), MOD-005 (task_models: `MachineInfo`), asyncio |

## 职责

封装 Git CLI 操作：pull / commit / push / tag / 多节点代码同步。

## 核心流程

```
常规 Git 操作:                     多节点同步:
pull(remote, branch)               sync_nodes(machines) → Dict[str, bool]
    └── git pull --rebase              │
                                       ├── asyncio.gather(
commit(message, add_all)               │       _sync_one_node(name, machine)
    ├── git add -A                     │       for name, machine in machines
    └── git commit -m "..."            │   )
                                       └── 汇总成功/失败结果
push(remote, branch)
    └── git push origin main       _sync_one_node(name, machine)
                                       └── ssh user@host 'cd work_dir && git pull --rebase'
tag_sprint(tag, message)
    ├── git tag -a {tag} -m "..."
    └── git push origin {tag}
```

## 辅助查询方法

| 方法 | 返回 | 说明 |
|------|------|------|
| `get_current_branch()` | `str` | `git rev-parse --abbrev-ref HEAD` |
| `get_short_sha()` | `str` | `git rev-parse --short HEAD` |
| `has_changes()` | `bool` | `git status --porcelain` 非空 |

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **Git CLI 封装** | 通过 `asyncio.create_subprocess_shell` 调用 git 命令 |
| **统一 `_run()`** | 所有命令走 `_run(cmd, label)` → 日志 + 返回 bool |
| **sync_nodes 并行** | `asyncio.gather` 并行同步所有节点 |
| **异常处理** | `_run()` 内捕获所有 Exception，返回 False |
| **SSH 端口** | 自动检测非默认端口，添加 `-p` 参数 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.11 提取并扩充 |
