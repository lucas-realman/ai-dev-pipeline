"""
AutoDev Pipeline — 任务引擎 (DD-MOD-004)
管理任务队列、依赖关系、执行顺序和状态追踪。
v3.0: next_batch() 使用 MachineRegistry 做动态分配。
"""
from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict, deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    pass

from .machine_registry import MachineRegistry
from .state_machine import TaskStateMachine
from .task_models import CodingTask, ReviewResult, TaskResult, TaskStatus, TestResult

log = logging.getLogger("orchestrator.task_engine")


class CycleDependencyError(Exception):
    """任务依赖环检测异常 (ALG-009)"""
    pass


class TaskEngine:
    """
    任务调度引擎 (DD-MOD-004):
    - 维护任务列表 + 状态
    - 依赖关系拓扑排序 + 环检测 (ALG-009)
    - next_batch() 使用 MachineRegistry 动态匹配
    - handle_*() 处理各阶段结果
    """

    def __init__(
        self,
        config: Optional[Any] = None,
        *,
        max_retries: int = 3,
        max_concurrent: int = 4,
        machine_registry: Optional[MachineRegistry] = None,
    ):
        # 支持两种构造方式: Config 对象或显式参数
        if config is not None and hasattr(config, 'max_retries'):
            self.max_retries = config.max_retries
            self.max_concurrent = config.max_concurrent
        else:
            self.max_retries = max_retries
            self.max_concurrent = max_concurrent

        self.registry = machine_registry or MachineRegistry()

        # 存储: task_id → (CodingTask, TaskStateMachine)
        self._tasks: OrderedDict[str, tuple] = OrderedDict()
        self._lock = threading.Lock()

        # 快照路径
        self._snapshot_path: Optional[Path] = None
        if config is not None and hasattr(config, 'repo_root'):
            self._snapshot_path = config.repo_root / ".task_engine_snapshot.json"

        # 统计
        self.total_dispatched = 0
        self.total_passed = 0
        self.total_failed = 0
        self.total_escalated = 0

    # ── 任务入队 ──

    def enqueue(self, tasks: List[CodingTask]) -> None:
        """批量入队任务 (含环检测 ALG-009)"""
        # 环检测: 构建完整依赖图 (现有 + 新增)
        self._check_cycles(tasks)

        with self._lock:
            for task in tasks:
                if task.task_id in self._tasks:
                    log.warning("任务 %s 已存在, 跳过", task.task_id)
                    continue
                sm = TaskStateMachine(task, max_retries=self.max_retries)
                sm.enqueue()
                self._tasks[task.task_id] = (task, sm)
                log.info("入队: %s tags=%s (%s)",
                         task.task_id, task.tags, task.description[:40])

    def enqueue_single(self, task: CodingTask) -> None:
        self.enqueue([task])

    def add_task(self, task: CodingTask) -> None:
        """enqueue_single 的别名, 保持 API 兼容"""
        self.enqueue_single(task)

    # ── 环检测 (ALG-009) ──

    def _check_cycles(self, new_tasks: List[CodingTask]) -> None:
        """Kahn 拓扑排序检测依赖环 (ALG-009)"""
        # 构建合并依赖图
        all_tasks: Dict[str, List[str]] = {}
        with self._lock:
            for tid, (task, _) in self._tasks.items():
                all_tasks[tid] = list(task.depends_on)

        for task in new_tasks:
            all_tasks[task.task_id] = list(task.depends_on)

        # Kahn 算法
        in_degree: Dict[str, int] = {tid: 0 for tid in all_tasks}
        for tid, deps in all_tasks.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[tid] = in_degree.get(tid, 0)  # ensure exists

        # 重新计算 in-degree
        in_degree = {tid: 0 for tid in all_tasks}
        for tid, deps in all_tasks.items():
            for dep in deps:
                if dep in all_tasks:
                    in_degree[tid] += 1

        queue: deque[str] = deque()
        for tid, deg in in_degree.items():
            if deg == 0:
                queue.append(tid)

        sorted_count = 0
        while queue:
            node = queue.popleft()
            sorted_count += 1
            # 找到所有以 node 为依赖的任务
            for tid, deps in all_tasks.items():
                if node in deps:
                    in_degree[tid] -= 1
                    if in_degree[tid] == 0:
                        queue.append(tid)

        if sorted_count < len(all_tasks):
            cycle_nodes = [tid for tid, deg in in_degree.items() if deg > 0]
            raise CycleDependencyError(
                f"检测到任务依赖环! 涉及节点: {cycle_nodes}"
            )

    # ── 快照持久化 (ALG-009b) ──

    def save_snapshot(self) -> None:
        """保存任务状态快照"""
        if not self._snapshot_path:
            return
        with self._lock:
            data = {
                "tasks": {
                    tid: task.to_dict()
                    for tid, (task, _) in self._tasks.items()
                },
                "stats": {
                    "total_dispatched": self.total_dispatched,
                    "total_passed": self.total_passed,
                    "total_failed": self.total_failed,
                    "total_escalated": self.total_escalated,
                },
            }
        try:
            self._snapshot_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.debug("快照已保存: %s", self._snapshot_path)
        except Exception as e:
            log.warning("快照保存失败: %s", e)

    def load_snapshot(self) -> bool:
        """从快照恢复任务状态"""
        if not self._snapshot_path or not self._snapshot_path.exists():
            return False
        try:
            data = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
            with self._lock:
                for tid, task_dict in data.get("tasks", {}).items():
                    task = CodingTask.from_dict(task_dict)
                    sm = TaskStateMachine(task, max_retries=self.max_retries)
                    self._tasks[tid] = (task, sm)
                stats = data.get("stats", {})
                self.total_dispatched = stats.get("total_dispatched", 0)
                self.total_passed = stats.get("total_passed", 0)
                self.total_failed = stats.get("total_failed", 0)
                self.total_escalated = stats.get("total_escalated", 0)
            log.info("从快照恢复 %d 个任务", len(self._tasks))
            return True
        except Exception as e:
            log.warning("快照加载失败: %s", e)
            return False

    # ── 取下一批 (v3.0: 基于 MachineRegistry 动态分配) ──

    def next_batch(self) -> List[CodingTask]:
        """
        取出下一批可并行执行的任务:
        - 状态为 QUEUED
        - 所有 depends_on 已 PASSED
        - 通过 MachineRegistry 匹配空闲机器
        - 最多 max_concurrent 个
        """
        with self._lock:
            completed_ids = self._completed_task_ids()
            idle_machines = self.registry.get_idle_machines()

            batch = []
            used_machine_ids: Set[str] = set()

            for tid, (task, sm) in self._tasks.items():
                if not sm.can_dispatch:
                    continue

                # 检查依赖
                if task.depends_on:
                    if not all(dep in completed_ids for dep in task.depends_on):
                        continue

                # v3.0: 通过 tags 匹配空闲机器
                available = [
                    m for m in idle_machines
                    if m.machine_id not in used_machine_ids
                ]

                if task.assigned_machine:
                    # 指定了机器 — 检查该机器是否空闲
                    specific = [m for m in available if m.machine_id == task.assigned_machine]
                    if not specific:
                        continue
                    matched = specific[0]
                elif task.target_machine:
                    # v2 兼容: target_machine 直接指定
                    specific = [m for m in available if m.machine_id == task.target_machine]
                    if not specific:
                        continue
                    matched = specific[0]
                else:
                    # v3.0: 基于 tags 匹配
                    matched = self.registry.match_machine(task.tags, available)
                    if not matched:
                        continue

                # 分配机器
                task.assigned_machine = matched.machine_id
                batch.append(task)
                used_machine_ids.add(matched.machine_id)

                if len(batch) >= self.max_concurrent:
                    break

            return batch

    # ── 分发确认 ──

    def mark_dispatched(self, task_id: str) -> None:
        with self._lock:
            task, sm = self._get(task_id)
            sm.dispatch()
            machine_id = task.effective_machine
            if machine_id:
                self.registry.set_busy(machine_id, task_id)
            self.total_dispatched += 1

    # ── 编码完成 ──

    def handle_coding_done(self, task_id: str, result: TaskResult) -> None:
        with self._lock:
            task, sm = self._get(task_id)
            machine_id = task.effective_machine
            if machine_id:
                self.registry.set_idle(machine_id)

            sm.coding_done(result)

            if sm.is_retryable:
                sm.requeue()

    # ── Review 完成 ──

    def handle_review_done(self, task_id: str, review: ReviewResult) -> None:
        with self._lock:
            task, sm = self._get(task_id)
            sm.start_review()
            sm.review_done(review)

            if review.passed:
                log.info("[%s] Review 通过 (score=%.1f), 进入测试", task_id, review.score)
            else:
                log.info("[%s] Review 失败 (layer=%s), retries=%d/%d",
                         task_id, review.layer, task.total_retries, self.max_retries)
                if sm.is_retryable:
                    sm.requeue()
                elif task.status == TaskStatus.ESCALATED:
                    self.total_escalated += 1

    # ── 测试完成 ──

    def handle_test_done(self, task_id: str, test_result: TestResult) -> None:
        with self._lock:
            task, sm = self._get(task_id)
            sm.test_done(test_result)
            sm.judge(test_result)

            if task.status == TaskStatus.PASSED:
                self.total_passed += 1
                log.info("[%s] ✅ 测试通过! (pass=%d/%d)",
                         task_id, test_result.passed_count, test_result.total)
            elif task.status == TaskStatus.FAILED:
                sm.handle_failure()
                if sm.is_retryable:
                    sm.requeue()
                    log.info("[%s] 测试失败, 重试 %d/%d",
                             task_id, task.total_retries, self.max_retries)
                else:
                    self.total_escalated += 1
                    log.error("[%s] ❌ 测试失败且已达最大重试, 升级人工", task_id)

    # ── 状态查询 ──

    def all_done(self) -> bool:
        with self._lock:
            return all(sm.is_terminal for _, sm in self._tasks.values())

    def get_status_summary(self) -> Dict[str, int]:
        with self._lock:
            counts: Dict[str, int] = {}
            for _, (task, _) in self._tasks.items():
                status = task.status.value
                counts[status] = counts.get(status, 0) + 1
            return counts

    def get_task(self, task_id: str) -> Optional[CodingTask]:
        with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id][0]
            return None

    def get_all_tasks(self) -> List[CodingTask]:
        with self._lock:
            return [task for task, _ in self._tasks.values()]

    def get_tasks_in_status(self, status: TaskStatus) -> List[CodingTask]:
        with self._lock:
            return [task for task, _ in self._tasks.values() if task.status == status]

    def get_escalated_tasks(self) -> List[CodingTask]:
        return self.get_tasks_in_status(TaskStatus.ESCALATED)

    @property
    def total_tasks(self) -> int:
        return len(self._tasks)

    @property
    def completed_count(self) -> int:
        return self.total_passed + self.total_escalated

    @property
    def in_progress_count(self) -> int:
        with self._lock:
            return sum(
                1 for task, _ in self._tasks.values()
                if task.status in (
                    TaskStatus.DISPATCHED, TaskStatus.CODING_DONE,
                    TaskStatus.REVIEW, TaskStatus.TESTING, TaskStatus.JUDGING,
                )
            )

    # ── 内部工具 ──

    def _get(self, task_id: str) -> tuple:
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        return self._tasks[task_id]

    def _completed_task_ids(self) -> Set[str]:
        return {
            tid for tid, (task, _) in self._tasks.items()
            if task.status == TaskStatus.PASSED
        }
