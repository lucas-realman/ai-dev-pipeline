"""
L2 组件测试 — 主编排器 & CLI (MOD-013)
追加 TC, 覆盖 Orchestrator / build_parser / _discover_tasks / _compute_summary
对齐 TEST-001 §2.2
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from orchestrator.main import Orchestrator, build_parser, MAX_ROUNDS
from orchestrator.task_models import CodingTask, TaskStatus, TaskResult, ReviewResult, TestResult


def _make_config(tmp_path: Path) -> MagicMock:
    """构建 mock Config"""
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.doc_set = []
    cfg.get_machines_list.return_value = [
        {"id": "m1", "host": "10.0.0.1", "user": "dev", "tags": ["gpu"]},
    ]
    cfg.get_machines.return_value = {}
    cfg.get.side_effect = lambda key, default=None: {
        "project.branch": "main",
        "git.remote": "origin",
        "git.sync_before_sprint": False,
        "git.auto_commit": False,
        "retry.max_review_retry": 2,
        "retry.max_test_retry": 2,
        "doc_parser.task_card": "",
    }.get(key, default)
    return cfg


def _make_task(tid="T001", status=TaskStatus.QUEUED):
    return CodingTask(
        task_id=tid,
        target_machine="m1",
        target_dir="agent/",
        description="test task",
    )


# ── TC: build_parser 基本参数 ────────────────────────────

@pytest.mark.component
def test_build_parser_defaults():
    """build_parser 返回有效的 ArgumentParser"""
    p = build_parser()
    args = p.parse_args([])
    assert args.config == "orchestrator/config.yaml"
    assert args.mode == "sprint"
    assert args.dry_run is False
    assert args.verbose is False


@pytest.mark.component
def test_build_parser_custom_args():
    """build_parser 自定义参数"""
    p = build_parser()
    args = p.parse_args([
        "-c", "custom.yaml",
        "--sprint-id", "S1",
        "--mode", "continuous",
        "--dry-run",
        "-v",
    ])
    assert args.config == "custom.yaml"
    assert args.sprint_id == "S1"
    assert args.mode == "continuous"
    assert args.dry_run is True
    assert args.verbose is True


# ── TC: Orchestrator 初始化 (mock 所有子模块) ────────────

@pytest.mark.component
def test_orchestrator_init(tmp_path):
    """Orchestrator.__init__ 正确连接所有子模块"""
    cfg = _make_config(tmp_path)

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.TaskEngine"), \
         patch("orchestrator.main.Dispatcher"), \
         patch("orchestrator.main.AutoReviewer"), \
         patch("orchestrator.main.TestRunner"), \
         patch("orchestrator.main.Reporter"), \
         patch("orchestrator.main.GitOps"):

        MockReg.return_value.load_from_config = MagicMock()
        orch = Orchestrator(cfg)

    assert orch.config is cfg
    assert orch._shutdown is False


# ── TC: _compute_summary ─────────────────────────────────

@pytest.mark.component
def test_compute_summary(tmp_path):
    """_compute_summary 正确统计各状态"""
    cfg = _make_config(tmp_path)

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.TaskEngine"), \
         patch("orchestrator.main.Dispatcher"), \
         patch("orchestrator.main.AutoReviewer"), \
         patch("orchestrator.main.TestRunner"), \
         patch("orchestrator.main.Reporter"), \
         patch("orchestrator.main.GitOps"):

        MockReg.return_value.load_from_config = MagicMock()
        orch = Orchestrator(cfg)

    tasks = [
        _make_task("T001"),
        _make_task("T002"),
        _make_task("T003"),
        _make_task("T004"),
    ]
    tasks[0].status = TaskStatus.PASSED
    tasks[1].status = TaskStatus.PASSED
    tasks[2].status = TaskStatus.FAILED
    tasks[3].status = TaskStatus.ESCALATED

    summary = orch._compute_summary(tasks)
    assert summary == {"total": 4, "passed": 2, "failed": 1, "escalated": 1}


# ── TC: _discover_tasks — DocAnalyzer 优先 ───────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_discover_tasks_analyzer_first(tmp_path):
    """doc_set 非空 → 使用 DocAnalyzer"""
    cfg = _make_config(tmp_path)
    cfg.doc_set = ["docs/**/*.md"]

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.TaskEngine"), \
         patch("orchestrator.main.Dispatcher"), \
         patch("orchestrator.main.AutoReviewer"), \
         patch("orchestrator.main.TestRunner"), \
         patch("orchestrator.main.Reporter"), \
         patch("orchestrator.main.GitOps"), \
         patch("orchestrator.main.DocAnalyzer") as MockAnalyzer:

        MockReg.return_value.load_from_config = MagicMock()
        orch = Orchestrator(cfg)

        mock_analyzer_inst = MockAnalyzer.return_value
        mock_analyzer_inst.analyze_and_decompose = AsyncMock(
            return_value=[_make_task("T001")]
        )

        tasks = await orch._discover_tasks()

    assert len(tasks) == 1
    assert tasks[0].task_id == "T001"


# ── TC: _discover_tasks — 回退 DocParser ─────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_discover_tasks_fallback_parser(tmp_path):
    """doc_set 为空 + task_card 设置 → 回退到 DocParser"""
    cfg = _make_config(tmp_path)
    cfg.doc_set = []
    # Override get to return a task card path
    original_get = cfg.get.side_effect

    def _get(key, default=None):
        if key == "doc_parser.task_card":
            return "docs/task_card.md"
        return original_get.get(key, default) if isinstance(original_get, dict) else default

    cfg.get.side_effect = _get

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.TaskEngine"), \
         patch("orchestrator.main.Dispatcher"), \
         patch("orchestrator.main.AutoReviewer"), \
         patch("orchestrator.main.TestRunner"), \
         patch("orchestrator.main.Reporter"), \
         patch("orchestrator.main.GitOps"), \
         patch("orchestrator.main.DocParser") as MockParser:

        MockReg.return_value.load_from_config = MagicMock()
        orch = Orchestrator(cfg)

        mock_parser_inst = MockParser.return_value
        mock_parser_inst.parse_task_card = MagicMock(
            return_value=[_make_task("T002")]
        )

        tasks = await orch._discover_tasks()

    assert len(tasks) == 1
    assert tasks[0].task_id == "T002"


# ── TC: _discover_tasks — 无任何来源 ─────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_discover_tasks_empty(tmp_path):
    """doc_set 空 + task_card 空 → 返回空列表"""
    cfg = _make_config(tmp_path)
    cfg.doc_set = []

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.TaskEngine"), \
         patch("orchestrator.main.Dispatcher"), \
         patch("orchestrator.main.AutoReviewer"), \
         patch("orchestrator.main.TestRunner"), \
         patch("orchestrator.main.Reporter"), \
         patch("orchestrator.main.GitOps"):

        MockReg.return_value.load_from_config = MagicMock()
        orch = Orchestrator(cfg)

        tasks = await orch._discover_tasks()

    assert tasks == []


# ── TC: MAX_ROUNDS 常量 ──────────────────────────────────

@pytest.mark.component
def test_max_rounds_value():
    """MAX_ROUNDS 必须是正整数"""
    assert MAX_ROUNDS > 0
    assert isinstance(MAX_ROUNDS, int)


# ── TC: _check_stale_busy ────────────────────────────────

@pytest.mark.component
def test_check_stale_busy(tmp_path):
    """超时机器被释放"""
    import time
    cfg = _make_config(tmp_path)

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.TaskEngine"), \
         patch("orchestrator.main.Dispatcher"), \
         patch("orchestrator.main.AutoReviewer"), \
         patch("orchestrator.main.TestRunner"), \
         patch("orchestrator.main.Reporter"), \
         patch("orchestrator.main.GitOps"):

        mock_reg = MockReg.return_value
        mock_reg.load_from_config = MagicMock()

        stale_machine = MagicMock()
        stale_machine.machine_id = "m1"
        stale_machine.busy_since = time.time() - 3600  # 1小时前
        mock_reg.get_busy_machines.return_value = [stale_machine]

        orch = Orchestrator(cfg)
        orch._check_stale_busy(stale_timeout=1800.0)

    mock_reg.set_idle.assert_called_once_with("m1")
