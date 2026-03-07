"""
AutoDev Pipeline — 自动 Review 引擎
三层自动代码审查:
  Layer 1: 静态检查 (py_compile + ruff)
  Layer 2: 契约对齐检查 (LLM)
  Layer 3: 设计符合度检查 (LLM)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .config import Config
from .task_models import CodingTask, ReviewResult, TaskResult

log = logging.getLogger("orchestrator.reviewer")


class AutoReviewer:
    """三层自动代码 Review"""

    # ALG-032: LLM 指数退避重试参数 (BUG-1 修复)
    _LLM_MAX_RETRIES: int = 3
    _LLM_BACKOFF_BASE: float = 2.0

    def __init__(self, config: Config):
        self.config = config
        self.repo_root = config.repo_root

    async def review_task(self, task: CodingTask, result: TaskResult) -> ReviewResult:
        """对编码结果执行三层 Review (DD-MOD-008 主入口)"""
        files = result.files_changed
        if not files:
            return ReviewResult(
                passed=False, layer="static",
                issues=["无变更文件"],
                fix_instruction="aider 未生成任何文件, 请重新执行编码任务。",
            )

        log.info("[%s] Review Layer 1: 静态检查", task.task_id)
        static_result = await self._run_l1_static(files)
        if not static_result.passed:
            return static_result

        log.info("[%s] Review Layer 2: 契约对齐", task.task_id)
        contract_result = await self._run_l2_contract(task, files)
        if not contract_result.passed:
            return contract_result

        log.info("[%s] Review Layer 3: 设计符合度", task.task_id)
        quality_result = await self._run_l3_quality(task, files)
        if not quality_result.passed:
            return quality_result

        log.info("[%s] ✅ Review 全部通过 (score=%.1f)", task.task_id, quality_result.score)
        return quality_result

    # 向后兼容别名
    async def review(self, task: CodingTask, result: TaskResult) -> ReviewResult:
        return await self.review_task(task, result)

    # ── Layer 1: 静态检查 ──

    async def _run_l1_static(self, files: List[str]) -> ReviewResult:
        issues = []
        for f in files:
            if not f.endswith(".py"):
                continue
            full_path = self.repo_root / f
            if not full_path.exists():
                continue

            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(full_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode != 0:
                    issues.append(f"编译错误 {f}: {proc.stderr.strip()}")
            except subprocess.TimeoutExpired:
                issues.append(f"编译超时 {f}")

            try:
                proc = subprocess.run(
                    ["ruff", "check", "--select", "E,W,F", str(full_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode != 0 and proc.stdout.strip():
                    errors = [
                        line for line in proc.stdout.strip().splitlines()
                        if any(e in line for e in ["E9", "F8", "F6", "F4"])
                    ]
                    if errors:
                        issues.append(f"Lint 严重问题 {f}:\n" + "\n".join(errors))
            except FileNotFoundError:
                pass
            except subprocess.TimeoutExpired:
                pass

        if issues:
            return ReviewResult(
                passed=False, layer="static", issues=issues,
                fix_instruction="静态检查发现以下错误:\n" + "\n".join(f"- {i}" for i in issues),
            )
        return ReviewResult(passed=True, layer="static", score=5.0)

    # ── Layer 2: 契约对齐 ──

    async def _run_l2_contract(self, task: CodingTask, files: List[str]) -> ReviewResult:
        code_content = self._build_code_snippet(files)
        if not code_content:
            return ReviewResult(passed=True, layer="contract", score=5.0)

        contracts = self._read_contracts(task)
        if not contracts:
            return ReviewResult(passed=True, layer="contract", score=5.0)

        prompt = f"""你是一个接口契约审查员。请对比以下代码和接口契约, 检查是否一致。

## 接口契约
{contracts}

## 生成的代码
{code_content}

## 输出格式 (严格 JSON)
如果完全一致: {{"passed": true, "issues": []}}
如果有不一致: {{"passed": false, "issues": ["问题1"], "fix_instruction": "修复指令"}}"""

        try:
            response = await self._call_llm(prompt)
            data = self._parse_json_response(response)
            if data.get("passed", False):
                return ReviewResult(passed=True, layer="contract", score=5.0)
            return ReviewResult(
                passed=False, layer="contract",
                issues=data.get("issues", ["契约对齐检查失败"]),
                fix_instruction=data.get("fix_instruction", "请检查接口定义是否与契约一致"),
            )
        except Exception as e:
            log.warning("[%s] Layer 2 LLM 调用失败, 降级通过: %s", task.task_id, e)
            return ReviewResult(passed=True, layer="contract", score=4.0)

    # ── Layer 3: 设计符合度 ──

    async def _run_l3_quality(self, task: CodingTask, files: List[str]) -> ReviewResult:
        code_content = self._build_code_snippet(files)
        if not code_content:
            return ReviewResult(passed=True, layer="quality", score=3.5)

        prompt = f"""你是一个高级代码审查员。请根据任务描述评审以下代码。

## 编码任务
{task.description}

## 验收标准
{chr(10).join(f'- {a}' for a in task.acceptance) if task.acceptance else '无特殊验收标准'}

## 生成的代码
{code_content[:8000]}

## 评审维度 (每项 1-5 分)
1. 功能完整性  2. 接口正确性  3. 错误处理  4. 代码质量  5. 可运行性

## 输出格式 (严格 JSON)
{{"scores": {{"功能完整性": 4, ...}}, "average_score": 4.0, "issues": [], "fix_instruction": ""}}"""

        try:
            response = await self._call_llm(prompt)
            data = self._parse_json_response(response)
            avg_score = data.get("average_score", 0.0)
            threshold = self.config.pass_threshold

            if avg_score >= threshold:
                return ReviewResult(
                    passed=True, layer="quality", score=avg_score,
                    scores=data.get("scores", {}), issues=data.get("issues", []),
                )
            return ReviewResult(
                passed=False, layer="quality", score=avg_score,
                scores=data.get("scores", {}),
                issues=data.get("issues", ["设计评分低于阈值"]),
                fix_instruction=data.get("fix_instruction",
                                         f"评分 {avg_score:.1f} < {threshold}, 请优化代码质量"),
            )
        except Exception as e:
            log.warning("[%s] Layer 3 LLM 调用失败, 降级通过: %s", task.task_id, e)
            return ReviewResult(passed=True, layer="quality", score=3.5)

    # ── LLM 调用 ──

    async def _call_llm(self, prompt: str) -> str:
        """调用 OpenAI 兼容 API (ALG-032: 3× 指数退避重试)"""
        import httpx

        url = f"{self.config.openai_api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.aider_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        last_err: Optional[Exception] = None
        for attempt in range(1, self._LLM_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as exc:
                last_err = exc
                if attempt < self._LLM_MAX_RETRIES:
                    wait = self._LLM_BACKOFF_BASE ** attempt
                    log.warning(
                        "LLM 调用失败 (第 %d/%d 次), %.1fs 后重试: %s",
                        attempt, self._LLM_MAX_RETRIES, wait, exc,
                    )
                    await asyncio.sleep(wait)
        raise RuntimeError(f"LLM 调用 {self._LLM_MAX_RETRIES} 次均失败: {last_err}")

    # ── 文件读取 ──

    def _build_code_snippet(self, files: List[str]) -> str:
        parts = []
        for f in files:
            path = self.repo_root / f
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                    parts.append(f"=== {f} ===\n{content}")
                except Exception:
                    pass
            elif path.is_dir():
                for py_file in sorted(path.rglob("*.py")):
                    try:
                        rel = py_file.relative_to(self.repo_root)
                        content = py_file.read_text(encoding="utf-8")
                        parts.append(f"=== {rel} ===\n{content}")
                    except Exception:
                        pass
        return "\n\n".join(parts)

    def _read_contracts(self, task: CodingTask) -> str:
        contracts_dir = self.repo_root / "contracts"
        if not contracts_dir.exists():
            return ""
        parts = []
        for f in sorted(contracts_dir.iterdir()):
            if f.suffix in (".yaml", ".yml", ".sql"):
                parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")
        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从 LLM 回复中解析 JSON:\n{text[:500]}")
