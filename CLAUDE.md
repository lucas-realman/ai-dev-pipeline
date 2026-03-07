# CLAUDE.md — 团队 AI 规范（共享层）

> 本文件供 Claude 系列模型自动加载。完整规范详见 `.github/copilot-instructions.md`。
> **注意**: 本文件由 team-ai-rules 自动同步生成，请勿直接编辑。

## 核心原则

- **文档是最重要的资产**，文档驱动开发，所有设计先于编码
- 全局 ID 体系：FR → SYS → ARCH → MOD → IF → DM → TC，跨文档全链路可追溯

## 加载时必须执行

### 1. 文档体系完整性检查

验证 `docs/` 下 12 个核心目录及文档是否存在：

| # | 目录 | 必须文档 |
|---|------|---------|
| 01 | `01-requirements/` | `REQ-001-*.md` |
| 02 | `02-system-design/` | `SYS-001-*.md` |
| 03 | `03-architecture/` | `ARCH-001-*.md`, `ARCH-002-*.md` |
| 04 | `04-outline-design/` | `OD-001-*.md`, `OD-002-*.md`, `OD-003-*.md` |
| 05 | `05-detail-design/` | `DD-001-*.md` |
| 06 | `06-traceability/` | `TRACE-001-*.md` |
| 07 | `07-testing/` | `TEST-001-*.md` |
| 08 | `08-iteration/` | `ITER-001-*.md` |
| 09 | `09-operations/` | `OPS-*.md` |
| 10 | `10-references/` | `REF-001-*.md` |
| 11 | `11-archive/` | `migrated/` 目录 |
| 12 | `12-review/` | `README.md` |

通过输出 `✅ docs/ 文档体系完整性检查通过`，缺失则 `⚠️ 缺失项: [列出]`。

### 2. "评审" 指令

当用户说 **"评审"** 时：
1. 读取 `docs/12-review/README.md` 获取角色矩阵
2. 确定新版本号，创建 `docs/12-review/vX.Y/`
3. 为每个角色生成独立评审意见文件
4. 生成 `评审总结.md` 汇总所有意见
5. 生成 `ACTION-ITEMS.md` 行动项跟踪
6. 更新 `docs/12-review/README.md` 版本记录

详细模板和格式规范见 `.github/copilot-instructions.md`。

## 通用规范

- 文档默认使用中文，技术术语保留英文
- 提交信息：使用中文，格式 `[类型] 描述`，类型包括：文档、功能、修复、重构、测试
- 修改代码后必须运行相关测试

---

<!-- 以下为项目特定规范，由 .ai-rules/project.claude.md 生成 -->

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
| 11 | `11-archive/` | `migrated/` 目录 |
| 12 | `12-review/` | `README.md` |

## 快速参考

- 文档导航：`docs/00-navigator.md`
- 评审角色：`docs/12-review/README.md`（当前 8 个角色）

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
