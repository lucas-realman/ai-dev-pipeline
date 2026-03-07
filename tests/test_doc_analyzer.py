"""
L2 组件测试 — 文档集分析器 (MOD-001)
TC-050 ~ TC-055, 覆盖 FR-008 / FR-009 / ALG-032
对齐 TEST-001 §2.2.6
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.doc_analyzer import DocAnalyzer
from orchestrator.task_models import CodingTask


# ── 辅助: 创建 Mock Config ──────────────────────────────

def _make_config(tmp_path: Path, doc_set: dict = None) -> MagicMock:
    cfg = MagicMock()
    cfg.project_path = tmp_path
    cfg.doc_set = doc_set or {}
    cfg.openai_api_base = "http://localhost:8000/v1"
    cfg.openai_api_key = "test-key"
    cfg.aider_model = "gpt-4"
    return cfg


# ── TC-050: load_doc_set 正常加载 (FR-008) ───────────────

@pytest.mark.component
def test_tc050_load_doc_set(tmp_path):
    """TC-050: glob 模式匹配, 文档内容正确拼接"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "req1.md").write_text("# 需求文档1\n内容A")
    (docs_dir / "req2.md").write_text("# 需求文档2\n内容B")

    cfg = _make_config(tmp_path, doc_set={"requirements": "docs/*.md"})
    analyzer = DocAnalyzer(cfg)

    doc_set = analyzer.load_doc_set()
    assert "requirements" in doc_set
    assert "内容A" in doc_set["requirements"]
    assert "内容B" in doc_set["requirements"]


# ── TC-051: 空文档集 (FR-008) ─────────────────────────────

@pytest.mark.component
def test_tc051_empty_doc_set(tmp_path):
    """TC-051: 无匹配文件 → 空 dict"""
    cfg = _make_config(tmp_path, doc_set={"design": "nonexistent/*.md"})
    analyzer = DocAnalyzer(cfg)

    doc_set = analyzer.load_doc_set()
    assert doc_set == {}


# ── TC-052: _extract_json 三种格式 (FR-009) ──────────────

@pytest.mark.component
def test_tc052_extract_json_plain():
    """TC-052a: 纯 JSON 数组"""
    text = '[{"task_id": "T1", "description": "test"}]'
    result = DocAnalyzer._extract_json(text)
    assert isinstance(result, list)
    assert result[0]["task_id"] == "T1"


@pytest.mark.component
def test_tc052b_extract_json_fenced():
    """TC-052b: ```json ``` 围栏"""
    text = '这是一段说明\n```json\n[{"task_id": "T2"}]\n```\n后续文本'
    result = DocAnalyzer._extract_json(text)
    assert result[0]["task_id"] == "T2"


@pytest.mark.component
def test_tc052c_extract_json_embedded():
    """TC-052c: 正文中嵌入 JSON"""
    text = '任务分解结果: [{"task_id": "T3"}] 以上'
    result = DocAnalyzer._extract_json(text)
    assert result[0]["task_id"] == "T3"


@pytest.mark.component
def test_tc052d_extract_json_invalid():
    """TC-052d: 无效 JSON → ValueError"""
    with pytest.raises(ValueError, match="无法从"):
        DocAnalyzer._extract_json("这段话不含任何 JSON")


# ── TC-053: _parse_tasks_from_llm (FR-009) ────────────────

@pytest.mark.component
def test_tc053_parse_tasks_from_llm(tmp_path):
    """TC-053: LLM 回复 → CodingTask 列表"""
    cfg = _make_config(tmp_path)
    analyzer = DocAnalyzer(cfg)

    llm_response = json.dumps([
        {
            "task_id": "S1_T1",
            "description": "实现认证模块",
            "tags": ["python"],
            "target_dir": "src/auth",
            "acceptance": ["测试通过"],
            "depends_on": [],
            "estimated_minutes": 30,
        },
        {
            "task_id": "S1_T2",
            "description": "实现日志模块",
            "tags": ["python"],
            "depends_on": ["S1_T1"],
        },
    ])

    tasks = analyzer._parse_tasks_from_llm(llm_response)
    assert len(tasks) == 2
    assert isinstance(tasks[0], CodingTask)
    assert tasks[0].task_id == "S1_T1"
    assert tasks[1].depends_on == ["S1_T1"]


# ── TC-054: analyze_and_decompose 正常路径 (FR-009, mock LLM) ─

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc054_analyze_and_decompose(tmp_path):
    """TC-054: 完整流程 (mock LLM)"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "requirements.md").write_text("# 需求\n实现用户管理模块")

    cfg = _make_config(tmp_path, doc_set={"requirements": "docs/*.md"})
    analyzer = DocAnalyzer(cfg)

    llm_return = json.dumps([
        {"task_id": "S1_T1", "description": "用户管理", "tags": ["python"]}
    ])

    with patch.object(analyzer, "_call_llm", new_callable=AsyncMock, return_value=llm_return):
        tasks = await analyzer.analyze_and_decompose(sprint=1)

    assert len(tasks) == 1
    assert tasks[0].task_id == "S1_T1"


# ── TC-055: LLM 调用失败 → 空列表 (ALG-032) ─────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc055_llm_failure_returns_empty(tmp_path):
    """TC-055: LLM 异常 → analyze_and_decompose 返回空列表"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "reqs.md").write_text("# 需求\n内容")

    cfg = _make_config(tmp_path, doc_set={"requirements": "docs/*.md"})
    analyzer = DocAnalyzer(cfg)

    with patch.object(
        analyzer, "_call_llm",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM 超时"),
    ):
        tasks = await analyzer.analyze_and_decompose()

    assert tasks == []


# ── 附加: get_doc_set_summary ─────────────────────────────

@pytest.mark.component
def test_doc_set_summary(tmp_path):
    """get_doc_set_summary 返回 {doc_type: count}"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("a")
    (docs_dir / "b.md").write_text("b")

    cfg = _make_config(tmp_path, doc_set={"requirements": "docs/*.md"})
    analyzer = DocAnalyzer(cfg)

    summary = analyzer.get_doc_set_summary()
    assert summary["requirements"] == 2
