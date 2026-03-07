"""
L2 组件测试 — 测试运行器 (MOD-009)
TC-080 ~ TC-083, 覆盖 FR-018 / FR-019 / ALG-017 / ALG-018
对齐 TEST-001 §2.2.9
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.test_runner import AcceptanceCriterion, TestRunner
from orchestrator.task_models import CodingTask, TestResult


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.get.side_effect = lambda key, default=None: {
        "test.fallback_threshold": 0.8,
        "test.timeout_sec": 60,
    }.get(key, default)
    return cfg


def _make_task(tid: str = "T-TR-001", module: str = "example") -> CodingTask:
    return CodingTask(
        task_id=tid,
        description="测试运行器测试",
        module_name=module,
        tags=["python"],
        target_dir="src/example",
    )


# ── TC-080: JSON 报告解析 (FR-018) ──────────────────────

@pytest.mark.component
def test_tc080_parse_json_report(tmp_path):
    """TC-080: pytest-json-report 正确解析"""
    cfg = _make_config(tmp_path)
    (tmp_path / "tests").mkdir()
    runner = TestRunner(cfg, repo_root=tmp_path)

    report = {
        "summary": {"total": 5, "passed": 4, "failed": 1, "error": 0},
        "duration": 3.5,
        "tests": [
            {"nodeid": "test_a::test_1", "outcome": "passed"},
            {"nodeid": "test_a::test_2", "outcome": "passed"},
            {"nodeid": "test_a::test_3", "outcome": "passed"},
            {"nodeid": "test_a::test_4", "outcome": "passed"},
            {
                "nodeid": "test_a::test_5",
                "outcome": "failed",
                "call": {"crash": {"message": "AssertionError"}},
            },
        ],
    }

    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report), encoding="utf-8")

    result = runner._parse_json_report("T-080", report_file)
    assert result.total == 5
    assert result.passed_count == 4
    assert result.failed_count == 1
    assert result.passed is False


# ── TC-081: stdout 解析 (FR-018) ─────────────────────────

@pytest.mark.component
def test_tc081_parse_pytest_output(tmp_path):
    """TC-081: 无 JSON 报告时从 stdout 解析"""
    cfg = _make_config(tmp_path)
    (tmp_path / "tests").mkdir()
    runner = TestRunner(cfg, repo_root=tmp_path)

    output = """
============================= test session starts ==============================
collected 10 items
test_foo.py ........F.
================================ FAILURES ======================================
FAILED test_foo.py::test_bad - AssertionError
========================= 9 passed, 1 failed in 2.30s =========================
"""
    result = runner._parse_pytest_output("T-081", output, returncode=1)
    assert result.passed_count == 9
    assert result.failed_count == 1
    assert result.passed is False


# ── TC-082: 测试文件发现策略 (ALG-018) ──────────────────

@pytest.mark.component
def test_tc082_discover_test_files_exact_match(tmp_path):
    """TC-082a: 精确匹配 test_{safe_id}.py"""
    cfg = _make_config(tmp_path)
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_t_tr_001.py").write_text("# test file")

    runner = TestRunner(cfg, repo_root=tmp_path)
    task = _make_task("T-TR-001")

    files = runner._discover_test_files(task)
    assert len(files) == 1
    assert files[0].name == "test_t_tr_001.py"


@pytest.mark.component
def test_tc082b_discover_by_module_name(tmp_path):
    """TC-082b: module_name 匹配 test_{module}.py"""
    cfg = _make_config(tmp_path)
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_auth.py").write_text("# auth tests")

    runner = TestRunner(cfg, repo_root=tmp_path)
    task = CodingTask(
        task_id="T-MOD-001", description="test",
        module_name="auth", tags=["python"],
    )

    files = runner._discover_test_files(task)
    assert len(files) == 1
    assert files[0].name == "test_auth.py"


@pytest.mark.component
def test_tc082c_no_test_files(tmp_path):
    """TC-082c: 无测试文件 → 空列表"""
    cfg = _make_config(tmp_path)
    test_dir = tmp_path / "tests"
    test_dir.mkdir()

    runner = TestRunner(cfg, repo_root=tmp_path)
    task = _make_task("T-NONE-001")

    files = runner._discover_test_files(task)
    assert files == []


# ── TC-083: run_tests 无测试文件 → 自动通过 (FR-019) ────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc083_no_test_auto_pass(tmp_path):
    """TC-083: 无测试文件 → 默认通过 (passed=True, total=0)"""
    cfg = _make_config(tmp_path)
    (tmp_path / "tests").mkdir()
    runner = TestRunner(cfg, repo_root=tmp_path)
    task = _make_task("T-NF-001")

    result = await runner.run_tests(task)
    assert result.passed is True
    assert result.total == 0


# ── 附加: fallback threshold 降级通过 (Bug17) ────────────

@pytest.mark.component
def test_fallback_threshold(tmp_path):
    """pass_rate >= threshold → 降级通过"""
    cfg = _make_config(tmp_path)
    (tmp_path / "tests").mkdir()
    runner = TestRunner(cfg, repo_root=tmp_path)

    failing_result = TestResult(
        task_id="T-FB-001", passed=False,
        total=10, passed_count=9, failed_count=1,
    )
    criteria = [AcceptanceCriterion(criterion_id="AC1", description="test")]

    result = runner._apply_fallback_threshold(failing_result, criteria)
    assert result.passed is True
    assert "Fallback threshold" in result.details


@pytest.mark.component
def test_fallback_threshold_not_met(tmp_path):
    """pass_rate < threshold → 维持失败"""
    cfg = _make_config(tmp_path)
    (tmp_path / "tests").mkdir()
    runner = TestRunner(cfg, repo_root=tmp_path)

    failing_result = TestResult(
        task_id="T-FB-002", passed=False,
        total=10, passed_count=5, failed_count=5,
    )
    criteria = [AcceptanceCriterion(criterion_id="AC1", description="test")]

    result = runner._apply_fallback_threshold(failing_result, criteria)
    assert result.passed is False


# ── 附加: run_tests 完整流程 (mock pytest) ───────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_run_tests_with_mock(tmp_path):
    """run_tests mock 子进程, 验证端到端"""
    cfg = _make_config(tmp_path)
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_example.py").write_text("# test")

    runner = TestRunner(cfg, repo_root=tmp_path)
    task = _make_task(module="example")

    mock_output = "3 passed in 0.5s"
    with patch.object(
        runner, "_run_pytest",
        new_callable=AsyncMock,
        return_value=(mock_output, 0),
    ):
        result = await runner.run_tests(task)

    assert result.passed_count == 3
    assert result.passed is True
