"""
AutoDev Pipeline — Git 操作封装
支持: pull / commit / push / tag / sync_nodes (多节点同步)
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .task_models import MachineInfo

log = logging.getLogger("orchestrator.git_ops")


class GitOps:
    """Git 操作工具"""

    def __init__(self, config: Config, repo_root: Optional[Path] = None):
        self.config = config
        self.repo_root = repo_root or config.repo_root
        self.branch = config.get("project.branch", "main") or "main"
        self.remote = config.get("git.remote", "origin") or "origin"

    async def pull(self, remote: Optional[str] = None, branch: Optional[str] = None) -> bool:
        """拉取远端最新代码"""
        r = remote or self.remote
        b = branch or self.branch
        cmd = f"git -C {self.repo_root} pull {r} {b} --rebase"
        return await self._run(cmd, f"git pull {r} {b}")

    async def commit(self, message: str, add_all: bool = True) -> bool:
        """提交变更"""
        if add_all:
            await self._run(f"git -C {self.repo_root} add -A", "git add -A")
        cmd = f'git -C {self.repo_root} commit -m "{message}"'
        return await self._run(cmd, "git commit")

    async def push(self, remote: Optional[str] = None, branch: Optional[str] = None) -> bool:
        """推送到远端"""
        r = remote or self.remote
        b = branch or self.branch
        cmd = f"git -C {self.repo_root} push {r} {b}"
        return await self._run(cmd, f"git push {r} {b}")

    async def tag_sprint(self, tag: str, message: Optional[str] = None) -> bool:
        """创建 sprint tag"""
        msg = message or f"Sprint tag: {tag}"
        cmd = f'git -C {self.repo_root} tag -a {tag} -m "{msg}"'
        ok = await self._run(cmd, f"git tag {tag}")
        if ok:
            r = self.remote
            await self._run(f"git -C {self.repo_root} push {r} {tag}", f"git push tag {tag}")
        return ok

    async def sync_nodes(self, machines: Dict[str, MachineInfo]) -> Dict[str, bool]:
        """同步代码到各节点 (SSH git pull)"""
        results: Dict[str, bool] = {}
        tasks = []
        for name, machine in machines.items():
            tasks.append(self._sync_one_node(name, machine))
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for (name, _), result in zip(machines.items(), completed):
            if isinstance(result, Exception):
                log.warning("同步节点 %s 异常: %s", name, result)
                results[name] = False
            else:
                results[name] = result
        return results

    async def _sync_one_node(self, name: str, machine: MachineInfo) -> bool:
        """同步单个节点"""
        work_dir = machine.work_dir or "~/my-project"
        port_opt = f"-p {machine.port}" if machine.port != 22 else ""
        cmd = (
            f"ssh {port_opt} {machine.user}@{machine.host} "
            f"'cd {work_dir} && git pull --rebase'"
        )
        return await self._run(cmd, f"sync node {name}")

    async def get_current_branch(self) -> str:
        """获取当前分支名"""
        proc = await asyncio.create_subprocess_shell(
            f"git -C {self.repo_root} rev-parse --abbrev-ref HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() if proc.returncode == 0 else "unknown"

    async def get_short_sha(self) -> str:
        """获取当前 commit 短 SHA"""
        proc = await asyncio.create_subprocess_shell(
            f"git -C {self.repo_root} rev-parse --short HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() if proc.returncode == 0 else "unknown"

    async def has_changes(self) -> bool:
        """检查是否有未提交的变更"""
        proc = await asyncio.create_subprocess_shell(
            f"git -C {self.repo_root} status --porcelain",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return bool(stdout.decode().strip())

    # ── 内部方法 ──

    async def _run(self, cmd: str, label: str) -> bool:
        """执行 shell 命令"""
        log.debug("[GitOps] %s: %s", label, cmd)
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                log.info("[GitOps] %s 成功", label)
                return True
            else:
                log.warning(
                    "[GitOps] %s 失败 (rc=%d): %s",
                    label, proc.returncode, stderr.decode().strip()[:200],
                )
                return False
        except Exception as e:
            log.error("[GitOps] %s 异常: %s", label, e)
            return False
