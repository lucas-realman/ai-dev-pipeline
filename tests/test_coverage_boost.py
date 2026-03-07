"""
Sprint 3 — 覆盖率提升测试
针对 dispatcher, reviewer, test_runner, reporter, config 中纯函数 / 可 mock 路径。
目标: 将覆盖率从 81% → 85%+
"""
from __future__ import annotations

import asyncio
import json
import os
import textwrap
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from orchestrator.task_models import (
    CodingTask, MachineInfo, MachineStatus, TaskResult, TaskStatus,
    ReviewResult, TestResult,
)

# ═══════════════════════════════════════════════════════════════════════
#  reviewer.py — 纯函数路径
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def reviewer(tmp_path):
    """创建 AutoReviewer (mock config)"""
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.openai_api_base = "http://fake:8000/v1"
    cfg.openai_api_key = "sk-test"
    cfg.aider_model = "gpt-4"
    cfg.pass_threshold = 4.0
    from orchestrator.reviewer import AutoReviewer
    return AutoReviewer(cfg)


class TestReviewerParseJsonResponse:
    """_parse_json_response 三条解析路径"""

    @pytest.mark.component
    def test_parse_direct_json(self, reviewer):
        result = reviewer._parse_json_response('{"passed": true, "issues": []}')
        assert result["passed"] is True

    @pytest.mark.component
    def test_parse_fenced_json(self, reviewer):
        text = '这是解释\n```json\n{"passed": false, "issues": ["bug1"]}\n```\n后续'
        result = reviewer._parse_json_response(text)
        assert result["passed"] is False
        assert "bug1" in result["issues"]

    @pytest.mark.component
    def test_parse_embedded_json(self, reviewer):
        text = "分析结果: 经过检查 {\"passed\": true, \"issues\": []} 以上"
        result = reviewer._parse_json_response(text)
        assert result["passed"] is True

    @pytest.mark.component
    def test_parse_invalid_json_raises(self, reviewer):
        with pytest.raises(ValueError, match="无法从 LLM"):
            reviewer._parse_json_response("no json here at all")


class TestReviewerBuildCodeSnippet:

    @pytest.mark.component
    def test_build_code_snippet_file(self, reviewer, tmp_path):
        py_file = tmp_path / "mod.py"
        py_file.write_text("def hello(): pass\n")
        result = reviewer._build_code_snippet(["mod.py"])
        assert "def hello" in result

    @pytest.mark.component
    def test_build_code_snippet_dir(self, reviewer, tmp_path):
        subdir = tmp_path / "pkg"
        subdir.mkdir()
        (subdir / "a.py").write_text("class A: pass\n")
        (subdir / "b.py").write_text("class B: pass\n")
        result = reviewer._build_code_snippet(["pkg"])
        assert "class A" in result
        assert "class B" in result

    @pytest.mark.component
    def test_build_code_snippet_missing(self, reviewer):
        result = reviewer._build_code_snippet(["nonexistent.py"])
        assert result == ""


class TestReviewerReadContracts:

    @pytest.mark.component
    def test_read_contracts_found(self, reviewer, tmp_path):
        cdir = tmp_path / "contracts"
        cdir.mkdir()
        (cdir / "api.yaml").write_text("openapi: 3.0")
        result = reviewer._read_contracts(CodingTask(task_id="T1", description="x"))
        assert "openapi" in result

    @pytest.mark.component
    def test_read_contracts_empty(self, reviewer, tmp_path):
        result = reviewer._read_contracts(CodingTask(task_id="T1", description="x"))
        assert result == ""


class TestReviewerReviewTask:

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_review_no_files(self, reviewer):
        """无变更文件时直接返回失败"""
        task = CodingTask(task_id="T1", description="test")
        result_obj = TaskResult(task_id="T1", exit_code=0, files_changed=[])
        rv = await reviewer.review_task(task, result_obj)
        assert not rv.passed
        assert "无变更文件" in rv.issues[0]

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_review_l1_compile_error(self, reviewer, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def foo(\n")  # syntax error
        task = CodingTask(task_id="T1", description="test")
        result_obj = TaskResult(task_id="T1", exit_code=0, files_changed=["bad.py"])
        rv = await reviewer.review_task(task, result_obj)
        assert not rv.passed
        assert rv.layer == "static"

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_review_l2_contract_llm_fallback(self, reviewer, tmp_path):
        """L2 LLM 调用失败时降级通过"""
        py = tmp_path / "good.py"
        py.write_text("def ok(): return 1\n")
        cdir = tmp_path / "contracts"
        cdir.mkdir()
        (cdir / "api.yaml").write_text("paths: {}")

        task = CodingTask(task_id="T1", description="test")
        result_obj = TaskResult(task_id="T1", exit_code=0, files_changed=["good.py"])

        with patch.object(reviewer, "_call_llm", side_effect=RuntimeError("no LLM")):
            rv = await reviewer.review_task(task, result_obj)
        # L2 降级通过 → 进入 L3 → L3 也降级通过
        assert rv.passed

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_review_l3_pass(self, reviewer, tmp_path):
        """L3 LLM 返回高分时通过"""
        py = tmp_path / "good.py"
        py.write_text("def ok(): return 1\n")

        task = CodingTask(task_id="T1", description="test")
        result_obj = TaskResult(task_id="T1", exit_code=0, files_changed=["good.py"])

        llm_resp = json.dumps({
            "scores": {"功能完整性": 5, "接口正确性": 5, "错误处理": 5, "代码质量": 5, "可运行性": 5},
            "average_score": 5.0,
            "issues": [],
            "fix_instruction": "",
        })
        with patch.object(reviewer, "_call_llm", return_value=llm_resp):
            rv = await reviewer.review_task(task, result_obj)
        assert rv.passed
        assert rv.score == 5.0

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_review_l3_fail(self, reviewer, tmp_path):
        """L3 评分低于阈值时失败"""
        py = tmp_path / "good.py"
        py.write_text("def ok(): return 1\n")

        task = CodingTask(task_id="T1", description="test")
        result_obj = TaskResult(task_id="T1", exit_code=0, files_changed=["good.py"])

        llm_resp = json.dumps({
            "scores": {"功能完整性": 2},
            "average_score": 2.0,
            "issues": ["质量差"],
            "fix_instruction": "请优化",
        })
        with patch.object(reviewer, "_call_llm", return_value=llm_resp):
            rv = await reviewer.review_task(task, result_obj)
        assert not rv.passed
        assert rv.score == 2.0

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_review_l2_contract_pass(self, reviewer, tmp_path):
        """L2 + L3 都通过"""
        py = tmp_path / "good.py"
        py.write_text("def ok(): return 1\n")
        cdir = tmp_path / "contracts"
        cdir.mkdir()
        (cdir / "api.yaml").write_text("paths: {}")

        task = CodingTask(task_id="T1", description="test")
        result_obj = TaskResult(task_id="T1", exit_code=0, files_changed=["good.py"])

        call_count = 0
        async def fake_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # L2
                return '{"passed": true, "issues": []}'
            else:  # L3
                return json.dumps({
                    "scores": {"功能完整性": 5},
                    "average_score": 5.0, "issues": [], "fix_instruction": "",
                })

        with patch.object(reviewer, "_call_llm", side_effect=fake_llm):
            rv = await reviewer.review_task(task, result_obj)
        assert rv.passed
        assert call_count == 2


# ═══════════════════════════════════════════════════════════════════════
#  test_runner.py — 结果解析 / 测试发现 / 降级阈值
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def runner(tmp_path):
    """创建 TestRunner (mock config)"""
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.get = lambda key, default=None: {
        "test.fallback_threshold": 0.8,
        "test.timeout_sec": 300,
    }.get(key, default)

    from orchestrator.test_runner import TestRunner
    return TestRunner(cfg, repo_root=tmp_path)


class TestRunnerParseJsonReport:

    @pytest.mark.component
    def test_parse_json_report_success(self, runner, tmp_path):
        report = tmp_path / ".pytest_reports" / "T1.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({
            "summary": {"total": 5, "passed": 5, "failed": 0, "error": 0},
            "duration": 1.5,
            "tests": [{"outcome": "passed", "nodeid": "t::a"}],
        }))
        result = runner._parse_json_report("T1", report)
        assert result.passed
        assert result.total == 5
        assert result.passed_count == 5

    @pytest.mark.component
    def test_parse_json_report_failures(self, runner, tmp_path):
        report = tmp_path / ".pytest_reports" / "T2.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({
            "summary": {"total": 3, "passed": 1, "failed": 2, "error": 0},
            "duration": 2.0,
            "tests": [
                {"outcome": "passed", "nodeid": "t::a"},
                {"outcome": "failed", "nodeid": "t::b", "call": {"crash": {"message": "assert false"}}},
                {"outcome": "failed", "nodeid": "t::c", "call": {"crash": {"message": "error"}}},
            ],
        }))
        result = runner._parse_json_report("T2", report)
        assert not result.passed
        assert result.failed_count == 2
        assert "t::b" in result.details

    @pytest.mark.component
    def test_parse_json_report_bad_json(self, runner, tmp_path):
        report = tmp_path / ".pytest_reports" / "T3.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("not json {{{")
        result = runner._parse_json_report("T3", report)
        assert not result.passed
        assert "parse error" in result.details.lower()


class TestRunnerParsePytestOutput:

    @pytest.mark.component
    def test_parse_passed(self, runner):
        output = "collected 5 items\n...\n5 passed in 1.2s"
        result = runner._parse_pytest_output("T1", output, 0)
        assert result.passed
        assert result.passed_count == 5

    @pytest.mark.component
    def test_parse_mixed(self, runner):
        output = "3 passed, 2 failed in 2.0s"
        result = runner._parse_pytest_output("T1", output, 1)
        assert not result.passed
        assert result.failed_count == 2

    @pytest.mark.component
    def test_parse_no_output_rc0(self, runner):
        result = runner._parse_pytest_output("T1", "", 0)
        assert result.passed
        assert result.total == 0


class TestRunnerFallbackThreshold:

    @pytest.mark.component
    def test_threshold_already_passed(self, runner):
        result = TestResult(task_id="T1", passed=True, total=10, passed_count=10)
        from orchestrator.test_runner import AcceptanceCriterion
        criteria = [AcceptanceCriterion(criterion_id="c1", description="x")]
        out = runner._apply_fallback_threshold(result, criteria)
        assert out.passed

    @pytest.mark.component
    def test_threshold_above(self, runner):
        result = TestResult(task_id="T1", passed=False, total=10, passed_count=9, failed_count=1)
        from orchestrator.test_runner import AcceptanceCriterion
        criteria = [AcceptanceCriterion(criterion_id="c1", description="x")]
        out = runner._apply_fallback_threshold(result, criteria)
        assert out.passed  # 90% >= 80%
        assert "Fallback" in out.details

    @pytest.mark.component
    def test_threshold_below(self, runner):
        result = TestResult(task_id="T1", passed=False, total=10, passed_count=5, failed_count=5)
        from orchestrator.test_runner import AcceptanceCriterion
        criteria = [AcceptanceCriterion(criterion_id="c1", description="x")]
        out = runner._apply_fallback_threshold(result, criteria)
        assert not out.passed  # 50% < 80%

    @pytest.mark.component
    def test_threshold_zero_total(self, runner):
        result = TestResult(task_id="T1", passed=False, total=0, passed_count=0)
        from orchestrator.test_runner import AcceptanceCriterion
        criteria = [AcceptanceCriterion(criterion_id="c1", description="x")]
        out = runner._apply_fallback_threshold(result, criteria)
        assert not out.passed


class TestRunnerDiscoverTestFiles:

    @pytest.mark.component
    def test_discover_exact_match(self, runner, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_t_001.py").write_text("def test_a(): pass")
        task = CodingTask(task_id="T-001", description="x")
        files = runner._discover_test_files(task)
        assert len(files) == 1

    @pytest.mark.component
    def test_discover_module_name(self, runner, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_mymod.py").write_text("def test_b(): pass")
        task = CodingTask(task_id="T-999", description="x", module_name="mymod")
        files = runner._discover_test_files(task)
        assert len(files) == 1

    @pytest.mark.component
    def test_discover_dir_match(self, runner, tmp_path):
        test_dir = tmp_path / "tests"
        sub = test_dir / "pkg"
        sub.mkdir(parents=True)
        (sub / "test_unit.py").write_text("def test_c(): pass")
        task = CodingTask(task_id="T-888", description="x", target_dir="src/pkg")
        files = runner._discover_test_files(task)
        assert len(files) == 1

    @pytest.mark.component
    def test_discover_pattern_tags(self, runner, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_backend.py").write_text("def test_d(): pass")
        task = CodingTask(task_id="T-777", description="x", tags=["backend"])
        files = runner._discover_test_files(task)
        assert len(files) == 1

    @pytest.mark.component
    def test_discover_nothing(self, runner, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        task = CodingTask(task_id="T-666", description="x")
        files = runner._discover_test_files(task)
        assert files == []


class TestRunnerExtractKeywords:

    @pytest.mark.component
    def test_extract_from_task(self, runner):
        task = CodingTask(task_id="T-100", description="x", target_dir="orchestrator/core", tags=["gpu"])
        kw = runner._extract_keywords(task)
        assert "t_100" in kw
        assert "core" in kw
        assert "gpu" in kw


class TestRunnerBuildAcceptanceCriteria:

    @pytest.mark.component
    def test_build_criteria_with_file(self, runner):
        task = CodingTask(
            task_id="T1", description="x",
            acceptance=["通过 tests/test_core.py 测试", "接口正确"],
        )
        criteria = runner._build_acceptance_criteria(task)
        assert len(criteria) == 2
        assert criteria[0].test_file == "tests/test_core.py"
        assert criteria[1].test_file is None

    @pytest.mark.component
    def test_build_criteria_empty(self, runner):
        task = CodingTask(task_id="T1", description="x")
        criteria = runner._build_acceptance_criteria(task)
        assert criteria == []


class TestRunnerAcceptanceTests:

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_run_acceptance_no_criteria(self, runner):
        from orchestrator.test_runner import AcceptanceCriterion
        task = CodingTask(task_id="T1", description="x")
        result = await runner.run_acceptance_tests(task, [])
        assert result.passed
        assert result.total == 0


# ═══════════════════════════════════════════════════════════════════════
#  dispatcher.py — 纯函数路径
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def dispatcher(tmp_path):
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.get_machines.return_value = {}
    cfg.single_task_timeout = 600
    cfg.git_branch = "main"
    cfg.aider_model = "gpt-4"
    cfg.openai_api_base = "http://fake:8000/v1"
    cfg.openai_api_key = "sk-test"
    cfg.task_card_path = ""
    from orchestrator.dispatcher import Dispatcher
    return Dispatcher(cfg, registry=None)


class TestDispatcherBuildInstruction:

    @pytest.mark.component
    def test_basic_instruction(self, dispatcher):
        task = CodingTask(task_id="T1", description="实现用户登录", target_dir="auth/")
        instr = dispatcher._build_instruction(task)
        assert "T1" in instr
        assert "实现用户登录" in instr
        assert "auth/" in instr

    @pytest.mark.component
    def test_instruction_with_acceptance(self, dispatcher):
        task = CodingTask(
            task_id="T2", description="测试", target_dir="./",
            acceptance=["通过单元测试", "代码覆盖率 > 80%"],
        )
        instr = dispatcher._build_instruction(task)
        assert "通过单元测试" in instr
        assert "验收标准" in instr

    @pytest.mark.component
    def test_instruction_with_fix(self, dispatcher):
        task = CodingTask(task_id="T3", description="修复", target_dir="./")
        task.fix_instruction = "上次编译失败，请修复语法错误"
        task.review_retry = 1
        task.test_retry = 1
        instr = dispatcher._build_instruction(task)
        assert "修复指令" in instr
        assert "编译失败" in instr


class TestDispatcherParseChangedFiles:

    @pytest.mark.component
    def test_parse_wrote_lines(self, dispatcher):
        stdout = "Wrote orchestrator/core.py\nWrote tests/test_core.py\ndone"
        files = dispatcher._parse_changed_files(stdout, "orchestrator/")
        assert "orchestrator/core.py" in files
        assert "tests/test_core.py" in files

    @pytest.mark.component
    def test_parse_create_mode(self, dispatcher):
        stdout = " create mode 100644 src/main.py\n"
        files = dispatcher._parse_changed_files(stdout, "src/")
        assert "src/main.py" in files

    @pytest.mark.component
    def test_parse_no_file_fallback(self, dispatcher):
        stdout = "no relevant output"
        files = dispatcher._parse_changed_files(stdout, "orchestrator/")
        assert files == ["orchestrator/"]


class TestDispatcherGetMachine:

    @pytest.mark.component
    def test_get_machine_no_machine(self, dispatcher):
        task = CodingTask(task_id="T1", description="x")
        assert dispatcher._get_machine(task) is None

    @pytest.mark.component
    def test_get_machine_fallback(self, tmp_path):
        m = MachineInfo(machine_id="gpu1", display_name="GPU1", host="10.0.0.1",
                        user="dev", work_dir="/home/dev")
        cfg = MagicMock()
        cfg.repo_root = tmp_path
        cfg.get_machines.return_value = {"gpu1": m}
        from orchestrator.dispatcher import Dispatcher
        d = Dispatcher(cfg, registry=None)
        task = CodingTask(task_id="T1", description="x", assigned_machine="gpu1")
        assert d._get_machine(task) is m

    @pytest.mark.component
    def test_get_machine_registry(self, tmp_path):
        m = MachineInfo(machine_id="gpu2", display_name="GPU2", host="10.0.0.2",
                        user="dev", work_dir="/home/dev")
        registry = MagicMock()
        registry.get_machine.return_value = m
        cfg = MagicMock()
        cfg.repo_root = tmp_path
        from orchestrator.dispatcher import Dispatcher
        d = Dispatcher(cfg, registry=registry)
        task = CodingTask(task_id="T1", description="x", assigned_machine="gpu2")
        assert d._get_machine(task) is m


class TestDispatcherIsLocal:

    @pytest.mark.component
    def test_is_local(self, dispatcher):
        m = MachineInfo(machine_id="m1", display_name="M1", host="localhost", user="dev", work_dir="/tmp")
        assert dispatcher._is_local(m)

    @pytest.mark.component
    def test_is_remote(self, dispatcher):
        m = MachineInfo(machine_id="m2", display_name="M2", host="192.168.1.100", user="dev", work_dir="/tmp")
        assert not dispatcher._is_local(m)


class TestDispatcherDispatchTask:

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_dispatch_no_machine_assigned(self, dispatcher):
        """无 machine 分配时直接失败"""
        task = CodingTask(task_id="T1", description="x")
        result = await dispatcher.dispatch_task(task)
        assert not result.success
        assert "未分配" in result.stderr or result.exit_code != 0

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_dispatch_task_timeout(self, tmp_path):
        """模拟超时场景"""
        m = MachineInfo(machine_id="gpu1", display_name="GPU1", host="localhost",
                        user="dev", work_dir="/tmp")
        registry = MagicMock()
        registry.get_machine.return_value = m
        cfg = MagicMock()
        cfg.repo_root = tmp_path
        cfg.single_task_timeout = 600
        cfg.git_branch = "main"
        cfg.aider_model = "gpt-4"
        cfg.openai_api_base = "http://fake"
        cfg.openai_api_key = "key"
        cfg.task_card_path = ""
        from orchestrator.dispatcher import Dispatcher
        d = Dispatcher(cfg, registry=registry)

        task = CodingTask(task_id="T1", description="x", assigned_machine="gpu1")
        # Mock _scp_content and _ssh_exec to raise TimeoutError
        with patch.object(d, "_scp_content", new_callable=AsyncMock), \
             patch.object(d, "_ssh_exec", side_effect=asyncio.TimeoutError):
            result = await d.dispatch_task(task)
        assert result.exit_code == 124
        assert "超时" in result.stderr

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_dispatch_batch(self, dispatcher):
        """dispatch_batch 并行调用"""
        t1 = CodingTask(task_id="T1", description="a")
        t2 = CodingTask(task_id="T2", description="b")
        with patch.object(dispatcher, "dispatch_task", new_callable=AsyncMock,
                          return_value=TaskResult(task_id="X", exit_code=0)):
            results = await dispatcher.dispatch_batch([t1, t2])
        assert len(results) == 2


# ═══════════════════════════════════════════════════════════════════════
#  reporter.py — 报告生成 & 通知
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def reporter(tmp_path):
    cfg = MagicMock()
    cfg.repo_root = tmp_path
    cfg.project_name = "test-project"
    cfg.get = lambda k, default="": {
        "notification.dingtalk_webhook": "",
        "notification.dingtalk_webhook_secret": "",
        "notification.dingtalk_app_key": "",
        "notification.dingtalk_app_secret": "",
        "notification.dingtalk_robot_code": "",
        "notification.dingtalk_conversation_id": "",
        "notification.at_mobiles": [],
        "notification.at_all": False,
    }.get(k, default)
    from orchestrator.reporter import Reporter
    return Reporter(cfg)


class TestReporterGenerateReport:

    @pytest.mark.component
    def test_generate_report(self, reporter, tmp_path):
        tasks = [
            CodingTask(task_id="T1", description="登录模块", assigned_machine="gpu1"),
        ]
        tasks[0].status = TaskStatus.PASSED
        summary = {"total": 1, "passed": 1, "failed": 0, "escalated": 0}
        path = reporter.generate_report("S1", tasks, summary)
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "Sprint S1" in content
        assert "T1" in content

    @pytest.mark.component
    def test_save_sprint_report_alias(self, reporter, tmp_path):
        tasks = [CodingTask(task_id="T2", description="x")]
        summary = {"total": 1, "passed": 0, "failed": 1}
        path = reporter.save_sprint_report("S2", tasks, summary)
        assert Path(path).exists()


class TestReporterNotify:

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_notify_no_config(self, reporter):
        """未配置钉钉时不抛异常"""
        await reporter.notify_sprint_start("S1", [])
        await reporter.notify_task_dispatched(CodingTask(task_id="T1", description="x"))
        await reporter.notify_task_result(CodingTask(task_id="T1", description="x"))
        await reporter.notify_sprint_done("S1", [])
        await reporter.notify_error("test error")
        await reporter.notify_shutdown("test")

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_webhook_signing(self, tmp_path):
        """Webhook 带签名路径"""
        cfg = MagicMock()
        cfg.repo_root = tmp_path
        cfg.project_name = "test"
        cfg.get = lambda k, default="": {
            "notification.dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "notification.dingtalk_webhook_secret": "SEC123456",
            "notification.dingtalk_app_key": "",
            "notification.dingtalk_app_secret": "",
            "notification.dingtalk_robot_code": "",
            "notification.dingtalk_conversation_id": "",
            "notification.at_mobiles": ["13800138000"],
            "notification.at_all": False,
        }.get(k, default)
        from orchestrator.reporter import Reporter
        r = Reporter(cfg)

        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client
            await r.notify_error("webhook test")
            mock_client.post.assert_called_once()

    @pytest.mark.component
    @pytest.mark.asyncio
    async def test_openapi_path(self, tmp_path):
        """OpenAPI 路径 (带 app_key + conversation_id)"""
        cfg = MagicMock()
        cfg.repo_root = tmp_path
        cfg.project_name = "test"
        cfg.get = lambda k, default="": {
            "notification.dingtalk_webhook": "",
            "notification.dingtalk_webhook_secret": "",
            "notification.dingtalk_app_key": "appkey123",
            "notification.dingtalk_app_secret": "appsecret123",
            "notification.dingtalk_robot_code": "robot1",
            "notification.dingtalk_conversation_id": "conv1",
            "notification.at_mobiles": [],
            "notification.at_all": False,
        }.get(k, default)
        from orchestrator.reporter import Reporter
        r = Reporter(cfg)

        with patch.object(r, "_get_access_token", return_value="fake_token"):
            import httpx
            mock_resp = MagicMock()
            mock_resp.status_code = 200

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                await r.notify_error("openapi test")
                mock_client.post.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
#  config.py — 属性访问
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def config_obj(tmp_path):
    """创建有效 config 对象"""
    cfg_path = tmp_path / "config.yaml"
    import yaml
    data = {
        "project": {"name": "testproj", "path": str(tmp_path), "branch": "dev"},
        "orchestrator": {"mode": "auto", "current_sprint": 1, "poll_interval": 5, "max_concurrent": 8, "port": 9999},
        "llm": {"openai_api_base": "http://fake", "openai_api_key": "sk-test", "model": "gpt-4"},
        "task": {"single_task_timeout": 300, "max_retries": 3},
        "git": {"branch": "release", "bare_repo": "/tmp/bare.git"},
        "testing": {"pytest_args": "-x", "pass_threshold": 3.5, "report_dir": "out/", "test_pass_rate_threshold": 0.9},
        "notification": {"dingtalk_webhook": "https://hook"},
        "paths": {
            "task_card": "docs/tasks.md",
            "design_doc": "docs/design.md",
            "contracts_dir": "contracts/",
            "log_dir": "logs/",
        },
        "machines": [
            {
                "machine_id": "gpu1", "display_name": "GPU Server",
                "host": "10.0.0.1", "user": "dev", "port": 22,
                "work_dir": "/home/dev/work", "tags": ["gpu"],
                "aider_prefix": "", "aider_model": "",
            }
        ],
        "doc_set": {"req": "docs/01-requirements/*.md"},
    }
    cfg_path.write_text(yaml.dump(data))
    from orchestrator.config import Config
    return Config(str(cfg_path), project_root=str(tmp_path))


class TestConfigProperties:

    @pytest.mark.component
    def test_project_name(self, config_obj):
        assert config_obj.project_name == "testproj"

    @pytest.mark.component
    def test_project_path(self, config_obj):
        assert config_obj.project_path.is_dir()

    @pytest.mark.component
    def test_doc_set(self, config_obj):
        assert "req" in config_obj.doc_set

    @pytest.mark.component
    def test_mode(self, config_obj):
        assert config_obj.mode == "auto"

    @pytest.mark.component
    def test_current_sprint(self, config_obj):
        assert config_obj.current_sprint == 1

    @pytest.mark.component
    def test_poll_interval(self, config_obj):
        assert config_obj.poll_interval == 5

    @pytest.mark.component
    def test_max_concurrent(self, config_obj):
        assert config_obj.max_concurrent == 8

    @pytest.mark.component
    def test_port(self, config_obj):
        assert config_obj.port == 9999

    @pytest.mark.component
    def test_openai_api_base(self, config_obj):
        assert "fake" in config_obj.openai_api_base

    @pytest.mark.component
    def test_openai_api_key(self, config_obj):
        assert config_obj.openai_api_key == "sk-test"

    @pytest.mark.component
    def test_aider_model(self, config_obj):
        assert config_obj.aider_model == "gpt-4"

    @pytest.mark.component
    def test_single_task_timeout(self, config_obj):
        assert config_obj.single_task_timeout == 300

    @pytest.mark.component
    def test_max_retries(self, config_obj):
        assert config_obj.max_retries == 3

    @pytest.mark.component
    def test_git_branch(self, config_obj):
        assert config_obj.git_branch == "release"  # git.branch 优先

    @pytest.mark.component
    def test_git_bare_repo(self, config_obj):
        assert config_obj.git_bare_repo == "/tmp/bare.git"

    @pytest.mark.component
    def test_pytest_args(self, config_obj):
        assert config_obj.pytest_args == "-x"

    @pytest.mark.component
    def test_pass_threshold(self, config_obj):
        assert config_obj.pass_threshold == 3.5

    @pytest.mark.component
    def test_report_dir(self, config_obj):
        assert config_obj.report_dir == "out/"

    @pytest.mark.component
    def test_test_pass_rate_threshold(self, config_obj):
        assert config_obj.test_pass_rate_threshold == 0.9

    @pytest.mark.component
    def test_dingtalk_webhook(self, config_obj):
        assert config_obj.dingtalk_webhook == "https://hook"

    @pytest.mark.component
    def test_task_card_path(self, config_obj):
        assert config_obj.task_card_path == "docs/tasks.md"

    @pytest.mark.component
    def test_design_doc_path(self, config_obj):
        assert config_obj.design_doc_path == "docs/design.md"

    @pytest.mark.component
    def test_contracts_dir(self, config_obj):
        assert config_obj.contracts_dir == "contracts/"

    @pytest.mark.component
    def test_log_dir(self, config_obj):
        assert config_obj.log_dir == "logs/"

    @pytest.mark.component
    def test_get_machines_list(self, config_obj):
        lst = config_obj.get_machines_list()
        assert len(lst) == 1
        assert lst[0]["machine_id"] == "gpu1"

    @pytest.mark.component
    def test_get_machines_dict(self, config_obj):
        d = config_obj.get_machines()
        assert "gpu1" in d
        assert d["gpu1"].host == "10.0.0.1"

    @pytest.mark.component
    def test_get_machine(self, config_obj):
        m = config_obj.get_machine("gpu1")
        assert m.display_name == "GPU Server"

    @pytest.mark.component
    def test_get_machine_not_found(self, config_obj):
        with pytest.raises(KeyError, match="gpu99"):
            config_obj.get_machine("gpu99")

    @pytest.mark.component
    def test_get_dotpath(self, config_obj):
        assert config_obj.get("orchestrator.mode") == "auto"
        assert config_obj.get("nonexistent.key", 42) == 42


class TestConfigSchemaValidation:

    @pytest.mark.component
    def test_invalid_missing_orchestrator(self, tmp_path):
        import yaml
        cfg_path = tmp_path / "bad.yaml"
        cfg_path.write_text(yaml.dump({
            "llm": {"openai_api_base": "x", "openai_api_key": "k", "model": "m"},
            "task": {"single_task_timeout": 60, "max_retries": 1},
        }))
        from orchestrator.config import Config, ConfigSchemaError
        with pytest.raises(ConfigSchemaError, match="orchestrator"):
            Config(str(cfg_path))

    @pytest.mark.component
    def test_invalid_timeout(self, tmp_path):
        import yaml
        cfg_path = tmp_path / "bad2.yaml"
        cfg_path.write_text(yaml.dump({
            "orchestrator": {"mode": "auto", "current_sprint": 1, "poll_interval": 5},
            "llm": {"openai_api_base": "x", "openai_api_key": "k", "model": "m"},
            "task": {"single_task_timeout": -1, "max_retries": 1},
        }))
        from orchestrator.config import Config, ConfigSchemaError
        with pytest.raises(ConfigSchemaError, match="single_task_timeout"):
            Config(str(cfg_path))

    @pytest.mark.component
    def test_machines_dict_format(self, tmp_path):
        """兼容旧版 dict 格式"""
        import yaml
        cfg_path = tmp_path / "old.yaml"
        cfg_path.write_text(yaml.dump({
            "orchestrator": {"mode": "auto", "current_sprint": 1, "poll_interval": 5},
            "llm": {"openai_api_base": "x", "openai_api_key": "k", "model": "m"},
            "task": {"single_task_timeout": 60, "max_retries": 1},
            "machines": {"m1": {"host": "h1", "user": "u1"}},
        }))
        from orchestrator.config import Config
        c = Config(str(cfg_path))
        lst = c.get_machines_list()
        assert len(lst) == 1
        assert lst[0]["machine_id"] == "m1"
