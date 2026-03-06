"""
AI Dev Pipeline — 数据模型
定义 CodingTask / TaskResult / ReviewResult 等核心数据结构。
v3.0: 任务不绑定 target_machine，改用 tags + 动态 assigned_machine。
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 任务状态枚举 ──────────────────────────────────────────

class TaskStatus(enum.Enum):
    """任务状态机 (对照设计文档 §2.3 状态图)"""
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
    STATIC   = "static"
    CONTRACT = "contract"
    DESIGN   = "design"


class MachineStatus(enum.Enum):
    ONLINE  = "online"
    BUSY    = "busy"
    OFFLINE = "offline"
    ERROR   = "error"


# ── 核心模型 ──────────────────────────────────────────────

@dataclass
class CodingTask:
    """
    一个编码任务。
    v3.0 变更:
    - target_machine → 可选（向后兼容），新增 tags + assigned_machine
    - target_dir → 可选，由 AI 在 doc_analyzer 中推断
    """
    task_id: str
    description: str
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
    """aider 编码执行结果"""
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
    """自动 Review 结果"""
    passed: bool
    layer: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    fix_instruction: Optional[str] = None
    score: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class TestResult:
    """pytest 测试结果"""
    passed: bool
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    duration_sec: float = 0.0
    failures: List[str] = field(default_factory=list)
    stdout: str = ""


@dataclass
class MachineInfo:
    """
    机器信息模型 (v3.0)。
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
    current_task: Optional[str] = None

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
            "current_task": self.current_task,
            "hardware_info": self.hardware_info,
            "load": self.load,
        }
