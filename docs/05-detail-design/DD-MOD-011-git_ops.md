# DD-MOD-011 — GitOps 模块详细设计

> **文档编号**: DD-MOD-011  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/git_ops.py` (137 行)  
> **上游文档**: [OD-MOD-011](../04-outline-design/OD-MOD-011-git_ops.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                        GitOps                            │
├──────────────────────────────────────────────────────────┤
│ + config    : Config                                     │
│ + work_dir  : str                                        │
├──────────────────────────────────────────────────────────┤
│ + __init__(config)                                       │
│ + pull() → None                              «async»     │
│ + commit(message, paths=None) → None         «async»     │
│ + push(branch=None) → None                   «async»     │
│ + tag_sprint(sprint_id, message) → None      «async»     │
│ + sync_nodes(machines) → None                «async»     │
│ + get_current_branch() → str                 «async»     │
│ + get_short_sha() → str                      «async»     │
│ + has_changes() → bool                       «async»     │
│ - _run(cmd) → (str, str, int)                «async»     │
└──────────────────────────────────────────────────────────┘
```

最小化设计: 10 个公开方法 + 1 个私有基础方法，总计 137 行。

---

## §2 核心函数设计

### 2.1 `_run` (基础执行器) ★

| 项目 | 内容 |
|------|------|
| **签名** | `async _run(self, cmd: List[str]) → Tuple[str, str, int]` |
| **职责** | 统一 Git CLI 异步执行入口 |
| **算法** | ALG-023 |

#### ALG-023: 统一 Git 命令执行

```
async function _run(cmd):
    log.debug("git cmd: %s", ' '.join(cmd))
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=self.work_dir     # 关键: 固定工作目录
    )
    
    stdout, stderr = await proc.communicate()
    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()
    
    if proc.returncode != 0:
        log.error("git failed [%d]: %s\n%s", 
                  proc.returncode, ' '.join(cmd), stderr_str)
    
    return (stdout_str, stderr_str, proc.returncode)
```

**设计要点**:
- 所有 Git 操作都经过此方法，确保统一日志和错误处理
- `cwd=self.work_dir` 确保 Git 操作始终在正确目录

### 2.2 `pull`

| 项目 | 内容 |
|------|------|
| **签名** | `async pull(self) → None` |
| **命令** | `git pull --rebase origin {branch}` |
| **异常** | 返回码非零 → `log.error` (不抛异常) |

### 2.3 `commit`

| 项目 | 内容 |
|------|------|
| **签名** | `async commit(self, message: str, paths: Optional[List[str]] = None) → None` |
| **流程** | |

```
1. if paths:
       git add {paths}
   else:
       git add -A
2. git commit -m "{message}"
```

### 2.4 `push` (含推送计数 ★v1.1)

| 项目 | 内容 |
|------|------|
| **签名** | `async push(self, branch: Optional[str] = None) → None` |
| **命令** | `git push origin {branch or config.branch}` |
| **★v1.1** | 内部维护 `_push_count` 计数器，每次成功 push 后自增 |

> 对应 ACTION-ITEM v2.1 A-117: Git 推送策略增强
>
> **推送计数告警机制**: Orchestrator 在每轮 Sprint 结束时检查
> `git_ops.push_count`，若超过阈值 (default: 50) 则发出
> WARNING 日志。提示多机并发推送可能造成分支冲突率上升。
>
> **Per-machine 分支模式**: 当 `config.per_machine_branch=true` 时，
> 各机器推送到独立分支 `auto/{machine_id}/{task_id}`，
> Sprint 结束后统一 merge 回主分支，减少并发冲突。

### 2.5 `tag_sprint`

| 项目 | 内容 |
|------|------|
| **签名** | `async tag_sprint(self, sprint_id: str, message: str = "") → None` |
| **命令** | `git tag -a sprint/{sprint_id} -m "{message}"` + `git push origin --tags` |

### 2.6 `sync_nodes` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async sync_nodes(self, machines: List[MachineInfo]) → None` |
| **职责** | 并行同步所有远程节点的 Git 仓库 |
| **算法** | ALG-024 |

#### ALG-024: 多节点并行同步

```
async function sync_nodes(machines):
    tasks = []
    for m in machines:
        cmd = f"ssh -p {m.port} {m.user}@{m.host} " \
              f"'cd {m.work_dir} && git fetch origin && " \
              f"git reset --hard origin/{config.branch}'"
        tasks.append(_run(['bash', '-c', cmd]))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for m, r in zip(machines, results):
        if isinstance(r, Exception):
            log.error("节点同步失败 %s: %s", m.machine_id, r)
        elif r[2] != 0:             # returncode
            log.error("节点同步失败 %s: %s", m.machine_id, r[1])
        else:
            log.info("节点同步成功: %s", m.machine_id)
```

### 2.7 `get_current_branch`

| 签名 | `async get_current_branch(self) → str` |
|------|----------------------------------------|
| 命令 | `git rev-parse --abbrev-ref HEAD` |

### 2.8 `get_short_sha`

| 签名 | `async get_short_sha(self) → str` |
|------|-------------------------------------|
| 命令 | `git rev-parse --short HEAD` |

### 2.9 `has_changes`

| 签名 | `async has_changes(self) → bool` |
|------|-------------------------------------|
| 命令 | `git status --porcelain` |
| 返回 | `len(stdout) > 0` |

---

## §3 序列图

### SEQ-011: Sprint 完成后的 Git 操作流

```
Orchestrator     GitOps          Local Git         Remote Origin     远程节点
    │               │               │                 │               │
    │ pull()        │               │                 │               │
    │──────────────>│               │                 │               │
    │               │ git pull      │                 │               │
    │               │ --rebase      │                 │               │
    │               │──────────────>│                 │               │
    │               │               │ fetch+rebase   │               │
    │               │               │────────────────>│               │
    │               │               │                 │               │
    │ commit(msg)   │               │                 │               │
    │──────────────>│               │                 │               │
    │               │ git add -A    │                 │               │
    │               │ git commit    │                 │               │
    │               │──────────────>│                 │               │
    │               │               │                 │               │
    │ push()        │               │                 │               │
    │──────────────>│               │                 │               │
    │               │ git push      │                 │               │
    │               │──────────────>│                 │               │
    │               │               │────────────────>│               │
    │               │               │                 │               │
    │ tag_sprint()  │               │                 │               │
    │──────────────>│               │                 │               │
    │               │ git tag +     │                 │               │
    │               │ push tags     │                 │               │
    │               │──────────────>│────────────────>│               │
    │               │               │                 │               │
    │ sync_nodes()  │               │                 │               │
    │──────────────>│               │                 │               │
    │               │ ssh node1     │                 │               │
    │               │───────────────────────────────────────────────>│
    │               │ ssh node2     │                 │               │
    │               │───────────────────────────────────────────────>│
    │               │ (parallel)    │                 │               │
    │               │               │                 │               │
    │     ok        │               │                 │               │
    │<──────────────│               │                 │               │
```

---

## §4 配置参数

| 配置路径 | 类型 | 说明 |
|----------|------|------|
| `project.branch` | str | 默认分支名 |
| `project.work_dir` | str | 本地工作目录 |

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §11 提取并扩充，含多节点同步算法 |
| v1.1 | 2026-03-07 | push() 推送计数告警; per-machine 分支模式说明 (A-117) |
