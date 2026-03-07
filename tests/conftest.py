"""
pytest 全局配置 — conftest.py
对齐 TEST-001 §3.2: 注册 4 个 pytest 标记 + 共享 fixtures

标记:
  - smoke:       L1 冒烟测试 (每次 commit)
  - component:   L2 组件测试 (每次 Sprint)
  - integration: L3 集成测试 (每次 Sprint)
  - acceptance:  L4 验收测试 (里程碑节点)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest
import yaml

# ── pytest 标记注册 ──────────────────────────────────────

def pytest_configure(config):
    """注册自定义 pytest 标记 (TEST-001 §3.2)"""
    config.addinivalue_line("markers", "smoke: L1 冒烟测试 — 每次 commit 执行")
    config.addinivalue_line("markers", "component: L2 组件测试 — 每个模块核心逻辑")
    config.addinivalue_line("markers", "integration: L3 集成测试 — 模块间端到端链路")
    config.addinivalue_line("markers", "acceptance: L4 验收测试 — 里程碑人工+自动验收")


# ── 路径常量 ──────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).parent.parent


# ── 共享 Fixtures ─────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> Path:
    """返回 tests/fixtures/ 目录路径"""
    return FIXTURES_DIR


@pytest.fixture
def project_root() -> Path:
    """返回项目根目录路径"""
    return PROJECT_ROOT


@pytest.fixture
def valid_config_path() -> Path:
    """合法配置文件路径"""
    return FIXTURES_DIR / "config_valid.yaml"


@pytest.fixture
def invalid_config_path() -> Path:
    """非法配置文件路径 (缺少必填项)"""
    return FIXTURES_DIR / "config_invalid.yaml"


@pytest.fixture
def bad_schema_config_path() -> Path:
    """Schema 错误配置文件路径"""
    return FIXTURES_DIR / "config_bad_schema.yaml"


@pytest.fixture
def sample_tasks_path() -> Path:
    """预定义任务列表 JSON 路径"""
    return FIXTURES_DIR / "sample_tasks.json"


@pytest.fixture
def mock_doc_set_dir() -> Path:
    """模拟文档集目录路径"""
    return FIXTURES_DIR / "mock_doc_set"


@pytest.fixture
def valid_config_data() -> Dict:
    """加载合法配置为字典"""
    path = FIXTURES_DIR / "config_valid.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_tasks_data() -> List[Dict]:
    """加载预定义任务列表"""
    import json
    path = FIXTURES_DIR / "sample_tasks.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """创建临时项目目录结构, 用于集成测试"""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / "orchestrator").mkdir()
    (project / "tests").mkdir()
    (project / "contracts").mkdir()
    (project / "docs").mkdir()
    (project / "reports").mkdir()
    return project


@pytest.fixture
def mock_config(tmp_project_dir: Path, valid_config_path: Path):
    """创建基于临时目录的 Config 对象 (用于组件/集成测试)"""
    from orchestrator.config import Config

    # 设置必要的环境变量, 避免 Config 加载失败
    env_backup = {}
    env_vars = {
        "OPENAI_API_BASE": "http://localhost:8000/v1",
        "OPENAI_API_KEY": "test-key-for-testing",
        "AIDER_MODEL": "test-model",
    }
    for k, v in env_vars.items():
        env_backup[k] = os.environ.get(k)
        os.environ[k] = v

    try:
        config = Config(
            config_path=str(valid_config_path),
            project_root=str(tmp_project_dir),
        )
        yield config
    finally:
        # 恢复环境变量
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture
def sample_coding_task():
    """创建一个标准测试用 CodingTask"""
    from orchestrator.task_models import CodingTask
    return CodingTask(
        task_id="T-TEST-001",
        description="测试任务: 实现示例模块",
        module_name="example",
        tags=["python", "testing"],
        target_dir="src/example",
        acceptance=["pytest tests/test_example.py 通过", "代码可正常导入"],
        depends_on=[],
        estimated_minutes=15,
    )


@pytest.fixture
def sample_coding_tasks():
    """创建一组带依赖关系的 CodingTask"""
    from orchestrator.task_models import CodingTask
    t1 = CodingTask(
        task_id="T-001",
        description="任务1: 基础模块",
        tags=["python"],
        target_dir="src/base",
    )
    t2 = CodingTask(
        task_id="T-002",
        description="任务2: 依赖任务1",
        tags=["python", "gpu"],
        depends_on=["T-001"],
        target_dir="src/advanced",
    )
    t3 = CodingTask(
        task_id="T-003",
        description="任务3: 独立任务",
        tags=["frontend"],
        target_dir="src/web",
    )
    return [t1, t2, t3]


@pytest.fixture
def mock_machine_registry():
    """创建预填充的 MachineRegistry"""
    from orchestrator.machine_registry import MachineRegistry
    from orchestrator.task_models import MachineInfo

    reg = MachineRegistry()
    machines = [
        MachineInfo(machine_id="gpu_4090", display_name="GPU", host="10.0.0.1",
                    user="dev", tags=["gpu", "python", "cuda"]),
        MachineInfo(machine_id="mac_mini", display_name="Mac", host="10.0.0.2",
                    user="dev", tags=["macos", "frontend", "python"]),
        MachineInfo(machine_id="gateway", display_name="GW", host="10.0.0.3",
                    user="dev", tags=["linux", "deploy", "docker"]),
    ]
    for m in machines:
        reg.register(m)
    return reg
