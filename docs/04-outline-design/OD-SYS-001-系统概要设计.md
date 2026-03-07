# OD-SYS-001 — 系统概要设计

> **文档编号**: OD-SYS-001  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **上游文档**: [ARCH-001](../03-architecture/ARCH-001-架构总览.md) · [ARCH-002](../03-architecture/ARCH-002-部署架构.md)  
> **下游文档**: [OD-MOD-001~013](.) · [OD-002](OD-002-数据模型设计.md) · [OD-003](OD-003-接口契约设计.md)  
> **关联文档**: [OD-001 索引](OD-001-模块概要设计.md)

---

## §1 系统组件总览

> 映射: ARCH-001~010 → MOD-001~013

本系统由 10 个架构组件组成，映射到 13 个实现模块（每模块独立 `.py` 文件，<300 行）。

| ARCH ID | 架构组件 | 上游 SYS | 实现模块 | 行数 |
|---------|---------|---------|---------|------|
| ARCH-001 | 文档解析组件 | SYS-001 | MOD-001 (doc_analyzer), MOD-002 (doc_parser) | 291+193 |
| ARCH-002 | 机器池组件 | SYS-002 | MOD-003 (machine_registry) | 186 |
| ARCH-003 | 任务调度组件 | SYS-003 | MOD-004 (task_engine), MOD-006 (dispatcher) | 253+325 |
| ARCH-004 | 审查组件 | SYS-004 | MOD-007 (reviewer) | 262 |
| ARCH-005 | 测试组件 | SYS-005 | MOD-008 (test_runner) | 341 |
| ARCH-006 | 状态管理组件 | SYS-006 | MOD-009 (state_machine), MOD-005 (task_models) | 147+201 |
| ARCH-007 | 通知报告组件 | SYS-007 | MOD-010 (reporter) | 239 |
| ARCH-008 | Git 自动化组件 | SYS-008 | MOD-011 (git_ops) | 136 |
| ARCH-009 | 配置管理组件 | — | MOD-012 (config) | 234 |
| ARCH-010 | 主循环入口 | SYS-001~009 | MOD-013 (main) | 365 |

**合计**: 13 模块, 3,175 行 Python

---

## §2 系统分层架构

```
┌────────────────────────────────────────────────────────────┐
│  L0 接入层                                                  │
│  ┌──────────┐  ┌──────────┐                                │
│  │ MOD-001  │  │ MOD-002  │  文档解析 (v3 AI 分解 / v2 表格)│
│  │DocAnalyzer│  │DocParser │                                │
│  └──────────┘  └──────────┘                                │
├────────────────────────────────────────────────────────────┤
│  L1 调度层                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ MOD-004  │  │ MOD-003  │  │ MOD-009  │                  │
│  │TaskEngine│  │ Registry │  │StateMach │  任务队列+状态管理 │
│  └──────────┘  └──────────┘  └──────────┘                  │
├────────────────────────────────────────────────────────────┤
│  L2 执行层                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ MOD-006  │  │ MOD-007  │  │ MOD-008  │                  │
│  │Dispatcher│  │ Reviewer │  │TestRunner│  分发+审查+测试    │
│  └──────────┘  └──────────┘  └──────────┘                  │
├────────────────────────────────────────────────────────────┤
│  L3 基础设施层                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ MOD-005  │  │ MOD-010  │  │ MOD-011  │  │ MOD-012  │   │
│  │TaskModels│  │ Reporter │  │ GitOps   │  │ Config   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├────────────────────────────────────────────────────────────┤
│  入口层                                                     │
│  ┌──────────┐                                              │
│  │ MOD-013  │  Orchestrator + CLI (autodev 命令)            │
│  │  main    │                                              │
│  └──────────┘                                              │
└────────────────────────────────────────────────────────────┘
```

---

## §3 核心调用链

> 映射: ARCH-001~010 → IF-001~012 (详见 [OD-003](OD-003-接口契约设计.md))

```
main.Orchestrator.run_sprint()
│
├── 1. DocAnalyzer.analyze_and_decompose(sprint_id)       [IF-001, IF-002]
│       ├── load_doc_set() → Dict[str, str]
│       ├── _call_llm(prompt) → JSON
│       └── return List[CodingTask]
│
├── 2. TaskEngine.enqueue(tasks)                          [IF-003]
│       └── _topological_sort(tasks)
│
├── 3. [LOOP] TaskEngine.next_batch(registry)             [IF-004]
│       ├── MachineRegistry.get_idle_machines()
│       ├── MachineRegistry.match_machine(tags)            [IF-005]
│       └── return List[CodingTask] (assigned_machine 已填)
│
├── 4. Dispatcher.dispatch_batch(tasks)                   [IF-006, IF-007]
│       ├── [PARALLEL] dispatch_task(task)
│       │   ├── _build_instruction(task) → str
│       │   ├── _scp_content(machine, instruction)
│       │   ├── _ssh_exec(machine, aider_cmd) → stdout, exit_code
│       │   └── return TaskResult
│       └── return List[TaskResult]
│
├── 5. AutoReviewer.review(task, result) → ReviewResult    [IF-008]
│       ├── L1: _static_check(files) — py_compile + ruff
│       ├── L2: _contract_check(task, files) — LLM
│       └── L3: _design_check(task, files) — LLM
│
├── 6. TestRunner.run_tests(task) → TestResult             [IF-009]
│       ├── _find_tests_for_task(task)
│       ├── _exec(pytest_cmd)
│       └── _parse_json_report() / _parse_pytest_output()
│
├── 7. TaskStateMachine.transition(event)                  [IF-010]
│       ├── coding_done() / review_done() / test_done()
│       ├── judge() → PASSED / FAILED
│       └── handle_failure() → RETRY / ESCALATED
│
├── 8. Reporter.notify(...)                                [IF-011]
│       ├── _send_dingtalk_webhook(markdown)
│       └── _save_local_report(markdown)
│
└── 9. GitOps.tag_sprint(tag) + push()                     [IF-012]
```

---

## §4 接口签名速查表

| IF ID | 方法签名 | 输入 | 输出 | 调用方 |
|-------|---------|------|------|--------|
| IF-001 | `DocAnalyzer.load_doc_set()` | — | `Dict[str, str]` | main |
| IF-002 | `DocAnalyzer.analyze_and_decompose(sprint_id)` | sprint ID | `List[CodingTask]` | main |
| IF-003 | `TaskEngine.enqueue(tasks)` | 任务列表 | `None` | main |
| IF-004 | `TaskEngine.next_batch(registry)` | 机器池 | `List[CodingTask]` | main |
| IF-005 | `MachineRegistry.match_machine(tags, machines)` | 标签+候选 | `Optional[MachineInfo]` | task_engine |
| IF-006 | `Dispatcher.dispatch_task(task)` | 任务 | `TaskResult` | main |
| IF-007 | `Dispatcher.dispatch_batch(tasks)` | 批量任务 | `List[TaskResult]` | main |
| IF-008 | `AutoReviewer.review(task, result)` | 任务+结果 | `ReviewResult` | main |
| IF-009 | `TestRunner.run_tests(task)` | 任务 | `TestResult` | main |
| IF-010 | `TaskStateMachine.judge()` | — | `TaskStatus` | main |
| IF-011 | `Reporter.notify_sprint_start(sprint_id, tasks)` | Sprint+任务 | `None` | main |
| IF-012 | `GitOps.tag_sprint(tag)` | 标签名 | `bool` | main |

---

## §5 模块-需求映射表

### 5.1 FR → MOD 正向映射

| FR | 描述 | SYS | ARCH | MOD (主) | MOD (辅) | IF |
|----|------|-----|------|---------|---------|-----|
| FR-001 | 文档集加载 | SYS-001 | ARCH-001 | MOD-001 | MOD-002 | IF-001 |
| FR-002 | AI 自动拆解 | SYS-001 | ARCH-001 | MOD-001 | — | IF-002 |
| FR-003 | 结构化任务输出 | SYS-001 | ARCH-001 | MOD-001 | MOD-005 | IF-002 |
| FR-004 | 动态注册机器 | SYS-002 | ARCH-002 | MOD-003 | — | IF-005 |
| FR-005 | 标签匹配+负载均衡 | SYS-002 | ARCH-002 | MOD-003 | — | IF-005 |
| FR-006 | 任务入队+排序 | SYS-003 | ARCH-003 | MOD-004 | — | IF-003 |
| FR-007 | 依赖拓扑排序 | SYS-003 | ARCH-003 | MOD-004 | — | IF-004 |
| FR-008 | 动态分配机器 | SYS-003 | ARCH-003 | MOD-004 | MOD-006 | IF-004, IF-007 |
| FR-009 | L1 静态检查 | SYS-004 | ARCH-004 | MOD-007 | — | IF-008 |
| FR-010 | L2 契约对齐 | SYS-004 | ARCH-004 | MOD-007 | — | IF-008 |
| FR-011 | L3 设计符合度 | SYS-004 | ARCH-004 | MOD-007 | — | IF-008 |
| FR-012 | pytest 自动执行 | SYS-005 | ARCH-005 | MOD-008 | — | IF-009 |
| FR-013 | 验收标准检查 | SYS-005 | ARCH-005 | MOD-008 | — | IF-009 |
| FR-014 | 11 态状态转换 | SYS-006 | ARCH-006 | MOD-009 | MOD-005 | IF-010 |
| FR-015 | 重试+升级逻辑 | SYS-006 | ARCH-006 | MOD-009 | — | IF-010 |
| FR-016 | 钉钉 Webhook 通知 | SYS-007 | ARCH-007 | MOD-010 | — | IF-011 |
| FR-017 | Sprint 完成报告 | SYS-007 | ARCH-007 | MOD-010 | — | IF-011 |
| FR-018 | 每日摘要推送 | SYS-007 | ARCH-007 | MOD-010 | — | IF-011 |
| FR-019 | pull/push 自动化 | SYS-008 | ARCH-008 | MOD-011 | — | IF-012 |
| FR-020 | Sprint tag 管理 | SYS-008 | ARCH-008 | MOD-011 | — | IF-012 |
| FR-021 | 反馈驱动迭代 | SYS-009 | ARCH-007 | MOD-010 | MOD-009 | IF-010, IF-011 |
| FR-022 | AI Bug 分类 | SYS-009 | ARCH-001 | MOD-001 | — | IF-002 |
| FR-023 | 修复任务注入 | SYS-009 | ARCH-003 | MOD-004 | — | IF-003 |

### 5.2 MOD → FR 反向映射 (责任矩阵)

| MOD | 模块 | 主要 FR | 辅助 FR | 测试优先级 |
|-----|------|---------|---------|-----------|
| MOD-001 | doc_analyzer | FR-001, FR-002, FR-003 | FR-022 | P0 |
| MOD-002 | doc_parser | FR-001 | — | P2 (兼容) |
| MOD-003 | machine_registry | FR-004, FR-005 | — | P0 |
| MOD-004 | task_engine | FR-006, FR-007, FR-008 | FR-023 | P0 |
| MOD-005 | task_models | FR-003, FR-014 | 全部 | P0 |
| MOD-006 | dispatcher | FR-006, FR-008 | — | P0 |
| MOD-007 | reviewer | FR-009, FR-010, FR-011 | — | P0 |
| MOD-008 | test_runner | FR-012, FR-013 | — | P0 |
| MOD-009 | state_machine | FR-014, FR-015 | FR-021 | P0 |
| MOD-010 | reporter | FR-016, FR-017, FR-018 | FR-021 | P1 |
| MOD-011 | git_ops | FR-019, FR-020 | — | P1 |
| MOD-012 | config | — | 全部 | P0 |
| MOD-013 | main | — | 全部 (编排) | P0 |

---

## §6 模块依赖图

```
                    ┌──────────┐
                    │ MOD-013  │ (main / Orchestrator)
                    │   main   │
                    └────┬─────┘
           ┌────────┬────┼────┬────────┬────────┐
           ▼        ▼    ▼    ▼        ▼        ▼
      ┌────────┐ ┌─────┐ ┌──────┐ ┌──────┐ ┌──────┐
      │MOD-001 │ │  04 │ │  06  │ │  07  │ │  08  │
      │DocAnaly│ │Task │ │Dispat│ │Review│ │TestRn│
      └───┬────┘ │Engin│ │ cher │ │  er  │ │  ner │
          │      └──┬──┘ └──┬───┘ └──┬───┘ └──┬───┘
          │         │       │        │        │
          │    ┌────┘       │        │        │
          │    ▼            │        │        │
          │ ┌──────┐        │        │        │
          │ │MOD-003│        │        │        │
          │ │Regist │◄───────┘        │        │
          │ └──┬───┘                  │        │
          │    │                      │        │
          ▼    ▼          ▼           ▼        ▼
      ┌─────────────────────────────────────────┐
      │  MOD-005 (task_models) — 全局数据结构     │
      └─────────────────────────────────────────┘
              ▲         ▲         ▲
              │         │         │
         ┌────┘    ┌────┘    ┌────┘
      ┌──────┐ ┌──────┐ ┌──────┐
      │MOD-009│ │MOD-010│ │MOD-011│
      │StateM │ │Report│ │GitOps│
      └──────┘ └──────┘ └──────┘
                                  ▲
                                  │
                            ┌──────┐
                            │MOD-012│
                            │Config │
                            └──────┘
```

> 箭头方向: 依赖方 → 被依赖方。MOD-005 (task_models) 为最底层，被所有模块依赖。MOD-012 (config) 被除 MOD-005 外所有模块依赖。

---

## 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-07 | 从 OD-001 提取系统级内容，形成独立系统概要设计 | AutoDev Pipeline |
