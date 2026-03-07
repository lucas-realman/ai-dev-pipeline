# DD-MOD-005 — TaskModels 模块详细设计

> **文档编号**: DD-MOD-005  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/task_models.py` (202 行)  
> **上游文档**: [OD-MOD-005](../04-outline-design/OD-MOD-005-task_models.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md) · [OD-002](../04-outline-design/OD-002-数据模型设计.md)  
> **下游文档**: 被全部模块依赖

---

## §1 类型体系

```
┌─────────────────────────────────────────────────────┐
│                    Enumerations                      │
├─────────────────────────────────────────────────────┤
│ TaskStatus (11 值)                                   │
│   CREATED → QUEUED → DISPATCHED → CODING_DONE →     │
│   REVIEW → TESTING → JUDGING → PASSED / FAILED /    │
│   RETRY / ESCALATED                                  │
├─────────────────────────────────────────────────────┤
│ ReviewLayer (3 值)                                   │
│   STATIC / CONTRACT / DESIGN                         │
├─────────────────────────────────────────────────────┤
│ MachineStatus (4 值)                                 │
│   ONLINE / BUSY / OFFLINE / ERROR                    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    Dataclasses                        │
├─────────────────────────────────────────────────────┤
│ CodingTask          TaskResult                       │
│ ReviewResult        TestResult                       │
│ MachineInfo                                          │
└─────────────────────────────────────────────────────┘
```

---

## §2 枚举详细定义

### 2.1 TaskStatus

| 枚举值 | 字符串值 | 说明 | 可转换到 |
|--------|---------|------|---------|
| `CREATED` | `"created"` | 初始态 | QUEUED |
| `QUEUED` | `"queued"` | 已入队，等待分发 | DISPATCHED |
| `DISPATCHED` | `"dispatched"` | 已分发到机器 | CODING_DONE, RETRY, ESCALATED |
| `CODING_DONE` | `"coding_done"` | 编码完成 | REVIEW |
| `REVIEW` | `"review"` | 审查中 | TESTING, RETRY, ESCALATED |
| `TESTING` | `"testing"` | 测试中 | JUDGING |
| `JUDGING` | `"judging"` | 判定中 | PASSED, FAILED |
| `PASSED` | `"passed"` | **终态**: 通过 | — |
| `FAILED` | `"failed"` | 测试失败 | RETRY, ESCALATED |
| `RETRY` | `"retry"` | 等待重试 | QUEUED |
| `ESCALATED` | `"escalated"` | **终态**: 升级人工 | — |

### 2.2 ReviewLayer

| 枚举值 | 字符串值 | 说明 |
|--------|---------|------|
| `STATIC` | `"static"` | 静态检查 (py_compile + ruff) |
| `CONTRACT` | `"contract"` | 契约对齐检查 (LLM) |
| `DESIGN` | `"design"` | 设计符合度检查 (LLM) |

### 2.3 MachineStatus

| 枚举值 | 字符串值 | 说明 |
|--------|---------|------|
| `ONLINE` | `"online"` | 在线空闲 |
| `BUSY` | `"busy"` | 正在执行任务 |
| `OFFLINE` | `"offline"` | 离线 |
| `ERROR` | `"error"` | 异常 |

---

## §3 CodingTask 详细设计

### 3.1 字段定义

| 字段 | 类型 | 默认值 | 类别 | 说明 |
|------|------|--------|------|------|
| `task_id` | `str` | 必填 | 标识 | 任务唯一 ID (如 `S1_T1`) |
| `description` | `str` | 必填 | 标识 | 任务描述 |
| `tags` | `List[str]` | `[]` | v3 调度 | 能力标签 (gpu, backend, frontend) |
| `context_files` | `List[str]` | `[]` | 输入 | 上下文文件路径列表 |
| `depends_on` | `List[str]` | `[]` | 调度 | 前置依赖的 task_id 列表 |
| `acceptance` | `List[str]` | `[]` | 验收 | 验收标准列表 |
| `estimated_minutes` | `int` | `30` | 调度 | 预估执行时间 (分钟) |
| `assigned_machine` | `Optional[str]` | `None` | v3 调度 | 运行时动态分配的机器 ID |
| `target_dir` | `str` | `"./"` | 输出 | 代码生成目标目录 |
| `target_machine` | `Optional[str]` | `None` | v2 兼容 | v2 格式直接指定的目标机器 |
| `status` | `TaskStatus` | `CREATED` | 运行时 | 当前状态 |
| `retry_count` | `int` | `0` | 运行时 | 总重试次数 |
| `review_retry` | `int` | `0` | 运行时 | 审查重试次数 |
| `test_retry` | `int` | `0` | 运行时 | 测试重试次数 |
| `fix_instruction` | `Optional[str]` | `None` | 运行时 | 修复指令 (失败时由审查/测试填入) |
| `last_error` | `Optional[str]` | `None` | 运行时 | 最近错误信息 |
| `created_at` | `float` | `time.time()` | 时间戳 | 创建时间 |
| `started_at` | `Optional[float]` | `None` | 时间戳 | 开始执行时间 |
| `finished_at` | `Optional[float]` | `None` | 时间戳 | 完成时间 |

### 3.2 计算属性

| 属性 | 返回类型 | 算法 |
|------|---------|------|
| `total_retries` | `int` | `review_retry + test_retry` |
| `effective_machine` | `Optional[str]` | `assigned_machine or target_machine` (v3 优先) |

### 3.3 序列化方法

#### `to_dict() → Dict[str, Any]`

将所有字段映射为基本类型字典。`status` 字段输出 `.value` 字符串。

#### `from_dict(cls, d: Dict[str, Any]) → CodingTask`

```
function from_dict(d):
    d = dict(d)                            # 避免修改原始数据
    d["status"] = TaskStatus(d.get("status", "created"))
    # 过滤: 只保留 dataclass 声明的字段
    valid_keys = CodingTask.__dataclass_fields__
    return CodingTask(**{k:v for k,v in d.items() if k in valid_keys})
```

---

## §4 TaskResult 详细设计

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `task_id` | `str` | 必填 | 任务 ID |
| `exit_code` | `int` | `1` | aider 进程退出码 |
| `stdout` | `str` | `""` | 标准输出 |
| `stderr` | `str` | `""` | 标准错误 |
| `files_changed` | `List[str]` | `[]` | 变更文件列表 |
| `duration_sec` | `float` | `0.0` | 执行耗时 (秒) |

**计算属性**: `success → bool` = `exit_code == 0`

---

## §5 ReviewResult 详细设计

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `passed` | `bool` | 必填 | 是否通过 |
| `layer` | `Optional[str]` | `None` | 失败的审查层级 |
| `issues` | `List[str]` | `[]` | 发现的问题列表 |
| `fix_instruction` | `Optional[str]` | `None` | 修复指令 |
| `score` | `float` | `0.0` | 综合评分 (L3 输出) |
| `scores` | `Dict[str, float]` | `{}` | 各维度评分 |

---

## §6 TestResult 详细设计

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `passed` | `bool` | 必填 | 是否通过 |
| `total` | `int` | `0` | 总测试数 |
| `passed_count` | `int` | `0` | 通过数 |
| `failed_count` | `int` | `0` | 失败数 |
| `error_count` | `int` | `0` | 错误数 |
| `duration_sec` | `float` | `0.0` | 执行耗时 |
| `failures` | `List[str]` | `[]` | 失败详情 |
| `stdout` | `str` | `""` | 原始输出 |

---

## §7 MachineInfo 详细设计

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `machine_id` | `str` | 必填 | 机器唯一标识 |
| `display_name` | `str` | `""` | 显示名 |
| `host` | `str` | `""` | 主机地址 |
| `port` | `int` | `22` | SSH 端口 |
| `user` | `str` | `""` | SSH 用户 |
| `work_dir` | `str` | `~/projects` | 远程工作目录 |
| `tags` | `List[str]` | `[]` | 能力标签 |
| `aider_prefix` | `str` | `""` | aider 执行前的 shell 前置命令 |
| `aider_model` | `str` | `""` | 该机器专用模型覆盖 |
| `status` | `MachineStatus` | `ONLINE` | 当前状态 |
| `current_task` | `Optional[str]` | `None` | 当前执行的任务 ID |
| `hardware_info` | `Dict[str, str]` | `{}` | 硬件信息 |
| `load` | `Dict[str, float]` | `{"cpu_percent":0, "ram_percent":0, "disk_free_gb":0}` | 实时负载 |

**序列化**: `to_dict()` 将 `status` 输出为 `.value` 字符串。

---

## §8 v2/v3 兼容设计

```
                v2 格式                          v3 格式
         ┌──────────────────┐           ┌──────────────────┐
         │ target_machine   │           │ tags: [gpu, py]  │
         │ = "4090"         │           │ assigned_machine │
         └────────┬─────────┘           │ = None (运行时)  │
                  │                     └────────┬─────────┘
                  │                              │
                  └──────┐    ┌──────────────────┘
                         ▼    ▼
                  effective_machine
                  = assigned_machine or target_machine
```

**兼容策略**:
1. `target_machine` 保留但标记为 "逐步废弃"
2. `effective_machine` 属性统一对外提供机器 ID
3. TaskEngine.next_batch() 优先使用 `assigned_machine`，回退 `target_machine`

---

## §9 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §5 提取并扩充，形成独立模块详述 |
