"""
基础冒烟测试 — 验证所有模块可正常导入 + 核心 API 正确
v3.0: 对齐 DD-MOD-005 / DD-MOD-006 / DD-MOD-004 新 API
"""
import importlib

import pytest

# ═══════════════════════════════════════════════════════════
#  导入 & 版本
# ═══════════════════════════════════════════════════════════

@pytest.mark.smoke
def test_import_all_modules():
    """所有 orchestrator 子模块都能正常 import"""
    modules = [
        "orchestrator",
        "orchestrator.task_models",
        "orchestrator.machine_registry",
        "orchestrator.config",
        "orchestrator.doc_analyzer",
        "orchestrator.doc_parser",
        "orchestrator.state_machine",
        "orchestrator.task_engine",
        "orchestrator.dispatcher",
        "orchestrator.reviewer",
        "orchestrator.reporter",
        "orchestrator.git_ops",
        "orchestrator.test_runner",
        "orchestrator.main",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"Failed to import {mod_name}"


@pytest.mark.smoke
def test_version():
    import orchestrator
    assert orchestrator.__version__ == "3.0.0"


# ═══════════════════════════════════════════════════════════
#  task_models (DD-MOD-005)
# ═══════════════════════════════════════════════════════════

@pytest.mark.smoke
def test_task_models_basic():
    """CodingTask / MachineInfo 创建 + 默认值"""
    from orchestrator.task_models import CodingTask, MachineInfo, MachineStatus, TaskStatus

    t = CodingTask(
        task_id="T-001",
        description="Test task",
        target_dir="src/core",
        tags=["gpu", "backend"],
    )
    assert t.task_id == "T-001"
    assert t.status == TaskStatus.CREATED    # v3.0: 默认 CREATED
    assert t.tags == ["gpu", "backend"]
    assert t.effective_machine is None

    m = MachineInfo(
        machine_id="m1",
        display_name="GPU Box",
        host="10.0.0.1",
        user="dev",
    )
    assert m.port == 22
    assert m.status == MachineStatus.ONLINE
    assert m.tags == []
    assert m.current_task_id is None
    assert m.busy_since is None


@pytest.mark.smoke
def test_task_id_validation():
    """CodingTask.__post_init__ 校验非法字段 (DD-MOD-005 §3.2)"""
    from orchestrator.task_models import CodingTask

    with pytest.raises(ValueError, match="task_id 包含非法字符"):
        CodingTask(task_id="T 001; rm -rf /", description="bad")

    with pytest.raises(ValueError, match="target_dir 禁止路径遍历"):
        CodingTask(task_id="T-002", description="bad", target_dir="../../etc")

    # 合法 ID (含 / 和 .)
    t = CodingTask(task_id="T-001/sub.task", description="ok")
    assert t.task_id == "T-001/sub.task"


@pytest.mark.smoke
def test_review_layer_enum():
    """ReviewLayer 枚举映射 (DD-MOD-005 §2.2)"""
    from orchestrator.task_models import ReviewLayer

    assert ReviewLayer.L1_STATIC.value == "static"
    assert ReviewLayer.L2_CONTRACT.value == "contract"
    assert ReviewLayer.L3_QUALITY.value == "quality"


@pytest.mark.smoke
def test_task_result_success():
    """TaskResult.success 属性 (DD-MOD-005 §4)"""
    from orchestrator.task_models import TaskResult

    r_ok = TaskResult(task_id="T-R1", exit_code=0)
    assert r_ok.success is True

    r_fail = TaskResult(task_id="T-R2", exit_code=1, stderr="error")
    assert r_fail.success is False


@pytest.mark.smoke
def test_coding_task_serialization():
    """CodingTask.to_dict / from_dict 往返"""
    from orchestrator.task_models import CodingTask, TaskStatus

    t = CodingTask(task_id="T-S1", description="serialize test", tags=["gpu"])
    d = t.to_dict()
    assert d["task_id"] == "T-S1"
    assert d["status"] == "created"

    t2 = CodingTask.from_dict(d)
    assert t2.task_id == t.task_id
    assert t2.status == TaskStatus.CREATED


# ═══════════════════════════════════════════════════════════
#  machine_registry (DD-MOD-003)
# ═══════════════════════════════════════════════════════════

@pytest.mark.smoke
def test_machine_registry_basic():
    """MachineRegistry 注册 / 查询 / 状态管理"""
    from orchestrator.machine_registry import MachineRegistry
    from orchestrator.task_models import MachineInfo, MachineStatus

    reg = MachineRegistry()
    m1 = MachineInfo(machine_id="m1", display_name="M1", host="10.0.0.1", user="u", tags=["gpu"])
    m2 = MachineInfo(machine_id="m2", display_name="M2", host="10.0.0.2", user="u", tags=["cpu"])

    reg.register(m1)
    reg.register(m2)
    assert len(reg.get_idle_machines()) == 2

    matched = reg.match_machine(["gpu"])
    assert matched is not None
    assert "gpu" in matched.tags

    reg.set_busy("m1", "T-001")
    assert len(reg.get_idle_machines()) == 1
    busy = reg.get_busy_machines()
    assert len(busy) == 1
    assert busy[0].current_task_id == "T-001"
    assert busy[0].busy_since is not None

    reg.set_idle("m1")
    assert len(reg.get_idle_machines()) == 2

    # set_offline (DD-MOD-003)
    reg.set_offline("m2")
    assert reg.get_machine("m2").status == MachineStatus.OFFLINE
    assert len(reg.get_idle_machines()) == 1


# ═══════════════════════════════════════════════════════════
#  state_machine (DD-MOD-006)
# ═══════════════════════════════════════════════════════════

@pytest.mark.smoke
def test_state_machine_transitions():
    """TaskStateMachine 完整 happy-path 流转"""
    from orchestrator.state_machine import TaskStateMachine
    from orchestrator.task_models import (
        CodingTask,
        ReviewResult,
        TaskResult,
        TaskStatus,
        TestResult,
    )

    task = CodingTask(task_id="T-002", description="sm test", target_dir="src")

    # 跟踪回调
    transitions = []
    def on_change(tid, old, new):
        transitions.append((tid, old, new))

    sm = TaskStateMachine(task, on_state_change=on_change)
    assert task.status == TaskStatus.CREATED

    sm.enqueue()
    assert task.status == TaskStatus.QUEUED

    sm.dispatch()
    assert task.status == TaskStatus.DISPATCHED

    sm.coding_done(TaskResult(task_id="T-002", exit_code=0))
    assert task.status == TaskStatus.CODING_DONE

    sm.start_review()
    assert task.status == TaskStatus.REVIEW

    sm.review_done(ReviewResult(passed=True, score=4.5))
    assert task.status == TaskStatus.TESTING

    test_result = TestResult(passed=True, total=5, passed_count=5)
    sm.test_done(test_result)
    assert task.status == TaskStatus.JUDGING

    sm.judge(test_result)
    assert task.status == TaskStatus.PASSED

    # 验证回调被触发
    assert len(transitions) > 0
    assert transitions[0] == ("T-002", TaskStatus.CREATED, TaskStatus.QUEUED)


@pytest.mark.smoke
def test_state_machine_illegal_transition():
    """非法状态转换抛出 StateMachineError"""
    from orchestrator.state_machine import StateMachineError, TaskStateMachine
    from orchestrator.task_models import CodingTask

    task = CodingTask(task_id="T-003", description="illegal test")
    sm = TaskStateMachine(task)

    # CREATED → DISPATCHED 非法 (应先 → QUEUED)
    with pytest.raises(StateMachineError, match="非法状态转换"):
        sm.dispatch()


@pytest.mark.smoke
def test_state_machine_retry_flow():
    """Review 失败 → RETRY → 重新排队"""
    from orchestrator.state_machine import TaskStateMachine
    from orchestrator.task_models import (
        CodingTask,
        ReviewResult,
        TaskResult,
        TaskStatus,
    )

    task = CodingTask(task_id="T-004", description="retry test")
    sm = TaskStateMachine(task, max_retries=3)

    sm.enqueue()
    sm.dispatch()
    sm.coding_done(TaskResult(task_id="T-004", exit_code=0))
    assert task.status == TaskStatus.CODING_DONE

    sm.start_review()
    sm.review_done(ReviewResult(passed=False, issues=["代码风格不佳"], fix_instruction="修复缩进"))
    assert task.status == TaskStatus.RETRY

    sm.requeue()
    assert task.status == TaskStatus.QUEUED


# ═══════════════════════════════════════════════════════════
#  task_engine (DD-MOD-004)
# ═══════════════════════════════════════════════════════════

@pytest.mark.smoke
def test_task_engine_basic():
    """TaskEngine 入队 + next_batch + mark_dispatched"""
    from orchestrator.machine_registry import MachineRegistry
    from orchestrator.task_engine import TaskEngine
    from orchestrator.task_models import CodingTask, MachineInfo, TaskResult, TaskStatus

    reg = MachineRegistry()
    reg.register(MachineInfo(machine_id="m1", host="10.0.0.1", user="u", tags=["gpu"]))

    engine = TaskEngine(max_retries=3, max_concurrent=2, machine_registry=reg)

    t1 = CodingTask(task_id="T-010", description="task 10", tags=["gpu"])
    t2 = CodingTask(task_id="T-011", description="task 11", depends_on=["T-010"])

    engine.enqueue([t1, t2])

    # T-011 依赖 T-010, 第一批只有 T-010
    batch = engine.next_batch()
    assert len(batch) == 1
    assert batch[0].task_id == "T-010"

    engine.mark_dispatched("T-010")
    assert t1.status == TaskStatus.DISPATCHED

    # 编码完成
    engine.handle_coding_done("T-010", TaskResult(task_id="T-010", exit_code=0))
    assert t1.status == TaskStatus.CODING_DONE


@pytest.mark.smoke
def test_task_engine_add_task_alias():
    """add_task 是 enqueue_single 的别名"""
    from orchestrator.task_engine import TaskEngine
    from orchestrator.task_models import CodingTask, TaskStatus

    engine = TaskEngine()
    t = CodingTask(task_id="T-A1", description="alias test")
    engine.add_task(t)

    assert engine.total_tasks == 1
    task = engine.get_task("T-A1")
    assert task is not None
    assert task.status == TaskStatus.QUEUED  # enqueue 后变 QUEUED


@pytest.mark.smoke
def test_task_engine_cycle_detection():
    """检测循环依赖 (ALG-009)"""
    from orchestrator.task_engine import CycleDependencyError, TaskEngine
    from orchestrator.task_models import CodingTask

    engine = TaskEngine()

    t1 = CodingTask(task_id="T-C1", description="c1", depends_on=["T-C2"])
    t2 = CodingTask(task_id="T-C2", description="c2", depends_on=["T-C1"])

    with pytest.raises(CycleDependencyError, match="依赖环"):
        engine.enqueue([t1, t2])
