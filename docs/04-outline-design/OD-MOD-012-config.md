# OD-MOD-012 — Config 模块概要设计

> **文档编号**: OD-MOD-012  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/config.py` (235 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-009](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-012](../05-detail-design/DD-MOD-012-config.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-012 |
| **核心类** | `Config` |
| **辅助函数** | `_expand_env_vars()` |
| **ARCH 组件** | ARCH-009 配置管理组件 |
| **关联 FR** | 基础设施，支撑所有模块 |
| **对外接口** | 属性访问 + `get(dotpath)` 点号路径查询 |
| **依赖** | pyyaml, MOD-005 (task_models: `MachineInfo`) |

## 职责

加载 `config.yaml` → 环境变量 `${VAR}` 展开 → 提供类型安全的配置访问。v3.0 新增 project/doc_set/machines(list) 支持。

## 配置层次

```
config.yaml
    │
    ├── project:          → project_name, project_path
    ├── doc_set:          → glob 模式映射
    ├── orchestrator:     → mode, current_sprint, poll_interval, max_concurrent, port
    ├── llm:              → openai_api_base, openai_api_key, model
    ├── task:             → single_task_timeout, max_retries
    ├── git:              → branch, remote, bare_repo
    ├── testing:          → pytest_args, pass_threshold, test_pass_rate_threshold
    ├── notification:     → dingtalk_webhook, dingtalk_app_key, at_mobiles
    ├── paths:            → task_card, design_doc, contracts_dir, log_dir
    └── machines: []      → v3.0 列表格式，每项含 machine_id, host, user, tags
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **环境变量展开** | 递归处理 `${VAR}` 引用，支持字符串/dict/list 嵌套 |
| **项目根优先级** | 参数 `project_root` > config `project.path` > 默认 (config.yaml 父目录的父目录) |
| **点号路径访问** | `get("orchestrator.mode")` 支持任意深度的嵌套访问 |
| **v2/v3 machines 兼容** | v3 为列表格式，v2 dict 格式自动转换 |
| **类型安全属性** | 核心配置通过 `@property` 返回类型明确的值 |
| **MachineInfo 构造** | `get_machines()` 和 `get_machines_list()` 两种访问方式 |

## 配置属性一览

| 分组 | 属性 | 类型 | 默认值 |
|------|------|------|--------|
| project | `project_name` | str | "unnamed-project" |
| project | `project_path` | Path | 自动推断 |
| project | `doc_set` | Dict[str,str] | {} |
| orchestrator | `mode` | str | — |
| orchestrator | `current_sprint` | int | — |
| orchestrator | `max_concurrent` | int | 4 |
| llm | `openai_api_base` | str | — |
| llm | `aider_model` | str | — |
| task | `single_task_timeout` | int | — |
| task | `max_retries` | int | — |
| testing | `pytest_args` | str | "-x -v --tb=short" |
| testing | `pass_threshold` | float | 4.0 |
| testing | `test_pass_rate_threshold` | float | 0.8 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.12 提取并扩充 |
