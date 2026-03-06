"""
AutoDev Pipeline — 文档集分析器 (v3.0 新增)
取代 v2 的 DocParser, 实现通用化的文档集 → 任务分解。

核心能力:
  1. 按 doc_set glob 模式加载项目文档
  2. 调用 LLM 进行自动任务分解
  3. 输出结构化 CodingTask 列表
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .task_models import CodingTask

log = logging.getLogger("orchestrator.doc_analyzer")


class DocAnalyzer:
    """
    通用文档集分析器。

    替代 v2 DocParser 的静态解析, 使用 LLM 理解任意格式的文档集,
    输出标准化的 CodingTask 列表。

    工作流程:
    1. load_doc_set(): 按 glob 模式收集文档
    2. analyze_and_decompose(): 将文档内容 + 约束 发给 LLM
    3. LLM 返回结构化 JSON: [{task_id, tags, description, ...}]
    4. 转换为 CodingTask 列表
    """

    def __init__(
        self,
        project_path: str,
        doc_set_config: Dict[str, str],
        llm_base: str = "",
        llm_key: str = "",
        llm_model: str = "",
    ):
        self.project_path = Path(project_path)
        self.doc_set_config = doc_set_config
        self.llm_base = llm_base
        self.llm_key = llm_key
        self.llm_model = llm_model

    # ── 文档加载 ──

    def load_doc_set(self) -> Dict[str, str]:
        """
        按 doc_set 配置的 glob 模式加载项目文档。

        Returns:
            {doc_type: combined_content}
            例: {"requirements": "# 基础需求\n...\n# 扩展需求\n...",
                 "design": "# 系统概要设计\n...", ...}
        """
        result: Dict[str, str] = {}

        for doc_type, pattern in self.doc_set_config.items():
            if not pattern:
                continue

            # 支持绝对路径或相对路径
            if Path(pattern).is_absolute():
                full_pattern = pattern
            else:
                full_pattern = str(self.project_path / pattern)

            matched_files = sorted(glob.glob(full_pattern, recursive=True))
            if not matched_files:
                log.warning("文档类型 '%s' 未匹配到文件: %s", doc_type, pattern)
                continue

            parts = []
            for filepath in matched_files:
                try:
                    content = Path(filepath).read_text(encoding="utf-8")
                    rel_path = Path(filepath).relative_to(self.project_path)
                    parts.append(f"=== {rel_path} ===\n{content}")
                except Exception as e:
                    log.warning("读取文件失败 %s: %s", filepath, e)

            if parts:
                result[doc_type] = "\n\n".join(parts)
                log.info("文档类型 '%s': 加载 %d 个文件", doc_type, len(parts))

        return result

    # ── 任务分解 ──

    async def analyze_and_decompose(
        self,
        sprint: Optional[int] = None,
        extra_context: str = "",
    ) -> List[CodingTask]:
        """
        将文档集发给 LLM, 自动分解为 CodingTask 列表。

        Args:
            sprint: 指定 Sprint 编号 (只分解该 Sprint 的任务)
            extra_context: 额外上下文 (如用户自然语言补充)

        Returns:
            CodingTask 列表
        """
        doc_set = self.load_doc_set()
        if not doc_set:
            log.error("文档集为空, 无法分解任务")
            return []

        prompt = self._build_decompose_prompt(doc_set, sprint, extra_context)

        try:
            response = await self._call_llm(prompt)
            tasks = self._parse_tasks_from_llm(response)
            log.info("LLM 分解出 %d 个任务", len(tasks))
            return tasks
        except Exception as e:
            log.error("LLM 任务分解失败: %s", e)
            return []

    def _build_decompose_prompt(
        self,
        doc_set: Dict[str, str],
        sprint: Optional[int],
        extra_context: str,
    ) -> str:
        """构建发给 LLM 的任务分解 prompt"""

        # 限制每个文档类型的长度, 避免超出 token 限制
        MAX_DOC_LEN = 6000
        doc_sections = []
        for doc_type, content in doc_set.items():
            truncated = content[:MAX_DOC_LEN]
            if len(content) > MAX_DOC_LEN:
                truncated += f"\n\n... (截断, 原文 {len(content)} 字符)"
            doc_sections.append(f"## {doc_type}\n{truncated}")

        docs_text = "\n\n---\n\n".join(doc_sections)

        sprint_hint = ""
        if sprint is not None:
            sprint_hint = f"\n注意: 只分解 Sprint {sprint} 的任务。\n"

        extra_hint = ""
        if extra_context:
            extra_hint = f"\n## 补充说明\n{extra_context}\n"

        return f"""你是一个自动化开发流水线的任务分解引擎。
请分析以下项目文档集, 将其中的开发工作分解为可独立执行的编码任务。

# 项目文档集

{docs_text}

{sprint_hint}
{extra_hint}

# 输出要求

请输出 JSON 数组, 每个元素代表一个编码任务:

```json
[
  {{
    "task_id": "S1_T1",
    "description": "实现用户认证模块 — 包含 JWT 签发和验证",
    "tags": ["python", "web", "auth"],
    "target_dir": "src/auth/",
    "acceptance": ["curl /api/login 返回 JWT", "pytest tests/test_auth.py 通过"],
    "depends_on": [],
    "estimated_minutes": 30,
    "context_files": ["contracts/api.yaml"]
  }}
]
```

## 规则
1. task_id 格式: S{{sprint}}_T{{序号}}
2. tags 必须填写, 用于匹配执行机器的能力标签
3. target_dir 指定 aider 生成代码的目标目录
4. acceptance 是验收标准列表
5. depends_on 填写前置任务的 task_id (可选)
6. estimated_minutes 预估执行时间 (分钟)
7. 每个任务应该是 1~2 小时可完成的粒度

请严格输出 JSON, 不要添加其他文字。"""

    # ── LLM 调用 ──

    async def _call_llm(self, prompt: str) -> str:
        """调用 OpenAI 兼容 API"""
        import httpx

        if not self.llm_base or not self.llm_key:
            raise RuntimeError("LLM API 未配置 (需要 llm.openai_api_base 和 llm.openai_api_key)")

        url = f"{self.llm_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.llm_model or "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # ── 解析 ──

    def _parse_tasks_from_llm(self, response: str) -> List[CodingTask]:
        """从 LLM 回复中解析 CodingTask 列表"""
        # 尝试提取 JSON
        data = self._extract_json(response)
        if not isinstance(data, list):
            raise ValueError(f"LLM 返回的不是 JSON 数组: {type(data)}")

        tasks = []
        for item in data:
            task = CodingTask(
                task_id=item.get("task_id", f"T{len(tasks)+1}"),
                description=item.get("description", ""),
                tags=item.get("tags", []),
                target_dir=item.get("target_dir", "./"),
                acceptance=item.get("acceptance", []),
                depends_on=item.get("depends_on", []),
                estimated_minutes=item.get("estimated_minutes", 30),
                context_files=item.get("context_files", []),
            )
            tasks.append(task)

        return tasks

    @staticmethod
    def _extract_json(text: str) -> Any:
        """从 LLM 回复中提取 JSON"""
        text = text.strip()

        # 直接解析
        if text.startswith("[") or text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # 从 ```json ``` 中提取
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 找第一个 [ 到最后一个 ]
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 LLM 回复中解析 JSON:\n{text[:500]}")

    # ── 工具方法 ──

    def get_doc_set_summary(self) -> Dict[str, int]:
        """返回文档集摘要: {doc_type: 文件数}"""
        summary = {}
        for doc_type, pattern in self.doc_set_config.items():
            if not pattern:
                summary[doc_type] = 0
                continue
            full_pattern = str(self.project_path / pattern) if not Path(pattern).is_absolute() else pattern
            matched = glob.glob(full_pattern, recursive=True)
            summary[doc_type] = len(matched)
        return summary
