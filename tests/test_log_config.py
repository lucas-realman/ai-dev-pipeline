"""
L2 组件测试 — 日志标准化 (NFR-013)
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from orchestrator.log_config import JsonFormatter, StandardFormatter, setup_logging


# ── JsonFormatter ────────────────────────────────


@pytest.mark.component
def test_json_formatter_basic():
    """JSON 格式器基本输出"""
    fmt = JsonFormatter()
    record = logging.LogRecord(
        "orchestrator.test", logging.INFO,
        "test.py", 1, "hello world", None, None,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["module"] == "orchestrator.test"
    assert data["message"] == "hello world"
    assert "timestamp" in data


@pytest.mark.component
def test_json_formatter_with_context_fields():
    """JSON 格式器附加上下文字段"""
    fmt = JsonFormatter()
    record = logging.LogRecord(
        "orchestrator.main", logging.WARNING,
        "main.py", 42, "任务分发", None, None,
    )
    record.task_id = "T-001"
    record.sprint_id = "sprint-1"
    record.machine_id = "gpu1"
    record.event = "dispatch"

    output = fmt.format(record)
    data = json.loads(output)
    assert data["task_id"] == "T-001"
    assert data["sprint_id"] == "sprint-1"
    assert data["machine_id"] == "gpu1"
    assert data["event"] == "dispatch"


@pytest.mark.component
def test_json_formatter_with_exception():
    """JSON 格式器包含异常信息"""
    fmt = JsonFormatter()
    try:
        raise ValueError("测试异常")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        "orchestrator.error", logging.ERROR,
        "error.py", 10, "发生错误", None, exc_info,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert "exception" in data
    assert "ValueError" in data["exception"]


# ── StandardFormatter ────────────────────────────


@pytest.mark.component
def test_standard_formatter():
    """标准文本格式器"""
    fmt = StandardFormatter()
    record = logging.LogRecord(
        "orchestrator.main", logging.ERROR,
        "main.py", 99, "严重错误", None, None,
    )
    output = fmt.format(record)
    assert "[orchestrator.main]" in output
    assert "ERROR" in output
    assert "严重错误" in output


# ── setup_logging ────────────────────────────────


@pytest.mark.component
def test_setup_logging_text():
    """setup_logging 配置文本日志"""
    setup_logging(level="DEBUG", log_format="text")

    root = logging.getLogger("orchestrator")
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1
    assert isinstance(root.handlers[0].formatter, StandardFormatter)

    # 清理
    root.handlers.clear()


@pytest.mark.component
def test_setup_logging_json():
    """setup_logging 配置 JSON 日志"""
    setup_logging(level="WARNING", log_format="json")

    root = logging.getLogger("orchestrator")
    assert root.level == logging.WARNING
    assert isinstance(root.handlers[0].formatter, JsonFormatter)

    root.handlers.clear()


@pytest.mark.component
def test_setup_logging_with_file(tmp_path):
    """setup_logging 配置文件输出"""
    log_file = str(tmp_path / "test.log")
    setup_logging(level="INFO", log_format="text", log_file=log_file)

    root = logging.getLogger("orchestrator")
    # 应有 2 个 handler: console + file
    assert len(root.handlers) >= 2

    # 写入一条日志
    root.info("文件日志测试")

    # 刷新并检查文件
    for h in root.handlers:
        h.flush()

    content = Path(log_file).read_text(encoding="utf-8")
    assert "文件日志测试" in content

    root.handlers.clear()


@pytest.mark.component
def test_setup_logging_env_defaults():
    """setup_logging 从环境变量读取默认值"""
    old_level = os.environ.get("LOG_LEVEL")
    old_format = os.environ.get("LOG_FORMAT")

    os.environ["LOG_LEVEL"] = "ERROR"
    os.environ["LOG_FORMAT"] = "json"

    try:
        setup_logging()
        root = logging.getLogger("orchestrator")
        assert root.level == logging.ERROR
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        if old_level is None:
            os.environ.pop("LOG_LEVEL", None)
        else:
            os.environ["LOG_LEVEL"] = old_level
        if old_format is None:
            os.environ.pop("LOG_FORMAT", None)
        else:
            os.environ["LOG_FORMAT"] = old_format

        logging.getLogger("orchestrator").handlers.clear()
