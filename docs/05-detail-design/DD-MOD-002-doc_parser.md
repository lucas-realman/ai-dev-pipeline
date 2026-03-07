# DD-MOD-002 — DocParser 模块详细设计

> **文档编号**: DD-MOD-002  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/doc_parser.py` (193 行)  
> **上游文档**: [OD-MOD-002](../04-outline-design/OD-MOD-002-doc_parser.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                      DocParser                           │
├──────────────────────────────────────────────────────────┤
│ - repo_path          : Path                              │
│ + config             : Config                             │
├──────────────────────────────────────────────────────────┤
│ + __init__(config: Config)                                │
│ + parse_task_card(card_path?, sprint?) → List[CodingTask]│
│ + read_contracts() → str                                 │
│ - _extract_sprint_section(text, sprint) → str            │
│ - _parse_tables(text) → List[CodingTask]                 │
│ - _expand_machine_range(code) → List[str]                │
│ - _infer_target_dir(output_files, machine_name) → str    │
│ - _infer_context_files(target_dir) → List[str]           │
└──────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ 模块级常量                                  │
├────────────────────────────────────────────┤
│ MACHINE_ALIAS: Dict[str, str]              │
│   W0→orchestrator, W1→4090, W2→mac_min_8T │
│   W3→gateway, W4→data_center, W5→orch.    │
│ MACHINE_DEFAULT_DIR: Dict[str, str]        │
│   4090→agent/, mac_min_8T→crm/ ...        │
└────────────────────────────────────────────┘
```

---

## §2 核心函数设计

### 2.1 `__init__`

| 项目 | 内容 |
|------|------|
| **签名** | `__init__(self, config: Config)` |
| **职责** | 初始化解析器，从 config 获取项目根路径 |
| **算法** | `self.config = config; self.repo_path = Path(config.work_dir)` |

### 2.2 `parse_task_card`

| 项目 | 内容 |
|------|------|
| **签名** | `parse_task_card(self, card_path: str = "docs/07-Sprint任务卡.md", sprint: Optional[int] = None) → List[CodingTask]` |
| **职责** | 解析 v2 格式的 Sprint 任务卡 Markdown 表格 |
| **输入** | `card_path` — 任务卡文件路径（绝对或相对）；`sprint` — 可选 Sprint 过滤 |
| **输出** | `List[CodingTask]` |
| **算法** | ALG-005 |
| **异常** | 文件不存在 → 返回空列表 + error 日志 |

#### ALG-005: 任务卡解析主流程

```
function parse_task_card(card_path, sprint):
    full_path = is_absolute(card_path) ? card_path : repo_path / card_path
    if not exists(full_path):
        log.error("任务卡不存在")
        return []
    
    text = read_text(full_path)
    
    if sprint is not None:
        text = _extract_sprint_section(text, sprint)
        if text is empty:
            log.warning("未找到 Sprint %s", sprint)
            return []
    
    tasks = _parse_tables(text)
    log.info("解析到 %d 个任务", len(tasks))
    return tasks
```

### 2.3 `_extract_sprint_section`

| 项目 | 内容 |
|------|------|
| **签名** | `_extract_sprint_section(self, text: str, sprint: int) → str` |
| **职责** | 从全文中提取指定 Sprint 对应的章节 |
| **算法** | ALG-006 |

#### ALG-006: Sprint 章节提取

```
function _extract_sprint_section(text, sprint):
    pattern = r"^##\s+\d+\.\s+Sprint\s+\d*{sprint}\d*[：:—\-]"
    lines = text.splitlines()
    start = None; end = len(lines)
    
    for i, line in enumerate(lines):
        if start is None:
            if regex.match(pattern, line): start = i
        elif line.startswith("## ") and not line.startswith("### "):
            end = i; break
    
    return start is None ? "" : join(lines[start:end])
```

**匹配模式**: `## N. Sprint Xnn：...` 格式的二级标题

### 2.4 `_parse_tables`

| 项目 | 内容 |
|------|------|
| **签名** | `_parse_tables(self, text: str) → List[CodingTask]` |
| **职责** | 解析 Markdown 表格行，提取任务定义 |
| **算法** | ALG-007 |

#### ALG-007: 表格解析算法

```
function _parse_tables(text):
    tasks = []; current_day = ""; task_counter = 0
    
    for line in text.splitlines():
        # 识别 Day 标题: #### Day N
        if match(r"^####\s+Day\s+(\d+)", line):
            current_day = match.group(1); continue
        
        # 跳过分隔行和表头
        if is_separator_line(line) or is_header_line(line): continue
        
        # 匹配任务行: | **W1** | ...
        if not match(r"\s*\|\s*\*\*(\w[\w\-]*)\*\*\s*\|", line): continue
        
        machine_code = match.group(1)
        parts = split_and_clean(line, "|")
        if len(parts) < 3: continue
        
        # 提取字段
        task_name       = parts[1]
        aider_instr     = parts[2] if len > 2 else ""
        output_files    = parts[3] if len > 3 else ""
        acceptance      = parts[4] if len > 4 else ""
        
        # 展开机器范围 (如 W1-W3 → [W1, W2, W3])
        machines = contains("-", machine_code) 
                   ? _expand_machine_range(machine_code)
                   : [machine_code]
        
        for mc in machines:
            machine_name = MACHINE_ALIAS.get(mc, mc)
            if unknown(machine_name): log.warning; continue
            
            task_counter += 1
            task_id = current_day ? "S{day}_{mc}" : "T{counter}"
            target_dir = _infer_target_dir(output_files, machine_name)
            context_files = _infer_context_files(target_dir)
            
            tasks.append(CodingTask(
                task_id, target_machine=machine_name,
                target_dir, description, context_files, acceptance
            ))
    
    return tasks
```

**关键细节**:
- 表格列顺序: 机器 | 任务名 | aider 指令 | 产出文件 | 完成标志
- 机器代号加粗格式: `**W1**`
- 描述字段清理: 去除中英文引号

### 2.5 `_expand_machine_range`

| 项目 | 内容 |
|------|------|
| **签名** | `_expand_machine_range(self, code: str) → List[str]` |
| **职责** | 展开 `W1-W3` → `["W1", "W2", "W3"]` |
| **算法** | 正则提取起止数字，生成 range 列表 |
| **正则** | `r"W(\d+)-W(\d+)"` |

### 2.6 `_infer_target_dir`

| 项目 | 内容 |
|------|------|
| **签名** | `_infer_target_dir(self, output_files: str, machine_name: str) → str` |
| **职责** | 从产出文件列表推断目标目录 |
| **算法** | 清理反引号 → 取第一个文件 → 提取首层目录；否则 fallback 到 `MACHINE_DEFAULT_DIR` |

### 2.7 `_infer_context_files`

| 项目 | 内容 |
|------|------|
| **签名** | `_infer_context_files(self, target_dir: str) → List[str]` |
| **职责** | 自动推断上下文文件 |
| **算法** | 收集 `contracts/*.yaml` + 目标目录下 `__init__.py` |

### 2.8 `read_contracts`

| 项目 | 内容 |
|------|------|
| **签名** | `read_contracts(self) → str` |
| **职责** | 读取所有契约文件拼合为文本 |
| **算法** | 遍历 `contracts/` 目录，过滤 `.yaml/.yml/.sql`，拼合 `=== name ===\n{content}` |

---

## §3 常量字典

### 3.1 MACHINE_ALIAS

| 代号 | 机器名 | 说明 |
|------|--------|------|
| `W0` | orchestrator | 编排节点 |
| `W1` | 4090 | GPU 节点 |
| `W2` | mac_min_8T | macOS 节点 |
| `W3` | gateway | 网关节点 |
| `W4` | data_center | 数据中心节点 |
| `W5` | orchestrator | 编排节点 (冗余) |

### 3.2 MACHINE_DEFAULT_DIR

| 机器名 | 默认目录 |
|--------|---------|
| 4090 | `agent/` |
| mac_min_8T | `crm/` |
| gateway | `deploy/` |
| data_center | `scripts/` |
| orchestrator | `orchestrator/` |

---

## §4 序列图

### SEQ-002: 任务卡解析流程

```
Orchestrator        DocParser           文件系统
    │                  │                   │
    │ parse_task_card  │                   │
    │  (path, sprint)  │                   │
    │─────────────────>│                   │
    │                  │  read_text(path)  │
    │                  │──────────────────>│
    │                  │  markdown text    │
    │                  │<─────────────────│
    │                  │                   │
    │                  │ _extract_sprint_  │
    │                  │  section()        │
    │                  │──────┐            │
    │                  │      │ regex      │
    │                  │<─────┘            │
    │                  │                   │
    │                  │ _parse_tables()   │
    │                  │──────┐            │
    │                  │      │ for line:  │
    │                  │      │ match,     │
    │                  │      │ expand,    │
    │                  │      │ infer      │
    │                  │<─────┘            │
    │                  │                   │
    │ List[CodingTask] │                   │
    │<─────────────────│                   │
```

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §2 提取并扩充，形成独立模块详述 |
