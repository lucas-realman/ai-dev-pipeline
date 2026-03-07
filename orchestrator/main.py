"""
AutoDev Pipeline — 主编排器 & CLI 入口 (DD-MOD-013)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .dispatcher import Dispatcher
from .doc_analyzer import DocAnalyzer
from .doc_parser import DocParser
from .git_ops import GitOps
from .machine_registry import MachineRegistry
from .reporter import Reporter
from .reviewer import AutoReviewer
from .state_machine import TaskStateMachine
from .task_engine import TaskEngine
from .task_models import CodingTask, TaskResult, TaskStatus
from .test_runner import TestRunner

log = logging.getLogger("orchestrator")

MAX_ROUNDS = 20  # 主循环最大轮次


class Orchestrator:
    """自动化开发流水线 — 主编排器 (DD-MOD-013)"""

    def __init__(self, config: Config):
        self.config = config
        self.registry = MachineRegistry()
        self.registry.load_from_config(config.get_machines_list())

        self.engine = TaskEngine(config, machine_registry=self.registry)
        self.dispatcher = Dispatcher(config, registry=self.registry)
        self.reviewer = AutoReviewer(config)
        self.test_runner = TestRunner(config)
        self.reporter = Reporter(config)
        self.git_ops = GitOps(config)
        self._shutdown = False

    # ── 信号处理 (ALG-030a) ──

    def _setup_signal_handlers(self) -> None:
        """注册 SIGTERM / SIGINT 优雅关闭处理器"""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal, sig)

    def _handle_signal(self, sig: signal.Signals) -> None:
        log.warning("收到信号 %s, 准备优雅关闭...", sig.name)
        self._shutdown = True

    # ── Stale-busy 检测 (ALG-030b) ──

    def _check_stale_busy(self, stale_timeout: float = 1800.0) -> None:
        """检测超时占用的机器并释放"""
        now = time.time()
        for m in self.registry.get_busy_machines():
            if m.busy_since and (now - m.busy_since) > stale_timeout:
                log.warning(
                    "机器 %s 疑似 stale-busy (%.0fs), 释放",
                    m.machine_id, now - m.busy_since,
                )
                self.registry.set_idle(m.machine_id)

    async def run_sprint(self, sprint_id: str, tasks: Optional[List[CodingTask]] = None) -> Dict:
        """
        执行一轮 Sprint (DD-MOD-013 主入口)
        如果没有传入 tasks, 则从文档集自动分解
        """
        self._setup_signal_handlers()
        log.info("========== Sprint %s 开始 ==========", sprint_id)

        if tasks is None:
            tasks = await self._discover_tasks()

        if not tasks:
            log.warning("没有找到任何任务, 退出")
            return {"total": 0, "passed": 0, "failed": 0, "escalated": 0}

        # 注册任务到引擎
        for t in tasks:
            self.engine.add_task(t)

        await self.reporter.notify_sprint_start(sprint_id, tasks)

        # 同步代码到各节点
        if self.config.get("git.sync_before_sprint", True):
            await self._sync_code()

        # 主循环
        await self._main_loop(tasks)

        # 收尾
        summary = self._compute_summary(tasks)
        report_path = self.reporter.generate_report(sprint_id, tasks, summary)
        await self.reporter.notify_sprint_done(sprint_id, tasks)

        # Git commit + tag
        if self.config.get("git.auto_commit", True):
            if await self.git_ops.has_changes():
                await self.git_ops.commit(f"sprint({sprint_id}): auto-commit by orchestrator")
                await self.git_ops.push()
            await self.git_ops.tag_sprint(f"sprint-{sprint_id}")

        log.info("========== Sprint %s 完成: %s ==========", sprint_id, summary)
        return summary

    async def run_continuous(self) -> None:
        """持续模式: 循环执行 sprint (用于 CI 或长期运行)"""
        sprint_no = 1
        while True:
            sprint_id = f"auto-{sprint_no:03d}"
            try:
                summary = await self.run_sprint(sprint_id)
                if summary["total"] == 0:
                    log.info("无更多任务, 退出持续模式")
                    break
                sprint_no += 1
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                log.info("收到中断信号, 退出")
                break
            except Exception as e:
                log.exception("Sprint %s 异常: %s", sprint_id, e)
                await self.reporter.notify_error(f"Sprint {sprint_id} 异常: {e}")
                break

    # ── 任务发现 ──

    async def _discover_tasks(self) -> List[CodingTask]:
        """通过文档集分解任务 (v3.0 新功能)"""
        doc_set_patterns = self.config.doc_set
        if doc_set_patterns:
            log.info("使用 DocAnalyzer 从文档集分解任务...")
            analyzer = DocAnalyzer(self.config)
            tasks = await analyzer.analyze_and_decompose()
            if tasks:
                return tasks

        # 回退到传统 DocParser
        task_card = self.config.get("doc_parser.task_card", "")
        if task_card:
            log.info("回退到 DocParser 解析任务卡...")
            parser = DocParser(self.config)
            return parser.parse_task_card(str(self.config.repo_root / task_card))

        return []

    # ── 主循环 ──

    async def _main_loop(self, tasks: List[CodingTask]) -> None:
        """
        主编排循环 (DD-MOD-013):
        每轮: batch → dispatch → review → test → judge
        """
        for round_no in range(1, MAX_ROUNDS + 1):
            # ALG-030a: 检查优雅关闭
            if self._shutdown:
                log.info("收到关闭信号, 退出主循环")
                await self.reporter.notify_shutdown("signal")
                break

            # ALG-030b: Stale-busy 检测
            self._check_stale_busy()

            pending = [
                t for t in tasks
                if t.status not in (TaskStatus.PASSED, TaskStatus.FAILED, TaskStatus.ESCALATED)
            ]
            if not pending:
                log.info("所有任务已完成, 退出主循环 (第 %d 轮)", round_no)
                break

            log.info("── 第 %d 轮, 剩余任务: %d ──", round_no, len(pending))

            # 1. 获取下一批可调度任务
            batch = self.engine.next_batch()
            if not batch:
                # 检查是否还有正在执行的任务
                in_progress = [t for t in tasks if t.status == TaskStatus.DISPATCHED]
                if in_progress:
                    log.info("等待 %d 个任务完成编码...", len(in_progress))
                    await asyncio.sleep(10)
                    continue
                else:
                    log.info("没有可调度的任务, 退出主循环")
                    break

            # 2. 分发 (阻塞等待编码完成, 返回 {task_id: TaskResult})
            dispatch_results = await self._dispatch_batch(batch)

            # 3. 审查 + 测试 + 判定
            for task in batch:
                result = dispatch_results.get(task.task_id)
                if result and result.success:
                    await self._process_task_result(task, result)

        else:
            log.warning("主循环达到最大轮次 %d, 强制退出", MAX_ROUNDS)
            for t in tasks:
                if t.status not in (TaskStatus.PASSED, TaskStatus.FAILED, TaskStatus.ESCALATED):
                    t.status = TaskStatus.ESCALATED

    async def _dispatch_batch(self, batch: List[CodingTask]) -> Dict[str, TaskResult]:
        """分发一批任务, 返回 {task_id: TaskResult}"""
        results: Dict[str, TaskResult] = {}
        for task in batch:
            result = await self.dispatcher.dispatch_task(task)
            results[task.task_id] = result
            if result.success:
                self.engine.mark_dispatched(task.task_id)
                await self.reporter.notify_task_dispatched(task)
                # dispatch_task 是阻塞的 — 编码已完成, 推进状态机
                self.engine.handle_coding_done(task.task_id, result)
            else:
                log.warning("任务 %s 分发失败: %s", task.task_id, result.stderr[:120])
                task.status = TaskStatus.QUEUED
        return results

    async def _process_task_result(self, task: CodingTask, dispatch_result: TaskResult) -> None:
        """对一个完成编码的任务执行: 审查 → 测试 → 判定 (DD-MOD-013)"""
        if task.status not in (TaskStatus.CODING_DONE, TaskStatus.REVIEW, TaskStatus.TESTING):
            return

        # 审查
        task.status = TaskStatus.REVIEW
        review = await self.reviewer.review_task(task, dispatch_result)
        if not review.passed:
            task.review_retry += 1
            max_review_retry = self.config.get("retry.max_review_retry", 2)
            if task.review_retry > max_review_retry:
                task.status = TaskStatus.ESCALATED
                log.warning("任务 %s 审查失败超过上限, 升级", task.task_id)
            else:
                task.status = TaskStatus.QUEUED
                log.info("任务 %s 审查未通过, 重新排队 (审查重试 %d)", task.task_id, task.review_retry)
            await self.reporter.notify_task_result(task, review=review)
            return

        # 测试
        task.status = TaskStatus.TESTING
        test_result = await self.test_runner.run_tests(task, dispatch_result)
        if not test_result.passed:
            task.test_retry += 1
            max_test_retry = self.config.get("retry.max_test_retry", 2)
            if task.test_retry > max_test_retry:
                task.status = TaskStatus.ESCALATED
                log.warning("任务 %s 测试失败超过上限, 升级", task.task_id)
            else:
                task.status = TaskStatus.QUEUED
                log.info("任务 %s 测试未通过, 重新排队 (测试重试 %d)", task.task_id, task.test_retry)
            await self.reporter.notify_task_result(task, review=review, test=test_result)
            return

        # 通过
        task.status = TaskStatus.PASSED
        log.info("✅ 任务 %s 通过", task.task_id)
        await self.reporter.notify_task_result(task, review=review, test=test_result)

    # ── 辅助 ──

    async def _sync_code(self) -> None:
        """同步代码到各节点"""
        machines = self.config.get_machines()
        if machines:
            results = await self.git_ops.sync_nodes(machines)
            failed = [n for n, ok in results.items() if not ok]
            if failed:
                log.warning("以下节点同步失败: %s", failed)

    def _compute_summary(self, tasks: List[CodingTask]) -> Dict:
        total = len(tasks)
        passed = sum(1 for t in tasks if t.status == TaskStatus.PASSED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        escalated = sum(1 for t in tasks if t.status == TaskStatus.ESCALATED)
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "escalated": escalated,
        }


# ── CLI 入口 ──

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="autodev",
        description="AutoDev Pipeline — 通用自动化开发流水线平台 v3.0",
    )
    p.add_argument(
        "-c", "--config",
        default="orchestrator/config.yaml",
        help="配置文件路径 (default: orchestrator/config.yaml)",
    )
    p.add_argument(
        "--project-path",
        default=None,
        help="项目根目录 (覆盖 config.yaml 中的 project.path)",
    )
    p.add_argument(
        "--sprint-id",
        default=None,
        help="Sprint ID (default: auto-001)",
    )
    p.add_argument(
        "--mode",
        choices=["sprint", "continuous"],
        default="sprint",
        help="运行模式: sprint (单轮) 或 continuous (持续)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式: 只解析任务, 不实际执行",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="启用 debug 日志",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # 日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 加载配置
    config_path = args.config
    project_root = args.project_path
    config = Config(config_path, project_root=project_root)

    # 构建编排器
    orch = Orchestrator(config)

    # 干跑模式
    if args.dry_run:
        log.info("[DRY-RUN] 解析任务...")
        tasks = asyncio.run(_dry_run_discover(orch))
        for t in tasks:
            log.info(
                "  %s | %s | tags=%s | machine=%s",
                t.task_id,
                t.description[:40],
                t.tags,
                t.effective_machine,
            )
        log.info("[DRY-RUN] 共 %d 个任务", len(tasks))
        return

    # 正式运行
    sprint_id = args.sprint_id or "auto-001"
    if args.mode == "sprint":
        asyncio.run(orch.run_sprint(sprint_id))
    else:
        asyncio.run(orch.run_continuous())


async def _dry_run_discover(orch: Orchestrator) -> List[CodingTask]:
    return await orch._discover_tasks()


if __name__ == "__main__":
    main()
