# DD-MOD-007 — Dispatcher 模块详细设计

> **文档编号**: DD-MOD-007  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/dispatcher.py` (325 行)  
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

#### ALG-013: 单任务分发流程 (含 SSH 预检 ★v1.1)

```
async function dispatch_task(task):
    machine = _get_machine(task)
    if machine is None:
        return TaskResult(exit_code=1, stderr="未找到机器")
    
    # ★v1.1 A-113: SSH 连接预检
    if not _is_local(machine):
        ok = await _ssh_pre_check(machine)
        if not ok:
            registry.set_offline(machine.machine_id)
            # 尝试换一台机器
            machine = _get_machine(task, exclude=[machine.machine_id])
            if machine is None:
                return TaskResult(exit_code=1, stderr="无可用机器")
    
    # ★v1.2 A-121: aider 版本锁定 — 分发前检测远程 aider 版本
    expected_ver = config.aider_version   # 如 "0.82.1", 空则跳过
    if expected_ver and not _is_local(machine):
        ok, actual_ver = await _check_aider_version(machine, expected_ver)
        if not ok:
            log.warning("机器 %s aider 版本不匹配: 期望 %s, 实际 %s",
                        machine.machine_id, expected_ver, actual_ver)
            # 非阻塞: 仅警告, 继续分发 (运维可通过配置强制失败)
    
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

#### ALG-014: SSH 脚本构建 (含退出码边界处理 ★v1.1)

```bash
# 1. 环境准备
{machine.aider_prefix}              # 如 conda activate, nvm use 等
# ★v1.1 A-114: API Key 通过 SSH env 传递 (SendEnv)
# 客户端 ssh_config 配置: SendEnv OPENAI_API_KEY OPENAI_API_BASE
# 服务端 sshd_config 配置: AcceptEnv OPENAI_*
# 回退方案: 若 SSH env 传递不可用，仍在脚本中 export
export OPENAI_API_BASE="${OPENAI_API_BASE:-'{api_base}'}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-'{api_key}'}"
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

# 4. 智能退出码修正 (含边界处理 ★v1.1 A-009)
FILE_COUNT=$(find {target_dir} -type f -not -name '.gitkeep' | wc -l)

# 退出码边界规则:
# - aider exit > 255   : 取模 (AIDER_EXIT & 0xFF) — POSIX shell 自动处理
# - aider exit < 0     : 取补码 (256 + AIDER_EXIT)     — Python 返回值
# - aider exit = None   : 进程被信号杀死 (SIGKILL/SIGSEGV)，
#                         对应 exit_code = -signal_num，视为失败
# - aider exit = 124    : 超时 (timeout 命令约定)
# - aider exit = 126/127: 命令不可执行/未找到 → 失败

if AIDER_EXIT != 0 && FILE_COUNT > 0: AIDER_EXIT=0   # 有文件算成功
if AIDER_EXIT == 0 && FILE_COUNT == 0: AIDER_EXIT=1   # 无文件算失败

# 5. Git 提交 + 3 次重试推送 (含推送策略增强 ★v1.1 A-117)
PUSH_COUNT=0
if AIDER_EXIT == 0:
    # ★v1.1: 每机 branch 支持 (per-machine branch push)
    PUSH_BRANCH="{branch}"             # 默认: 主分支
    # 可选: PUSH_BRANCH="auto/{machine_id}/{task_id}"  # per-machine 分支
    
    git add -A {target_dir} tests/
    git commit -m '[{task_id}] auto: {description}'
    
    for RETRY in 1 2 3:
        git pull --rebase origin $PUSH_BRANCH && git push origin HEAD:$PUSH_BRANCH && { PUSH_COUNT=$((PUSH_COUNT+1)); break; }
        git rebase --abort 2>/dev/null || true
        git pull --no-rebase origin $PUSH_BRANCH && git push origin HEAD:$PUSH_BRANCH && { PUSH_COUNT=$((PUSH_COUNT+1)); break; }
        git merge --abort 2>/dev/null || true
        sleep 2
    done
    
    # ★v1.1: 推送计数 (Orchestrator 侧累加用于告警)
    echo "__PUSH_COUNT__=$PUSH_COUNT"

# 6. 清理临时文件
rm -f {msg_remote_path}
exit $AIDER_EXIT
```

**关键设计决策**:
- **Git push 3 次重试**: 先 rebase 推，失败则 no-rebase 推，避免并发冲突
- **智能退出码**: aider 返回非零但有文件产出 → 视为成功
- **contract_reads**: 自动扫描 `contracts/*.yaml` + task_card 加入 `--read` 参数
- **★v1.1 A-117 推送策略增强**:
  - **推送计数告警**: Orchestrator 解析 stdout 中的 `__PUSH_COUNT__`，单 Sprint 累计超过阈值 (default: 50) 时触发 WARNING，提示可能存在分支冲突风险
  - **Per-machine 分支**: 当 `config.per_machine_branch=true` 时，每台机器推送到 `auto/{machine_id}/{task_id}` 分支，由 Orchestrator 在 Sprint 结束后统一 merge 回主分支
  - **退出码边界** (★v1.1 A-009): 文档化 >255 取模、负数取补码、None 为信号终止、124 为超时

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

### 2.8 `_ssh_pre_check` ★v1.1

> 对应 ACTION-ITEM v2.1 A-113: SSH 连接预检

| 项目 | 内容 |
|------|------|
| **签名** | `async _ssh_pre_check(self, machine: MachineInfo) → bool` |
| **职责** | 分发前验证目标机器 SSH 连通性，快速失败 |
| **超时** | 5秒 (ConnectTimeout=5) |
| **算法** | ALG-013a |

#### ALG-013a: SSH 连接预检

```
async function _ssh_pre_check(machine):
    """
    轻量级 SSH 连通性检查。
    成功: 返回 True
    失败: 记录日志 + 返回 False (调用方负责置为 OFFLINE)
    """
    cmd = [
        'ssh', '-T',
        '-o', 'ConnectTimeout=5',
        '-o', 'BatchMode=yes',         # 禁止交互式密码提示
        '-p', str(machine.port),
        f'{machine.user}@{machine.host}',
        'echo ok'
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=10   # 整体超时 10s (> ConnectTimeout)
        )
        
        if proc.returncode == 0 and 'ok' in stdout.decode():
            return True
        
        log.warning("机器 %s SSH 预检失败: exit=%d, %s",
                    machine.machine_id, proc.returncode, stderr.decode())
        return False
        
    except asyncio.TimeoutError:
        log.warning("机器 %s SSH 预检超时 (10s)", machine.machine_id)
        return False
    except Exception as e:
        log.warning("机器 %s SSH 预检异常: %s", machine.machine_id, e)
        return False
```

**设计决策**:
- `BatchMode=yes`: 禁止密码提示，避免阻塞
- `ConnectTimeout=5`: 快速失败，不拖慢主流程
- 失败后 `registry.set_offline(machine_id)` 由调用方在 ALG-013 中完成
- 不在此处重试 — 重试由任务重新调度实现

### 2.9 `_check_aider_version` ★v1.2

> 对应 ACTION-ITEM v2.1 A-121: 防止 aider 版本漂移导致调用行为不一致

| 项目 | 内容 |
|------|------|
| **签名** | `async _check_aider_version(self, machine: MachineInfo, expected: str) → Tuple[bool, str]` |
| **职责** | 远程执行 `aider --version`，与期望版本比较 |
| **超时** | 10s |

#### ALG-013b: aider 版本检查

```
async function _check_aider_version(machine, expected):
    """
    通过 SSH 在远程机器上执行 aider --version，比较版本号。
    返回 (match: bool, actual_version: str)
    """
    cmd = f"{machine.aider_prefix} && aider --version 2>/dev/null || echo unknown"
    
    try:
        proc = await _ssh_exec_simple(machine, cmd, timeout=10)
        actual = proc.stdout.strip()   # 如 "aider 0.82.1"
        # 提取版本号: 移除前缀 "aider "
        ver_str = actual.replace("aider ", "").strip()
        
        if ver_str == expected:
            return (True, ver_str)
        return (False, ver_str)
    except Exception:
        return (False, "unknown")
```

**设计决策**:
- **默认警告不阻塞**: 版本不匹配仅记录 WARNING，不中断分发，避免因小版本差异阻塞整条流水线
- **可配置强制模式**: 未来可增加 `config.aider_version_strict=true` 使不匹配时返回失败
- **与 SSH 预检复用**: 版本检查在 SSH 预检 (ALG-013a) 之后执行，此时已确认连通性

### 2.10 `_collect_local_ips` (静态方法)

| 项目 | 内容 |
|------|------|
| **职责** | 收集本机所有 IP 地址 |
| **算法** | 初始集合 `{127.0.0.1, localhost, ::1}` + `socket.gethostname()` + `getaddrinfo()` |

### 2.11 `_parse_changed_files` (静态方法)

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

## §3a AI 代码执行沙箱设计 ★v1.2

> 对应 ACTION-ITEM: v1.0 A-019 — "AI 代码执行沙箱方案 (最小: cwd + 用户隔离)"

### 3a.1 威胁模型

aider 作为 AI 代码生成器，可能产出如下风险指令:

| 威胁 | 风险等级 | 示例 |
|------|---------|------|
| 目录逃逸 | 🔴 高 | `../../etc/passwd`、`cd /` |
| 系统命令注入 | 🔴 高 | `os.system("rm -rf /")` |
| 网络外联 | 🟡 中 | `requests.get("http://evil.com")` |
| 环境变量窃取 | 🟡 中 | `os.environ["OPENAI_API_KEY"]` |
| 大量文件生成 | 🟢 低 | 创建 1000 个文件耗尽 inode |

### 3a.2 最小沙箱方案: cwd + 用户隔离

本系统采用 **"最小沙箱"** 策略，不引入 Docker/gVisor 等重型方案，
通过操作系统级别的 cwd 锁定 + 用户隔离实现基本安全边界：

#### 层次 1: 工作目录锁定 (cwd 隔离)

```bash
# ALG-014 构建的 SSH 脚本中已包含:
cd {work_dir}                    # 进入项目目录
# aider --yes-always 只操作当前目录下的文件

# ★v1.2 新增: 目录边界校验
# 在 _build_ssh_script 末尾追加:
GENERATED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
for f in $GENERATED_FILES; do
  case "$f" in
    ../*|/*) echo "[SANDBOX] 目录逃逸: $f" >&2; exit 99 ;;
  esac
done
```

- aider `--yes-always --auto-commits` 只在 `{work_dir}` 下操作
- 生成后通过 `git diff --name-only` 检查文件路径
- 任何逃逸 (`../` 或绝对路径) 返回 `exit 99`
- Dispatcher 接收到 `exit_code=99` 时标记任务为 `ESCALATED`

#### 层次 2: 用户隔离

```yaml
# config.yaml 中 Worker 机器配置示例:
machines:
  - host: 192.168.1.101
    user: aider-worker          # ← 专用低权限用户
    work_dir: /home/aider-worker/projects/myapp
```

| 隔离维度 | 措施 | 说明 |
|---------|------|------|
| **用户** | 专用 `aider-worker` 账号 | 不使用 `root` 或开发者个人账号 |
| **权限** | `chmod 700 /home/aider-worker` | 无法访问其他用户目录 |
| **sudo** | 不在 sudoers 中 | 无法提权 |
| **SSH** | 仅 ed25519 密钥认证 | 禁用密码登录 |
| **网络** | iptables 限制出站 | 仅允许 Git Remote + LLM API 端口 |

#### 层次 3: 运行时限制

```bash
# SSH 脚本中追加 ulimit 限制:
ulimit -f 102400        # 文件大小上限 100MB
ulimit -n 256           # 打开文件描述符上限
ulimit -u 64            # 子进程数上限
ulimit -t 600           # CPU 时间上限 (秒)
```

### 3a.3 退出码语义扩展

| exit_code | 含义 | 处理 |
|-----------|------|------|
| 0 | 正常完成 | CODING_DONE → REVIEW |
| 1 | aider 编码失败 | RETRY (最多 3 次) |
| 99 | **沙箱违规 (目录逃逸)** | **ESCALATED (不重试)** |
| 124 | 超时 (timeout) | RETRY |
| 137 / -9 | OOM killed | RETRY + 机器标记 WARNING |

### 3a.4 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Docker vs 用户隔离 | 用户隔离 | Worker 机器 ≤3 台、性能开销低、无 Docker 依赖 |
| 实时文件监控 vs 事后校验 | 事后校验 | inotify 监控引入复杂度，git diff 已足够 |
| 网络隔离级别 | iptables 白名单 | 仅允许 Git Remote + LLM API，运维可控 |
| exit_code 99 处理 | ESCALATED (不重试) | 沙箱违规视为安全事件，必须人工介入 |

### 3a.5 演进路线

```
Phase 1 (当前): cwd 锁定 + 用户隔离 + ulimit
Phase 2 (后续): Docker 容器化 (需评估性能影响)
Phase 3 (远期): gVisor/Firecracker 微虚拟机
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
| v1.1 | 2026-03-07 | ALG-013a SSH 预检; ALG-014 API Key env 传递+退出码边界; A-117 推送策略增强 |
| v1.2 | 2026-03-07 | §2.9 新增 ALG-013b aider 版本检查; ALG-013 分发前插入版本比对 (A-121); §3a AI 代码执行沙箱设计 — cwd 锁定+用户隔离+ulimit (A-019) |
