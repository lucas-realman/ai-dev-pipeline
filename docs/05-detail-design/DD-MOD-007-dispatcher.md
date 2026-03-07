# DD-MOD-007 — Dispatcher 模块详细设计

> **文档编号**: DD-MOD-007  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/dispatcher.py` (326 行)  
> **上游文档**: [OD-MOD-007](../04-outline-design/OD-MOD-007-dispatcher.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                      Dispatcher                          │
├──────────────────────────────────────────────────────────┤
│ + config           : Config                              │
│ + registry         : Optional[MachineRegistry]           │
│ - _fallback_machines : Dict[str, MachineInfo]            │
│ - _local_ips       : Set[str]                            │
├──────────────────────────────────────────────────────────┤
│ + __init__(config, registry=None)                        │
│ + dispatch_task(task) → TaskResult           «async»     │
│ + dispatch_batch(tasks) → List[TaskResult]   «async»     │
│ - _get_machine(task) → Optional[MachineInfo]             │
│ - _is_local(machine) → bool                              │
│ - _build_instruction(task) → str                         │
│ - _build_ssh_script(task, machine, msg_path) → str       │
│ - _scp_content(machine, content, remote) → None «async»  │
│ - _ssh_exec(machine, script, timeout) → TaskResult       │
│                                              «async»     │
│ - _parse_changed_files(stdout, dir) → List[str] «static» │
│ - _collect_local_ips() → Set[str]            «static»    │
└──────────────────────────────────────────────────────────┘
       ▲ 依赖                 ▲ 依赖
       │                      │
 ┌─────┴─────┐         ┌─────┴─────┐
 │  Config   │         │ MachineReg│
 │ (MOD-012) │         │ (MOD-003) │
 └───────────┘         └───────────┘
```

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self, config: Config, registry: Optional[MachineRegistry] = None)` |
| **职责** | 初始化分发器，收集本机 IP |
| **兼容** | 无 registry 时 fallback 到 `config.get_machines()` |

### 2.2 `dispatch_task` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async dispatch_task(self, task: CodingTask) → TaskResult` |
| **职责** | 在目标机器上执行 aider 编码任务 |
| **算法** | ALG-013 |
| **超时** | `config.single_task_timeout` (默认 600s) |

#### ALG-013: 单任务分发流程

```
async function dispatch_task(task):
    machine = _get_machine(task)
    if machine is None:
        return TaskResult(exit_code=1, stderr="未找到机器")
    
    start_time = time.time()
    log.info("分发到 %s", machine.machine_id)
    
    try:
        # 1. 构建 aider 指令
        instruction = _build_instruction(task)
        msg_remote_path = "/tmp/aider_msg_{task_id}"
        
        # 2. SCP 上传指令文件
        await _scp_content(machine, instruction, msg_remote_path)
        
        # 3. 构建并执行 SSH 脚本
        ssh_script = _build_ssh_script(task, machine, msg_remote_path)
        result = await _ssh_exec(machine, ssh_script, timeout)
        
        # 4. 解析结果
        result.task_id = task.task_id
        result.duration_sec = time.time() - start_time
        
        if result.success:
            result.files_changed = _parse_changed_files(stdout, target_dir)
        
        return result
        
    except asyncio.TimeoutError:
        return TaskResult(exit_code=124, stderr="任务超时")
    except Exception as e:
        return TaskResult(exit_code=1, stderr=str(e))
```

### 2.3 `dispatch_batch`

| 项目 | 内容 |
|------|------|
| **签名** | `async dispatch_batch(self, tasks: List[CodingTask]) → List[TaskResult]` |
| **职责** | 并行分发一批任务 |
| **算法** | `asyncio.gather(*[dispatch_task(t) for t in tasks])` |
| **并行度** | 由 tasks 数量决定 (受 TaskEngine.max_concurrent 约束) |

### 2.4 `_build_instruction`

| 项目 | 内容 |
|------|------|
| **签名** | `_build_instruction(self, task: CodingTask) → str` |
| **职责** | 将 CodingTask 转换为 aider 可理解的 Markdown 指令 |
| **输出格式** | |

```markdown
# 编码任务 {task_id}

## 目标
{description}

## 验收标准
- {acceptance[0]}
- {acceptance[1]}

## 约束
1. 严格遵循 contracts/ 下的接口契约
2. 包含必要的依赖声明
3. 代码可直接运行
4. 只生成 {target_dir} 目录下的文件
5. 包含完整的错误处理和 docstring
6. 在 tests/ 目录下生成对应的 pytest 测试文件

## ⚠️ 修复指令 (第 N 次重试)   ← 仅重试时
{fix_instruction}
```

### 2.5 `_build_ssh_script` ★

| 项目 | 内容 |
|------|------|
| **签名** | `_build_ssh_script(self, task, machine, msg_remote_path) → str` |
| **职责** | 构建远程执行的完整 shell 脚本 |
| **算法** | ALG-014 |

#### ALG-014: SSH 脚本构建

```bash
# 1. 环境准备
{machine.aider_prefix}              # 如 conda activate, nvm use 等
export OPENAI_API_BASE='{api_base}'
export OPENAI_API_KEY='{api_key}'
cd {machine.work_dir}

# 2. Git 工作区清理
git rebase --abort 2>/dev/null || true
git merge --abort 2>/dev/null || true
git checkout -- . 2>/dev/null || true
git clean -fd 2>/dev/null || true
git fetch origin {branch}
git reset --hard origin/{branch}

# 3. 执行 aider
mkdir -p {target_dir}
AIDER_MSG=$(cat {msg_remote_path})
aider --model '{model}' \
      --yes-always --no-auto-commits \
      {contract_reads} \
      --message "$AIDER_MSG"
AIDER_EXIT=$?

# 4. 智能退出码修正
FILE_COUNT=$(find {target_dir} -type f -not -name '.gitkeep' | wc -l)
if AIDER_EXIT != 0 && FILE_COUNT > 0: AIDER_EXIT=0   # 有文件算成功
if AIDER_EXIT == 0 && FILE_COUNT == 0: AIDER_EXIT=1   # 无文件算失败

# 5. Git 提交 + 3 次重试推送
if AIDER_EXIT == 0:
    git add -A {target_dir} tests/
    git commit -m '[{task_id}] auto: {description}'
    
    for RETRY in 1 2 3:
        git pull --rebase && git push && break
        git rebase --abort
        git pull --no-rebase && git push && break
        git merge --abort
        sleep 2

# 6. 清理临时文件
rm -f {msg_remote_path}
exit $AIDER_EXIT
```

**关键设计决策**:
- **Git push 3 次重试**: 先 rebase 推，失败则 no-rebase 推，避免并发冲突
- **智能退出码**: aider 返回非零但有文件产出 → 视为成功
- **contract_reads**: 自动扫描 `contracts/*.yaml` + task_card 加入 `--read` 参数

### 2.6 `_scp_content`

| 项目 | 内容 |
|------|------|
| **签名** | `async _scp_content(self, machine, content, remote_path) → None` |
| **职责** | 将指令内容上传到远程机器 |
| **算法** | 写入临时文件 → 本地则 `shutil.copy2`，远程则 `scp -q -o ConnectTimeout=10 -P port` |
| **异常** | SCP 返回非零 → `RuntimeError` |
| **资源** | finally 块确保删除本地临时文件 |

### 2.7 `_ssh_exec`

| 项目 | 内容 |
|------|------|
| **签名** | `async _ssh_exec(self, machine, script, timeout=600) → TaskResult` |
| **职责** | 通过 SSH 在远程执行 shell 脚本 |
| **本地检测** | `_is_local(machine)` → 直接执行 `bash -s` |
| **SSH 参数** | `-T -p {port} -o ConnectTimeout=10 -o ServerAliveInterval=30` |
| **输入** | script 通过 stdin pipe 传入 |
| **超时** | `asyncio.wait_for(proc.communicate(), timeout)` |

### 2.8 `_collect_local_ips` (静态方法)

| 项目 | 内容 |
|------|------|
| **职责** | 收集本机所有 IP 地址 |
| **算法** | 初始集合 `{127.0.0.1, localhost, ::1}` + `socket.gethostname()` + `getaddrinfo()` |

### 2.9 `_parse_changed_files` (静态方法)

| 项目 | 内容 |
|------|------|
| **职责** | 从 aider stdout 中解析变更文件列表 |
| **算法** | 匹配 `Wrote {file}` 和 `create mode ... {file}` 行 |
| **回退** | 无匹配则返回 `[target_dir]` |

---

## §3 序列图

### SEQ-007: 远程 SSH 分发流程

```
Orchestrator    Dispatcher       远程机器          Git Remote
    │               │               │                │
    │ dispatch_task  │               │                │
    │──────────────>│               │                │
    │               │ _build_       │                │
    │               │  instruction  │                │
    │               │───┐           │                │
    │               │<──┘           │                │
    │               │               │                │
    │               │ SCP upload    │                │
    │               │──────────────>│                │
    │               │    ok         │                │
    │               │<──────────────│                │
    │               │               │                │
    │               │ SSH exec      │                │
    │               │──────────────>│                │
    │               │               │ git reset      │
    │               │               │ --hard         │
    │               │               │───────────────>│
    │               │               │                │
    │               │               │ aider          │
    │               │               │ --model ...    │
    │               │               │ (coding)       │
    │               │               │                │
    │               │               │ git commit     │
    │               │               │──────┐         │
    │               │               │<─────┘         │
    │               │               │                │
    │               │               │ git push       │
    │               │               │ (3 retries)    │
    │               │               │───────────────>│
    │               │               │    ok          │
    │               │               │<───────────────│
    │               │               │                │
    │               │  TaskResult   │                │
    │               │<──────────────│                │
    │  TaskResult   │               │                │
    │<──────────────│               │                │
```

---

## §4 配置参数

| 配置路径 | 类型 | 说明 |
|----------|------|------|
| `task.single_task_timeout` | int | SSH 执行超时 (秒) |
| `llm.openai_api_base` | str | LLM API 地址 |
| `llm.openai_api_key` | str | LLM API Key |
| `llm.model` | str | 默认模型 |
| `project.branch` | str | Git 分支名 |
| `paths.task_card` | str | 任务卡路径 (加入 --read) |

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §7 提取并扩充，形成独立模块详述 |
