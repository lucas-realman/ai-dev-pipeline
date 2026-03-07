"""
L2 组件测试 — Dashboard API (DD-MOD-014, NFR-015)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orchestrator.dashboard import (
    _get_machines_summary,
    _get_tasks_summary,
    _state,
    app,
    register_orchestrator,
)
from orchestrator.task_models import CodingTask, MachineInfo, MachineStatus, TaskStatus

# ── Fixtures ─────────────────────────────────────────────


class FakeOrchestrator:
    """精简版 Orchestrator 供 Dashboard 测试"""

    def __init__(self, machines=None, tasks=None):
        self.registry = FakeRegistry(machines or [])
        self.engine = FakeEngine(tasks or [])


class FakeRegistry:
    def __init__(self, machines):
        self._machines = machines

    def get_all_machines(self):
        return self._machines


class FakeEngine:
    def __init__(self, tasks):
        self._tasks = {}
        for t in tasks:
            sm = MagicMock()
            self._tasks[t.task_id] = (t, sm)


# ── register_orchestrator ────────────────────────


@pytest.mark.component
def test_register_orchestrator():
    """register_orchestrator 注入实例"""
    fake = FakeOrchestrator()
    old = _state.get("orchestrator")
    try:
        register_orchestrator(fake)
        assert _state["orchestrator"] is fake
    finally:
        _state["orchestrator"] = old


# ── /api/status (有 orchestrator) ────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_status_with_orchestrator():
    """/api/status 注册 Orchestrator 后返回聚合数据"""
    from httpx import ASGITransport, AsyncClient

    m1 = MachineInfo(machine_id="m1", host="10.0.0.1", user="dev", tags=["gpu"])
    m1.status = MachineStatus.ONLINE
    m2 = MachineInfo(machine_id="m2", host="10.0.0.2", user="dev", tags=["cpu"])
    m2.status = MachineStatus.BUSY

    t1 = CodingTask(task_id="T1", description="d1", tags=["gpu"])
    t1.status = TaskStatus.PASSED
    t2 = CodingTask(task_id="T2", description="d2", tags=["cpu"])
    t2.status = TaskStatus.QUEUED

    fake = FakeOrchestrator(machines=[m1, m2], tasks=[t1, t2])
    old = _state.get("orchestrator")
    _state["orchestrator"] = fake

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["machines"]["total"] == 2
        assert data["machines"]["online"] == 1
        assert data["machines"]["busy"] == 1
        assert data["tasks"]["total"] == 2
        assert data["tasks"]["passed"] == 1
        assert data["tasks"]["queued"] == 1
    finally:
        _state["orchestrator"] = old


@pytest.mark.component
@pytest.mark.asyncio
async def test_machines_with_orchestrator():
    """/api/machines 返回详细机器信息"""
    from httpx import ASGITransport, AsyncClient

    m1 = MachineInfo(machine_id="gpu1", display_name="GPU-4090",
                     host="10.0.0.1", user="dev", tags=["gpu", "cuda"])
    m1.status = MachineStatus.ONLINE
    m1.current_task_id = None

    fake = FakeOrchestrator(machines=[m1])
    old = _state.get("orchestrator")
    _state["orchestrator"] = fake

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/machines")

        data = resp.json()
        assert len(data["machines"]) == 1
        assert data["machines"][0]["machine_id"] == "gpu1"
        assert data["machines"][0]["tags"] == ["gpu", "cuda"]
        assert data["machines"][0]["status"] == "online"
    finally:
        _state["orchestrator"] = old


@pytest.mark.component
@pytest.mark.asyncio
async def test_tasks_with_orchestrator():
    """/api/tasks 返回详细任务信息"""
    from httpx import ASGITransport, AsyncClient

    t1 = CodingTask(task_id="T-100", description="实现核心模块", tags=["python"])
    t1.status = TaskStatus.DISPATCHED
    t1.assigned_machine = "gpu1"

    fake = FakeOrchestrator(tasks=[t1])
    old = _state.get("orchestrator")
    _state["orchestrator"] = fake

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tasks")

        data = resp.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == "T-100"
        assert data["tasks"][0]["status"] == "dispatched"
    finally:
        _state["orchestrator"] = old


# ── _get_machines_summary ────────────────────────


@pytest.mark.component
def test_get_machines_summary():
    """聚合机器状态统计"""
    m1 = MachineInfo(machine_id="m1", host="h1", user="u", tags=[])
    m1.status = MachineStatus.ONLINE
    m2 = MachineInfo(machine_id="m2", host="h2", user="u", tags=[])
    m2.status = MachineStatus.BUSY
    m3 = MachineInfo(machine_id="m3", host="h3", user="u", tags=[])
    m3.status = MachineStatus.OFFLINE
    m4 = MachineInfo(machine_id="m4", host="h4", user="u", tags=[])
    m4.status = MachineStatus.ERROR

    fake = FakeOrchestrator(machines=[m1, m2, m3, m4])
    result = _get_machines_summary(fake)

    assert result["total"] == 4
    assert result["online"] == 1
    assert result["busy"] == 1
    assert result["offline"] == 2  # OFFLINE + ERROR


# ── _get_tasks_summary ───────────────────────────


@pytest.mark.component
def test_get_tasks_summary_all_statuses():
    """聚合所有任务状态"""
    tasks = []
    for status, tid in [
        (TaskStatus.QUEUED, "T1"),
        (TaskStatus.DISPATCHED, "T2"),
        (TaskStatus.CODING_DONE, "T3"),
        (TaskStatus.REVIEW, "T4"),
        (TaskStatus.TESTING, "T5"),
        (TaskStatus.PASSED, "T6"),
        (TaskStatus.FAILED, "T7"),
        (TaskStatus.ESCALATED, "T8"),
    ]:
        t = CodingTask(task_id=tid, description=f"d-{tid}", tags=[])
        t.status = status
        tasks.append(t)

    fake = FakeOrchestrator(tasks=tasks)
    result = _get_tasks_summary(fake)

    assert result["total"] == 8
    assert result["queued"] == 1
    assert result["in_progress"] == 4  # dispatched + coding + reviewing + testing
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["escalated"] == 1
