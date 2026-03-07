# AI-Dev-Pipeline — 项目特定规范（Copilot 项目层）

> 本文件由 sync.sh 与共享层合并后生成最终 .github/copilot-instructions.md，请勿直接编辑。

## 项目代码规范

1. **Python ≥ 3.10**，遵循 `pyproject.toml` 配置
2. **CLI 入口**: `autodev`

## Git 工作流

1. **远程仓库**: `origin` → `git@github-lucas:lucas-realman/ai-dev-pipeline.git`
2. **主分支**: `main`
3. **推送命令**: `git push origin main`（注意使用 origin，不是 github-lucas）
4. **标签**: 重要里程碑使用 annotated tag (`git tag -a vX.Y -m "描述"`)

## 快速参考

```
项目根目录
├── .github/copilot-instructions.md   ← 本文件（项目规范，自动生成）
├── docs/00-navigator.md              ← 文档导航索引
├── docs/12-review/README.md          ← 评审角色矩阵
├── orchestrator/                     ← 13 模块 Python 源码
├── tests/                            ← 单元测试
└── pyproject.toml                    ← 项目配置
```

## 代码评审规则

当用户说 **“代码评审”** 时，必须执行以下流程：

1. 读取 `docs/12-review/README.md`
2. 以上一轮最新全量评审为基线（当前默认为 `v5.0`）
3. 强制检查以下 3 类内容：
	- 文档是否完整、是否可执行
	- 代码规范性是否达标（命名、异常、日志、测试、模块职责）
	- 文档与代码实现是否一致（CLI、配置、API、目录结构、运行方式）
4. 生成 3 份新增角色评审报告：
	- `13-软件开发工程师-评审意见.md`
	- `14-软件测试工程师-评审意见.md`
	- `15-系统测试工程师-评审意见.md`
5. 生成新的 `评审总结.md`，汇总 **8 个既有角色 + 4 个技术专项 + 3 个新增角色**
6. 生成新的 `ACTION-ITEMS.md`，按 P0→P3 合并去重

代码评审不是只看代码本身，必须同时检查：

- 文档可读性与可执行性
- 实现与文档的一致性
- 测试覆盖与交付物一致性
