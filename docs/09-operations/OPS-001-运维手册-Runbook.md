# OPS-001 — 运维手册 (Runbook)

> **文档编号**: OPS-001  
> **版本**: v1.0  
> **状态**: 正式  
> **创建日期**: 2026-03-07  
> **上游文档**: [DD-SYS-001](../05-detail-design/DD-SYS-001-系统详细设计.md) · [DD-MOD-013](../05-detail-design/DD-MOD-013-main.md)  
> **对应 ACTION-ITEM**: v2.0 A-013 / v1.0 A-012

---

## §1 系统概述

AutoDev Pipeline 是一个 AI 驱动的自动化编码流水线，通过 LLM 分解任务、SSH 远程分发 aider 编码、自动审查和测试，实现 Sprint 级别的代码自动化生产。

### 1.1 运行架构

```
[Orchestrator 主机]
    ├── orchestrator/main.py (CLI: autodev)
    ├── config.yaml
    ├── logs/
    │   ├── orchestrator.log
    │   ├── orchestrator.jsonl (JSON 结构化日志)
    │   └── llm_audit/
    └── reports/

    SSH ──→ [W1: 192.168.1.101]  (aider + git)
    SSH ──→ [W2: 192.168.1.102]  (aider + git)
    SSH ──→ [W3: 192.168.1.103]  (aider + git)

    HTTPS ──→ LLM API (OpenAI-compatible)
    HTTPS ──→ 钉钉 Webhook
    SSH/HTTPS ──→ Git Remote (GitHub/GitLab)
```

### 1.2 关键端口与服务

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| SSH (Worker) | 22 | TCP | Orchestrator → Worker 机器 |
| LLM API | 443 | HTTPS | 文档分解 + 代码审查 |
| Prometheus Metrics | 9090 | HTTP | 监控指标暴露 (可选) |
| 钉钉 Webhook | 443 | HTTPS | 通知推送 |
| Git Remote | 22/443 | SSH/HTTPS | 代码推送 |

---

## §2 日常运维操作

### 2.1 启动 Sprint

```bash
# 标准启动
autodev sprint --sprint 1 --config ./config.yaml

# 预览模式 (不执行, 仅查看任务分解)
autodev dry-run --sprint 1 --config ./config.yaml

# 后台运行 (systemd 或 nohup)
nohup autodev sprint --sprint 1 > /dev/null 2>&1 &
```

### 2.2 停止 Sprint

```bash
# 优雅停机 (等待当前任务完成)
kill -SIGTERM <pid>

# 强制停机 (会丢失进行中的任务)
kill -SIGKILL <pid>
# ⚠️ 下次启动时会自动从快照恢复
```

### 2.3 查看运行状态

```bash
# 检查进程
ps aux | grep autodev

# 查看实时日志
tail -f logs/orchestrator.log

# 查看 JSON 结构化日志
cat logs/orchestrator.jsonl | jq '.level, .msg'

# 检查 Sprint 报告
ls -la reports/
cat reports/sprint_report_*.md
```

### 2.4 配置变更

```bash
# 1. 编辑配置
vim config.yaml

# 2. 验证配置 (dry-run 模式)
autodev dry-run --config ./config.yaml

# 3. 重启服务
kill -SIGTERM <pid> && sleep 5 && autodev sprint --sprint N --config ./config.yaml
```

---

## §3 故障排查手册

### 3.1 LLM API 连接失败

**症状**: `[ERROR] LLM 调用失败, 已重试 3 次: Connection refused`

**排查步骤**:
1. 检查 LLM API 可达性: `curl -I $OPENAI_API_BASE/models`
2. 检查 API Key: `echo $OPENAI_API_KEY | head -c 8` (只看前 8 字符)
3. 检查代理/防火墙: `traceroute <api-host>`
4. 查看 LLM 审计日志: `ls logs/llm_audit/$(date +%Y-%m-%d)/`

**处理**:
- 临时: 流水线会自动降级 (DocAnalyzer → DocParser, Reviewer → 3.5 分边界通过)
- 根治: 修复网络/API Key 后重启

### 3.2 SSH 连接失败

**症状**: `[WARNING] 机器 W1 SSH 预检失败: exit=255`

**排查步骤**:
1. 手动 SSH 测试: `ssh -T -o ConnectTimeout=5 dev@192.168.1.101 'echo ok'`
2. 检查 SSH Key: `ssh-add -l`
3. 检查 sshd 配置: `ssh dev@host 'cat /etc/ssh/sshd_config | grep PermitRoot'`
4. 检查网络: `ping 192.168.1.101`

**处理**:
- 机器自动标记为 OFFLINE，任务迁移到其他机器
- 修复 SSH 后，重启 Orchestrator 或等待下一轮自动重试

### 3.3 Git Push 冲突

**症状**: `[WARNING] git push 失败, 重试中 (2/3)`

**排查步骤**:
1. 查看日志中的 push 计数: `grep __PUSH_COUNT__ logs/orchestrator.log`
2. 检查远程分支状态: `git log --oneline origin/main -5`
3. 检查是否有人手动 push 了代码

**处理**:
- 内置 3 次重试 (rebase → no-rebase fallback)
- 如果频繁冲突，启用 per-machine branch 模式: `config.per_machine_branch: true`

### 3.4 磁盘空间不足

**症状**: `[ERROR] 机器 W1: No space left on device (ERR-022)`

**处理**:
1. SSH 到目标机器清理: `ssh dev@W1 'df -h && du -sh /tmp/* | sort -rh | head'`
2. 清理旧的 aider 临时文件: `ssh dev@W1 'rm -f /tmp/aider_msg_*'`
3. 恢复机器状态: 重启 Orchestrator (自动重检)

### 3.5 OOM (内存溢出)

**症状**: `[CRITICAL] 机器 W1: 进程被 OOM Killer 终止 (exit=-9)`

**处理**:
1. 检查机器内存: `ssh dev@W1 'free -h'`
2. 检查是否有内存泄漏的 aider 进程: `ssh dev@W1 'ps aux --sort=-%mem | head -10'`
3. 如果连续 2 次 OOM，机器会被本轮 Sprint 永久排除

### 3.6 崩溃恢复

**症状**: Orchestrator 进程意外退出

**处理**:
1. 重新启动即可: `autodev sprint --sprint N`
2. 系统自动从 `_snapshot.json` 恢复状态
3. 已 DISPATCHED 但未返回的任务会被标记为 RETRY
4. ⚠️ 远程可能已产出代码但未 push — 手动检查: `ssh dev@W1 'cd project && git status'`

---

## §4 监控与告警

### 4.1 关键监控指标

| 指标 | 健康阈值 | 告警条件 |
|------|---------|---------|
| LLM 调用成功率 | ≥95% | 5min 内错误率 >30% |
| 任务通过率 | ≥70% | Sprint 通过率 <50% |
| SSH 连通性 | 所有机器 ONLINE | 任一机器连续 3 次预检失败 |
| 磁盘可用 | ≥20% | 任一机器 <10% |
| Sprint 进度 | 持续推进 | 30min 无进展 |

### 4.2 日志轮转

```bash
# loguru 自动轮转 (config.yaml)
# rotation: 50 MB
# retention: 30 days

# 手动清理旧日志
find logs/ -name "*.log*" -mtime +30 -delete
find logs/llm_audit/ -type d -mtime +30 -exec rm -rf {} +
```

---

## §5 备份与恢复

### 5.1 需要备份的数据

| 数据 | 路径 | 频率 | 重要性 |
|------|------|------|--------|
| 配置文件 | `config.yaml` | 变更后 | 🔴 关键 |
| 状态快照 | `_snapshot.json` | 自动 (每次状态变更) | 🟡 可重建 |
| Sprint 报告 | `reports/` | Sprint 后 | 🟢 可选 |
| LLM 审计日志 | `logs/llm_audit/` | 按需 | 🟢 可选 |
| 契约文件 | `contracts/` | 变更后 | 🔴 关键 |

### 5.2 恢复步骤

```bash
# 1. 恢复配置
cp backup/config.yaml ./config.yaml

# 2. 恢复契约
cp -r backup/contracts/ ./contracts/

# 3. 重新启动 (快照自动恢复)
autodev sprint --sprint N
```

---

## §6 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 初版: 日常操作、故障排查、监控告警、备份恢复 |
