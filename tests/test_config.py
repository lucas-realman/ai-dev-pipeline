"""
L2 组件测试 — 配置加载器 (MOD-012)
TC-040 ~ TC-043, 覆盖 FR-016 / FR-017 / ALG-025a
对齐 TEST-001 §2.2.4
"""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from orchestrator.config import Config, ConfigSchemaError


# ── TC-040: 合法 YAML 加载 (FR-016) ──────────────────────

@pytest.mark.component
def test_tc040_valid_config_load(valid_config_path, tmp_project_dir):
    """TC-040: 合法 YAML 正常加载, 关键属性可读"""
    config = Config(
        config_path=str(valid_config_path),
        project_root=str(tmp_project_dir),
    )
    assert config.mode is not None
    assert config.current_sprint is not None
    assert config.max_retries >= 0
    assert config.repo_root == tmp_project_dir


# ── TC-041: 环境变量展开 (FR-017) ─────────────────────────

@pytest.mark.component
def test_tc041_env_var_expansion(tmp_path):
    """TC-041: ${VAR} 格式环境变量正确展开"""
    os.environ["TEST_API_KEY"] = "my-secret-key-12345"
    os.environ["TEST_API_BASE"] = "http://test.api.com/v1"

    config_data = {
        "orchestrator": {"mode": "sprint", "current_sprint": 1, "poll_interval": 10},
        "llm": {
            "openai_api_base": "${TEST_API_BASE}",
            "openai_api_key": "${TEST_API_KEY}",
            "model": "gpt-4",
        },
        "task": {"single_task_timeout": 600, "max_retries": 3},
    }

    config_file = tmp_path / "config_env.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    try:
        config = Config(config_path=str(config_file), project_root=str(tmp_path))
        assert config.openai_api_key == "my-secret-key-12345"
        assert config.openai_api_base == "http://test.api.com/v1"
    finally:
        os.environ.pop("TEST_API_KEY", None)
        os.environ.pop("TEST_API_BASE", None)


# ── TC-042: 必填字段缺失 → ConfigSchemaError (ALG-025a) ──

@pytest.mark.component
def test_tc042_missing_required_fields(tmp_path):
    """TC-042: 缺少 orchestrator/llm/task → ConfigSchemaError"""
    config_data = {"project": {"name": "test"}}  # 缺少全部必填段

    config_file = tmp_path / "config_bad.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with pytest.raises(ConfigSchemaError, match="配置文件校验失败"):
        Config(config_path=str(config_file), project_root=str(tmp_path))


@pytest.mark.component
def test_tc042b_missing_llm_fields(tmp_path):
    """TC-042b: orchestrator 存在但 llm 缺少 api_key → ConfigSchemaError"""
    config_data = {
        "orchestrator": {"mode": "sprint", "current_sprint": 1, "poll_interval": 10},
        "llm": {"openai_api_base": "http://x", "model": "gpt-4"},  # 缺少 openai_api_key
        "task": {"single_task_timeout": 600, "max_retries": 3},
    }

    config_file = tmp_path / "config_nollm.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with pytest.raises(ConfigSchemaError, match="openai_api_key"):
        Config(config_path=str(config_file), project_root=str(tmp_path))


# ── TC-043: machines 列表解析 (FR-004) ────────────────────

@pytest.mark.component
def test_tc043_machines_list_parsing(tmp_path):
    """TC-043: machines 列表正确解析为 MachineInfo"""
    config_data = {
        "orchestrator": {"mode": "sprint", "current_sprint": 1, "poll_interval": 10},
        "llm": {
            "openai_api_base": "http://api.x/v1",
            "openai_api_key": "key123",
            "model": "gpt-4",
        },
        "task": {"single_task_timeout": 600, "max_retries": 3},
        "machines": [
            {
                "machine_id": "gpu01",
                "display_name": "GPU Server",
                "host": "10.0.0.1",
                "user": "dev",
                "tags": ["python", "gpu"],
            },
            {
                "machine_id": "cpu01",
                "display_name": "CPU Server",
                "host": "10.0.0.2",
                "user": "dev",
                "tags": ["python"],
            },
        ],
    }

    config_file = tmp_path / "config_machines.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    config = Config(config_path=str(config_file), project_root=str(tmp_path))

    machines_list = config.get_machines_list()
    assert len(machines_list) == 2
    assert machines_list[0]["machine_id"] == "gpu01"

    machines_dict = config.get_machines()
    assert "gpu01" in machines_dict
    assert machines_dict["gpu01"].host == "10.0.0.1"
    assert "gpu" in machines_dict["gpu01"].tags


# ── 附加: get() 点号路径访问 ──────────────────────────────

@pytest.mark.component
def test_config_dotpath_access(valid_config_path, tmp_project_dir):
    """config.get() 支持 a.b.c 风格的路径访问"""
    config = Config(
        config_path=str(valid_config_path),
        project_root=str(tmp_project_dir),
    )
    assert config.get("orchestrator.mode") is not None
    assert config.get("nonexistent.key", "default_val") == "default_val"


# ── 附加: 负 timeout 校验 ────────────────────────────────

@pytest.mark.component
def test_negative_timeout_raises(tmp_path):
    """task.single_task_timeout 为负 → ConfigSchemaError"""
    config_data = {
        "orchestrator": {"mode": "sprint", "current_sprint": 1, "poll_interval": 10},
        "llm": {
            "openai_api_base": "http://x/v1",
            "openai_api_key": "k",
            "model": "m",
        },
        "task": {"single_task_timeout": -1, "max_retries": 3},
    }
    config_file = tmp_path / "config_neg.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with pytest.raises(ConfigSchemaError, match="正数"):
        Config(config_path=str(config_file), project_root=str(tmp_path))


# ── 附加: 旧版 dict 格式 machines 兼容 ──────────────────

@pytest.mark.component
def test_machines_dict_compat(tmp_path):
    """machines 为 dict 格式时自动转换为 list 格式"""
    config_data = {
        "orchestrator": {"mode": "sprint", "current_sprint": 1, "poll_interval": 10},
        "llm": {
            "openai_api_base": "http://x/v1",
            "openai_api_key": "k",
            "model": "m",
        },
        "task": {"single_task_timeout": 600, "max_retries": 3},
        "machines": {
            "W1": {"host": "10.0.0.1", "user": "dev", "tags": ["gpu"]},
            "W2": {"host": "10.0.0.2", "user": "dev"},
        },
    }
    config_file = tmp_path / "config_dict.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")

    config = Config(config_path=str(config_file), project_root=str(tmp_path))
    ml = config.get_machines_list()
    assert len(ml) == 2
    ids = {m["machine_id"] for m in ml}
    assert "W1" in ids
    assert "W2" in ids
