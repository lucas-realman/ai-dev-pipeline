# DD-MOD-010 — Reporter 模块详细设计

> **文档编号**: DD-MOD-010  
> **版本**: v1.0  
> **状态**: 正式  
> **更新日期**: 2026-03-07  
> **对应源码**: `orchestrator/reporter.py` (239 行)  
> **上游文档**: [OD-MOD-010](../04-outline-design/OD-MOD-010-reporter.md) · [DD-SYS-001](DD-SYS-001-系统详细设计.md)  
> **下游文档**: [TEST-001](../07-testing/TEST-001-测试策略与方案.md)

---

## §1 类结构

```
┌──────────────────────────────────────────────────────────┐
│                       Reporter                           │
├──────────────────────────────────────────────────────────┤
│ + config         : Config                                │
│ + webhook_url    : Optional[str]                         │
│ + webhook_secret : Optional[str]                         │
│ + app_key        : Optional[str]                         │
│ + app_secret     : Optional[str]                         │
│ - _access_token  : Optional[str]                         │
│ - _token_expiry  : float                                 │
│ + reports_dir    : str                                   │
├──────────────────────────────────────────────────────────┤
│ + __init__(config)                                       │
│ + notify_sprint_start(sprint_id, tasks)      «async»     │
│ + notify_task_dispatched(task, machine)       «async»     │
│ + notify_task_result(task, result)            «async»     │
│ + notify_sprint_done(sprint_id, summary)     «async»     │
│ + notify_error(message, context)             «async»     │
│ + notify_shutdown(reason)                    «async»     │
│ + generate_report(sprint_id, results) → str              │
│ - _send_webhook(title, text)                 «async»     │
│ - _send_openapi(title, text)                 «async»     │
│ - _get_access_token() → str                  «async»     │
│ - _compute_sign(timestamp, secret) → str     «static»    │
│ - _safe_notify(coro)                         «async»     │
└──────────────────────────────────────────────────────────┘
```

---

## §2 核心函数设计

### 2.1 通知接口 (6 个)

| 方法 | 触发时机 | 消息内容 |
|------|---------|---------|
| `notify_sprint_start(sprint_id, tasks)` | Sprint 启动 | Sprint ID + 任务数 + 任务列表 |
| `notify_task_dispatched(task, machine)` | 任务分发后 | task_id → machine_id |
| `notify_task_result(task, result)` | 任务完成后 | pass/fail + score + duration |
| `notify_sprint_done(sprint_id, summary)` | Sprint 结束 | 总结统计 |
| `notify_error(message, context)` | 异常发生 | 错误信息 + 上下文 |
| `notify_shutdown(reason)` | 系统停机 | 停机原因 (SIGTERM/SIGINT/异常) |

所有通知方法内部调用 `_safe_notify`，确保通知失败不影响主流程。

### 2.2 `_send_webhook` (DingTalk Webhook)

| 项目 | 内容 |
|------|------|
| **签名** | `async _send_webhook(self, title: str, text: str) → None` |
| **职责** | 通过钉钉自定义机器人发送 Markdown 消息 |
| **算法** | ALG-021 |

#### ALG-021: Webhook HMAC-SHA256 签名

```
function _send_webhook(title, text):
    if not self.webhook_url:
        return
    
    timestamp = str(int(time.time() * 1000))
    sign = _compute_sign(timestamp, self.webhook_secret)
    
    url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
    
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text
        }
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(url, json=payload, timeout=10)
```

**`_compute_sign` 实现**:
```python
string_to_sign = f"{timestamp}\n{secret}"
hmac_code = hmac.new(
    secret.encode('utf-8'),
    string_to_sign.encode('utf-8'),
    digestmod=hashlib.sha256
).digest()
return urllib.parse.quote_plus(base64.b64encode(hmac_code))
```

### 2.3 `_send_openapi` (DingTalk OpenAPI)

| 项目 | 内容 |
|------|------|
| **签名** | `async _send_openapi(self, title: str, text: str) → None` |
| **职责** | 通过钉钉企业内部机器人 OpenAPI 发送消息 |
| **算法** | ALG-022 |

#### ALG-022: OpenAPI access_token 缓存

```
function _send_openapi(title, text):
    if not self.app_key:
        return
    
    token = await _get_access_token()
    
    url = "https://oapi.dingtalk.com/topapi/message/..."
    headers = {"x-acs-dingtalk-access-token": token}
    
    await session.post(url, json=payload, headers=headers)

function _get_access_token():
    # 缓存策略: token 有效期内直接返回
    if self._access_token and time.time() < self._token_expiry:
        return self._access_token
    
    # 请求新 token
    url = "https://oapi.dingtalk.com/gettoken"
    params = {"appkey": self.app_key, "appsecret": self.app_secret}
    
    resp = await session.get(url, params=params)
    data = await resp.json()
    
    self._access_token = data["access_token"]
    self._token_expiry = time.time() + data["expires_in"] - 60  # 提前 60s 刷新
    
    return self._access_token
```

### 2.4 `generate_report`

| 项目 | 内容 |
|------|------|
| **签名** | `generate_report(self, sprint_id: str, results: List[Dict]) → str` |
| **职责** | 生成本地 Markdown 报告文件 |
| **输出** | `reports/sprint_{id}_{timestamp}.md` |

**报告结构**:
```markdown
# Sprint {sprint_id} 报告
> 生成时间: {datetime}

## 概要
- 总任务数: N
- 成功: N | 失败: N | 跳过: N
- 总耗时: N 秒
- 平均评分: N.N / 5.0

## 任务详情

### {task_id}
- **状态**: ✅ / ❌
- **机器**: machine_id
- **耗时**: Ns
- **审查分**: N.N / 5.0
- **测试**: M/N passed (xx%)
- **文件变更**: [...]

## 失败分析
(失败任务的错误摘要)
```

### 2.5 `_safe_notify`

| 项目 | 内容 |
|------|------|
| **签名** | `async _safe_notify(self, coro: Coroutine) → None` |
| **职责** | 包装通知协程，捕获所有异常 |
| **策略** | `try/except Exception → logger.warning` |

> 设计原则: 通知是辅助功能，任何通知失败不得影响编码流水线。

---

## §3 序列图

### SEQ-010: 双通道通知流程

```
Orchestrator     Reporter       DingTalk Webhook    DingTalk OpenAPI
    │               │               │                   │
    │ notify_xxx    │               │                   │
    │──────────────>│               │                   │
    │               │               │                   │
    │               │ HMAC sign     │                   │
    │               │───┐           │                   │
    │               │<──┘           │                   │
    │               │               │                   │
    │               │ POST markdown │                   │
    │               │──────────────>│                   │
    │               │     200       │                   │
    │               │<──────────────│                   │
    │               │               │                   │
    │               │ get_token     │                   │
    │               │ (cached?)     │                   │
    │               │──────────────────────────────────>│
    │               │     token     │                   │
    │               │<──────────────────────────────────│
    │               │               │                   │
    │               │ POST message  │                   │
    │               │──────────────────────────────────>│
    │               │     200       │                   │
    │               │<──────────────────────────────────│
    │               │               │                   │
    │     ok        │               │                   │
    │<──────────────│               │                   │
```

---

## §4 配置参数

| 配置路径 | 类型 | 说明 |
|----------|------|------|
| `dingtalk.webhook_url` | str | Webhook 地址 (含 access_token) |
| `dingtalk.webhook_secret` | str | HMAC 签名密钥 |
| `dingtalk.app_key` | str | 企业内部应用 AppKey |
| `dingtalk.app_secret` | str | 企业内部应用 AppSecret |
| `paths.reports_dir` | str | 报告输出目录 (默认 `reports/`) |

---

## §5 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-07 | 从 DD-001 §10 提取并扩充，含双通道详细算法 |
