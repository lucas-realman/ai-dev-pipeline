"""
AutoDev Pipeline — 文档解析器 (DD-MOD-002 / v2 兼容层)
向后兼容 v2 的 DocParser 接口, 内部委托给 DocAnalyzer。

如果项目仍使用 v2 格式的任务卡 (W0-W5 表格), 可直接使用此模块。
新项目建议直接使用 doc_analyzer.DocAnalyzer。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

from .task_models import CodingTask

log = logging.getLogger("orchestrator.doc_parser")

# v2 机器代号 → 机器名 (兼容旧任务卡格式)
MACHINE_ALIAS: Dict[str, str] = {
    "W0": "orchestrator",
    "W1": "4090",
    "W2": "mac_min_8T",
    "W3": "gateway",
    "W4": "data_center",
    "W5": "orchestrator",
}

# 机器名 → 默认关联目录
MACHINE_DEFAULT_DIR: Dict[str, str] = {
    "4090": "agent/",
    "mac_min_8T": "crm/",
    "gateway": "deploy/",
    "data_center": "scripts/",
    "orchestrator": "orchestrator/",
}


class DocParser:
    """
    解析 Sprint 任务卡 + 设计文档 → 生成 CodingTask 列表 (DD-MOD-002)。
    兼容 v2 格式, 新项目建议使用 DocAnalyzer。
    """

    def __init__(self, config: Any):
        """
        支持两种构造方式:
        1. DocParser(config: Config)  — 推荐 (DD-MOD-002)
        2. DocParser(repo_path: str)  — 兼容
        """
        if hasattr(config, 'repo_root'):
            self.repo_path = Path(config.repo_root)
        else:
            self.repo_path = Path(str(config))

    def parse_task_card(
        self,
        card_path: str = "docs/07-Sprint任务卡.md",
        sprint: Optional[int] = None,
    ) -> List[CodingTask]:
        """
        解析任务卡 Markdown 表格, 返回 CodingTask 列表。

        表格格式:
        | **W1** | 任务名 | "aider 指令" | `产出文件` | 完成标志 |
        """
        full_path = Path(card_path) if Path(card_path).is_absolute() else self.repo_path / card_path
        if not full_path.exists():
            log.error("任务卡不存在: %s", full_path)
            return []

        text = full_path.read_text(encoding="utf-8")

        if sprint is not None:
            text = self._extract_sprint_section(text, sprint)
            if not text:
                log.warning("未找到 Sprint %s 相关章节", sprint)
                return []

        tasks = self._parse_tables(text)
        log.info("解析到 %d 个任务", len(tasks))
        return tasks

    def _extract_sprint_section(self, text: str, sprint: int) -> str:
        """提取 Sprint 对应章节"""
        pattern = rf"^##\s+\d+\.\s+Sprint\s+\d*{sprint}\d*[：:—\-]"
        lines = text.splitlines()
        start = None
        end = len(lines)
        for i, line in enumerate(lines):
            if start is None:
                if re.match(pattern, line):
                    start = i
            elif line.startswith("## ") and not line.startswith("### "):
                end = i
                break
        if start is None:
            return ""
        return "\n".join(lines[start:end])

    def _parse_tables(self, text: str) -> List[CodingTask]:
        """解析所有 Day 表格"""
        tasks: List[CodingTask] = []
        current_day = ""
        task_counter = 0

        for line in text.splitlines():
            day_match = re.match(r"^####\s+Day\s+(\d+)", line)
            if day_match:
                current_day = day_match.group(1)
                continue

            if re.match(r"\s*\|[-\s|]+\|", line):
                continue
            if re.match(r"\s*\|\s*机器\s*\|", line):
                continue

            m = re.match(r"\s*\|\s*\*\*(\w[\w\-]*)\*\*\s*\|", line)
            if not m:
                continue

            machine_code = m.group(1)
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]

            if len(parts) < 3:
                continue

            task_name = parts[1].strip()
            aider_instruction = parts[2].strip() if len(parts) > 2 else ""
            output_files = parts[3].strip() if len(parts) > 3 else ""
            acceptance = parts[4].strip() if len(parts) > 4 else ""

            if "-" in machine_code:
                machines = self._expand_machine_range(machine_code)
            else:
                machines = [machine_code]

            for mc in machines:
                machine_name = MACHINE_ALIAS.get(mc, mc)
                if machine_name == mc and not mc.startswith("W"):
                    log.warning("未知机器代号: %s, 跳过", mc)
                    continue

                task_counter += 1
                task_id = f"S{current_day}_{mc}" if current_day else f"T{task_counter}"
                target_dir = self._infer_target_dir(output_files, machine_name)
                clean_instruction = aider_instruction.strip('"').strip('\u201c').strip('\u201d')
                context_files = self._infer_context_files(target_dir)

                # v3.0: 通过 tags 关联, 同时保留 target_machine 兼容
                tasks.append(CodingTask(
                    task_id=task_id,
                    target_machine=machine_name,
                    target_dir=target_dir,
                    description=f"{task_name}: {clean_instruction}" if clean_instruction else task_name,
                    context_files=context_files,
                    acceptance=[acceptance] if acceptance else [],
                ))

        return tasks

    def _expand_machine_range(self, code: str) -> List[str]:
        m = re.match(r"W(\d+)-W(\d+)", code)
        if not m:
            return [code]
        start, end = int(m.group(1)), int(m.group(2))
        return [f"W{i}" for i in range(start, end + 1)]

    def _infer_target_dir(self, output_files: str, machine_name: str) -> str:
        clean = output_files.replace("`", "").replace("(更新)", "").strip()
        if clean and "/" in clean:
            first_file = clean.split(",")[0].strip()
            parts = first_file.split("/")
            if len(parts) >= 2:
                return parts[0] + "/"
        return MACHINE_DEFAULT_DIR.get(machine_name, "./")

    def _infer_context_files(self, target_dir: str) -> List[str]:
        context = []
        contracts_dir = self.repo_path / "contracts"
        if contracts_dir.exists():
            for f in contracts_dir.iterdir():
                if f.suffix in (".yaml", ".yml", ".sql"):
                    context.append(str(f.relative_to(self.repo_path)))
        clean_dir = target_dir.rstrip("/")
        init_file = self.repo_path / clean_dir / "__init__.py"
        if init_file.exists():
            context.append(str(init_file.relative_to(self.repo_path)))
        return context

    def read_contracts(self) -> str:
        """读取所有契约文件内容"""
        contracts_dir = self.repo_path / "contracts"
        if not contracts_dir.exists():
            return ""
        parts = []
        for f in sorted(contracts_dir.iterdir()):
            if f.suffix in (".yaml", ".yml", ".sql"):
                parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)
