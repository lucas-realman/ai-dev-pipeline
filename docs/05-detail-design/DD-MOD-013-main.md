# DD-MOD-013 — Main / Orchestrator 模块详细设计

> **文档编号**: DD-MOD-013  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/main.py` (365 行)  
> **上游文档**: [OD-MOD-013](../04-outline-design/OD-MOD-013-main.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────────────┐
│                        Orchestrator                              │
├──────────────────────────────────────────────────────────────────┤
│ + config      : Config                                           │
│ + engine      : TaskEngine                                       │
│ + dispatcher  : Dispatcher                                       │
│ + reviewer    : AutoReviewer                                     │
│ + test_runner : TestRunner                                       │
│ + reporter    : Reporter                                         │
│ + git         : GitOps                                           │
│ + registry    : Optional[MachineRegistry]                        │
├──────────────────────────────────────────────────────────────────┤
│ + __init__(config_path=None)                                     │
│ + run_sprint(sprint_id=None) → None              «async»         │
│ + run_continuous() → None                        «async»         │
│ - _discover_tasks(sprint_id) → List[CodingTask]  «async»         │
│ - _main_loop() → None                           «async»         │
│ - _dispatch_batch(batch) → List[TaskResult]      «async»         │
│ - _wait_for_coding(tasks) → None                 «async»         │
│ - _process_task_result(task, result) → None      «async»         │
│ - _judge_task(task, review, test_result) → bool                  │
├──────────────────────────────────────────────────────────────────┤
│ «CLI» main() → None  (argparse 入口)                             │
└──────────────────────────────────────────────────────────────────┘
           │
           ├── Config (MOD-012)
           ├── TaskEngine (MOD-004)
           ├── MachineRegistry (MOD-003)
           ├── Dispatcher (MOD-007)
           ├── AutoReviewer (MOD-008)
           ├── TestRunner (MOD-009)
           ├── Reporter (MOD-010)
           └── GitOps (MOD-011)
```

**Orchestrator 是顶层 Facade**，组合所有子模块，不包含业务逻辑细节。

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self, config_path: Optional[str] = None)` |
| **职责** | 初始化所有子模块，注册信号处理 |
| **顺序** | Config → MachineRegistry → TaskEngine → Dispatcher → AutoReviewer → TestRunner → Reporter → GitOps → ★信号注册 |

### 2.1a 信号处理 ★v1.1

> 对应 ACTION-ITEM v2.1 A-112: SIGTERM/SIGINT 优雅停机

| 项目 | 内容 |
|------|------|
| **信号** | `SIGTERM`, `SIGINT` (Ctrl+C) |
| **行为** | 设置 `_shutdown_flag = True` → 等待当前 batch 完成 → 保存快照 → 发送通知 → exit(0) |
| **算法** | ALG-030a |

#### ALG-030a: 优雅停机流程

```
# __init__ 中注册:
_shutdown_flag = False

def _signal_handler(signum, frame):
    nonlocal _shutdown_flag
    if _shutdown_flag:
        # 第二次信号: 强制退出
        log.warning("收到第二次终止信号, 强制退出")
        sys.exit(1)
    
    _shutdown_flag = True
    log.info("收到 %s, 等待当前 batch 完成后优雅退出...", 
             signal.Signals(signum).name)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
```

**_main_loop 集成点** (ALG-030 补充):
```
# ALG-030 主循环中每轮检查:
while round_num < MAX_ROUNDS:
    if _shutdown_flag:
        log.info("优雅停机: 保存快照并退出")
        engine._save_snapshot()          # 持久化当前状态
        reporter.notify_shutdown()       # 通知停机
        break
    
    batch = engine.next_batch()
    ... # 原有逻辑
```

### 2.2 `run_sprint` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async run_sprint(self, sprint_id: Optional[str] = None) → None` |
| **职责** | 执行一个完整的 Sprint 周期 |
| **算法** | ALG-028 |

#### ALG-028: Sprint 执行主流程

```
async function run_sprint(sprint_id=None):
    sprint_id = sprint_id or config.sprint_id
    
    # 1. Git 同步
    await git.pull()
    
    # 2. 任务发现
    tasks = await _discover_tasks(sprint_id)
    if not tasks:
        log.warning("无任务可执行")
        return
    
    # 3. 入队
    for task in tasks:
        engine.enqueue(task)
    
    # 4. 通知 Sprint 开始
    await reporter.notify_sprint_start(sprint_id, tasks)
    
    # 5. 主循环
    await _main_loop()
    
    # 6. 生成报告
    results = engine.get_all_tasks()
    report_path = reporter.generate_report(sprint_id, results)
    
    # 7. Git 提交
    await git.commit(f"[{sprint_id}] auto: sprint complete")
    await git.push()
    await git.tag_sprint(sprint_id)
    
    # 8. 通知 Sprint 结束
    summary = _build_summary(results)
    await reporter.notify_sprint_done(sprint_id, summary)
    
    # 9. 同步节点
    machines = registry.get_all() if registry else []
    await git.sync_nodes(machines)
```

### 2.3 `_discover_tasks` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async _discover_tasks(self, sprint_id: str) → List[CodingTask]` |
| **职责** | 双路径任务发现：v3 DocAnalyzer → v2 DocParser fallback |
| **算法** | ALG-029 |

#### ALG-029: 双路径任务发现

```
async function _discover_tasks(sprint_id):
    # 路径 1: v3 LLM 文档分析
    try:
        analyzer = DocAnalyzer(config)
        tasks = await analyzer.analyze_and_decompose()
        if tasks:
            log.info("v3 任务发现: %d 个任务", len(tasks))
            return tasks
    except Exception as e:
        log.warning("v3 任务发现失败: %s, 回退到 v2", e)
    
    # 路径 2: v2 Markdown 解析
    parser = DocParser(config)
    tasks = parser.parse_task_card(sprint_id)
    log.info("v2 任务发现: %d 个任务", len(tasks))
    return tasks
```

### 2.4 `_main_loop` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async _main_loop(self) → None` |
| **算法** | ALG-030 |
| **常量** | `MAX_ROUNDS = 20` |

#### ALG-030: 主调度循环 (含 stale-busy 检测 ★v1.1)

```
async function _main_loop():
    round_num = 0
    
    while round_num < MAX_ROUNDS:
        round_num += 1
        
        # ★v1.1: 优雅停机检查 (A-112)
        if _shutdown_flag:
            log.info("优雅停机: 保存快照并退出")
            engine._save_snapshot()
            await reporter.notify_shutdown()
            break
        
        # ★v1.1: Stale-busy 检测 (A-116)
        _detect_stale_busy_machines()
        
        # 1. 获取下一批可执行任务
        batch = engine.next_batch()
        if not batch:
            # 检查是否全部完成
            if engine.all_done():
                log.info("所有任务已完成")
                break
            # 可能有任务在等待重试
            await asyncio.sleep(5)
            continue
        
        log.info("第 %d 轮, 分发 %d 个任务", round_num, len(batch))
        
        # 2. 分发
        results = await _dispatch_batch(batch)
        
        # 3. 处理结果
        for task, result in zip(batch, results):
            await _process_task_result(task, result)
        
        # 4. 轮间等待
        await asyncio.sleep(2)
    
    if round_num >= MAX_ROUNDS:
        log.error("达到最大轮次限制 %d", MAX_ROUNDS)
```

#### ALG-030b: Stale-busy 检测 ★v1.1

> 对应 ACTION-ITEM v2.1 A-116: 检测 BUSY 状态超时的机器

```
function _detect_stale_busy_machines():
    """
    检测已处于 BUSY 状态超过 2×single_task_timeout 的机器。
    这类机器可能因 SSH 断开、进程崩溃等原因未正常释放。
    """
    stale_threshold = config.single_task_timeout * 2    # 默认 1200s
    now = time.time()
    
    for machine in registry.get_busy_machines():
        if machine.busy_since and (now - machine.busy_since) > stale_threshold:
            log.warning(
                "模块 %s BUSY 超时 (%ds), 强制置为 IDLE",
                machine.machine_id,
                int(now - machine.busy_since)
            )
            registry.set_idle(machine.machine_id)
            
            # 该机器上的任务: 设置为 RETRY 或 ESCALATED
            if machine.current_task_id:
                task, sm = engine._get(machine.current_task_id)
                if not sm.is_terminal:
                    sm.handle_failure()
                    if sm.is_retryable:
                        sm.requeue()
```

**决策参数**:

| 参数 | 值 | 说明 |
|------|-----|------|
| `stale_threshold` | `2 × single_task_timeout` | 默认 2×600=1200s (20min) |
| 检测频率 | 每轮主循环检查一次 | 约每 7s (2s wait + dispatch 时间) |
```

### 2.5 `_dispatch_batch`

| 项目 | 内容 |
|------|------|
| **签名** | `async _dispatch_batch(self, batch: List[CodingTask]) → List[TaskResult]` |
| **职责** | 为每个任务分配机器并分发 |
| **流程** | |

```
1. 为每任务标记 DISPATCHED 状态
2. 通知 reporter.notify_task_dispatched
3. results = await dispatcher.dispatch_batch(batch)
4. 返回 results
```

### 2.6 `_process_task_result` ★

| 项目 | 内容 |
|------|------|
| **签名** | `async _process_task_result(self, task, result) → None` |
| **职责** | 对编码结果执行 Review → Test → Judge |
| **算法** | ALG-031 |

#### ALG-031: 任务结果处理流程

```
async function _process_task_result(task, result):
    if not result.success:
        # 编码失败: 直接标记失败
        engine.handle_coding_done(task.task_id, result)
        await reporter.notify_task_result(task, result)
        return
    
    # 编码成功 → L1/L2/L3 审查
    engine.handle_coding_done(task.task_id, result)
    review = await reviewer.review_task(task, result)
    
    if not review.passed:
        # 审查失败 → 重试
        engine.handle_review_done(task.task_id, review)
        await reporter.notify_task_result(task, result)
        return
    
    engine.handle_review_done(task.task_id, review)
    
    # 审查通过 → 测试
    test_result = await test_runner.run_tests(task, result)
    
    if not test_result.passed:
        # 测试失败 → 重试
        engine.handle_test_done(task.task_id, test_result)
        await reporter.notify_task_result(task, result)
        return
    
    # 全部通过
    engine.handle_test_done(task.task_id, test_result)
    await reporter.notify_task_result(task, result)
```

### 2.7 `run_continuous`

| 项目 | 内容 |
|------|------|
| **签名** | `async run_continuous(self) → None` |
| **职责** | 持续监听任务卡变化并执行 Sprint |
| **策略** | 轮询间隔 60s，检测文件 mtime 变化 |

---

## §3 序列图

### SEQ-012: 完整 Sprint 生命周期

```
CLI          Orchestrator   DocAnalyzer  TaskEngine  Dispatcher  Reviewer  TestRunner  Reporter  GitOps
 │               │              │            │           │          │          │          │         │
 │ run_sprint    │              │            │           │          │          │          │         │
 │──────────────>│              │            │           │          │          │          │         │
 │               │ pull()       │            │           │          │          │          │         │
 │               │──────────────────────────────────────────────────────────────────────────────── >│
 │               │              │            │           │          │          │          │         │
 │               │ analyze      │            │           │          │          │          │         │
 │               │─────────────>│            │           │          │          │          │         │
 │               │  tasks       │            │           │          │          │          │         │
 │               │<─────────────│            │           │          │          │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ enqueue(tasks)            │           │          │          │          │         │
 │               │──────────────────────────>│           │          │          │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ notify start │            │           │          │          │          │         │
 │               │────────────────────────────────────────────────────────────>│          │         │
 │               │              │            │           │          │          │          │         │
 │               │             ═══ MAIN LOOP (MAX 20 ROUNDS) ═══              │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ next_batch   │            │           │          │          │          │         │
 │               │──────────────────────────>│           │          │          │          │         │
 │               │  [task1, task2]           │           │          │          │          │         │
 │               │<─────────────────────────│           │          │          │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ dispatch_batch            │           │          │          │          │         │
 │               │──────────────────────────────────────>│          │          │          │         │
 │               │              │            │  results  │          │          │          │         │
 │               │<──────────────────────────────────────│          │          │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ review       │            │           │          │          │          │         │
 │               │──────────────────────────────────────────────── >│          │          │         │
 │               │  ReviewResult│            │           │          │          │          │         │
 │               │<─────────────────────────────────────────────── │          │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ run_tests    │            │           │          │          │          │         │
 │               │──────────────────────────────────────────────────────────>  │          │         │
 │               │  TestResult  │            │           │          │          │          │         │
 │               │<──────────────────────────────────────────────────────────  │          │         │
 │               │              │            │           │          │          │          │         │
 │               │             ═══ END LOOP ═══                    │          │          │         │
 │               │              │            │           │          │          │          │         │
 │               │ report       │            │           │          │          │          │         │
 │               │────────────────────────────────────────────────────────────>│          │         │
 │               │              │            │           │          │          │          │         │
 │               │ commit+push+tag           │           │          │          │          │         │
 │               │──────────────────────────────────────────────────────────────────────────────── >│
 │               │              │            │           │          │          │          │         │
 │  done         │              │            │           │          │          │          │         │
 │<──────────────│              │            │           │          │          │          │         │
```

---

## §4 CLI 设计

### 4.1 argparse 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--config` / `-c` | str | None | 配置文件路径 |
| `--sprint` / `-s` | str | None | Sprint ID |
| `--mode` | str | `"sprint"` | 运行模式: `sprint` / `continuous` / `dry-run` |
| `--verbose` / `-v` | flag | False | 调试日志 |

### 4.2 运行模式

| 模式 | 入口 | 说明 |
|------|------|------|
| `sprint` | `run_sprint(sprint_id)` | 执行单次 Sprint |
| `continuous` | `run_continuous()` | 持续监听任务卡，循环执行 |
| `dry-run` | `_discover_tasks()` | 仅发现任务并打印，不执行 |

### 4.3 入口函数

```python
def main():
    args = parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    orch = Orchestrator(config_path=args.config)
    
    if args.mode == "sprint":
        asyncio.run(orch.run_sprint(args.sprint))
    elif args.mode == "continuous":
        asyncio.run(orch.run_continuous())
    elif args.mode == "dry-run":
        tasks = asyncio.run(orch._discover_tasks(args.sprint))
        for t in tasks:
            print(f"  {t.task_id}: {t.description}")
```

---

## §5 用户交互场景 ★v1.2

> 对应 ACTION-ITEM v2.0 A-015: 描述各交互入口的用户行为期望

### 场景 1: Sprint 模式 (标准用法)

```
用户执行: autodev sprint --sprint 1 --config ./config.yaml
```

| 阶段 | 用户可见输出 | 期望行为 |
|------|------------|---------|
| 启动 | `[INFO] 配置加载完成: config.yaml` | 校验配置 + 初始化所有模块 |
| 任务发现 | `[INFO] 分解出 8 个任务` | LLM 分解 + 自动构建任务队列 |
| Git 同步 | `[INFO] 同步 3 台机器...` | 远程机器 git pull 到最新 |
| 主循环 | `[INFO] 第 1 轮: 分发 5 个任务` | 持续打印轮次进度 |
| 任务结果 | `[INFO] T-001 PASSED (score=4.2)` | 每个任务有明确通过/失败 |
| 中断 | Ctrl+C → `[WARNING] 收到 SIGINT, 优雅停机...` | 等待当前任务完成后退出 |
| 完成 | `[INFO] Sprint 完成: 8/8 通过` | 输出汇总 + 生成报告 |

**退出码**:
| 码 | 含义 |
|-----|------|
| 0 | Sprint 全部通过 |
| 1 | 存在失败/升级任务 |
| 2 | 配置错误 / 无法启动 |

### 场景 2: Dry-run 模式 (任务预览)

```
用户执行: autodev dry-run --sprint 1
```

| 行为 | 说明 |
|------|------|
| 仅执行任务发现 | 调用 DocAnalyzer + DocParser |
| 打印任务列表 | 每行: `task_id: description` |
| 不执行分发/审查/测试 | 纯预览, 无副作用 |
| 退出码 0 | 即使没有任务也返回 0 |

### 场景 3: Continuous 模式 (持续监听)

```
用户执行: autodev continuous
```

| 行为 | 说明 |
|------|------|
| 循环检测新 Sprint | 每 60s 检查一次新任务 |
| 自动执行 | 发现任务后与 Sprint 模式相同 |
| 后台运行 | 适合 systemd / docker 部署 |
| 停机 | SIGTERM → 完成当前 Sprint 后退出 |

### 场景 4: 配置错误

```
用户执行: autodev sprint (config.yaml 缺少必填项)
```

| 行为 | 说明 |
|------|------|
| 启动即失败 | Schema 校验 (ALG-025a) 检测到错误 |
| 清晰报错 | `ConfigSchemaError: 配置校验失败 (3 项): [llm.openai_api_key] LLM API Key 未配置...` |
| 退出码 2 | 配置层面的失败 |

### 场景 5: LLM 不可用

| 行为 | 说明 |
|------|------|
| 3× 重试后降级 | DocAnalyzer → fallback 到 DocParser (v2 格式) |
| AutoReviewer L2/L3 降级 | L2 跳过, L3 给 3.5 分边界通过 |
| 通知钉钉 | 告警 LLM 连接失败 |
| 不中断流水线 | 降级通过但标记, 人工后续关注 |

---

## §6 常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_ROUNDS` | 20 | 主循环最大轮次 |
| `POLL_INTERVAL` | 5 | 空闲轮次等待秒数 |
| `CONTINUOUS_INTERVAL` | 60 | continuous 模式轮询间隔 |

---

## §7 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §13 提取并扩充，含完整 Sprint 生命周期 |
| v1.1 | 2026-03-07 | ALG-030a SIGTERM/SIGINT 信号处理; ALG-030b Stale-busy 检测; ALG-030 集成优雅停机 |
| v1.2 | 2026-03-07 | §5a 用户交互场景: 5 种典型使用场景与期望行为 (A-015) |
