"""
L2 组件测试 — 报告与通知 (MOD-010)
TC-090 ~ TC-094, 覆盖 FR-020 / FR-021
对齐 TEST-001 §2.2.10
"""
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.reporter import Reporter
from orchestrator.task_models import CodingTask, ReviewResult, TaskStatus, TestResult


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.project_name = "test-project"
    cfg.get.side_effect = lambda key, default=None: {
        "notification.dingtalk_webhook": "",
        "notification.dingtalk_webhook_secret": "",
        "notification.dingtalk_app_key": "",
        "notification.dingtalk_app_secret": "",
        "notification.dingtalk_robot_code": "",
        "notification.dingtalk_conversation_id": "",
        "notification.at_mobiles": [],
        "notification.at_all": False,
    }.get(key, default)
    return cfg


def _make_tasks(n: int = 3) -> list:
    tasks = []
    for i in range(n):
        t = CodingTask(
            task_id=f"T-R-{i:03d}",
            description=f"报告测试任务 {i}",
            tags=["python"],
        )
        if i < 2:
            t.status = TaskStatus.PASSED
        else:
            t.status = TaskStatus.ESCALATED
        tasks.append(t)
    return tasks


# ── TC-090: generate_report (FR-020) ─────────────────────

@pytest.mark.component
def test_tc090_generate_report(tmp_path):
    """TC-090: 生成 Markdown 报告, 文件可读"""
    cfg = _make_config(tmp_path)
    (tmp_path / "reports").mkdir()
    reporter = Reporter(cfg)

    tasks = _make_tasks()
    summary = {"total": 3, "passed": 2, "failed": 0, "escalated": 1}

    filepath = reporter.generate_report("S1", tasks, summary)
    assert Path(filepath).exists()

    content = Path(filepath).read_text(encoding="utf-8")
    assert "Sprint S1 报告" in content
    assert "test-project" in content
    assert "T-R-000" in content
    assert "通过: 2" in content


# ── TC-091: save_sprint_report 别名 (FR-020) ─────────────

@pytest.mark.component
def test_tc091_save_sprint_report_alias(tmp_path):
    """TC-091: save_sprint_report 是 generate_report 的别名"""
    cfg = _make_config(tmp_path)
    (tmp_path / "reports").mkdir()
    reporter = Reporter(cfg)

    tasks = _make_tasks(1)
    filepath = reporter.save_sprint_report("S2", tasks, {"total": 1})
    assert Path(filepath).exists()


# ── TC-092: DingTalk Webhook (FR-021, mock httpx) ────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc092_dingtalk_webhook(tmp_path):
    """TC-092: 钉钉 Webhook 发送 (mock httpx.post)"""
    cfg = _make_config(tmp_path)
    (tmp_path / "reports").mkdir()

    # 覆盖 get 以返回 webhook
    def mock_get(key, default=None):
        if key == "notification.dingtalk_webhook":
            return "https://oapi.dingtalk.com/robot/send?access_token=test"
        return default
    cfg.get.side_effect = mock_get

    reporter = Reporter(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("orchestrator.reporter.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        tasks = _make_tasks(2)
        await reporter.notify_sprint_start("S1", tasks)

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["msgtype"] == "markdown"


# ── TC-093: 无通知配置 → 跳过 (FR-021) ──────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc093_no_notification_config(tmp_path):
    """TC-093: 未配置钉钉 → 不发送, 不报错"""
    cfg = _make_config(tmp_path)
    (tmp_path / "reports").mkdir()
    reporter = Reporter(cfg)

    # 不应该抛异常
    await reporter.notify_sprint_start("S1", _make_tasks())
    await reporter.notify_error("test error")
    await reporter.notify_shutdown("test")


# ── TC-094: notify_task_result (FR-021) ──────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc094_notify_task_result(tmp_path):
    """TC-094: 任务结果通知构造正确"""
    cfg = _make_config(tmp_path)
    (tmp_path / "reports").mkdir()
    reporter = Reporter(cfg)

    task = CodingTask(task_id="T-NR", description="test", tags=["python"])
    task.status = TaskStatus.PASSED

    review = ReviewResult(passed=True, layer="quality", score=4.5)
    test = TestResult(passed=True, task_id="T-NR", total=5, passed_count=5)

    # 不报错即可 (无 webhook 时跳过)
    await reporter.notify_task_result(task, review=review, test=test)


# ── 附加: _elapsed 格式化 ────────────────────────────────

@pytest.mark.component
def test_elapsed_format(tmp_path):
    """_elapsed 返回人类可读时间"""
    cfg = _make_config(tmp_path)
    (tmp_path / "reports").mkdir()
    reporter = Reporter(cfg)
    reporter._start_time = time.time() - 3661  # 1h 1m 1s

    elapsed = reporter._elapsed()
    assert "1h" in elapsed
    assert "1m" in elapsed
