# AI-Dev-Pipeline — 项目特定规范（项目层）

> 本文件由 sync.sh 与共享层合并后生成最终 CLAUDE.md，请勿直接编辑根目录 CLAUDE.md。

## 项目信息

- **项目名称**: AI-Dev-Pipeline (AutoDev Pipeline)
- **CLI 入口**: `autodev`
- **Python**: ≥ 3.10
- **主分支**: `main`

## 文档体系（项目特定文件名）

| # | 目录 | 实际文件名 |
|---|------|-----------|
| 01 | `01-requirements/` | `REQ-001-系统需求规格说明书.md` |
| 02 | `02-system-design/` | `SYS-001-系统设计说明书.md` |
| 03 | `03-architecture/` | `ARCH-001-架构总览.md`, `ARCH-002-部署架构.md` |
| 04 | `04-outline-design/` | `OD-001-模块概要设计.md`, `OD-002-数据模型设计.md`, `OD-003-接口契约设计.md` |
| 05 | `05-detail-design/` | `DD-001-详细设计说明书.md` |
| 06 | `06-traceability/` | `TRACE-001-追溯矩阵.md` |
| 07 | `07-testing/` | `TEST-001-测试策略与方案.md` |
| 08 | `08-iteration/` | `ITER-001-迭代计划.md` |
| 09 | `09-operations/` | `OPS-003-风险识别与应对.md` |
| 10 | `10-references/` | `REF-001-术语表.md` |
| 11 | `11-references/` | `migrated/` 目录 |
| 12 | `12-review/` | `README.md` |

## 快速参考

- 文档导航：`docs/00-navigator.md`
- 评审角色：`docs/12-review/README.md`（当前 8 个角色）

## 代码评审触发规则

当用户说 **“代码评审”** 时，必须执行增量代码评审流程：

1. 读取 `docs/12-review/README.md`
2. 以最新全量评审为基线（当前建议 `v5.0`）
3. 强制覆盖以下评审范围：
	- 文档评审
	- 代码规范性评审
	- 文档与代码实现一致性评审
4. 新增生成 3 份角色报告：
	- `13-软件开发工程师-评审意见.md`
	- `14-软件测试工程师-评审意见.md`
	- `15-系统测试工程师-评审意见.md`
5. 生成新的 `评审总结.md`，需汇总 **8 个既有角色 + 4 个技术专项 + 3 个新增角色**
6. 生成新的 `ACTION-ITEMS.md`，按优先级归并问题

代码评审结论必须明确指出：

- 文档是否能指导真实使用
- 代码是否符合项目规范
- 文档描述是否与代码真实行为一致

## Git 工作流

1. **远程仓库**: `origin` → `git@github-lucas:lucas-realman/ai-dev-pipeline.git`
2. **推送命令**: `git push origin main`
3. **标签**: 重要里程碑使用 annotated tag (`git tag -a vX.Y -m "描述"`)

## 项目结构

```
├── .github/copilot-instructions.md   ← 项目规范（自动生成）
├── docs/00-navigator.md              ← 文档导航索引
├── docs/12-review/README.md          ← 评审角色矩阵
├── orchestrator/                     ← 13 模块 Python 源码
├── tests/                            ← 单元测试
└── pyproject.toml                    ← 项目配置
```
