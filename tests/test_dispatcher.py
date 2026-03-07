"""
L2 组件测试 — SSH 分发器 (MOD-007)
TC-060 ~ TC-063, 覆盖 FR-010 / FR-011 / ALG-013
对齐 TEST-001 §2.2.7
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.dispatcher import Dispatcher
from orchestrator.task_models import CodingTask, MachineInfo, TaskResult


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.single_task_timeout = 60
    cfg.git_branch = "main"
    cfg.aider_model = "gpt-4"
    cfg.openai_api_base = "http://localhost/v1"
    cfg.openai_api_key = "key"
    cfg.task_card_path = ""
    cfg.get_machines.return_value = {}
    # 创建 contracts 目录
    (tmp_path / "contracts").mkdir(exist_ok=True)
    return cfg


def _make_task(tid: str = "T-D001", machine_id: str = "m1") -> CodingTask:
    return CodingTask(
        task_id=tid,
        description="Test dispatch task",
        tags=["python"],
        target_dir="src/",
        assigned_machine=machine_id,
    )


def _make_machine(mid: str = "m1", host: str = "10.0.0.1") -> MachineInfo:
    return MachineInfo(
        machine_id=mid,
        display_name="Test Machine",
        host=host,
        user="dev",
        work_dir="~/projects",
        tags=["python"],
    )


# ── TC-060: 正常分发 (FR-010, mock SSH) ──────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc060_dispatch_task_success(tmp_path):
    """TC-060: dispatch_task 正常执行 → TaskResult.success=True"""
    cfg = _make_config(tmp_path)
    registry = MagicMock()
    registry.get_machine.return_value = _make_machine()

    dispatcher = Dispatcher(cfg, registry=registry)

    mock_result = TaskResult(task_id="T-D001", exit_code=0, stdout="Wrote src/main.py")
    with patch.object(dispatcher, "_ssh_pre_check", new_callable=AsyncMock, return_value=True), \
         patch.object(dispatcher, "_scp_content", new_callable=AsyncMock), \
         patch.object(dispatcher, "_ssh_exec", new_callable=AsyncMock, return_value=mock_result):
        result = await dispatcher.dispatch_task(_make_task())

    assert result.success is True
    assert result.task_id == "T-D001"


# ── TC-061: SSH 预检失败 (ALG-013a) ──────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc061_ssh_precheck_fail(tmp_path):
    """TC-061: SSH 不可连 → 返回失败, 机器置为 offline"""
    cfg = _make_config(tmp_path)
    registry = MagicMock()
    registry.get_machine.return_value = _make_machine()

    dispatcher = Dispatcher(cfg, registry=registry)

    with patch.object(dispatcher, "_ssh_pre_check", new_callable=AsyncMock, return_value=False):
        result = await dispatcher.dispatch_task(_make_task())

    assert result.success is False
    assert "预检失败" in result.stderr
    registry.set_offline.assert_called_once_with("m1")


# ── TC-062: 机器不存在 (FR-010) ──────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc062_machine_not_found(tmp_path):
    """TC-062: 任务指定的机器在 registry 中不存在"""
    cfg = _make_config(tmp_path)
    registry = MagicMock()
    registry.get_machine.return_value = None

    dispatcher = Dispatcher(cfg, registry=registry)
    result = await dispatcher.dispatch_task(_make_task(machine_id="nonexistent"))

    assert result.success is False
    assert "未找到机器" in result.stderr


# ── TC-063: _build_instruction 指令构建 (FR-010) ─────────

@pytest.mark.component
def test_tc063_build_instruction(tmp_path):
    """TC-063: _build_instruction 生成合理的 aider 指令"""
    cfg = _make_config(tmp_path)
    dispatcher = Dispatcher(cfg)

    task = CodingTask(
        task_id="T-BI-001",
        description="实现用户登录模块",
        target_dir="src/auth",
        acceptance=["测试通过", "接口规范"],
        tags=["python"],
    )

    instruction = dispatcher._build_instruction(task)
    assert "T-BI-001" in instruction
    assert "用户登录模块" in instruction
    assert "测试通过" in instruction
    assert "src/auth" in instruction


# ── 附加: dispatch_batch 并行执行 ────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_dispatch_batch(tmp_path):
    """dispatch_batch 并行分发多个任务"""
    cfg = _make_config(tmp_path)
    registry = MagicMock()
    registry.get_machine.return_value = _make_machine()

    dispatcher = Dispatcher(cfg, registry=registry)

    mock_result = TaskResult(task_id="", exit_code=0, stdout="ok")
    with patch.object(dispatcher, "_ssh_pre_check", new_callable=AsyncMock, return_value=True), \
         patch.object(dispatcher, "_scp_content", new_callable=AsyncMock), \
         patch.object(dispatcher, "_ssh_exec", new_callable=AsyncMock, return_value=mock_result):
        tasks = [_make_task(f"T-B{i}") for i in range(3)]
        results = await dispatcher.dispatch_batch(tasks)

    assert len(results) == 3
    assert all(r.success for r in results)


# ── 附加: _is_local 本机检测 ─────────────────────────────

@pytest.mark.component
def test_is_local(tmp_path):
    """_is_local 正确识别 localhost"""
    cfg = _make_config(tmp_path)
    dispatcher = Dispatcher(cfg)

    local_machine = MachineInfo(machine_id="local", host="127.0.0.1", user="dev")
    remote_machine = MachineInfo(machine_id="remote", host="10.0.0.99", user="dev")

    assert dispatcher._is_local(local_machine) is True
    assert dispatcher._is_local(remote_machine) is False


# ── 附加: _parse_changed_files ────────────────────────────

@pytest.mark.component
def test_parse_changed_files():
    """_parse_changed_files 从 stdout 中提取修改的文件"""
    stdout = "Wrote src/main.py\nWrote src/utils.py\nDone."
    files = Dispatcher._parse_changed_files(stdout, "src/")
    assert "src/main.py" in files
    assert "src/utils.py" in files
