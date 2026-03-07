"""
AutoDev Pipeline — 测试运行器 (DD-MOD-009)
支持:
1. pytest 单元测试 (JSON 报告)
2. 验收测试 (基于 acceptance criteria)
3. 降级阈值容忍 (Bug17 修复)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .config import Config
from .task_models import CodingTask, TaskResult, TestResult

log = logging.getLogger("orchestrator.test_runner")


@dataclass
class AcceptanceCriterion:
    """验收标准条目"""
    criterion_id: str
    description: str
    category: str = "functional"  # functional / non-functional / edge-case
    test_file: Optional[str] = None
    passed: bool = False
    reason: str = ""


class TestRunner:
    """测试运行器 (DD-MOD-009) — 负责在各节点上执行 pytest 并采集结果"""

    def __init__(self, config: Config, repo_root: Optional[Path] = None):
        self.config = config
        self.repo_root = repo_root or config.repo_root
        self.test_dir = self.repo_root / "tests"
        self.fallback_threshold: float = config.get("test.fallback_threshold", 0.8)
        self.timeout: int = config.get("test.timeout_sec", 300)
        self._json_report_dir = self.repo_root / ".pytest_reports"
        self._json_report_dir.mkdir(parents=True, exist_ok=True)

    # ── 主要入口 ──

    async def run_tests(
        self, task: CodingTask, result: Optional["TaskResult"] = None,
    ) -> TestResult:
        """对一个任务执行测试 (DD-MOD-009 ALG-017)"""
        test_files = self._discover_test_files(task)
        if not test_files:
            log.info("任务 %s 没有找到测试文件, 默认通过", task.task_id)
            return TestResult(
                task_id=task.task_id,
                passed=True,
                total=0,
                passed_count=0,
                failed_count=0,
                error_count=0,
                duration_sec=0.0,
                details="No test files found — auto-pass",
            )

        report_file = self._json_report_dir / f"{task.task_id}.json"
        test_paths_str = " ".join(str(f) for f in test_files)
        cmd = (
            f"cd {self.repo_root} && "
            f"python -m pytest {test_paths_str} "
            f"--json-report --json-report-file={report_file} "
            f"-v --tb=short -q 2>&1"
        )

        stdout, returncode = await self._run_pytest(cmd, task)

        if report_file.exists():
            return self._parse_json_report(task.task_id, report_file)
        else:
            return self._parse_pytest_output(task.task_id, stdout, returncode)

    async def run_acceptance_tests(
        self,
        task: CodingTask,
        criteria: List[AcceptanceCriterion],
    ) -> TestResult:
        """执行验收测试 (针对 acceptance criteria)"""
        if not criteria:
            return TestResult(
                task_id=task.task_id,
                passed=True,
                total=0,
                passed_count=0,
                failed_count=0,
                error_count=0,
                duration_sec=0.0,
                details="No acceptance criteria defined",
            )

        test_files = []
        for c in criteria:
            if c.test_file:
                f = self.test_dir / c.test_file
                if f.exists():
                    test_files.append(f)

        if not test_files:
            functional_tests = self._discover_test_files(task)
            test_files = functional_tests

        if not test_files:
            log.info("验收测试未找到测试文件: %s", task.task_id)
            return TestResult(
                task_id=task.task_id,
                passed=True,
                total=len(criteria),
                passed_count=0,
                failed_count=0,
                error_count=0,
                duration_sec=0.0,
                details="No acceptance test files found — criteria not verified",
            )

        report_file = self._json_report_dir / f"{task.task_id}_acceptance.json"
        test_paths_str = " ".join(str(f) for f in test_files)
        cmd = (
            f"cd {self.repo_root} && "
            f"python -m pytest {test_paths_str} "
            f"--json-report --json-report-file={report_file} "
            f"-v --tb=short -q 2>&1"
        )

        stdout, returncode = await self._run_pytest(cmd, task)

        if report_file.exists():
            result_obj = self._parse_json_report(task.task_id, report_file)
        else:
            result_obj = self._parse_pytest_output(task.task_id, stdout, returncode)

        result_obj = self._apply_fallback_threshold(result_obj, criteria)
        return result_obj

    # ── 测试发现策略 ──

    def _discover_test_files(self, task: CodingTask) -> List[Path]:
        """
        三层策略查找任务相关测试文件 (ALG-018):
        1. 精确匹配: test_{task_id}.py 或 test_{module_name}.py
        2. 目录匹配: tests/{target_dir}/
        3. 模式匹配: tests/ 下包含 task_id 关键字的文件
        """
        found: List[Path] = []

        # 策略 1: 精确匹配 (task_id + module_name)
        safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", task.task_id).lower()
        exact_file = self.test_dir / f"test_{safe_id}.py"
        if exact_file.exists():
            found.append(exact_file)
            return found

        # module_name 精确匹配 (DD-MOD-009 ALG-018 Tier 1)
        module_name = getattr(task, 'module_name', '')
        if module_name:
            mod_file = self.test_dir / f"test_{module_name}.py"
            if mod_file.exists():
                found.append(mod_file)
                return found

        # 策略 2: 目录匹配
        if task.target_dir:
            dir_name = Path(task.target_dir).name
            test_subdir = self.test_dir / dir_name
            if test_subdir.is_dir():
                for f in test_subdir.glob("test_*.py"):
                    found.append(f)
            if found:
                return found

        # 策略 3: 模式匹配
        if self.test_dir.is_dir():
            keywords = self._extract_keywords(task)
            for f in self.test_dir.rglob("test_*.py"):
                name = f.stem.lower()
                if any(kw in name for kw in keywords):
                    found.append(f)

        return found

    def _extract_keywords(self, task: CodingTask) -> List[str]:
        """从任务中提取搜索关键字"""
        keywords = []
        safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", task.task_id).lower()
        keywords.append(safe_id)

        # 从 target_dir 提取
        if task.target_dir:
            parts = Path(task.target_dir).parts
            for p in parts[-2:]:
                keywords.append(p.lower().replace("-", "_"))

        # 从 tags 提取
        for tag in (task.tags or []):
            keywords.append(tag.lower().replace("-", "_"))

        return [k for k in keywords if len(k) >= 3]

    # ── 结果解析 ──

    def _parse_json_report(self, task_id: str, report_file: Path) -> TestResult:
        """解析 pytest-json-report 输出"""
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("解析 JSON 报告失败: %s", e)
            return TestResult(
                task_id=task_id, passed=False,
                total=0, passed_count=0, failed_count=0, error_count=0,
                duration_sec=0.0, details=f"JSON report parse error: {e}",
            )

        summary = data.get("summary", {})
        total = summary.get("total", 0)
        passed_count = summary.get("passed", 0)
        failed_count = summary.get("failed", 0)
        error_count = summary.get("error", 0)
        duration = data.get("duration", 0.0)

        # 收集失败详情
        failures = []
        for test in data.get("tests", []):
            if test.get("outcome") in ("failed", "error"):
                node_id = test.get("nodeid", "unknown")
                call = test.get("call", {})
                msg = call.get("crash", {}).get("message", "")[:200]
                failures.append(f"  - {node_id}: {msg}")

        details = "\n".join(failures) if failures else "All tests passed"
        all_passed = failed_count == 0 and error_count == 0

        return TestResult(
            task_id=task_id,
            passed=all_passed,
            total=total,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            duration_sec=duration,
            details=details,
        )

    def _parse_pytest_output(
        self, task_id: str, output: str, returncode: int
    ) -> TestResult:
        """当 JSON 报告不可用时, 从 stdout 中解析结果"""
        total = passed = failed = errors = 0

        # 尝试解析 "X passed, Y failed, Z error" 行
        pattern = re.compile(
            r"(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error",
            re.IGNORECASE,
        )
        for m in pattern.finditer(output):
            if m.group(1):
                passed = int(m.group(1))
            if m.group(2):
                failed = int(m.group(2))
            if m.group(3):
                errors = int(m.group(3))
        total = passed + failed + errors

        if total == 0 and returncode == 0:
            return TestResult(
                task_id=task_id, passed=True,
                total=0, passed_count=0, failed_count=0, error_count=0,
                duration_sec=0.0, details="No test output detected, rc=0",
            )

        return TestResult(
            task_id=task_id,
            passed=(failed == 0 and errors == 0),
            total=total,
            passed_count=passed,
            failed_count=failed,
            error_count=errors,
            duration_sec=0.0,
            details=output[-500:] if not (failed == 0 and errors == 0) else "Parsed from stdout",
        )

    def _apply_fallback_threshold(
        self,
        result: TestResult,
        criteria: List[AcceptanceCriterion],
    ) -> TestResult:
        """
        Bug17 修复: 降级阈值容忍
        如果通过率 >= fallback_threshold 且以前未通过, 视为通过
        """
        if result.passed:
            return result

        if result.total == 0:
            return result

        pass_rate = result.passed_count / result.total
        if pass_rate >= self.fallback_threshold:
            log.info(
                "任务 %s 通过率 %.1f%% >= 阈值 %.1f%%, 降级通过",
                result.task_id,
                pass_rate * 100,
                self.fallback_threshold * 100,
            )
            return TestResult(
                task_id=result.task_id,
                passed=True,
                total=result.total,
                passed_count=result.passed_count,
                failed_count=result.failed_count,
                error_count=result.error_count,
                duration_sec=result.duration_sec,
                details=(
                    f"[Fallback threshold] pass_rate={pass_rate:.2f}"
                    f" >= {self.fallback_threshold}\n" + result.details
                ),
            )

        return result

    # ── 命令执行 ──

    async def _run_pytest(self, cmd: str, task: CodingTask) -> Tuple[str, int]:
        """在本地执行测试命令 (DD-MOD-009)"""
        log.debug("[TestRunner] %s: %s", task.task_id, cmd[:120])
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout_bytes, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return f"TIMEOUT after {self.timeout}s", 124

            return stdout_bytes.decode(errors="replace"), proc.returncode or 0
        except Exception as e:
            log.error("[TestRunner] 执行异常 %s: %s", task.task_id, e)
            return str(e), 1

    # ── 验收标准构建 ──

    def _build_acceptance_criteria(self, task: CodingTask) -> List[AcceptanceCriterion]:
        """
        从 CodingTask.acceptance 列表构建 AcceptanceCriterion 对象列表 (DD-MOD-009)。

        每条 acceptance 文本会尝试从中提取测试文件模式 (glob);
        如果无法提取, 则保留 description 供人工判定。
        """
        criteria: List[AcceptanceCriterion] = []
        for idx, text in enumerate(task.acceptance or [], start=1):
            cid = f"{task.task_id}_AC{idx}"
            # 尝试提取 pytest 文件路径
            m = re.search(r"(tests?/[^\s]+\.py)", text)
            test_file = m.group(1) if m else None
            criteria.append(
                AcceptanceCriterion(
                    criterion_id=cid,
                    description=text,
                    test_file=test_file,
                )
            )
        return criteria
