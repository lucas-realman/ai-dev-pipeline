"""文档示例与配置样例回归测试。"""
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


@pytest.mark.component
def test_config_example_uses_supported_env_syntax():
    """示例配置必须使用 Config 支持的 ${VAR} 语法。"""
    content = _read("configs/config.example.yaml")
    assert "user: ${USER}" in content
    assert "user: $USER" not in content


@pytest.mark.component
def test_ops_runbook_uses_current_cli_syntax():
    """运维手册中的 CLI 示例必须与真实参数格式一致。"""
    content = _read("docs/09-operations/OPS-001-运维手册-Runbook.md")
    assert "autodev sprint --sprint" not in content
    assert "autodev dry-run --sprint" not in content
    assert "autodev --config ./config.yaml --sprint-id sprint-001 --mode sprint" in content
    assert "autodev --config ./config.yaml --sprint-id sprint-001 --dry-run" in content


@pytest.mark.component
def test_health_response_examples_match_dashboard_implementation():
    """README 与部署手册中的健康检查示例必须与真实返回保持一致。"""
    readme = _read("README.md")
    deployment = _read("docs/09-operations/OPS-002-部署手册-Deployment.md")
    expected = '{"status": "healthy", "version": "3.0.0"}'
    assert expected in readme
    assert '{"status":"healthy","version":"3.0.0"}' in deployment


@pytest.mark.component
def test_dashboard_modes_are_documented():
    """文档中必须明确区分本地联动模式与 Docker 独立模式。"""
    readme = _read("README.md")
    ops = _read("docs/09-operations/OPS-002-部署手册-Deployment.md")
    user = _read("docs/09-operations/USER-001-用户手册.md")

    assert "--serve-dashboard" in readme
    assert "Docker 独立模式" in readme
    assert "本地联动模式" in ops
    assert "9500" in ops and "8080" in ops
    assert "--serve-dashboard" in user