# OD-MOD-008 — TestRunner 模块概要设计

> **文档编号**: OD-MOD-008  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/test_runner.py` (342 行)  
> **上游文档**: [OD-SYS-001](OD-SYS-001-系统概要设计.md) · [ARCH-005](../03-architecture/ARCH-001-架构总览.md)  
> **下游文档**: [DD-MOD-008](../05-detail-design/DD-MOD-008-test_runner.md)

---

## 模块概况

| 属性 | 值 |
|------|---|
| **模块 ID** | MOD-008 |
| **核心类** | `TestRunner`, `AcceptanceCriterion` |
| **ARCH 组件** | ARCH-005 测试组件 |
| **关联 FR** | FR-012 pytest 执行, FR-013 验收测试 |
| **对外接口** | IF-009 `run_tests(task) → TestResult` |
| **依赖** | MOD-012 (config), MOD-005 (task_models), asyncio |

## 职责

执行 pytest 自动测试 + 验收标准检查。支持 JSON 报告解析、降级阈值容忍 (Bug17 修复)。

## 核心流程

```
run_tests(task) → TestResult
    │
    ├── _find_tests_for_task(task)
    │       ├── Tier-1: 精确匹配 test_{filename}.py
    │       ├── Tier-2: 同目录下 test_*.py
    │       └── Tier-3: 模式匹配 (task_id 关键词)
    │
    ├── _exec(pytest_cmd)
    │       ├── pytest --json-report --json-report-file=...
    │       ├── asyncio.create_subprocess_shell
    │       └── timeout 控制
    │
    ├── _parse_json_report(report_path)    ← 优先 JSON 报告
    │   或 _parse_pytest_output(stdout)    ← 回退到正则解析
    │
    └── _apply_fallback_threshold(result)  ← Bug17 修复
            └── pass_rate >= threshold → 降级通过

run_acceptance_tests(task, criteria) → TestResult
    │
    ├── 遍历 AcceptanceCriterion 列表
    ├── 执行每个验收用例
    └── 汇总结果
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **3 层测试发现** | 精确匹配 → 目录匹配 → 模式匹配，确保找到对应测试 |
| **JSON 报告优先** | 使用 `pytest-json-report` 插件获取结构化结果 |
| **正则回退** | JSON 报告不可用时，正则解析 pytest stdout |
| **降级阈值 (Bug17)** | `test_pass_rate_threshold` (默认 0.8)，通过率达标可降级通过 |
| **验收测试** | `AcceptanceCriterion` 支持自定义验收标准 |

## 错误处理策略

| 场景 | 处理 |
|------|------|
| 无对应测试文件 | TestResult(passed=True, total=0)，视为无测试可跑 |
| pytest 执行超时 | 进程 kill，TestResult(passed=False) |
| JSON 报告缺失 | 回退到正则解析 stdout |
| 低通过率 | 检查 fallback_threshold，达标则降级通过 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 OD-001 §1.8 提取并扩充 |
