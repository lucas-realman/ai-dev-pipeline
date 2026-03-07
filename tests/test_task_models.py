"""
L2 组件测试 — 数据模型 (MOD-005)
TC-003 ~ TC-005 补全, 覆盖 FR-001 / FR-002
对齐 TEST-001 §2.2.5
"""

import pytest

from orchestrator.task_models import (
    CodingTask,
    MachineInfo,
    MachineStatus,
    ReviewLayer,
    ReviewResult,
    TaskResult,
    TaskStatus,
    TestResult,
)

# ── TC-003: CodingTask 创建与校验 (FR-001) ───────────────

@pytest.mark.component
def test_tc003_coding_task_creation():
    """TC-003: CodingTask 合法构造 + __post_init__ 校验"""
    t = CodingTask(
        task_id="S1_T1",
        description="实现用户认证模块",
        module_name="auth",
        tags=["python", "web"],
        target_dir="src/auth",
        depends_on=["S1_T0"],
        acceptance=["pytest 通过"],
    )
    assert t.task_id == "S1_T1"
    assert t.status == TaskStatus.CREATED
    assert t.retry_count == 0
    assert t.total_retries == 0


@pytest.mark.component
def test_tc003b_task_id_illegal_chars():
    """TC-003b: task_id 含非法字符 → ValueError"""
    with pytest.raises(ValueError, match="非法字符"):
        CodingTask(task_id="T 001!@", description="bad id")


@pytest.mark.component
def test_tc003c_target_dir_path_traversal():
    """TC-003c: target_dir 含 .. → ValueError"""
    with pytest.raises(ValueError, match="路径遍历"):
        CodingTask(task_id="T-001", description="test", target_dir="../etc/passwd")


# ── TC-004: to_dict / from_dict 往返 (FR-001) ────────────

@pytest.mark.component
def test_tc004_to_dict_from_dict_roundtrip():
    """TC-004: CodingTask → dict → CodingTask 不丢失数据"""
    orig = CodingTask(
        task_id="T-RT-001",
        description="round trip test",
        module_name="core",
        tags=["python", "gpu"],
        depends_on=["T-RT-000"],
        target_dir="src/core",
        estimated_minutes=45,
        assigned_machine="gpu_4090",
    )
    orig.status = TaskStatus.QUEUED
    orig.retry_count = 2

    d = orig.to_dict()
    assert isinstance(d, dict)
    assert d["task_id"] == "T-RT-001"
    assert d["status"] == "queued"

    restored = CodingTask.from_dict(d)
    assert restored.task_id == orig.task_id
    assert restored.status == TaskStatus.QUEUED
    assert restored.tags == ["python", "gpu"]
    assert restored.depends_on == ["T-RT-000"]
    assert restored.assigned_machine == "gpu_4090"


# ── TC-005: effective_machine 属性 (FR-002) ───────────────

@pytest.mark.component
def test_tc005_effective_machine_priority():
    """TC-005: assigned_machine 优先于 target_machine"""
    t1 = CodingTask(task_id="T-EM1", description="test",
                    assigned_machine="gpu01", target_machine="cpu01")
    assert t1.effective_machine == "gpu01"

    t2 = CodingTask(task_id="T-EM2", description="test",
                    target_machine="cpu01")
    assert t2.effective_machine == "cpu01"

    t3 = CodingTask(task_id="T-EM3", description="test")
    assert t3.effective_machine is None


# ── 附加: TaskStatus 枚举 ────────────────────────────────

@pytest.mark.component
def test_task_status_members():
    """TaskStatus 包含 11 个状态"""
    assert len(TaskStatus) == 11
    assert TaskStatus.CREATED.value == "created"
    assert TaskStatus.ESCALATED.value == "escalated"


@pytest.mark.component
def test_review_layer_members():
    """ReviewLayer 包含 3 个层级"""
    assert len(ReviewLayer) == 3
    assert ReviewLayer.L1_STATIC.value == "static"


# ── 附加: TaskResult 模型 ─────────────────────────────────

@pytest.mark.component
def test_task_result_success_property():
    """TaskResult.success == (exit_code == 0)"""
    r_ok = TaskResult(task_id="T-1", exit_code=0)
    assert r_ok.success is True

    r_fail = TaskResult(task_id="T-2", exit_code=1)
    assert r_fail.success is False


# ── 附加: ReviewResult 模型 ───────────────────────────────

@pytest.mark.component
def test_review_result_fields():
    """ReviewResult 基本字段可读"""
    r = ReviewResult(
        passed=False, layer="contract",
        issues=["接口不一致"], fix_instruction="修复 API 签名",
        score=3.2, scores={"功能完整性": 3, "接口正确性": 3},
    )
    assert r.passed is False
    assert len(r.issues) == 1
    assert r.score == 3.2


# ── 附加: TestResult 模型 ─────────────────────────────────

@pytest.mark.component
def test_test_result_fields():
    """TestResult 基本字段"""
    tr = TestResult(passed=True, task_id="T-1", total=10,
                    passed_count=10, failed_count=0)
    assert tr.passed is True
    assert tr.total == 10


# ── 附加: MachineInfo 模型 ────────────────────────────────

@pytest.mark.component
def test_machine_info_defaults():
    """MachineInfo 默认值"""
    m = MachineInfo(machine_id="test01")
    assert m.status == MachineStatus.ONLINE
    assert m.port == 22
    assert m.current_task_id is None
    assert m.load["cpu_percent"] == 0.0


@pytest.mark.component
def test_machine_info_to_dict():
    """MachineInfo.to_dict() 包含所有关键字段"""
    m = MachineInfo(machine_id="gpu01", host="10.0.0.1",
                    user="dev", tags=["python", "gpu"])
    d = m.to_dict()
    assert d["machine_id"] == "gpu01"
    assert d["host"] == "10.0.0.1"
    assert "python" in d["tags"]
