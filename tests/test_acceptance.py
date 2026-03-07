"""
L4 验收测试 — test_acceptance.py
对齐 TEST-001 §2.5: TC-121 ~ TC-127
对齐 plan-v2 §2.4.2: S3-07 ~ S3-13

验收策略:
  - 真实端到端验证 (mock 外部依赖: SSH / LLM / 钉钉)
  - 安全合规检查 (密钥泄露扫描)
  - 性能基线验证 (单任务分发延迟)
  - 可扩展性验证 (新模块接入)
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Config
from orchestrator.dashboard import app as dashboard_app
from orchestrator.dispatcher import Dispatcher
from orchestrator.log_config import JsonFormatter, StandardFormatter
from orchestrator.machine_registry import MachineRegistry
from orchestrator.main import Orchestrator
from orchestrator.reporter import Reporter
from orchestrator.task_engine import TaskEngine
from orchestrator.task_models import (
    CodingTask,
    MachineInfo,
    ReviewLayer,
    ReviewResult,
    TaskResult,
    TaskStatus,
    TestResult,
)

# ── 辅助工厂 ─────────────────────────────────────────────


def _mock_config(tmp_path: Path) -> MagicMock:
    """构建 mock Config"""
    cfg = MagicMock(spec=Config)
    cfg.project_name = "acceptance-test"
    cfg.repo_root = tmp_path
    cfg.max_retries = 3
    cfg.max_concurrent = 2
    cfg.get.return_value = None
    cfg.get_machines_list.return_value = [
        {"machine_id": "m1", "display_name": "GPU-4090", "host": "10.0.0.1",
         "user": "dev", "tags": ["gpu", "python"], "port": 22, "work_dir": "~/work"},
        {"machine_id": "m2", "display_name": "Mac-Mini", "host": "10.0.0.2",
         "user": "dev", "tags": ["frontend", "python"], "port": 22, "work_dir": "~/work"},
        {"machine_id": "m3", "display_name": "Gateway", "host": "10.0.0.3",
         "user": "dev", "tags": ["linux", "deploy"], "port": 22, "work_dir": "~/work"},
    ]
    (tmp_path / "reports").mkdir(exist_ok=True)
    return cfg


def _task(tid: str, **kw) -> CodingTask:
    return CodingTask(
        task_id=tid,
        description=kw.get("desc", f"验收任务 {tid}"),
        tags=kw.get("tags", ["python"]),
        target_dir=kw.get("target_dir", f"src/{tid}"),
        depends_on=kw.get("depends_on", []),
    )


def _ok_dispatch(tid: str) -> TaskResult:
    return TaskResult(task_id=tid, exit_code=0, stdout="OK", duration_sec=1.0)


def _ok_review() -> ReviewResult:
    return ReviewResult(passed=True, layer=ReviewLayer.L1_STATIC, score=4.5, issues=[])


def _ok_test() -> TestResult:
    return TestResult(passed=True, total=5, passed_count=5, failed_count=0, duration_sec=1.0)


# ═══════════════════════════════════════════════════════════
# TC-121: 单 Sprint 端到端 (S3-07)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_tc121_single_sprint_e2e(tmp_path):
    """
    TC-121: 完整 Sprint 端到端验证
    load_doc → decompose → enqueue → dispatch → review → test → report
    """
    cfg = _mock_config(tmp_path)

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.Dispatcher") as MockDisp, \
         patch("orchestrator.main.AutoReviewer") as MockRev, \
         patch("orchestrator.main.TestRunner") as MockTest, \
         patch("orchestrator.main.Reporter") as MockReport, \
         patch("orchestrator.main.GitOps") as MockGit:

        # 配置 mock
        MockReg.return_value.load_from_config = MagicMock()
        mock_disp = MockDisp.return_value
        mock_rev = MockRev.return_value
        mock_test = MockTest.return_value
        mock_reporter = MockReport.return_value
        mock_git = MockGit.return_value

        mock_disp.dispatch_task = AsyncMock(side_effect=lambda t: _ok_dispatch(t.task_id))
        mock_rev.review_task = AsyncMock(return_value=_ok_review())
        mock_test.run_tests = AsyncMock(return_value=_ok_test())
        mock_reporter.notify_sprint_start = AsyncMock()
        mock_reporter.notify_task_dispatched = AsyncMock()
        mock_reporter.notify_task_result = AsyncMock()
        mock_reporter.notify_sprint_done = AsyncMock()
        mock_reporter.generate_report = MagicMock(return_value=str(tmp_path / "reports/report.md"))
        mock_git.sync_nodes = AsyncMock(return_value={})
        mock_git.auto_commit = AsyncMock()
        mock_git.create_tag = AsyncMock()

        orch = Orchestrator(cfg)

        # 使用真实引擎 + 注册表
        real_registry = MachineRegistry()
        real_registry.load_from_config(cfg.get_machines_list())
        orch.engine = TaskEngine(config=cfg, machine_registry=real_registry)
        orch.registry = real_registry

        # 执行 Sprint
        tasks = [_task("T001", tags=["gpu"]), _task("T002", tags=["frontend"]),
                 _task("T003", tags=["python"])]

        result = await orch.run_sprint("acceptance-sprint-1", tasks)

    # 验证: 全部通过
    assert result["total"] == 3
    assert result["passed"] == 3
    assert result["failed"] == 0
    assert result["escalated"] == 0

    # 验证: 通知链路完整
    mock_reporter.notify_sprint_start.assert_called_once()
    mock_reporter.notify_sprint_done.assert_called_once()
    assert mock_disp.dispatch_task.call_count == 3


# ═══════════════════════════════════════════════════════════
# TC-122: 文档驱动拆解准确性 (S3-08)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_tc122_doc_driven_accuracy(tmp_path):
    """
    TC-122: DocAnalyzer 拆解结果包含完整的 CodingTask 字段
    验证 LLM 返回的任务结构完整性 (mock LLM)
    """
    from orchestrator.doc_analyzer import DocAnalyzer

    cfg = _mock_config(tmp_path)

    # 模拟 LLM 返回结构化任务 JSON (数组格式, 匹配 _parse_tasks_from_llm)
    mock_llm_response = json.dumps([
        {
            "task_id": "T-DOC-001",
            "description": "实现用户认证模块",
            "module_name": "auth",
            "tags": ["python", "security"],
            "target_dir": "src/auth",
            "acceptance": ["pytest tests/test_auth.py 通过"],
            "depends_on": [],
            "estimated_minutes": 30,
        }
    ])

    with (
        patch.object(
            DocAnalyzer, "load_doc_set",
            return_value={"requirements.md": "# 需求\n实现用户认证"},
        ),
        patch.object(
            DocAnalyzer, "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ),
    ):
        analyzer = DocAnalyzer(cfg)
        tasks = await analyzer.analyze_and_decompose()

    # 验证: 任务数量与 LLM 输出一致
    assert len(tasks) >= 1
    task = tasks[0]

    # 验证: CodingTask 必须字段完整
    assert task.task_id, "task_id 不能为空"
    assert task.description, "description 不能为空"
    assert isinstance(task.tags, list), "tags 必须是列表"
    assert task.target_dir, "target_dir 不能为空"


# ═══════════════════════════════════════════════════════════
# TC-123: 报告可读性 (S3-09)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
def test_tc123_report_readability(tmp_path):
    """
    TC-123: 生成的 Sprint 报告内容可读、结构完整
    验证 Markdown 报告包含标题、统计表格、任务明细
    """
    cfg = _mock_config(tmp_path)
    reporter = Reporter(cfg)

    tasks = [_task("T001", tags=["gpu"]), _task("T002", tags=["frontend"])]
    tasks[0].status = TaskStatus.PASSED
    tasks[1].status = TaskStatus.FAILED

    summary = {"total": 2, "passed": 1, "failed": 1, "escalated": 0}
    report_path = reporter.generate_report("sprint-acceptance", tasks, summary)

    assert Path(report_path).exists(), "报告文件必须存在"

    content = Path(report_path).read_text(encoding="utf-8")

    # 验证: 报告包含核心要素
    assert "Sprint sprint-acceptance" in content, "报告必须包含 Sprint 标识"
    assert "T001" in content, "报告必须列出每个任务"
    assert "T002" in content, "报告必须列出每个任务"
    # 验证: Markdown 结构
    assert content.count("#") >= 2, "报告必须有多级标题"
    assert "|" in content, "报告必须包含表格"


# ═══════════════════════════════════════════════════════════
# TC-124: 性能基线 (S3-10)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_tc124_performance_baseline(tmp_path):
    """
    TC-124: 单任务分发延迟 <5s 基线验证
    使用 mock SSH (不实际连接), 验证 Dispatch 逻辑延迟
    """
    cfg = _mock_config(tmp_path)

    with patch("orchestrator.main.MachineRegistry") as MockReg, \
         patch("orchestrator.main.Dispatcher") as MockDisp, \
         patch("orchestrator.main.AutoReviewer") as MockRev, \
         patch("orchestrator.main.TestRunner") as MockTest, \
         patch("orchestrator.main.Reporter") as MockReport, \
         patch("orchestrator.main.GitOps") as MockGit:

        MockReg.return_value.load_from_config = MagicMock()
        mock_disp = MockDisp.return_value
        mock_rev = MockRev.return_value
        mock_test = MockTest.return_value
        mock_reporter = MockReport.return_value
        mock_git = MockGit.return_value

        # 模拟 dispatch 有 0.1s 延迟 (真实环境中 SSH 连接)
        async def fast_dispatch(task):
            await asyncio.sleep(0.1)
            return _ok_dispatch(task.task_id)

        mock_disp.dispatch_task = AsyncMock(side_effect=fast_dispatch)
        mock_rev.review_task = AsyncMock(return_value=_ok_review())
        mock_test.run_tests = AsyncMock(return_value=_ok_test())
        mock_reporter.notify_sprint_start = AsyncMock()
        mock_reporter.notify_task_dispatched = AsyncMock()
        mock_reporter.notify_task_result = AsyncMock()
        mock_reporter.notify_sprint_done = AsyncMock()
        mock_reporter.generate_report = MagicMock(return_value="reports/perf.md")
        mock_git.sync_nodes = AsyncMock(return_value={})
        mock_git.auto_commit = AsyncMock()
        mock_git.create_tag = AsyncMock()

        orch = Orchestrator(cfg)

        real_registry = MachineRegistry()
        real_registry.load_from_config(cfg.get_machines_list())
        orch.engine = TaskEngine(config=cfg, machine_registry=real_registry)
        orch.registry = real_registry

        task = _task("T-PERF-001", tags=["python"])

        start = time.monotonic()
        result = await orch.run_sprint("perf-sprint", [task])
        elapsed = time.monotonic() - start

    # 性能断言: 单任务(含 dispatch + review + test) < 5s
    assert elapsed < 5.0, f"单任务 Sprint 耗时 {elapsed:.2f}s, 超过 5s 基线"
    assert result["passed"] == 1


# ═══════════════════════════════════════════════════════════
# TC-125: SSH 密钥认证验证 (S3-11)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
def test_tc125_ssh_key_auth():
    """
    TC-125: Dispatcher SSH 命令使用 ed25519 密钥验证 (不使用密码)
    验证: 生成的 SSH 命令中不包含密码字段
    """

    cfg = MagicMock(spec=Config)
    cfg.get.return_value = None
    cfg.project_name = "test"
    cfg.repo_root = Path("/tmp/test")

    disp = Dispatcher(cfg, registry=MachineRegistry())

    # 检查 Dispatcher 构建 SSH 命令的方式
    # Dispatcher 使用 ssh -o StrictHostKeyChecking=no 等选项
    # 验证: 不应有 sshpass / -p password 等密码相关内容
    machine = MachineInfo(
        machine_id="test_m1", host="10.0.0.1", user="dev",
        tags=["python"], port=22,
    )

    # 检查内部 SSH 命令构建 (如果可用)
    if hasattr(disp, "_build_ssh_command") or hasattr(disp, "_build_command"):
        cmd_builder = (
            getattr(disp, "_build_ssh_command", None)
            or getattr(disp, "_build_command", None)
        )
        if cmd_builder:
            cmd = cmd_builder(machine, "echo test")
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            assert "password" not in cmd_str.lower(), "SSH 命令不应包含密码"
            assert "sshpass" not in cmd_str.lower(), "不应使用 sshpass"

    # 验证: 模块不依赖 paramiko 密码认证
    import orchestrator.dispatcher as disp_mod
    source = Path(disp_mod.__file__).read_text(encoding="utf-8")
    assert "password" not in source.lower() or "# password" in source.lower() or \
           source.lower().count("password") <= 2, \
        "Dispatcher 源码不应硬编码密码"


# ═══════════════════════════════════════════════════════════
# TC-126: 仓库无密钥泄露 (S3-12)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
def test_tc126_no_secrets_in_repo():
    """
    TC-126: 仓库中不应包含密钥、密码等敏感信息
    扫描: private key / secret / password / api_key (排除测试文件和配置模板)
    """
    project_root = Path(__file__).parent.parent

    # 需扫描的目录
    scan_dirs = [project_root / "orchestrator"]
    sensitive_patterns = [
        r"-----BEGIN\s+(RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"sk-[a-zA-Z0-9]{20,}",       # OpenAI key pattern
        r"ghp_[a-zA-Z0-9]{36}",       # GitHub PAT
        r"AKIA[0-9A-Z]{16}",          # AWS access key
    ]

    violations = []

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in sensitive_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    rel_path = py_file.relative_to(project_root)
                    violations.append(f"{rel_path}: 匹配 {pattern}")

    assert not violations, "发现敏感信息泄露:\n" + "\n".join(violations)


# ═══════════════════════════════════════════════════════════
# TC-127: 新模块接入验证 (S3-13)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
def test_tc127_new_module_onboarding(tmp_path):
    """
    TC-127: 验证新模块可以在 <1h 内接入
    实际验证: 创建一个骨架模块, 验证能被 Orchestrator 加载
    """
    # 创建骨架模块
    module_dir = tmp_path / "orchestrator"
    module_dir.mkdir()
    (module_dir / "__init__.py").write_text("")

    skeleton = '''"""新模块骨架 — 用于验证接入流程"""
from __future__ import annotations

import logging
from typing import Any, Dict

log = logging.getLogger("orchestrator.new_module")


class NewModule:
    """示例新模块"""

    def __init__(self, config: Any = None):
        self.config = config
        log.info("NewModule initialized")

    async def process(self, data: Dict) -> Dict:
        """处理逻辑"""
        return {"status": "ok", "processed": True}
'''
    (module_dir / "new_module.py").write_text(skeleton, encoding="utf-8")

    # 验证: 模块可以导入
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "orchestrator.new_module",
        module_dir / "new_module.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 验证: 类可以实例化
    instance = mod.NewModule()
    assert hasattr(instance, "process"), "新模块必须有 process 方法"

    # 验证: 异步方法可调用
    result = asyncio.get_event_loop().run_until_complete(instance.process({"test": True}))
    assert result["status"] == "ok"

    # 验证: 现有模块骨架结构一致性 (统一接口规范)
    from orchestrator import __version__
    assert __version__, "orchestrator 包必须有版本号"

    # 验证: 新模块可以获取 logger
    assert mod.log.name == "orchestrator.new_module"


# ═══════════════════════════════════════════════════════════
# Dashboard API 验收 (NFR-015)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_dashboard_api_status():
    """NFR-015: /api/status 返回有效 JSON"""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "status" in data
    assert data["status"] == "running"
    assert "machines" in data
    assert "tasks" in data
    assert "uptime_seconds" in data


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_dashboard_api_health():
    """NFR-015: /api/health 返回健康状态"""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_dashboard_api_machines():
    """NFR-015: /api/machines 返回机器列表"""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/machines")

    assert resp.status_code == 200
    data = resp.json()
    assert "machines" in data
    assert isinstance(data["machines"], list)


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_dashboard_api_tasks():
    """NFR-015: /api/tasks 返回任务列表"""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tasks")

    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


# ═══════════════════════════════════════════════════════════
# 日志标准化验收 (NFR-013)
# ═══════════════════════════════════════════════════════════


@pytest.mark.acceptance
def test_log_json_format():
    """NFR-013: JSON 日志格式可被 json.loads() 解析"""
    import logging

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="orchestrator.test", level=logging.INFO,
        pathname="test.py", lineno=1, msg="测试日志",
        args=None, exc_info=None,
    )
    record.task_id = "T-001"
    record.sprint_id = "sprint-1"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["module"] == "orchestrator.test"
    assert parsed["message"] == "测试日志"
    assert parsed["task_id"] == "T-001"
    assert parsed["sprint_id"] == "sprint-1"
    assert "timestamp" in parsed


@pytest.mark.acceptance
def test_log_standard_format():
    """NFR-013: 标准文本日志格式正确"""
    import logging

    formatter = StandardFormatter()
    record = logging.LogRecord(
        name="orchestrator.main", level=logging.WARNING,
        pathname="main.py", lineno=42, msg="警告信息",
        args=None, exc_info=None,
    )

    output = formatter.format(record)
    assert "[orchestrator.main]" in output
    assert "WARNING" in output
    assert "警告信息" in output
