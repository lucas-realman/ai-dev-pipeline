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
