"""
AutoDev Pipeline — Dashboard API (DD-MOD-014, NFR-015)
FastAPI 端点: /api/status — 机器/任务/测试状态查询。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import __version__

log = logging.getLogger("orchestrator.dashboard")

app = FastAPI(
    title="AutoDev Pipeline Dashboard",
    version=__version__,
    description="AI 自动化开发流水线 — 状态监控 API",
)

# ── 全局状态存储 (进程内共享) ────────────────────
# 由 Orchestrator 在运行期间注入
_state: Dict[str, Any] = {
    "start_time": time.time(),
    "orchestrator": None,  # Orchestrator 实例引用
}


def register_orchestrator(orch: Any) -> None:
    """注册 Orchestrator 实例到 Dashboard (进程内调用)"""
    _state["orchestrator"] = orch
    log.info("Dashboard 已注册 Orchestrator 实例")


# ── API 端点 ────────────────────────────────────


@app.get("/api/status")
async def get_status() -> JSONResponse:
    """
    系统全局状态 (NFR-015)
    返回: 版本、运行时间、机器/任务概要
    """
    uptime = time.time() - _state["start_time"]
    orch = _state.get("orchestrator")

    result: Dict[str, Any] = {
        "version": __version__,
        "status": "running",
        "uptime_seconds": round(uptime, 1),
        "timestamp": datetime.now().isoformat(),
    }

    if orch is not None:
        result["machines"] = _get_machines_summary(orch)
        result["tasks"] = _get_tasks_summary(orch)
    else:
        result["machines"] = {
            "total": 0, "online": 0, "busy": 0, "offline": 0,
        }
        result["tasks"] = {
            "total": 0, "queued": 0, "in_progress": 0,
            "passed": 0, "failed": 0, "escalated": 0,
        }

    return JSONResponse(content=result)


@app.get("/api/machines")
async def get_machines() -> JSONResponse:
    """机器池详细状态"""
    orch = _state.get("orchestrator")
    if orch is None:
        return JSONResponse(content={"machines": []})

    machines = []
    for m in orch.registry.get_all_machines():
        machines.append({
            "machine_id": m.machine_id,
            "display_name": m.display_name,
            "host": m.host,
            "status": m.status.value,
            "tags": m.tags,
            "current_task_id": m.current_task_id,
        })
    return JSONResponse(content={"machines": machines})


@app.get("/api/tasks")
async def get_tasks() -> JSONResponse:
    """任务列表详细状态"""
    orch = _state.get("orchestrator")
    if orch is None:
        return JSONResponse(content={"tasks": []})

    tasks = []
    for task_id, (task, sm) in orch.engine._tasks.items():
        tasks.append({
            "task_id": task.task_id,
            "description": task.description[:80],
            "status": task.status.value,
            "machine": task.effective_machine,
            "tags": task.tags,
            "retry_count": task.retry_count,
            "review_retry": task.review_retry,
            "test_retry": task.test_retry,
        })
    return JSONResponse(content={"tasks": tasks})


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """健康检查端点"""
    return JSONResponse(content={"status": "healthy", "version": __version__})


# ── 内部辅助 ────────────────────────────────────


def _get_machines_summary(orch: Any) -> Dict[str, int]:
    """聚合机器状态"""
    all_machines = orch.registry.get_all_machines()
    online = sum(1 for m in all_machines if m.status.value == "online")
    busy = sum(1 for m in all_machines if m.status.value == "busy")
    offline = sum(1 for m in all_machines if m.status.value in ("offline", "error"))
    return {
        "total": len(all_machines),
        "online": online,
        "busy": busy,
        "offline": offline,
    }


def _get_tasks_summary(orch: Any) -> Dict[str, int]:
    """聚合任务状态"""
    summary: Dict[str, int] = {
        "total": 0, "queued": 0, "in_progress": 0,
        "passed": 0, "failed": 0, "escalated": 0,
    }
    for task_id, (task, sm) in orch.engine._tasks.items():
        summary["total"] += 1
        status = task.status.value
        if status == "queued":
            summary["queued"] += 1
        elif status in ("dispatched", "coding_done", "review", "testing", "judging", "retry"):
            summary["in_progress"] += 1
        elif status == "passed":
            summary["passed"] += 1
        elif status == "failed":
            summary["failed"] += 1
        elif status == "escalated":
            summary["escalated"] += 1
    return summary
