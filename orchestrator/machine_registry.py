"""
AI Dev Pipeline — 动态机器池管理
v3.0 核心新增模块: 管理开发机器的注册、状态、任务分配。
替代 v2 中硬编码的 5 台机器配置。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Set

from .task_models import MachineInfo, MachineStatus

log = logging.getLogger("orchestrator.machine_registry")


class MachineRegistry:
    """
    动态机器池管理器。

    功能:
    - 从 config.yaml 加载初始机器列表
    - 支持运行时注册/注销机器 (未来通过 API)
    - 按 tags 匹配任务需求
    - 追踪机器状态 (online/busy/offline/error)
    - 负载均衡: 选择最空闲的匹配机器
    """

    def __init__(self):
        self._machines: Dict[str, MachineInfo] = {}
        self._lock = threading.Lock()

    # ── 注册 / 注销 ──

    def register(self, machine: MachineInfo) -> None:
        """注册一台机器到池中"""
        with self._lock:
            self._machines[machine.machine_id] = machine
            log.info("机器注册: %s (%s@%s) tags=%s",
                     machine.machine_id, machine.user, machine.host, machine.tags)

    def unregister(self, machine_id: str) -> bool:
        """从池中移除一台机器"""
        with self._lock:
            if machine_id in self._machines:
                del self._machines[machine_id]
                log.info("机器注销: %s", machine_id)
                return True
            return False

    def load_from_config(self, machines_config: list) -> None:
        """从 config.yaml 的 machines 列表加载机器"""
        for cfg in machines_config:
            machine = MachineInfo(
                machine_id=cfg["machine_id"],
                display_name=cfg.get("display_name", cfg["machine_id"]),
                host=cfg["host"],
                port=cfg.get("port", 22),
                user=cfg["user"],
                work_dir=cfg.get("work_dir", "~/projects"),
                tags=cfg.get("tags", []),
                aider_prefix=cfg.get("aider_prefix", ""),
                aider_model=cfg.get("aider_model", ""),
            )
            self.register(machine)

    # ── 查询 ──

    def get_machine(self, machine_id: str) -> Optional[MachineInfo]:
        """获取指定机器信息"""
        with self._lock:
            return self._machines.get(machine_id)

    def get_all_machines(self) -> List[MachineInfo]:
        """获取所有机器"""
        with self._lock:
            return list(self._machines.values())

    def get_online_machines(self) -> List[MachineInfo]:
        """获取所有在线且空闲的机器"""
        with self._lock:
            return [
                m for m in self._machines.values()
                if m.status == MachineStatus.ONLINE
            ]

    def get_idle_machines(self) -> List[MachineInfo]:
        """获取所有空闲机器 (online 且无当前任务)"""
        with self._lock:
            return [
                m for m in self._machines.values()
                if m.status == MachineStatus.ONLINE and m.current_task_id is None
            ]

    def get_busy_machines(self) -> List[MachineInfo]:
        """获取所有忙碌机器 (DD-MOD-003)"""
        with self._lock:
            return [
                m for m in self._machines.values()
                if m.status == MachineStatus.BUSY
            ]

    def get_online_count(self) -> int:
        """在线机器数"""
        with self._lock:
            return sum(1 for m in self._machines.values()
                       if m.status in (MachineStatus.ONLINE, MachineStatus.BUSY))

    # ── 任务匹配 ──

    def match_machine(
        self,
        task_tags: List[str],
        available: Optional[List[MachineInfo]] = None,
    ) -> Optional[MachineInfo]:
        """
        基于 tags 能力匹配 + 负载均衡的任务分配。

        策略:
        1. 优先匹配: tags 完全覆盖 task_tags 的空闲机器
        2. 降级匹配: 忽略 tags，取任意空闲机器
        3. 无可用: 返回 None (任务排队等待)
        """
        if available is None:
            available = self.get_idle_machines()

        if not available:
            return None

        task_tags_set = set(task_tags) if task_tags else set()

        # 优先: tags 完全覆盖
        if task_tags_set:
            candidates = [
                m for m in available
                if task_tags_set.issubset(set(m.tags))
            ]
            if candidates:
                return self._pick_least_loaded(candidates)

        # 降级: 任意空闲机器 (tags 部分匹配优先)
        if task_tags_set:
            # 按 tags 交集大小排序
            scored = sorted(
                available,
                key=lambda m: len(task_tags_set & set(m.tags)),
                reverse=True,
            )
            return scored[0]

        # 无 tags 要求: 最空闲的
        return self._pick_least_loaded(available)

    # ── 状态管理 ──

    def set_status(self, machine_id: str, status: MachineStatus) -> None:
        """设置机器状态"""
        with self._lock:
            if machine_id in self._machines:
                self._machines[machine_id].status = status

    def set_busy(self, machine_id: str, task_id: str) -> None:
        """标记机器为忙碌"""
        with self._lock:
            if machine_id in self._machines:
                self._machines[machine_id].status = MachineStatus.BUSY
                self._machines[machine_id].current_task_id = task_id
                self._machines[machine_id].busy_since = time.time()

    def set_idle(self, machine_id: str) -> None:
        """标记机器为空闲"""
        with self._lock:
            if machine_id in self._machines:
                self._machines[machine_id].status = MachineStatus.ONLINE
                self._machines[machine_id].current_task_id = None
                self._machines[machine_id].busy_since = None

    def set_offline(self, machine_id: str) -> None:
        """标记机器为离线 (DD-MOD-003)"""
        with self._lock:
            if machine_id in self._machines:
                self._machines[machine_id].status = MachineStatus.OFFLINE
                self._machines[machine_id].current_task_id = None
                self._machines[machine_id].busy_since = None

    def update_load(self, machine_id: str, load: Dict[str, float]) -> None:
        """更新机器负载信息 (心跳上报)"""
        with self._lock:
            if machine_id in self._machines:
                self._machines[machine_id].load.update(load)

    # ── 内部工具 ──

    @staticmethod
    def _pick_least_loaded(machines: List[MachineInfo]) -> MachineInfo:
        """选择负载最低的机器"""
        return min(machines, key=lambda m: m.load.get("cpu_percent", 0.0))

    def __len__(self) -> int:
        return len(self._machines)

    def __repr__(self) -> str:
        return f"MachineRegistry({len(self._machines)} machines)"
