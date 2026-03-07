# DD-MOD-012 — Config 模块详细设计

> **文档编号**: DD-MOD-012  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/config.py` (234 行)  
> **上游文档**: [OD-MOD-012](../04-outline-design/OD-MOD-012-config.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                        Config                            │
├──────────────────────────────────────────────────────────┤
│ + _data         : dict                                   │
│ + config_path   : str                                    │
├──────────────────────────────────────────────────────────┤
│ + __init__(config_path=None)                             │
│ + get(key_path, default=None) → Any                      │
│ + get_machines() → Dict[str, MachineInfo]       «v2»     │
│ + get_machines_list() → List[MachineInfo]       «v3»     │
│ - _load(config_path) → dict                              │
│ - _expand_env_vars(data) → Any                 «static»  │
├──────────────────────────────────────────────────────────┤
│ «@property»                                              │
│ + branch → str                                           │
│ + work_dir → str                                         │
│ + task_card_path → str                                   │
│ + contracts_dir → str                                    │
│ + reports_dir → str                                      │
│ + openai_api_base → str                                  │
│ + openai_api_key → str                                   │
│ + model → str                                            │
│ + max_concurrent → int                                   │
│ + max_retries → int                                      │
│ + single_task_timeout → int                              │
│ + test_timeout → int                                     │
│ + review_threshold → float                               │
│ + pass_threshold → float                                 │
│ + sprint_id → str                                        │
│ + dingtalk_webhook_url → Optional[str]                   │
│ + dingtalk_webhook_secret → Optional[str]                │
│ + dingtalk_app_key → Optional[str]                       │
│ + dingtalk_app_secret → Optional[str]                    │
│ + log_level → str                                        │
└──────────────────────────────────────────────────────────┘
```

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self, config_path: Optional[str] = None)` |
| **查找链** | 参数 → 环境变量 `AUTODEV_CONFIG` → `./config.yaml` → `./orchestrator/config.yaml` |
| **异常** | 全部未找到 → `FileNotFoundError` (ERR-002) |

### 2.2 `_load`

| 项目 | 内容 |
|------|------|
| **签名** | `_load(self, config_path: str) → dict` |
| **算法** | ALG-025 |

#### ALG-025: YAML 配置加载与环境变量展开

```
function _load(config_path):
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    
    # 递归展开环境变量
    data = _expand_env_vars(raw)
    
    # ★v1.1: Schema 校验
    _validate_schema(data)
    
    return data
```

### 2.2a `_validate_schema` ★v1.1

| 项目 | 内容 |
|------|------|
| **签名** | `@staticmethod _validate_schema(data: dict) → None` |
| **职责** | 启动时校验配置必填字段，失败时耗尽的报错 |
| **异常** | `ConfigSchemaError` (ERR-025) |
| **算法** | ALG-025a |

> 对应 ACTION-ITEM v2.1 A-111

#### ALG-025a: 配置 Schema 校验

```
function _validate_schema(data):
    """
    启动时校验配置必填字段。所有错误累积后一次性报出。
    """
    errors = []
    
    # 必填字段检查
    REQUIRED_FIELDS = [
        ("llm.openai_api_key", "LLM API Key 未配置"),
        ("project.branch", "分支名未配置"),
    ]
    
    for key_path, msg in REQUIRED_FIELDS:
        value = _get_nested(data, key_path)
        if value is None or value == "":
            errors.append(f"[{key_path}] {msg}")
    
    # machines 列表非空检查
    machines = _get_nested(data, "machines")
    if not machines:
        errors.append("[machines] 机器列表不能为空")
    elif isinstance(machines, list):
        for i, m in enumerate(machines):
            if not m.get("machine_id"):
                errors.append(f"[machines.{i}.machine_id] 缺失")
            if not m.get("host"):
                errors.append(f"[machines.{i}.host] 缺失")
    
    # 数值范围检查
    max_concurrent = _get_nested(data, "task.max_concurrent")
    if max_concurrent is not None and (not isinstance(max_concurrent, int) or max_concurrent < 1):
        errors.append("[task.max_concurrent] 必须为正整数")
    
    max_retries = _get_nested(data, "task.max_retries")
    if max_retries is not None and (not isinstance(max_retries, int) or max_retries < 0):
        errors.append("[task.max_retries] 必须为非负整数")
    
    if errors:
        msg = "\n".join(errors)
        raise ConfigSchemaError(f"配置校验失败 ({len(errors)} 项):\n{msg}")  # ERR-025
```

**校验规则汇总**:

| 字段 | 规则 | 严重程度 |
|------|------|----------|
| `llm.openai_api_key` | 非空 | 阻塞启动 |
| `project.branch` | 非空 | 阻塞启动 |
| `machines` | 非空 list/dict | 阻塞启动 |
| `machines[*].machine_id` | 非空 | 阻塞启动 |
| `machines[*].host` | 非空 | 阻塞启动 |
| `task.max_concurrent` | 正整数 | 警告 |
| `task.max_retries` | 非负整数 | 警告 |

### 2.3 `_expand_env_vars` (静态方法) ★

| 项目 | 内容 |
|------|------|
| **签名** | `@staticmethod _expand_env_vars(data: Any) → Any` |
| **职责** | 递归解析 YAML 值中的 `${VAR}` 和 `${VAR:-default}` 占位符 |
| **算法** | ALG-026 |

#### ALG-026: 递归环境变量展开

```
function _expand_env_vars(data):
    if isinstance(data, str):
        # 正则匹配 ${VAR} 或 ${VAR:-default}
        pattern = r'\$\{(\w+)(?::-(.*?))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default  = match.group(2)   # 可能为 None
            value    = os.environ.get(var_name)
            if value is not None:
                return value
            if default is not None:
                return default
            return match.group(0)       # 原样保留
        
        return re.sub(pattern, replacer, data)
    
    elif isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    
    else:
        return data   # int, float, bool, None → 原样
```

**示例**:
```yaml
llm:
  api_key: "${OPENAI_API_KEY}"
  model: "${MODEL:-claude-sonnet-4-6}"
```
→ `api_key` 从 `$OPENAI_API_KEY` 读取，`model` 在环境变量不存在时回退到 `claude-sonnet-4-6`

### 2.4 `get` (点路径访问)

| 项目 | 内容 |
|------|------|
| **签名** | `get(self, key_path: str, default: Any = None) → Any` |
| **算法** | ALG-027 |

#### ALG-027: 点路径递归查找

```
function get(key_path, default=None):
    """支持 'llm.model' 或 'machines.0.host' 风格的访问路径"""
    keys = key_path.split('.')
    node = self._data
    
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
        elif isinstance(node, list) and key.isdigit():
            idx = int(key)
            node = node[idx] if idx < len(node) else None
        else:
            return default
        
        if node is None:
            return default
    
    return node
```

### 2.5 `get_machines` (v2 兼容)

| 项目 | 内容 |
|------|------|
| **签名** | `get_machines(self) → Dict[str, MachineInfo]` |
| **职责** | v2 配置格式: `machines:` 为 dict，key 即 machine_id |
| **返回** | `{machine_id: MachineInfo(...)}`  |

### 2.6 `get_machines_list` (v3 格式)

| 项目 | 内容 |
|------|------|
| **签名** | `get_machines_list(self) → List[MachineInfo]` |
| **职责** | v3 配置格式: `machines:` 为 list，每项含 `machine_id` |
| **算法** | |

```
function get_machines_list():
    machines_raw = self.get('machines', [])
    
    if isinstance(machines_raw, dict):
        # v2 兼容: dict → list
        return [
            MachineInfo(machine_id=k, **v)
            for k, v in machines_raw.items()
        ]
    
    # v3: list
    return [MachineInfo(**m) for m in machines_raw]
```

---

## §3 配置文件 Schema

### 3.1 config.yaml 完整结构

```yaml
# ======== 项目配置 ========
project:
  branch: "main"
  work_dir: "/path/to/repo"
  sprint_id: "sprint-001"

# ======== 路径配置 ========
paths:
  task_card: "docs/task_card.md"
  contracts_dir: "contracts/"
  reports_dir: "reports/"

# ======== LLM 配置 ========
llm:
  openai_api_base: "${OPENAI_API_BASE:-http://localhost:8080/v1}"
  openai_api_key: "${OPENAI_API_KEY}"
  model: "${MODEL:-claude-sonnet-4-6}"

# ======== 任务配置 ========
task:
  max_concurrent: 5
  max_retries: 3
  single_task_timeout: 600
  test_timeout: 300
  review_threshold: 3.5
  pass_threshold: 0.8
  aider_version: "0.82.1"       # ★v1.2: 锁定 aider 版本 (A-121)

# ======== 机器列表 (v3) ========
machines:
  - machine_id: "W1"
    host: "192.168.1.101"
    port: 22
    user: "dev"
    work_dir: "/home/dev/project"
    tags: ["python", "backend"]
    aider_prefix: "conda activate aider"
  - machine_id: "W2"
    host: "192.168.1.102"
    ...

# ======== 钉钉通知 (可选) ========
dingtalk:
  webhook_url: "${DINGTALK_WEBHOOK_URL:-}"
  webhook_secret: "${DINGTALK_SECRET:-}"
  app_key: "${DINGTALK_APP_KEY:-}"
  app_secret: "${DINGTALK_APP_SECRET:-}"

# ======== 日志 ========
logging:
  level: "${LOG_LEVEL:-INFO}"
```

### 3.2 @property 映射表

| 属性名 | 配置路径 | 类型 | 默认值 |
|--------|---------|------|--------|
| `branch` | `project.branch` | str | `"main"` |
| `work_dir` | `project.work_dir` | str | `"."` |
| `sprint_id` | `project.sprint_id` | str | `"sprint-001"` |
| `task_card_path` | `paths.task_card` | str | `"docs/task_card.md"` |
| `contracts_dir` | `paths.contracts_dir` | str | `"contracts/"` |
| `reports_dir` | `paths.reports_dir` | str | `"reports/"` |
| `openai_api_base` | `llm.openai_api_base` | str | — |
| `openai_api_key` | `llm.openai_api_key` | str | — |
| `model` | `llm.model` | str | `"claude-sonnet-4-6"` |
| `max_concurrent` | `task.max_concurrent` | int | `5` |
| `max_retries` | `task.max_retries` | int | `3` |
| `single_task_timeout` | `task.single_task_timeout` | int | `600` |
| `test_timeout` | `task.test_timeout` | int | `300` |
| `review_threshold` | `task.review_threshold` | float | `3.5` |
| `pass_threshold` | `task.pass_threshold` | float | `0.8` |
| `log_level` | `logging.level` | str | `"INFO"` |
| `aider_version` | `task.aider_version` | str | `""` (不校验) |

---

## §4 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §12 提取并扩充，含完整 Schema 与属性映射 |
| v1.1 | 2026-03-07 | 新增 ALG-025a Schema 校验; 增加 ConfigSchemaError (ERR-025) |
| v1.2 | 2026-03-07 | 新增 `aider_version` 配置项; @property 映射 (A-121) |
