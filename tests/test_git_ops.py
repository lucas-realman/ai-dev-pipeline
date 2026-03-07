"""
L2 组件测试 — Git 操作 (MOD-011)
TC-100 ~ TC-102, 覆盖 FR-022 / ALG-027
对齐 TEST-001 §2.2.11
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.git_ops import GitOps
from orchestrator.task_models import MachineInfo


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.get.side_effect = lambda key, default=None: {
        "project.branch": "main",
        "git.remote": "origin",
    }.get(key, default)
    return cfg


# ── TC-100: pull/commit/push 正常 (FR-022, mock shell) ──

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc100_pull_commit_push(tmp_path):
    """TC-100: pull → commit → push 调用链"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    with patch.object(git, "_run", new_callable=AsyncMock, return_value=True) as mock_run:
        assert await git.pull() is True
        assert await git.commit("test commit") is True
        assert await git.push() is True

    assert mock_run.call_count >= 3
    assert git.push_count == 1


# ── TC-101: tag_sprint (FR-022) ─────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc101_tag_sprint(tmp_path):
    """TC-101: tag_sprint 创建标签并推送"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    with patch.object(git, "_run", new_callable=AsyncMock, return_value=True) as mock_run:
        result = await git.tag_sprint("testing-v1.0", message="Sprint 1 测试完成")

    assert result is True
    # 至少调用 2 次: git tag + git push tag
    assert mock_run.call_count >= 2


# ── TC-102: sync_nodes 多节点同步 (ALG-027) ─────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc102_sync_nodes(tmp_path):
    """TC-102: 多节点并行同步"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    machines = {
        "m1": MachineInfo(machine_id="m1", host="10.0.0.1", user="dev"),
        "m2": MachineInfo(machine_id="m2", host="10.0.0.2", user="dev"),
    }

    with patch.object(git, "_sync_one_node", new_callable=AsyncMock, return_value=True):
        results = await git.sync_nodes(machines)

    assert len(results) == 2
    assert results["m1"] is True
    assert results["m2"] is True


# ── 附加: sync_nodes 部分失败 ────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_sync_nodes_partial_failure(tmp_path):
    """某节点同步失败不影响其他节点"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    machines = {
        "m1": MachineInfo(machine_id="m1", host="10.0.0.1", user="dev"),
        "m2": MachineInfo(machine_id="m2", host="10.0.0.2", user="dev"),
    }

    async def _side_effect(name, machine):
        if name == "m2":
            raise RuntimeError("SSH timeout")
        return True

    with patch.object(git, "_sync_one_node", new_callable=AsyncMock, side_effect=_side_effect):
        results = await git.sync_nodes(machines)

    assert results["m1"] is True
    assert results["m2"] is False


# ── 附加: get_current_branch / get_short_sha (mock) ─────

@pytest.mark.component
@pytest.mark.asyncio
async def test_get_current_branch(tmp_path):
    """get_current_branch 返回分支名"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"feature/test\n", b""))

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
        branch = await git.get_current_branch()

    assert branch == "feature/test"


@pytest.mark.component
@pytest.mark.asyncio
async def test_has_changes_false(tmp_path):
    """无变更 → has_changes=False"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
        assert await git.has_changes() is False


# ── 附加: _run 失败返回 False ────────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_run_failure(tmp_path):
    """_run 命令失败 → 返回 False"""
    cfg = _make_config(tmp_path)
    git = GitOps(cfg, repo_root=tmp_path)

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

    with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
        result = await git._run("git push", "test push")

    assert result is False
