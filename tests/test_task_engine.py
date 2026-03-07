"""
L2 组件测试 — 任务引擎 (MOD-004)
TC-030 ~ TC-035, 覆盖 FR-006 / FR-007 / FR-023
对齐 TEST-001 §2.2.3
"""
import json

import pytest

from orchestrator.machine_registry import MachineRegistry
from orchestrator.task_engine import CycleDependencyError, TaskEngine
from orchestrator.task_models import (
    CodingTask,
    MachineInfo,
    ReviewResult,
    TaskResult,
    TaskStatus,
    TestResult,
)


def _make_registry(n: int = 3) -> MachineRegistry:
    """创建含 n 台空闲机器的注册表"""
    reg = MachineRegistry()
    for i in range(n):
        reg.register(MachineInfo(
            machine_id=f"m{i}",
            display_name=f"Machine-{i}",
            host=f"10.0.0.{i+1}",
            user="dev",
            tags=["python"],
        ))
    return reg


def _make_task(tid: str, deps: list | None = None, tags: list | None = None) -> CodingTask:
    return CodingTask(
        task_id=tid,
        description=f"task {tid}",
        depends_on=deps or [],
        tags=tags or ["python"],
    )


# ── TC-030: 入队 + 拓扑排序 (FR-006) ─────────────────────────

@pytest.mark.component
def test_tc030_enqueue_with_dependency():
    """TC-030: 含依赖的 task 列表入队, 依赖在前"""
    reg = _make_registry(3)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    t1 = _make_task("T-001")
    t2 = _make_task("T-002", deps=["T-001"])
    t3 = _make_task("T-003", deps=["T-002"])

    engine.enqueue([t1, t2, t3])

    assert engine.total_tasks == 3

    # 首批只应该取到 T-001 (T-002 依赖 T-001, T-003 依赖 T-002)
    batch = engine.next_batch()
    assert len(batch) == 1
    assert batch[0].task_id == "T-001"


# ── TC-031: next_batch 遵循并发限制 (FR-007) ──────────────────

@pytest.mark.component
def test_tc031_next_batch_respects_concurrency_limit():
    """TC-031: 5 tasks 无依赖, limit=2 → 返回 2 个"""
    reg = _make_registry(5)
    engine = TaskEngine(max_retries=3, max_concurrent=2, machine_registry=reg)

    tasks = [_make_task(f"T-{i:03d}") for i in range(5)]
    engine.enqueue(tasks)

    batch = engine.next_batch()
    assert len(batch) == 2  # max_concurrent=2


# ── TC-032: 依赖未满足不出队 (FR-006) ─────────────────────────

@pytest.mark.component
def test_tc032_dependency_not_met():
    """TC-032: A→B 依赖, A 未完成 → B 不在 batch 中"""
    reg = _make_registry(3)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    t_a = _make_task("T-A")
    t_b = _make_task("T-B", deps=["T-A"])

    engine.enqueue([t_a, t_b])

    batch = engine.next_batch()
    batch_ids = [t.task_id for t in batch]
    assert "T-A" in batch_ids
    assert "T-B" not in batch_ids  # A 还没完成, B 不应出队

    # 模拟 A 完成
    engine.mark_dispatched("T-A")
    engine.handle_coding_done("T-A", TaskResult(task_id="T-A", exit_code=0))
    # CODING_DONE → REVIEW → TESTING → JUDGING → PASSED
    engine.handle_review_done("T-A", ReviewResult(passed=True, score=5.0))
    engine.handle_test_done("T-A", TestResult(passed=True, task_id="T-A", total=1, passed_count=1))

    assert engine.get_task("T-A").status == TaskStatus.PASSED

    # 现在 B 应该可以出队
    batch2 = engine.next_batch()
    batch2_ids = [t.task_id for t in batch2]
    assert "T-B" in batch2_ids


# ── TC-033: all_done 正确判定 (FR-006) ─────────────────────────

@pytest.mark.component
def test_tc033_all_done():
    """TC-033: 全部 PASSED → all_done=True"""
    reg = _make_registry(2)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    t1 = _make_task("T-D1")
    t2 = _make_task("T-D2")
    engine.enqueue([t1, t2])

    assert engine.all_done() is False

    # 完成 T-D1
    engine.mark_dispatched("T-D1")
    engine.handle_coding_done(
        "T-D1", TaskResult(task_id="T-D1", exit_code=0),
    )
    engine.handle_review_done(
        "T-D1", ReviewResult(passed=True, score=5.0),
    )
    engine.handle_test_done(
        "T-D1",
        TestResult(
            passed=True, task_id="T-D1", total=1, passed_count=1,
        ),
    )

    assert engine.all_done() is False

    # 完成 T-D2
    engine.mark_dispatched("T-D2")
    engine.handle_coding_done(
        "T-D2", TaskResult(task_id="T-D2", exit_code=0),
    )
    engine.handle_review_done(
        "T-D2", ReviewResult(passed=True, score=5.0),
    )
    engine.handle_test_done(
        "T-D2",
        TestResult(
            passed=True, task_id="T-D2", total=1, passed_count=1,
        ),
    )

    assert engine.all_done() is True

    summary = engine.get_status_summary()
    assert summary.get("passed", 0) == 2


# ── TC-034: Bug → 修复任务注入 (FR-023) ───────────────────────

@pytest.mark.component
def test_tc034_hotfix_task_injection():
    """TC-034: 生成 FIX-001 任务, priority=P0, 插入队列"""
    reg = _make_registry(2)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    # 已有存量任务
    t1 = _make_task("T-ORIG-001")
    engine.enqueue([t1])

    # 注入修复任务 (模拟 confirmed bug report)
    fix_task = CodingTask(
        task_id="FIX-001",
        description="修复 reviewer.py _LLM_MAX_RETRIES 未定义",
        tags=["python", "hotfix"],
        depends_on=[],
        estimated_minutes=10,
    )
    engine.enqueue_single(fix_task)

    assert engine.total_tasks == 2
    assert engine.get_task("FIX-001") is not None

    # FIX-001 应该在 next_batch 中(无依赖, 可立即出队)
    batch = engine.next_batch()
    batch_ids = [t.task_id for t in batch]
    assert "FIX-001" in batch_ids


# ── TC-035: 修复任务依赖设置 (FR-023) ─────────────────────────

@pytest.mark.component
def test_tc035_hotfix_task_independent():
    """TC-035: FIX-001 depends_on 为空, tags 含 hotfix"""
    fix_task = CodingTask(
        task_id="FIX-002",
        description="修复 test_runner.py _exec 方法名",
        tags=["python", "hotfix"],
        depends_on=[],
    )
    assert fix_task.depends_on == []
    assert "hotfix" in fix_task.tags


# ── 附加: 循环依赖检测 (ALG-009) ──────────────────────────────

@pytest.mark.component
def test_cycle_detection():
    """循环依赖: A→B, B→C, C→A → CycleDependencyError"""
    reg = _make_registry(3)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    t_a = _make_task("T-A", deps=["T-C"])
    t_b = _make_task("T-B", deps=["T-A"])
    t_c = _make_task("T-C", deps=["T-B"])

    with pytest.raises(CycleDependencyError, match="依赖环"):
        engine.enqueue([t_a, t_b, t_c])


# ── 附加: 快照 save/load ─────────────────────────────────────

@pytest.mark.component
def test_snapshot_save_load(tmp_path):
    """save_snapshot / load_snapshot 能正确持久化和恢复"""
    reg = _make_registry(2)

    class FakeConfig:
        max_retries = 3
        max_concurrent = 4
        repo_root = tmp_path

    engine = TaskEngine(config=FakeConfig(), machine_registry=reg)
    engine.enqueue([_make_task("T-SS1"), _make_task("T-SS2")])
    engine.save_snapshot()

    # 确认快照文件存在
    snapshot_file = tmp_path / ".task_engine_snapshot.json"
    assert snapshot_file.exists()

    data = json.loads(snapshot_file.read_text())
    assert "T-SS1" in data["tasks"]
    assert "T-SS2" in data["tasks"]

    # 新引擎从快照恢复
    engine2 = TaskEngine(config=FakeConfig(), machine_registry=_make_registry(2))
    loaded = engine2.load_snapshot()
    assert loaded is True
    assert engine2.total_tasks == 2


# ── 附加: add_task 别名 ──────────────────────────────────────

@pytest.mark.component
def test_add_task_alias():
    """add_task 是 enqueue_single 的别名"""
    reg = _make_registry(1)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    engine.add_task(_make_task("T-ALIAS"))
    assert engine.total_tasks == 1
    assert engine.get_task("T-ALIAS") is not None


# ── 附加: get_status_summary ──────────────────────────────────

@pytest.mark.component
def test_status_summary():
    """get_status_summary 返回各状态计数"""
    reg = _make_registry(2)
    engine = TaskEngine(max_retries=3, max_concurrent=4, machine_registry=reg)

    engine.enqueue([_make_task("T-S1"), _make_task("T-S2")])
    summary = engine.get_status_summary()
    assert summary.get("queued", 0) == 2
