# DD-MOD-013 — Main / Orchestrator 模块详细设计

> **文档编号**: DD-MOD-013  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/main.py` (366 行)  
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
| **职责** | 初始化所有子模块 |
| **顺序** | Config → MachineRegistry → TaskEngine → Dispatcher → AutoReviewer → TestRunner → Reporter → GitOps |

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
    results = engine.get_all_results()
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

#### ALG-030: 主调度循环

```
async function _main_loop():
    round_num = 0
    
    while round_num < MAX_ROUNDS:
        round_num += 1
        
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
        engine.handle_coding_failed(task, result.stderr)
        await reporter.notify_task_result(task, result)
        return
    
    # 编码成功 → L1/L2/L3 审查
    engine.handle_coding_done(task)
    review = await reviewer.review_task(task, result)
    
    if not review.passed:
        # 审查失败 → 重试
        engine.handle_review_failed(task, review.fix_instruction)
        await reporter.notify_task_result(task, result)
        return
    
    engine.handle_review_passed(task)
    
    # 审查通过 → 测试
    test_result = await test_runner.run_tests(task, result)
    
    if not test_result.passed:
        # 测试失败 → 重试
        engine.handle_test_failed(task, test_result.summary)
        await reporter.notify_task_result(task, result)
        return
    
    # 全部通过
    engine.handle_test_passed(task)
    engine.mark_done(task)
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

## §5 常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_ROUNDS` | 20 | 主循环最大轮次 |
| `POLL_INTERVAL` | 5 | 空闲轮次等待秒数 |
| `CONTINUOUS_INTERVAL` | 60 | continuous 模式轮询间隔 |

---

## §6 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §13 提取并扩充，含完整 Sprint 生命周期 |
