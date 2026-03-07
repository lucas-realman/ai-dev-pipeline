"""
L2 组件测试 — 自动 Review 引擎 (MOD-008)
TC-070 ~ TC-073, 覆盖 FR-012 / FR-013 / ALG-032
对齐 TEST-001 §2.2.8
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.reviewer import AutoReviewer
from orchestrator.task_models import CodingTask, TaskResult


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.openai_api_base = "http://localhost/v1"
    cfg.openai_api_key = "test-key"
    cfg.aider_model = "gpt-4"
    cfg.pass_threshold = 4.0
    return cfg


def _make_task_with_file(tmp_path: Path, code: str = "print('hello')\n") -> tuple:
    """创建一个含实际 .py 文件的任务"""
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    py_file = src_dir / "example.py"
    py_file.write_text(code, encoding="utf-8")

    task = CodingTask(
        task_id="T-RV-001",
        description="测试模块",
        tags=["python"],
        target_dir="src",
    )
    result = TaskResult(
        task_id="T-RV-001",
        exit_code=0,
        files_changed=["src/example.py"],
    )
    return task, result


# ── TC-070: Layer 1 静态检查通过 (FR-012) ────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc070_l1_static_pass(tmp_path):
    """TC-070: 合法 Python 代码 → Layer 1 通过"""
    cfg = _make_config(tmp_path)
    reviewer = AutoReviewer(cfg)

    task, result = _make_task_with_file(tmp_path, "def hello():\n    return 'hi'\n")

    review_result = await reviewer._run_l1_static(result.files_changed)
    assert review_result.passed is True
    assert review_result.layer == "static"


# ── TC-071: Layer 1 静态检查失败 (FR-012) ────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc071_l1_static_fail(tmp_path):
    """TC-071: 语法错误 Python → Layer 1 失败"""
    cfg = _make_config(tmp_path)
    reviewer = AutoReviewer(cfg)

    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "bad.py").write_text("def foo(\n", encoding="utf-8")

    result = await reviewer._run_l1_static(["src/bad.py"])
    assert result.passed is False
    assert result.layer == "static"
    assert any("编译错误" in issue for issue in result.issues)


# ── TC-072: review_task 三层完整流程 (FR-012/FR-013) ─────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc072_review_task_all_pass(tmp_path):
    """TC-072: 三层全部通过 (mock LLM)"""
    cfg = _make_config(tmp_path)
    (tmp_path / "contracts").mkdir(exist_ok=True)
    (tmp_path / "contracts" / "api.yaml").write_text("openapi: 3.0\n")

    reviewer = AutoReviewer(cfg)
    task, result = _make_task_with_file(tmp_path, "def hello():\n    return 'hi'\n")

    l2_resp = json.dumps({"passed": True, "issues": []})
    l3_resp = json.dumps({
        "scores": {"功能完整性": 5, "接口正确性": 5},
        "average_score": 5.0,
        "issues": [],
        "fix_instruction": "",
    })

    with patch.object(
        reviewer, "_call_llm",
        new_callable=AsyncMock,
        side_effect=[l2_resp, l3_resp],
    ):
        review = await reviewer.review_task(task, result)

    assert review.passed is True
    assert review.score >= 4.0


# ── TC-073: Layer 3 评分低于阈值 (FR-013) ────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_tc073_l3_below_threshold(tmp_path):
    """TC-073: L3 评分 < pass_threshold → 不通过"""
    cfg = _make_config(tmp_path)
    cfg.pass_threshold = 4.0
    (tmp_path / "contracts").mkdir(exist_ok=True)

    reviewer = AutoReviewer(cfg)
    task, result = _make_task_with_file(tmp_path, "x = 1\n")

    l2_resp = json.dumps({"passed": True, "issues": []})
    l3_resp = json.dumps({
        "scores": {"功能完整性": 2},
        "average_score": 2.5,
        "issues": ["功能不完整"],
        "fix_instruction": "请完善功能",
    })

    with patch.object(
        reviewer, "_call_llm",
        new_callable=AsyncMock,
        side_effect=[l2_resp, l3_resp],
    ):
        review = await reviewer.review_task(task, result)

    assert review.passed is False
    assert review.score < 4.0


# ── 附加: 无文件变更 → 自动失败 ──────────────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_no_files_changed(tmp_path):
    """files_changed 为空 → Review 失败"""
    cfg = _make_config(tmp_path)
    reviewer = AutoReviewer(cfg)

    task = CodingTask(task_id="T-NF", description="test", tags=["python"])
    result = TaskResult(task_id="T-NF", exit_code=0, files_changed=[])

    review = await reviewer.review_task(task, result)
    assert review.passed is False
    assert "无变更文件" in review.issues[0]


# ── 附加: _parse_json_response ────────────────────────────

@pytest.mark.component
def test_parse_json_response():
    """_parse_json_response 从各种格式提取 JSON"""
    # 正常 JSON
    assert AutoReviewer._parse_json_response('{"passed": true}')["passed"] is True

    # 围栏格式
    text = '```json\n{"passed": false}\n```'
    assert AutoReviewer._parse_json_response(text)["passed"] is False

    # 嵌入式
    text = '审查结果: {"passed": true, "issues": []} 结束'
    assert AutoReviewer._parse_json_response(text)["passed"] is True


# ── 附加: LLM 降级 (L2 失败 → 降级通过) ─────────────────

@pytest.mark.component
@pytest.mark.asyncio
async def test_l2_llm_fail_degrades(tmp_path):
    """L2 LLM 调用异常 → 降级通过 (score=4.0)"""
    cfg = _make_config(tmp_path)
    (tmp_path / "contracts").mkdir(exist_ok=True)
    (tmp_path / "contracts" / "api.yaml").write_text("x: 1\n")
    reviewer = AutoReviewer(cfg)

    task, result = _make_task_with_file(tmp_path, "x = 1\n")

    l3_resp = json.dumps({
        "scores": {"功能完整性": 5},
        "average_score": 5.0,
        "issues": [],
        "fix_instruction": "",
    })

    with patch.object(
        reviewer, "_call_llm",
        new_callable=AsyncMock,
        side_effect=[RuntimeError("LLM timeout"), l3_resp],
    ):
        review = await reviewer.review_task(task, result)

    # L2 降级通过, L3 正常通过
    assert review.passed is True
