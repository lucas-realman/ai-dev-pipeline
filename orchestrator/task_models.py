"""
AI Dev Pipeline — 数据模型 (DD-MOD-005)
定义 CodingTask / TaskResult / ReviewResult / TestResult / MachineInfo 等核心数据结构。
v3.0: 任务不绑定 target_machine，改用 tags + 动态 assigned_machine。
"""
from __future__ import annotations

import enum
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── 字符白名单 (§3.2 __post_init__ 校验) ──

_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_\-/.]+$')


# ── 任务状态枚举 ──────────────────────────────────────────

class TaskStatus(enum.Enum):
    """任务状态机 (DD-MOD-005 §2.1)"""
    CREATED     = "created"
    QUEUED      = "queued"
    DISPATCHED  = "dispatched"
    CODING_DONE = "coding_done"
    REVIEW      = "review"
    TESTING     = "testing"
    JUDGING     = "judging"
    PASSED      = "passed"
    FAILED      = "failed"
    RETRY       = "retry"
    ESCALATED   = "escalated"


class ReviewLayer(enum.Enum):
    """审查层级 (DD-MOD-005 §2.2)"""
    L1_STATIC   = "static"
    L2_CONTRACT = "contract"
    L3_QUALITY  = "quality"


class MachineStatus(enum.Enum):
    ONLINE  = "online"
    BUSY    = "busy"
    OFFLINE = "offline"
    ERROR   = "error"


# ── 核心模型 ──────────────────────────────────────────────

@dataclass
class CodingTask:
    """
    一个编码任务 (DD-MOD-005 §3)。
    v3.0 变更:
    - target_machine → 可选（向后兼容），新增 tags + assigned_machine
    - target_dir → 可选，由 AI 在 doc_analyzer 中推断
    """
    task_id: str
    description: str
    module_name: str = ""                                    # DD-MOD-005 §3.1: 目标模块名
    tags: List[str] = field(default_factory=list)           # 能力标签 (gpu, backend, frontend)
    context_files: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    acceptance: List[str] = field(default_factory=list)
    estimated_minutes: int = 30

    # v3.0: 动态分配
    assigned_machine: Optional[str] = None                   # 由调度器在运行时填入
    target_dir: str = "./"                                   # 可由 AI 推断

    # v2 兼容 (逐步废弃)
    target_machine: Optional[str] = None

    # 运行时状态
    status: TaskStatus = TaskStatus.CREATED
    retry_count: int = 0
    review_retry: int = 0
    test_retry: int = 0
    fix_instruction: Optional[str] = None
    last_error: Optional[str] = None

    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    def __post_init__(self) -> None:
        """DD-MOD-005 §3.2: 创建时自动校验关键字段"""
        # 1. task_id 格式校验
        if not self.task_id or not _SAFE_ID_RE.match(self.task_id):
            raise ValueError(
                f"task_id 包含非法字符: '{self.task_id}' "
                f"(允许: a-z A-Z 0-9 _ - / .)")
        # 2. target_dir 路径安全校验
        if self.target_dir and self.target_dir != "./":
            if not _SAFE_ID_RE.match(self.target_dir):
                raise ValueError(
                    f"target_dir 包含非法字符: '{self.target_dir}'")
            if '..' in self.target_dir:
                raise ValueError(
                    f"target_dir 禁止路径遍历 (..): '{self.target_dir}'")
        # 3. depends_on 引用校验
        for dep_id in self.depends_on:
            if not _SAFE_ID_RE.match(dep_id):
                raise ValueError(
                    f"depends_on 包含非法 task_id: '{dep_id}'")

    @property
    def total_retries(self) -> int:
        return self.review_retry + self.test_retry

    @property
    def effective_machine(self) -> Optional[str]:
        """返回实际执行机器 (v3 优先 assigned_machine, 回退 target_machine)"""
        return self.assigned_machine or self.target_machine

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "module_name": self.module_name,
            "tags": self.tags,
            "assigned_machine": self.assigned_machine,
            "target_machine": self.target_machine,
            "target_dir": self.target_dir,
            "context_files": self.context_files,
            "depends_on": self.depends_on,
            "acceptance": self.acceptance,
            "estimated_minutes": self.estimated_minutes,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "review_retry": self.review_retry,
            "test_retry": self.test_retry,
            "fix_instruction": self.fix_instruction,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CodingTask:
        d = dict(d)
        d["status"] = TaskStatus(d.get("status", "created"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskResult:
    """aider 编码执行结果 (DD-MOD-005 §4)"""
    task_id: str
    exit_code: int = 1
    stdout: str = ""
    stderr: str = ""
    files_changed: List[str] = field(default_factory=list)
    duration_sec: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class ReviewResult:
    """自动 Review 结果 (DD-MOD-005 §5)"""
    passed: bool
    layer: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    fix_instruction: Optional[str] = None
    score: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class TestResult:
    """pytest 测试结果 (DD-MOD-005 §6)"""
    passed: bool
    task_id: str = ""
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    duration_sec: float = 0.0
    pass_rate: float = 0.0
    failures: List[str] = field(default_factory=list)
    stdout: str = ""
    details: str = ""
    reason: str = ""


@dataclass
class MachineInfo:
    """
    机器信息模型 (DD-MOD-005 §7)。
    从 config.yaml machines[] 加载，由 MachineRegistry 管理。
    """
    machine_id: str
    display_name: str = ""
    host: str = ""
    port: int = 22
    user: str = ""
    work_dir: str = "~/projects"
    tags: List[str] = field(default_factory=list)
    aider_prefix: str = ""
    aider_model: str = ""
    status: MachineStatus = MachineStatus.ONLINE
    current_task_id: Optional[str] = None
    busy_since: Optional[float] = None

    # 硬件信息 (可选, 手动或自动探测)
    hardware_info: Dict[str, str] = field(default_factory=dict)

    # 实时负载 (心跳上报)
    load: Dict[str, float] = field(default_factory=lambda: {
        "cpu_percent": 0.0,
        "ram_percent": 0.0,
        "disk_free_gb": 0.0,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "display_name": self.display_name,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "work_dir": self.work_dir,
            "tags": self.tags,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "busy_since": self.busy_since,
            "hardware_info": self.hardware_info,
            "load": self.load,
        }
