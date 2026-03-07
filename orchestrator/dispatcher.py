"""
AutoDev Pipeline — SSH 分发器 (DD-MOD-007)
通过 SSH 在远程机器上执行 aider 编码任务。
支持: MachineRegistry 动态分配, SSH 预检, aider 版本校验。
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import socket
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config
from .machine_registry import MachineRegistry
from .task_models import CodingTask, MachineInfo, TaskResult

log = logging.getLogger("orchestrator.dispatcher")


class Dispatcher:
    """
    SSH 分发器 (DD-MOD-007): 将 CodingTask 发送到目标机器并执行 aider。
    支持 MachineRegistry 动态分配; SSH 连通预检 (ALG-013a); aider 版本锁定 (ALG-013b)。
    """

    def __init__(self, config: Config, registry: Optional[MachineRegistry] = None):
        self.config = config
        self.registry = registry
        # 兼容: 如果没有 registry, 从 config 获取
        self._fallback_machines = config.get_machines() if registry is None else {}
        self._local_ips = self._collect_local_ips()

    def _get_machine(self, task: CodingTask) -> Optional[MachineInfo]:
        """获取任务的目标机器信息"""
        machine_id = task.effective_machine
        if not machine_id:
            return None
        if self.registry:
            return self.registry.get_machine(machine_id)
        return self._fallback_machines.get(machine_id)

    @staticmethod
    def _collect_local_ips():
        ips = {"127.0.0.1", "localhost", "::1"}
        try:
            hostname = socket.gethostname()
            ips.add(hostname)
            for info in socket.getaddrinfo(hostname, None):
                ips.add(info[4][0])
        except Exception:
            pass
        return ips

    def _is_local(self, machine: MachineInfo) -> bool:
        return machine.host in self._local_ips

    async def dispatch_task(self, task: CodingTask) -> TaskResult:
        """在目标机器上执行 aider 编码任务 (ALG-013, 含 SSH 预检)"""
        machine = self._get_machine(task)
        if not machine:
            return TaskResult(
                task_id=task.task_id,
                exit_code=1,
                stderr=f"未找到机器: {task.effective_machine}",
            )

        # ★ ALG-013a: SSH 连接预检
        if not self._is_local(machine):
            ok = await self._ssh_pre_check(machine)
            if not ok:
                if self.registry:
                    self.registry.set_offline(machine.machine_id)
                return TaskResult(
                    task_id=task.task_id,
                    exit_code=1,
                    stderr=f"机器 {machine.machine_id} SSH 预检失败",
                )

        # ★ ALG-013b: aider 版本锁定
        expected_ver = getattr(self.config, "aider_version", "")
        if expected_ver and not self._is_local(machine):
            ver_ok, actual_ver = await self._check_aider_version(machine, expected_ver)
            if not ver_ok:
                log.warning(
                    "机器 %s aider 版本不匹配: 期望 %s, 实际 %s",
                    machine.machine_id, expected_ver, actual_ver,
                )

        start_time = time.time()
        log.info("[%s] 分发到 %s (%s@%s), 目录: %s",
                 task.task_id, machine.machine_id, machine.user, machine.host,
                 task.target_dir)

        try:
            instruction = self._build_instruction(task)
            msg_remote_path = f"/tmp/aider_msg_{task.task_id}"
            await self._scp_content(machine, instruction, msg_remote_path)

            ssh_script = self._build_ssh_script(task, machine, msg_remote_path)
            result = await self._ssh_exec(
                machine, ssh_script,
                timeout=self.config.single_task_timeout,
            )

            duration = time.time() - start_time
            result.task_id = task.task_id
            result.duration_sec = duration

            if result.success:
                result.files_changed = self._parse_changed_files(result.stdout, task.target_dir)
                log.info("[%s] ✅ 编码成功 (%.1fs), 变更: %s",
                         task.task_id, duration, result.files_changed)
            else:
                log.warning("[%s] ❌ 编码失败 (%.1fs, exit=%d)",
                            task.task_id, duration, result.exit_code)

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            log.error("[%s] ⏱ 超时 (%.1fs)", task.task_id, duration)
            return TaskResult(
                task_id=task.task_id,
                exit_code=124,
                stderr=f"任务超时 ({self.config.single_task_timeout}s)",
                duration_sec=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            log.error("[%s] 异常: %s", task.task_id, e, exc_info=True)
            return TaskResult(
                task_id=task.task_id,
                exit_code=1,
                stderr=str(e),
                duration_sec=duration,
            )

    async def dispatch_batch(self, tasks: List[CodingTask]) -> List[TaskResult]:
        """并行分发一批任务"""
        coros = [self.dispatch_task(task) for task in tasks]
        return await asyncio.gather(*coros)

    # ── 构建指令 ──

    def _build_instruction(self, task: CodingTask) -> str:
        """将 CodingTask 转换为 aider 可理解的自然语言指令"""
        parts = [
            f"# 编码任务 {task.task_id}\n",
            f"## 目标\n{task.description}\n",
        ]

        if task.acceptance:
            parts.append("## 验收标准\n")
            for a in task.acceptance:
                parts.append(f"- {a}\n")

        parts.append(f"""
## 约束
1. 严格遵循 contracts/ 下的接口契约
2. 包含必要的依赖声明
3. 代码可直接运行
4. 只生成 `{task.target_dir}` 目录下的文件, 不要修改其他目录
5. 包含完整的错误处理和 docstring
6. 在 tests/ 目录下生成对应的 pytest 测试文件
""")

        if task.fix_instruction:
            parts.append(f"""
## ⚠️ 修复指令 (第 {task.total_retries} 次重试)
上一轮执行存在以下问题, 请优先修复:

{task.fix_instruction}
""")

        return "\n".join(parts)

    def _build_ssh_script(
        self, task: CodingTask, machine: MachineInfo, msg_remote_path: str,
    ) -> str:
        """构建要在远程机器上执行的完整 shell 脚本"""
        branch = self.config.git_branch
        model = machine.aider_model or self.config.aider_model
        api_base = self.config.openai_api_base
        api_key = self.config.openai_api_key

        # 构建 --read 参数
        contract_reads = ""
        contracts_dir = self.config.repo_root / "contracts"
        if contracts_dir.exists():
            for f in contracts_dir.iterdir():
                if f.suffix in (".yaml", ".yml", ".sql"):
                    contract_reads += f" --read contracts/{f.name}"

        task_card = self.config.task_card_path
        if task_card:
            contract_reads += f" --read {task_card}"

        return f"""
{machine.aider_prefix}
export OPENAI_API_BASE='{api_base}'
export OPENAI_API_KEY='{api_key}'
cd {machine.work_dir}

# 确保工作区干净
git rebase --abort 2>/dev/null || true
git merge --abort 2>/dev/null || true
git checkout -- . 2>/dev/null || true
git clean -fd 2>/dev/null || true
git fetch origin {branch}
git reset --hard origin/{branch}

mkdir -p {task.target_dir}

AIDER_MSG=$(cat {msg_remote_path} 2>/dev/null || echo '在 {task.target_dir} 目录下实现 {task.description[:80]}')

aider --model '{model}' \\
      --yes-always \\
      --no-auto-commits \\
      {contract_reads} \\
      --message "$AIDER_MSG"
AIDER_EXIT=$?

FILE_COUNT=$(find {task.target_dir} -type f -not -name '.gitkeep' 2>/dev/null | wc -l)
if [[ $AIDER_EXIT -ne 0 ]] && [[ $FILE_COUNT -gt 0 ]]; then
    echo "[WARN] aider exit=$AIDER_EXIT but found $FILE_COUNT files, treating as success"
    AIDER_EXIT=0
fi
if [[ $AIDER_EXIT -eq 0 ]] && [[ $FILE_COUNT -eq 0 ]]; then
    echo "[FAIL] aider exit=0 but no files created, treating as failure"
    AIDER_EXIT=1
fi

if [[ $AIDER_EXIT -eq 0 ]]; then
    cd {machine.work_dir}
    git add -A {task.target_dir}
    git add -A tests/ 2>/dev/null || true
    git checkout -- . 2>/dev/null || true
    git commit -m '[{task.task_id}] auto: {task.description[:60]}' || true

    PUSHED=0
    for RETRY in 1 2 3; do
        if git pull --rebase origin {branch} 2>&1; then
            git push origin {branch} 2>&1 && PUSHED=1 && break
        fi
        git rebase --abort 2>/dev/null || true
        if git pull --no-rebase origin {branch} 2>&1; then
            git push origin {branch} 2>&1 && PUSHED=1 && break
        fi
        git merge --abort 2>/dev/null || true
        sleep 2
    done
    if [[ $PUSHED -ne 1 ]]; then
        echo "[PUSH FAILED after 3 retries]" >&2
        exit 1
    fi
fi

rm -f {msg_remote_path}
exit $AIDER_EXIT
"""

    # ── SSH 执行工具 ──

    async def _scp_content(
        self, machine: MachineInfo, content: str, remote_path: str,
    ) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            local_path = f.name

        try:
            if self._is_local(machine):
                shutil.copy2(local_path, remote_path)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "scp", "-q", "-o", "ConnectTimeout=10",
                    "-P", str(machine.port),
                    local_path,
                    f"{machine.user}@{machine.host}:{remote_path}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                if proc.returncode != 0:
                    err_msg = stderr.decode("utf-8", errors="replace") if stderr else "unknown"
                    raise RuntimeError(f"SCP 失败 (exit={proc.returncode}): {err_msg}")
        finally:
            os.unlink(local_path)

    async def _ssh_exec(
        self,
        machine: MachineInfo,
        script: str,
        timeout: int = 600,
    ) -> TaskResult:
        if self._is_local(machine):
            proc = await asyncio.create_subprocess_exec(
                "bash", "-s",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "ssh",
                "-T",
                "-p", str(machine.port),
                "-o", "ConnectTimeout=10",
                "-o", "ServerAliveInterval=30",
                f"{machine.user}@{machine.host}",
                "bash -s",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=script.encode("utf-8")), timeout=timeout,
        )

        return TaskResult(
            task_id="",
            exit_code=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    @staticmethod
    def _parse_changed_files(stdout: str, target_dir: str) -> List[str]:
        files = []
        for line in stdout.splitlines():
            if line.strip().startswith("Wrote "):
                f = line.strip().replace("Wrote ", "").strip()
                files.append(f)
            elif line.strip().startswith("create mode"):
                parts = line.strip().split()
                if len(parts) >= 3:
                    files.append(parts[-1])
        if not files:
            files = [target_dir]
        return files

    # ── SSH 辅助: 预检 / 版本检查 / 简易执行 ──

    async def _ssh_pre_check(self, machine: MachineInfo) -> bool:
        """
        轻量级 SSH 连通性检查 (ALG-013a)。

        成功: 返回 True
        失败: 记录日志 + 返回 False (调用方负责置为 OFFLINE)
        """
        cmd = [
            "ssh", "-T",
            "-o", "ConnectTimeout=5",
            "-o", "BatchMode=yes",
            "-p", str(machine.port),
            f"{machine.user}@{machine.host}",
            "echo ok",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0 and "ok" in stdout.decode():
                return True
            log.warning(
                "机器 %s SSH 预检失败: exit=%d, %s",
                machine.machine_id, proc.returncode,
                stderr.decode("utf-8", errors="replace"),
            )
            return False
        except asyncio.TimeoutError:
            log.warning("机器 %s SSH 预检超时 (10s)", machine.machine_id)
            return False
        except Exception as exc:
            log.warning("机器 %s SSH 预检异常: %s", machine.machine_id, exc)
            return False

    async def _check_aider_version(
        self, machine: MachineInfo, expected: str,
    ) -> Tuple[bool, str]:
        """
        远程执行 ``aider --version``, 与期望版本比较 (ALG-013b)。

        Returns:
            (match, actual_version_str)
        """
        cmd = f"{machine.aider_prefix} && aider --version 2>/dev/null || echo unknown"
        try:
            raw = await self._ssh_exec_simple(machine, cmd, timeout=10)
            ver_str = raw.replace("aider", "").strip()
            return (ver_str == expected, ver_str)
        except Exception:
            return (False, "unknown")

    async def _ssh_exec_simple(
        self, machine: MachineInfo, cmd: str, *, timeout: int = 10,
    ) -> str:
        """
        在远程机器上执行一条简单命令并返回 stdout (UTF-8)。

        适用于轻量脚本 (版本检查、echo 等), 不做 SCP / 文件上传。
        """
        ssh_cmd = [
            "ssh", "-T",
            "-o", "ConnectTimeout=5",
            "-o", "BatchMode=yes",
            "-p", str(machine.port),
            f"{machine.user}@{machine.host}",
            cmd,
        ]
        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace").strip()

    async def check_task_done(self, task: CodingTask) -> bool:
        """
        检查远程机器上的 aider 任务是否已完成。

        通过检测远程临时指令文件是否已删除来判定 —
        ALG-014 脚本末尾会 ``rm -f {msg_remote_path}``。

        Returns:
            True 表示任务已完成 (指令文件已被清理)
        """
        machine = self._get_machine(task)
        if not machine:
            return True  # 无法查到机器, 视为完成 (由调用方处理异常)

        if self._is_local(machine):
            msg_path = Path(f"/tmp/aider_msg_{task.task_id}")
            return not msg_path.exists()

        try:
            raw = await self._ssh_exec_simple(
                machine,
                f"test -f /tmp/aider_msg_{task.task_id} && echo running || echo done",
                timeout=10,
            )
            return "done" in raw
        except Exception:
            return False
