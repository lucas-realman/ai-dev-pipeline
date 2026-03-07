"""
L2 组件测试 — 机器注册表 (MOD-003)
TC-020 ~ TC-024, 覆盖 FR-004 / FR-005 / NFR-003
对齐 TEST-001 §2.2.2
"""
import threading

import pytest

from orchestrator.machine_registry import MachineRegistry
from orchestrator.task_models import MachineInfo, MachineStatus


def _make_machine(mid: str, tags: list | None = None, cpu: float = 0.0) -> MachineInfo:
    m = MachineInfo(
        machine_id=mid,
        display_name=mid.upper(),
        host=f"10.0.0.{mid[-1]}",
        user="dev",
        tags=tags or [],
    )
    m.load["cpu_percent"] = cpu
    return m


# ── TC-020: 注册/注销机器 (FR-004) ────────────────────────────

@pytest.mark.component
def test_tc020_register_unregister():
    """TC-020: register + unregister, 数量增减正确"""
    reg = MachineRegistry()
    m1 = _make_machine("m1", ["gpu"])
    m2 = _make_machine("m2", ["cpu"])

    reg.register(m1)
    assert len(reg) == 1
    reg.register(m2)
    assert len(reg) == 2
    assert len(reg.get_all_machines()) == 2

    # 注销已存在的
    result = reg.unregister("m1")
    assert result is True
    assert len(reg) == 1

    # 注销不存在的
    result = reg.unregister("m999")
    assert result is False
    assert len(reg) == 1

    # 查询
    assert reg.get_machine("m2") is not None
    assert reg.get_machine("m1") is None


# ── TC-021: 标签匹配 — 命中 (FR-005) ─────────────────────────

@pytest.mark.component
def test_tc021_tag_match_hit():
    """TC-021: tags=["gpu"] → 返回含 gpu 标签的机器"""
    reg = MachineRegistry()
    reg.register(_make_machine("m1", ["gpu", "python"]))
    reg.register(_make_machine("m2", ["cpu", "python"]))
    reg.register(_make_machine("m3", ["gpu", "cuda"]))

    matched = reg.match_machine(["gpu"])
    assert matched is not None
    assert "gpu" in matched.tags

    # 多标签: 需要同时满足
    matched_multi = reg.match_machine(["gpu", "cuda"])
    assert matched_multi is not None
    assert matched_multi.machine_id == "m3"

    # 无标签要求: 返回任意空闲
    matched_any = reg.match_machine([])
    assert matched_any is not None


# ── TC-022: 标签匹配 — 降级匹配 (FR-005) ─────────────────────

@pytest.mark.component
def test_tc022_tag_match_fallback():
    """TC-022: tags=["nonexistent"] 完全不匹配 → 降级返回部分匹配/任意空闲"""
    reg = MachineRegistry()
    reg.register(_make_machine("m1", ["gpu"]))
    reg.register(_make_machine("m2", ["cpu"]))

    # 没有机器有 "nonexistent" 标签, 但降级策略会返回某台空闲机器
    matched = reg.match_machine(["nonexistent"])
    assert matched is not None  # 降级匹配: 返回交集最大的

    # 所有机器都离线时返回 None
    reg.set_offline("m1")
    reg.set_offline("m2")
    matched_none = reg.match_machine(["gpu"])
    assert matched_none is None


# ── TC-023: 负载排序 (FR-005) ─────────────────────────────────

@pytest.mark.component
def test_tc023_load_balancing_least_loaded():
    """TC-023: 3台不同负载 → 返回 cpu_percent 最低的"""
    reg = MachineRegistry()
    reg.register(_make_machine("m1", ["python"], cpu=90.0))
    reg.register(_make_machine("m2", ["python"], cpu=10.0))
    reg.register(_make_machine("m3", ["python"], cpu=50.0))

    matched = reg.match_machine(["python"])
    assert matched is not None
    assert matched.machine_id == "m2"  # 10% CPU → 最低负载


# ── TC-024: 线程安全 (NFR-003) ────────────────────────────────

@pytest.mark.component
def test_tc024_thread_safety():
    """TC-024: 并发 register/set_busy → 无竞态异常"""
    reg = MachineRegistry()
    errors = []

    def register_worker(n: int):
        try:
            for i in range(50):
                mid = f"w{n}_m{i}"
                m = _make_machine(mid, ["tag"])
                reg.register(m)
        except Exception as e:
            errors.append(e)

    def status_worker(n: int):
        try:
            for i in range(50):
                mid = f"w{n}_m{i}"
                reg.set_busy(mid, f"T-{i}")
                reg.set_idle(mid)
        except Exception as e:
            errors.append(e)

    # 同时启动注册和状态切换线程
    threads = []
    for n in range(4):
        threads.append(threading.Thread(target=register_worker, args=(n,)))
        threads.append(threading.Thread(target=status_worker, args=(n,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(errors) == 0, f"线程安全测试发现 {len(errors)} 个异常: {errors}"


# ── 附加: load_from_config ────────────────────────────────────

@pytest.mark.component
def test_load_from_config():
    """验证 load_from_config 正确解析列表配置"""
    reg = MachineRegistry()
    machines_config = [
        {"machine_id": "gpu_4090", "host": "10.0.0.1", "user": "dev",
         "tags": ["gpu", "cuda"], "work_dir": "~/project"},
        {"machine_id": "mac_mini", "host": "10.0.0.2", "user": "dev",
         "tags": ["macos"], "port": 2222},
    ]
    reg.load_from_config(machines_config)

    assert len(reg) == 2
    m = reg.get_machine("mac_mini")
    assert m is not None
    assert m.port == 2222
    assert "macos" in m.tags


@pytest.mark.component
def test_set_busy_and_idle():
    """验证 set_busy / set_idle 正确切换状态"""
    reg = MachineRegistry()
    reg.register(_make_machine("m1"))

    reg.set_busy("m1", "T-001")
    m = reg.get_machine("m1")
    assert m.status == MachineStatus.BUSY
    assert m.current_task_id == "T-001"
    assert m.busy_since is not None

    reg.set_idle("m1")
    m = reg.get_machine("m1")
    assert m.status == MachineStatus.ONLINE
    assert m.current_task_id is None
    assert m.busy_since is None


@pytest.mark.component
def test_online_count():
    """验证 get_online_count 统计在线+忙碌"""
    reg = MachineRegistry()
    reg.register(_make_machine("m1"))
    reg.register(_make_machine("m2"))
    reg.register(_make_machine("m3"))

    assert reg.get_online_count() == 3

    reg.set_busy("m1", "T-001")
    assert reg.get_online_count() == 3  # busy 仍算 online

    reg.set_offline("m2")
    assert reg.get_online_count() == 2
