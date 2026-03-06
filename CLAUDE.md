# CLAUDE.md — AI-Dev-Pipeline 项目规范

> 本文件供 Claude 系列模型自动加载。完整规范详见 `.github/copilot-instructions.md`。

## 核心原则

- **文档是最重要的资产**，文档驱动开发，所有设计先于编码
- 全局 ID 体系：FR → SYS → ARCH → MOD → IF → DM → TC，跨文档全链路可追溯

## 加载时必须执行

### 1. 文档体系完整性检查

验证 `docs/` 下 10 个核心目录及文档是否存在：

| # | 目录 | 必须文档 |
|---|------|---------|
| 01 | `01-requirements/` | `REQ-001-系统需求规格说明书.md` |
| 02 | `02-system-design/` | `SYS-001-系统设计说明书.md` |
| 03 | `03-architecture/` | `ARCH-001-架构总览.md`, `ARCH-002-部署架构.md` |
| 04 | `04-outline-design/` | `OD-001-模块概要设计.md`, `OD-002-数据模型设计.md`, `OD-003-接口契约设计.md` |
| 05 | `05-traceability/` | `TRACE-001-追溯矩阵.md` |
| 06 | `06-testing/` | `TEST-001-测试策略与方案.md` |
| 07 | `07-iteration/` | `ITER-001-迭代计划.md` |
| 08 | `08-operations/` | `OPS-003-风险识别与应对.md` |
| 09 | `09-references/` | `REF-001-术语表.md` |
| 10 | `10-references/` | `migrated/` 目录 |

通过输出 `✅ docs/ 文档体系完整性检查通过`，缺失则 `⚠️ 缺失项: [列出]`。

### 2. "评审" 指令

当用户说 **"评审"** 时：
1. 读取 `docs/11-review/README.md` 获取角色矩阵
2. 确定新版本号，创建 `docs/11-review/vX.Y/`
3. 为每个角色生成独立评审意见文件
4. 生成 `评审总结.md` 汇总所有意见
5. 生成 `ACTION-ITEMS.md` 行动项跟踪
6. 更新 `docs/11-review/README.md` 版本记录

详细模板和格式规范见 `.github/copilot-instructions.md`。

## 快速参考

- 文档导航：`docs/00-navigator.md`
- 评审角色：`docs/11-review/README.md`（当前 8 个角色）
- Python ≥ 3.10 | CLI 入口 `autodev` | 主分支 `main`
- 推送：`git push origin main`
