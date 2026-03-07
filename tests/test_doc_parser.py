"""
L2 组件测试 — 文档解析器 v2 兼容层 (MOD-002)
追加 TC, 覆盖 parse_task_card / _parse_tables / MACHINE_ALIAS / _expand_machine_range
对齐 TEST-001 §2.2
"""
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orchestrator.doc_parser import DocParser, MACHINE_ALIAS, MACHINE_DEFAULT_DIR
from orchestrator.task_models import CodingTask


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    return cfg


SAMPLE_CARD = textwrap.dedent("""\
    ## 1. Sprint 1：基础冲刺

    #### Day 1

    | 机器 | 任务 | Aider 指令 | 产出 | 验收 |
    |------|------|------------|------|------|
    | **W1** | 创建模块A | "实现featureA" | `agent/mod_a.py` | pytest pass |
    | **W2** | 创建模块B | "实现featureB" | `crm/mod_b.py` | pytest pass |

    #### Day 2

    | 机器 | 任务 | Aider 指令 | 产出 | 验收 |
    |------|------|------------|------|------|
    | **W3** | 部署网关 | "配置gateway" | `deploy/gateway.yaml` | curl 200 |
""")


# ── TC: parse_task_card 正常解析 ─────────────────────────

@pytest.mark.component
def test_parse_task_card_normal(tmp_path):
    """parse_task_card 解析 Day 表格并返回 CodingTask 列表"""
    card_path = tmp_path / "docs" / "07-Sprint任务卡.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(SAMPLE_CARD, encoding="utf-8")

    cfg = _make_config(tmp_path)
    parser = DocParser(cfg)
    tasks = parser.parse_task_card(str(card_path))

    assert len(tasks) == 3
    assert all(isinstance(t, CodingTask) for t in tasks)


# ── TC: parse_task_card 文件不存在 → 空列表 ──────────────

@pytest.mark.component
def test_parse_task_card_not_exist(tmp_path):
    """任务卡不存在 → 返回空列表"""
    cfg = _make_config(tmp_path)
    parser = DocParser(cfg)
    tasks = parser.parse_task_card("nonexistent.md")

    assert tasks == []


# ── TC: MACHINE_ALIAS 映射完整性 ────────────────────────

@pytest.mark.component
def test_machine_alias_completeness():
    """MACHINE_ALIAS 至少包含 W0~W5"""
    for key in ("W0", "W1", "W2", "W3", "W4", "W5"):
        assert key in MACHINE_ALIAS


# ── TC: _expand_machine_range ────────────────────────────

@pytest.mark.component
def test_expand_machine_range():
    """W1-W3 → [W1, W2, W3]"""
    cfg = _make_config(Path("/tmp"))
    parser = DocParser(cfg)
    result = parser._expand_machine_range("W1-W3")

    assert result == ["W1", "W2", "W3"]


@pytest.mark.component
def test_expand_machine_range_single():
    """非范围格式原样返回"""
    cfg = _make_config(Path("/tmp"))
    parser = DocParser(cfg)
    result = parser._expand_machine_range("W2")

    assert result == ["W2"]


# ── TC: _infer_target_dir ────────────────────────────────

@pytest.mark.component
def test_infer_target_dir_from_output_files():
    """从产出文件路径推断目标目录"""
    cfg = _make_config(Path("/tmp"))
    parser = DocParser(cfg)
    result = parser._infer_target_dir("`agent/mod_a.py`", "4090")

    assert result == "agent/"


@pytest.mark.component
def test_infer_target_dir_fallback_machine():
    """无路径信息 → 回退到 MACHINE_DEFAULT_DIR"""
    cfg = _make_config(Path("/tmp"))
    parser = DocParser(cfg)
    result = parser._infer_target_dir("", "4090")

    assert result == MACHINE_DEFAULT_DIR["4090"]


# ── TC: _infer_context_files ─────────────────────────────

@pytest.mark.component
def test_infer_context_files_with_contracts(tmp_path):
    """有 contracts 目录 → 包含 yaml 文件"""
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "c1.yaml").write_text("test: true", encoding="utf-8")
    (contracts / "c2.yml").write_text("mode: dev", encoding="utf-8")

    cfg = _make_config(tmp_path)
    parser = DocParser(cfg)
    files = parser._infer_context_files("agent/")

    assert "contracts/c1.yaml" in files
    assert "contracts/c2.yml" in files


# ── TC: read_contracts ───────────────────────────────────

@pytest.mark.component
def test_read_contracts(tmp_path):
    """read_contracts 读取所有契约文件"""
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "CONTRACT-001.yaml").write_text("api: v1\n", encoding="utf-8")

    cfg = _make_config(tmp_path)
    parser = DocParser(cfg)
    content = parser.read_contracts()

    assert "CONTRACT-001.yaml" in content
    assert "api: v1" in content


@pytest.mark.component
def test_read_contracts_no_dir(tmp_path):
    """contracts 目录不存在 → 返回空字符串"""
    cfg = _make_config(tmp_path)
    parser = DocParser(cfg)
    assert parser.read_contracts() == ""


# ── TC: 构造兼容 — 传字符串 ─────────────────────────────

@pytest.mark.component
def test_constructor_with_string():
    """DocParser 可传入字符串路径"""
    parser = DocParser("/tmp/myproject")
    assert parser.repo_path == Path("/tmp/myproject")


# ── TC: _extract_sprint_section 过滤 ────────────────────

@pytest.mark.component
def test_parse_task_card_with_sprint_filter(tmp_path):
    """传入 sprint=1 只解析对应章节"""
    card = tmp_path / "card.md"
    two_sprints = textwrap.dedent("""\
        ## 1. Sprint 1：基础

        #### Day 1

        | 机器 | 任务 | Aider 指令 | 产出 | 验收 |
        |------|------|------------|------|------|
        | **W1** | 任务A | "指令A" | `agent/a.py` | pass |

        ## 2. Sprint 2：进阶

        #### Day 1

        | 机器 | 任务 | Aider 指令 | 产出 | 验收 |
        |------|------|------------|------|------|
        | **W2** | 任务B | "指令B" | `crm/b.py` | pass |
    """)
    card.write_text(two_sprints, encoding="utf-8")

    cfg = _make_config(tmp_path)
    parser = DocParser(cfg)
    tasks = parser.parse_task_card(str(card), sprint=1)

    assert len(tasks) == 1
    assert "任务A" in tasks[0].description
