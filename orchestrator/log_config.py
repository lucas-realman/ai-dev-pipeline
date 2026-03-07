"""
AutoDev Pipeline — 日志标准化 (NFR-013)
统一日志格式: [module] level message
支持 JSON 日志模式 (LOG_FORMAT=json)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional


class JsonFormatter(logging.Formatter):
    """JSON 结构化日志格式器 (NFR-013, TC-120)"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        # 附加上下文字段
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        if hasattr(record, "sprint_id"):
            log_entry["sprint_id"] = record.sprint_id
        if hasattr(record, "machine_id"):
            log_entry["machine_id"] = record.machine_id
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        # 异常信息
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class StandardFormatter(logging.Formatter):
    """标准文本日志格式器: [module] level message"""

    FORMAT = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)


def setup_logging(
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """
    配置全局日志 (NFR-013)

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR), 默认从 LOG_LEVEL 环境变量
        log_format: "json" | "text", 默认从 LOG_FORMAT 环境变量
        log_file: 日志文件路径, 可选
    """
    level = level or os.environ.get("LOG_LEVEL", "INFO")
    log_format = log_format or os.environ.get("LOG_FORMAT", "text")

    root = logging.getLogger("orchestrator")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除现有 handlers
    root.handlers.clear()

    # 选择格式器
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = StandardFormatter()

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # 文件 handler (可选)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.info("日志初始化完成: level=%s, format=%s", level, log_format)
