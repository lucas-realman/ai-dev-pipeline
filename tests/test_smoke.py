"""
基础冒烟测试 — 验证所有模块可正常导入
"""
import importlib


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


def test_version():
    import orchestrator
    assert orchestrator.__version__ == "3.0.0"


def test_task_models_basic():
    from orchestrator.task_models import CodingTask, MachineInfo, MachineStatus, TaskStatus

    t = CodingTask(
        task_id="T-001",
        description="Test task",
        target_dir="src/core",
        tags=["gpu", "backend"],
    )
    assert t.task_id == "T-001"
    assert t.status == TaskStatus.QUEUED
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


def test_machine_registry_basic():
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
    reg.set_idle("m1")
    assert len(reg.get_idle_machines()) == 2


def test_state_machine_transitions():
    from orchestrator.state_machine import TaskStateMachine
    from orchestrator.task_models import CodingTask, TaskStatus

    sm = TaskStateMachine()
    task = CodingTask(task_id="T-002", description="sm test", target_dir="src")

    sm.enqueue(task)
    assert task.status == TaskStatus.QUEUED

    sm.dispatch(task)
    assert task.status == TaskStatus.CODING

    sm.coding_done(task)
    assert task.status == TaskStatus.CODED

    sm.review_done(task, passed=True)
    assert task.status == TaskStatus.TESTING

    sm.test_done(task, passed=True)
    assert task.status == TaskStatus.JUDGING

    sm.judge(task, passed=True)
    assert task.status == TaskStatus.PASSED
