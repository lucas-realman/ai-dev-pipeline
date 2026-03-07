"""
L2 组件测试 — 状态机 (MOD-009)
TC-010 ~ TC-015, 覆盖 FR-014 / FR-015
对齐 TEST-001 §2.2.1
"""
import pytest

from orchestrator.state_machine import StateMachineError, TaskStateMachine
from orchestrator.task_models import (
    CodingTask,
    ReviewResult,
    TaskResult,
    TaskStatus,
    TestResult,
)


def _make_task(task_id: str = "T-SM-001") -> CodingTask:
    return CodingTask(task_id=task_id, description="state machine test")


# ── TC-010: 正常全路径 CREATED → PASSED (FR-014) ─────────────

@pytest.mark.component
def test_tc010_happy_path_created_to_passed():
    """TC-010: 依次调用 enqueue/dispatch/.../judge → status=PASSED"""
    task = _make_task()
    sm = TaskStateMachine(task, max_retries=3)

    assert task.status == TaskStatus.CREATED

    sm.enqueue()
    assert task.status == TaskStatus.QUEUED

    sm.dispatch()
    assert task.status == TaskStatus.DISPATCHED
    assert task.started_at is not None

    sm.coding_done(TaskResult(task_id=task.task_id, exit_code=0))
    assert task.status == TaskStatus.CODING_DONE

    sm.start_review()
    assert task.status == TaskStatus.REVIEW

    sm.review_done(ReviewResult(passed=True, score=5.0))
    assert task.status == TaskStatus.TESTING

    sm.test_done(TestResult(passed=True, task_id=task.task_id))
    assert task.status == TaskStatus.JUDGING

    sm.judge(TestResult(passed=True, task_id=task.task_id, total=5, passed_count=5))
    assert task.status == TaskStatus.PASSED
    assert task.finished_at is not None
    assert sm.is_terminal is True


# ── TC-011: 非法转换抛异常 (FR-015) ───────────────────────────

@pytest.mark.component
def test_tc011_illegal_transition_raises():
    """TC-011: QUEUED 直接调 judge() → StateMachineError"""
    task = _make_task("T-SM-011")
    sm = TaskStateMachine(task)

    sm.enqueue()
    assert task.status == TaskStatus.QUEUED

    # QUEUED 不能直接 judge
    with pytest.raises(StateMachineError, match="非法状态转换"):
        sm.judge(TestResult(passed=True))

    # CREATED 不能 dispatch
    task2 = _make_task("T-SM-011b")
    sm2 = TaskStateMachine(task2)
    with pytest.raises(StateMachineError, match="非法状态转换"):
        sm2.dispatch()

    # DISPATCHED 不能直接 start_review
    task3 = _make_task("T-SM-011c")
    sm3 = TaskStateMachine(task3)
    sm3.enqueue()
    sm3.dispatch()
    with pytest.raises(StateMachineError, match="非法状态转换"):
        sm3.start_review()


# ── TC-012: 重试计数 ≤3 触发 RETRY (FR-015) ───────────────────

@pytest.mark.component
def test_tc012_retry_within_limit():
    """TC-012: review_done(failed) 时 retries < max → RETRY"""
    task = _make_task("T-SM-012")
    sm = TaskStateMachine(task, max_retries=3)

    # 第 1 轮: CREATED → QUEUED → DISPATCHED → CODING_DONE → REVIEW → RETRY
    sm.enqueue()
    sm.dispatch()
    sm.coding_done(TaskResult(task_id=task.task_id, exit_code=0))
    sm.start_review()
    sm.review_done(ReviewResult(passed=False, issues=["issue1"], fix_instruction="fix it"))
    assert task.status == TaskStatus.RETRY
    assert task.review_retry == 1
    assert sm.is_retryable is True

    # 重新入队
    sm.requeue()
    assert task.status == TaskStatus.QUEUED
    assert task.retry_count == 1

    # 第 2 轮
    sm.dispatch()
    sm.coding_done(TaskResult(task_id=task.task_id, exit_code=0))
    sm.start_review()
    sm.review_done(ReviewResult(passed=False, issues=["issue2"]))
    assert task.status == TaskStatus.RETRY
    assert task.review_retry == 2

    sm.requeue()

    # 第 3 轮
    sm.dispatch()
    sm.coding_done(TaskResult(task_id=task.task_id, exit_code=0))
    sm.start_review()
    sm.review_done(ReviewResult(passed=False, issues=["issue3"]))
    # total_retries = review_retry(3) + test_retry(0) = 3 ≥ max_retries(3) → ESCALATED
    assert task.status == TaskStatus.ESCALATED


# ── TC-013: 重试超限触发 ESCALATED (FR-015) ────────────────────

@pytest.mark.component
def test_tc013_retry_exceeds_limit_escalated():
    """TC-013: handle_failure() 超过 max_retries → ESCALATED"""
    task = _make_task("T-SM-013")
    sm = TaskStateMachine(task, max_retries=2)

    sm.enqueue()
    sm.dispatch()
    sm.coding_done(TaskResult(task_id=task.task_id, exit_code=0))
    sm.start_review()
    sm.review_done(ReviewResult(passed=True, score=5.0))

    # TESTING → JUDGING → FAILED
    sm.test_done(TestResult(passed=False, task_id=task.task_id, failures=["fail1"]))
    sm.judge(TestResult(passed=False, task_id=task.task_id, failures=["fail1"]))
    assert task.status == TaskStatus.FAILED

    # 第 1 次 handle_failure → RETRY (total_retries=1 < 2)
    sm.handle_failure()
    assert task.status == TaskStatus.RETRY
    assert task.test_retry == 1
    sm.requeue()

    # 再走一轮
    sm.dispatch()
    sm.coding_done(TaskResult(task_id=task.task_id, exit_code=0))
    sm.start_review()
    sm.review_done(ReviewResult(passed=True, score=5.0))
    sm.test_done(TestResult(passed=False, task_id=task.task_id, failures=["fail2"]))
    sm.judge(TestResult(passed=False, task_id=task.task_id, failures=["fail2"]))

    # 第 2 次 handle_failure → total_retries=2 ≥ max(2) → ESCALATED
    sm.handle_failure()
    assert task.status == TaskStatus.ESCALATED
    assert sm.is_terminal is True


# ── TC-014: is_terminal 属性 (FR-014) ─────────────────────────

@pytest.mark.component
def test_tc014_is_terminal_property():
    """TC-014: PASSED 和 ESCALATED 都是终态"""
    # PASSED
    task_p = _make_task("T-SM-014a")
    sm_p = TaskStateMachine(task_p)
    sm_p.enqueue()
    sm_p.dispatch()
    sm_p.coding_done(TaskResult(task_id=task_p.task_id, exit_code=0))
    sm_p.start_review()
    sm_p.review_done(ReviewResult(passed=True, score=5.0))
    sm_p.test_done(TestResult(passed=True, task_id=task_p.task_id))
    sm_p.judge(TestResult(passed=True, task_id=task_p.task_id))
    assert sm_p.is_terminal is True

    # ESCALATED
    task_e = _make_task("T-SM-014b")
    sm_e = TaskStateMachine(task_e, max_retries=0)
    sm_e.enqueue()
    sm_e.dispatch()
    sm_e.coding_done(TaskResult(task_id=task_e.task_id, exit_code=1, stderr="error"))
    assert task_e.status == TaskStatus.ESCALATED
    assert sm_e.is_terminal is True


# ── TC-015: can_dispatch 属性 (FR-014) ────────────────────────

@pytest.mark.component
def test_tc015_can_dispatch_property():
    """TC-015: QUEUED → True; DISPATCHED → False"""
    task = _make_task("T-SM-015")
    sm = TaskStateMachine(task)

    # CREATED => 不可调度
    assert sm.can_dispatch is False

    sm.enqueue()
    assert sm.can_dispatch is True
    assert sm.is_waiting is True

    sm.dispatch()
    assert sm.can_dispatch is False
    assert sm.is_waiting is False


# ── 附加: 回调触发测试 ────────────────────────────────────────

@pytest.mark.component
def test_state_change_callback_triggered():
    """验证 on_state_change 回调在每次转换时被调用"""
    transitions = []

    def on_change(tid, old, new):
        transitions.append((tid, old.value, new.value))

    task = _make_task("T-SM-CB")
    sm = TaskStateMachine(task, on_state_change=on_change)

    sm.enqueue()
    sm.dispatch()

    assert len(transitions) == 2
    assert transitions[0] == ("T-SM-CB", "created", "queued")
    assert transitions[1] == ("T-SM-CB", "queued", "dispatched")


@pytest.mark.component
def test_callback_exception_does_not_break_transition():
    """on_state_change 回调抛异常不应阻断状态转换"""

    def bad_callback(tid, old, new):
        raise RuntimeError("callback error")

    task = _make_task("T-SM-CBE")
    sm = TaskStateMachine(task, on_state_change=bad_callback)

    sm.enqueue()  # 即使回调异常, 状态仍应变为 QUEUED
    assert task.status == TaskStatus.QUEUED
