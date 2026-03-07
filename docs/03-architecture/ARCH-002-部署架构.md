# ARCH-002 — 部署架构

> **文档编号**: ARCH-002  
> **版本**: v1.0  
> **状态**: 草稿  
> **更新日期**: 2026-03-06  
> **上游文档**: [SYS-001](../02-system-design/SYS-001-系统设计说明书.md) · [ARCH-001](ARCH-001-架构总览.md)  
> **下游文档**: [OD-001](../04-outline-design/OD-001-模块概要设计.md) · [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 机器拓扑

> 映射: SYS-002, FR-004~005, CON-002/007

### 1.1 物理拓扑图

```
                          Internet
                              │
                              │ HTTPS (出站 only)
                              │ → 一步 API (LLM)
                              │ → 钉钉 Webhook
                              │
                    ══════════╪══════════════════
                              │
                    ┌─────────┴──────────┐
                    │   Router/Firewall   │
                    │   172.16.0.0/16     │
                    └─────────┬──────────┘
                              │
          ┌───────────┬───────┼───────┬───────────┐
          │           │       │       │           │
    ┌─────┴─────┐ ┌───┴────┐ │ ┌─────┴────┐ ┌────┴──────┐
    │orchestrator│ │  4090  │ │ │ gateway  │ │data_center│
    │.14.201    │ │.11.194 │ │ │.14.215   │ │.14.90     │
    │           │ │        │ │ │          │ │           │
    │ ★ 调度中心│ │ GPU×2  │ │ │ 通用编码 │ │ 通用编码  │
    │ pytest    │ │ vLLM   │ │ │          │ │ PG 热备   │
    │ aider     │ │ aider  │ │ │ aider    │ │ aider     │
    └───────────┘ └────────┘ │ └──────────┘ └───────────┘
                             │
                       ┌─────┴─────┐
                       │mac_min_8T │
                       │.12.50     │
                       │           │
                       │ Git 裸仓库│
                       │ 7.3TB SSD │
                       │ aider     │
                       └───────────┘
```

### 1.2 机器角色与职责矩阵

| 机器 | IP | CPU | 内存 | GPU | 存储 | 角色 | 服务 |
|------|----|-----|------|-----|------|------|------|
| **orchestrator** | 172.16.14.201 | Xeon 64C | 128 GB | 2×4090 | — | 调度中心 | Orchestrator, pytest, aider |
| **4090** | 172.16.11.194 | Xeon 64C | 128 GB | 2×4090 | — | GPU 计算 | vLLM (Qwen3-30B), aider |
| **mac_min_8T** | 172.16.12.50 | M4 Pro 12C | 64 GB | — | 7.3 TB SSD | 存储 / 编码 | Git 裸仓库, aider |
| **gateway** | 172.16.14.215 | i5 16C | 32 GB | — | — | 通用编码 | aider |
| **data_center** | 172.16.14.90 | i5 16C | 32 GB | — | — | 通用编码 | aider, PG 热备 |

### 1.3 标签匹配规则

机器池通过 `tags` 实现任务-机器匹配：

| 标签 | 含义 | 拥有该标签的机器 |
|------|------|----------------|
| `gpu` | 需要 GPU 加速 | orchestrator, 4090 |
| `high-mem` | 需要 ≥64 GB 内存 | orchestrator, 4090, mac_min_8T |
| `ssd` | 大量磁盘 I/O | mac_min_8T |
| `general` | 无特殊要求 | gateway, data_center |

---

## §2 网络与安全

> 映射: NFR-009~011, CON-002

### 2.1 网络策略

| 方向 | 协议 | 端口 | 源 → 目标 | 用途 |
|------|------|------|----------|------|
| 内网入 | SSH | 22 | orchestrator → 所有 Worker | 编码分发 |
| 内网入 | HTTP | 8000 | 4090 vLLM | Agent 推理 |
| 出站 | HTTPS | 443 | orchestrator → 一步API | LLM 调用 |
| 出站 | HTTPS | 443 | orchestrator → 钉钉 | 通知 |
| 内网入 | SSH | 22 | 所有 Worker → mac_min_8T | Git push/pull |
| **禁止** | — | — | 外网 → 内网 | 无公网入站 |

### 2.2 密钥管理

| 密钥类型 | 存储位置 | 访问范围 |
|----------|---------|---------|
| SSH 密钥 | `~/.ssh/` (每台机器) | 机器间免密登录 |
| LLM API Key | `.env` (orchestrator) | 仅 orchestrator 进程 |
| 钉钉 Webhook URL | `.env` (orchestrator) | 仅 reporter 模块 |
| Git 裸仓库 | mac_min_8T bare repo | 所有机器可 push/pull |

**安全规则**:
- `.env` 文件在 `.gitignore` 中，不进入版本控制
- SSH 密钥使用 ed25519 算法，禁用密码登录
- LLM API Key 通过环境变量 `${OPENAI_API_KEY}` 注入，不硬编码

---

## §3 容器化与部署规划

> 映射: NFR-007~008, CON-006

### 3.1 当前部署方式 (v1.0)

| 组件 | 部署方式 | 管理工具 |
|------|---------|---------|
| Orchestrator | 系统进程 (systemd) | `autodev` CLI |
| aider | pip 安装 (各 Worker) | 手动/脚本 |
| vLLM | Docker 容器 (4090) | docker compose |
| Git 裸仓库 | 文件系统 (mac_min_8T) | Git 原生 |
| PostgreSQL | 系统服务 (data_center) | systemd |

### 3.2 容器化路线图 (v2.0 规划)

```
v1.0 (当前)               v2.0 (规划)
─────────────             ─────────────
系统进程部署       →       Docker Compose 统一编排
手动安装 aider     →       aider Docker 镜像
分散的 .env 文件   →       Docker secrets / vault
手动 SSH 配置      →       容器化 Worker 自动注册
```

| 里程碑 | 内容 | 前置条件 |
|--------|------|---------|
| v2.0-M1 | Orchestrator Docker 镜像 + compose.yaml | v1.0 稳定运行 2 周 |
| v2.0-M2 | Worker 统一 Docker 镜像 (含 aider + SSH) | M1 验证通过 |
| v2.0-M3 | 机器自动注册 (Worker 启动时向 Registry 注册) | M2 验证通过 |

---

## 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-06 | 初始版本：机器拓扑 + 网络安全 + 容器化规划 | AutoDev Pipeline |
