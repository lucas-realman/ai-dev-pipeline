"""
AutoDev Pipeline — 配置加载器 (DD-MOD-012)
从 config.yaml + .env 加载并解析配置。
v3.0 变更:
  - 新增 project / doc_set / machines (list) 支持
  - machines 从 dict 改为 list, 用 machine_id 作为主键
  - 保留对旧 Config API 的完全兼容
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .task_models import MachineInfo


class ConfigSchemaError(Exception):
    """配置 Schema 校验失败 (DD-MOD-012 ALG-025a)"""
    pass


_CONFIG_DIR = Path(__file__).parent
_DEFAULT_PROJECT_ROOT = _CONFIG_DIR.parent


def _expand_env_vars(obj: Any) -> Any:
    """递归展开 ${VAR} 格式的环境变量引用"""
    if isinstance(obj, str):
        def _replace(m):
            var = m.group(1)
            return os.environ.get(var, m.group(0))
        return re.sub(r"\$\{(\w+)\}", _replace, obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(i) for i in obj]
    return obj


class Config:
    """Orchestrator 配置 (v3.0)"""

    def __init__(self, config_path: Optional[str] = None, project_root: Optional[str] = None):
        if config_path is None:
            config_path = str(_CONFIG_DIR / "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        self._data: Dict[str, Any] = _expand_env_vars(raw)

        # 项目根目录: 优先使用参数, 其次 config, 最后默认
        if project_root:
            self._project_root = Path(project_root).expanduser().resolve()
        elif self._data.get("project", {}).get("path"):
            self._project_root = Path(self._data["project"]["path"]).expanduser().resolve()
        else:
            self._project_root = _DEFAULT_PROJECT_ROOT

        # DD-MOD-012 ALG-025a: Schema 验证
        self._validate_schema()

    def _validate_schema(self) -> None:
        """校验必填字段、类型和范围 (ALG-025a)"""
        errors: List[str] = []

        # orchestrator 必须存在
        orch = self._data.get("orchestrator")
        if not isinstance(orch, dict):
            errors.append("缺少必填配置段: orchestrator")
        else:
            if "mode" not in orch:
                errors.append("orchestrator.mode 是必填项")
            if "current_sprint" not in orch:
                errors.append("orchestrator.current_sprint 是必填项")

        # llm 必须存在
        llm = self._data.get("llm")
        if not isinstance(llm, dict):
            errors.append("缺少必填配置段: llm")
        else:
            for key in ("openai_api_base", "openai_api_key", "model"):
                if not llm.get(key):
                    errors.append(f"llm.{key} 是必填项")

        # task 必须存在
        task = self._data.get("task")
        if not isinstance(task, dict):
            errors.append("缺少必填配置段: task")
        else:
            timeout = task.get("single_task_timeout")
            if timeout is not None and (not isinstance(timeout, (int, float)) or timeout <= 0):
                errors.append(f"task.single_task_timeout 必须为正数, 当前值: {timeout}")
            retries = task.get("max_retries")
            if retries is not None and (not isinstance(retries, int) or retries < 0):
                errors.append(f"task.max_retries 必须为非负整数, 当前值: {retries}")

        # machines 类型检查
        machines = self._data.get("machines")
        if machines is not None and not isinstance(machines, (list, dict)):
            errors.append("machines 必须为列表或字典")

        if errors:
            raise ConfigSchemaError(
                "配置文件校验失败:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    # ── 项目配置 (v3.0 新增) ──

    @property
    def project_name(self) -> str:
        return self._data.get("project", {}).get("name", "unnamed-project")

    @property
    def project_path(self) -> Path:
        return self._project_root

    @property
    def doc_set(self) -> Dict[str, str]:
        """文档集 glob 映射: {doc_type: glob_pattern}"""
        return self._data.get("doc_set", {})

    # ── Orchestrator ──

    @property
    def mode(self) -> str:
        return self._data["orchestrator"]["mode"]

    @property
    def current_sprint(self) -> int:
        return self._data["orchestrator"]["current_sprint"]

    @property
    def poll_interval(self) -> int:
        return self._data["orchestrator"]["poll_interval"]

    @property
    def max_concurrent(self) -> int:
        return self._data["orchestrator"].get("max_concurrent", 4)

    @property
    def port(self) -> int:
        return self._data["orchestrator"].get("port", 9500)

    # ── LLM / aider ──

    @property
    def openai_api_base(self) -> str:
        return self._data["llm"]["openai_api_base"]

    @property
    def openai_api_key(self) -> str:
        return self._data["llm"]["openai_api_key"]

    @property
    def aider_model(self) -> str:
        return self._data["llm"]["model"]

    # ── Task ──

    @property
    def single_task_timeout(self) -> int:
        return self._data["task"]["single_task_timeout"]

    @property
    def max_retries(self) -> int:
        return self._data["task"]["max_retries"]

    # ── Git ──

    @property
    def git_branch(self) -> str:
        branch = self._data.get("git", {}).get("branch")
        if branch:
            return branch
        return self._data.get("project", {}).get("branch", "main")

    @property
    def git_bare_repo(self) -> str:
        return self._data.get("git", {}).get("bare_repo", "")

    # ── Testing ──

    @property
    def pytest_args(self) -> str:
        return self._data.get("testing", {}).get("pytest_args", "-x -v --tb=short")

    @property
    def pass_threshold(self) -> float:
        return self._data.get("testing", {}).get("pass_threshold", 4.0)

    @property
    def report_dir(self) -> str:
        return self._data.get("testing", {}).get("report_dir", "reports/")

    @property
    def test_pass_rate_threshold(self) -> float:
        return float(self._data.get("testing", {}).get("test_pass_rate_threshold", 0.8))

    # ── Notification ──

    @property
    def dingtalk_webhook(self) -> Optional[str]:
        return self._data.get("notification", {}).get("dingtalk_webhook")

    # ── Paths (兼容旧版) ──

    @property
    def task_card_path(self) -> str:
        return self._data.get("paths", {}).get("task_card", "docs/Sprint任务卡.md")

    @property
    def design_doc_path(self) -> str:
        return self._data.get("paths", {}).get("design_doc", "docs/系统概要设计.md")

    @property
    def contracts_dir(self) -> str:
        return self._data.get("paths", {}).get("contracts_dir", "contracts/")

    @property
    def log_dir(self) -> str:
        return self._data.get("paths", {}).get("log_dir", "logs/")

    # ── 机器列表 (v3.0: 列表格式) ──

    def get_machines_list(self) -> List[dict]:
        """返回原始机器配置列表 (供 MachineRegistry.load_from_config 使用)"""
        machines = self._data.get("machines", [])
        if isinstance(machines, list):
            return machines
        # 兼容旧版 dict 格式
        result = []
        for name, cfg in machines.items():
            entry = dict(cfg)
            entry["machine_id"] = str(name)
            entry.setdefault("display_name", str(name))
            entry.setdefault("tags", [])
            result.append(entry)
        return result

    def get_machines(self) -> Dict[str, MachineInfo]:
        """
        兼容旧版: 返回 Dict[name, MachineInfo]。
        v3.0 代码应使用 MachineRegistry 而非此方法。
        """
        result = {}
        for cfg in self.get_machines_list():
            mid = cfg["machine_id"]
            result[mid] = MachineInfo(
                machine_id=mid,
                display_name=cfg.get("display_name", mid),
                host=cfg["host"],
                port=cfg.get("port", 22),
                user=cfg["user"],
                work_dir=cfg.get("work_dir", "~/projects"),
                tags=cfg.get("tags", []),
                aider_prefix=cfg.get("aider_prefix", ""),
                aider_model=cfg.get("aider_model", ""),
            )
        return result

    def get_machine(self, name: str) -> MachineInfo:
        machines = self.get_machines()
        if name not in machines:
            raise KeyError(f"未知机器: {name}, 可用: {list(machines.keys())}")
        return machines[name]

    # ── raw 访问 ──

    def get(self, dotpath: str, default: Any = None) -> Any:
        """用点号路径获取配置: config.get('orchestrator.mode')"""
        keys = dotpath.split(".")
        node = self._data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    @property
    def repo_root(self) -> Path:
        """项目实际根目录"""
        return self._project_root
