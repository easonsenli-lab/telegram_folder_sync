# 移除实时私聊监听功能开发文档

本文档给 Antigravity / 后续 AI 使用。目标是移除后台常驻实时私聊监听，降低 Telegram session 长期在线、FloodWait、wrong session ID、状态误判等风险。

## 1. 目标

用户现在希望：

- 去掉后台实时监听所有账号私聊的功能。
- 不再让后台为了私聊通知而长期保持 Telegram 用户账号 session 在线。
- 后续优先使用 Bot 做通知和消息中转。
- 保留账号管理、加群、广告任务、账号登录、账号归属、公司权限等核心逻辑。

重要：不是删除整个账号管理系统，也不是删除 Telegram 账号 session。

## 2. 正确项目

主后台项目：

```text
E:\telegram_workspace\telegram_folder_sync
```

核心文件：

```text
web_server.py
frontend/src/App.tsx
private_dm_events.py
```

不要改错到：

```text
E:\telegram_bot_workspace              # AI/通知 Bot
E:\telegram_translate_bot_workspace    # 翻译 Bot
```

Bot 相关文档：

```text
E:\telegram_bot_workspace\AI_BOT_HANDOFF.md
```

## 3. 为什么要移除

当前实时私聊设计会导致：

- `auto_private_listener_loop()` 周期性连接所有可用账号。
- 多个账号长期持有 Telethon client。
- 页面轮询、私聊监听、任务执行、状态检测可能同时碰同一个 session。
- Telegram 可能返回：

```text
FloodWaitError caused by GetUsersRequest
Security error ... wrong session ID
Server closed the connection
Connection reset by peer
```

这些错误已经导致过账号在 UI 上被误标成未登录。

最新规则已经修复：检测失败不能写成未登录。但实时监听本身仍会造成连接压力，所以要移除或关闭。

## 4. 移除范围

需要移除或禁用：

1. 后台自动私聊监听：

```text
auto_private_listener_loop()
ensure_private_listener_for_account()
auto_private_listener_accounts
auto_private_listener_cooldowns
```

2. 启动时自动创建监听任务：

```text
startup_event()
asyncio.create_task(auto_private_listener_loop())
```

3. 前端“私聊通知 / 浏览器右下角弹窗”：

```text
private_dm_event stream
Notification API
requestDmNotificationPermission
私聊通知按钮
```

4. 自动保持私聊监听状态展示：

```text
private_listener
private_listener_source
监听中
```

5. 周期性私聊未读摘要轮询，如果它只是读缓存可以保留；如果会触发 Telegram 连接，必须改成只读缓存。

## 5. 建议保留的能力

建议保留：

- 后台账号列表。
- 账号登录。
- 加群任务。
- 广告轰炸任务。
- 账号归属 / 公司权限。
- Bot 后台任务通知。
- 已缓存私聊查看，如果不触发 Telegram 实时请求。

建议改成：

```text
私聊页面 = 可选历史缓存查看 / 手动刷新
```

但默认不要自动连接 Telegram 用户账号去抓私聊。

如果用户最终决定完全迁移到 Bot 中转，则私聊页面可以后续再删除。

## 6. 后端修改建议

### 6.1 增加总开关

建议在 `web_server.py` 顶部加配置：

```python
ENABLE_REALTIME_PRIVATE_DM = os.getenv("ENABLE_REALTIME_PRIVATE_DM", "0") == "1"
```

默认关闭。

### 6.2 禁止启动自动监听

找到启动事件：

```python
asyncio.create_task(auto_private_listener_loop())
```

改为：

```python
if ENABLE_REALTIME_PRIVATE_DM:
    asyncio.create_task(auto_private_listener_loop())
```

默认不启动。

### 6.3 禁用手动启动监听接口

接口：

```text
POST /api/accounts/private-listeners/start-idle
```

建议保留接口但返回明确提示：

```json
{
  "started": [],
  "skipped": [],
  "failed": [],
  "disabled": true,
  "message": "实时私聊监听已关闭，请使用 Bot 通知/中转方案"
}
```

不要删除接口，避免前端旧代码调用时报 404。

### 6.4 账号状态不要再显示监听中

`/api/accounts` 返回里：

```python
private_listener_active = acc.id in auto_private_listener_accounts and live_connected
```

关闭后应固定为：

```python
private_listener_active = False
private_listener_source = None
```

或者只在 `ENABLE_REALTIME_PRIVATE_DM=True` 时计算。

### 6.5 私聊接口只读缓存

检查这些接口：

```text
GET /api/accounts/private-unread-summary
GET /api/accounts/{account_id}/private-dialogs
GET /api/accounts/{account_id}/private-dialogs/{peer_id}/messages
POST /api/accounts/{account_id}/private-dialogs/{peer_id}/send
GET /api/private-dm/stream
```

建议策略：

- `private-unread-summary`：只读 `data/private_dm_events.jsonl` 和 ack，不触发 Telegram。
- `private-dialogs?cache_only=true`：保留。
- `private-dialogs` 默认也改成 cache only，除非显式 `manual=true`。
- `messages` 默认只读缓存。
- `send` 如果还保留，必须走账号操作锁，并明确提示“该功能依赖用户账号 session，可能影响任务”。如果要彻底迁移到 Bot，则后续删除发送能力。
- `private-dm/stream` 可以保留但不会有新实时事件，或者返回 disabled ping。

## 7. 前端修改建议

文件：

```text
frontend/src/App.tsx
```

需要做：

1. 删除或隐藏“开启私聊通知 / 通知已开 / 通知被禁”按钮。
2. 删除浏览器 Notification 逻辑。
3. 删除或禁用 `/api/private-dm/stream` 实时事件监听。
4. 账号卡片上的“监听中”状态不要展示。
5. 私聊入口如果保留，文案改为：

```text
私聊缓存
仅展示已缓存私聊；实时接待请使用 RosePay Bot。
```

6. 打开私聊页面默认 `cache_only=true`。
7. 不要因为私聊功能关闭而影响账号可用状态。

## 8. 不要动的东西

不要删除：

```text
data/rosepay.db
sessions/
accounts/
data/secret.key
```

不要改坏：

- 账号归属 `owner_username`
- 公司权限 `company`
- 管理员查看全部账号能力
- 普通用户只能看自己/本公司账号的限制
- 加群任务
- 广告任务
- Bot 后台任务通知

## 9. 和 Bot 的后续衔接

用户倾向后续方案：

```text
客户联系 Bot -> Bot 转发到管理群 -> 管理员通过 Bot 回复客户
```

这部分应该在 `E:\telegram_bot_workspace` 里做，不应该继续依赖主后台实时监听用户账号私聊。

后续 Bot 可做：

- 客户私聊 Bot 自动建档。
- Bot 把客户消息转发到管理群。
- 管理员引用/按钮回复客户。
- 按用户/公司权限分配客户。
- 后台任务完成仍由 Bot 通知对应用户。

## 10. 验证清单

修改后本地必须验证：

```powershell
cd E:\telegram_workspace\telegram_folder_sync
python -m py_compile web_server.py

cd E:\telegram_workspace\telegram_folder_sync\frontend
npm run build
```

功能验证：

- 启动服务后日志不再自动出现 `[PrivateListener] Auto listener active...`
- 进入账号管理页不会自动连接所有账号。
- 刷新账号列表不会因为私聊监听关闭报错。
- `/api/accounts` 中不再显示 `private_listener=true`。
- 加群任务可启动。
- 广告任务可启动。
- Bot 后台任务通知仍可发送。
- 登录状态检测失败仍显示 `status_check_failed`，不会误标未登录。

## 11. 推荐实施顺序

1. 先加 `ENABLE_REALTIME_PRIVATE_DM` 开关，默认关闭。
2. 禁止启动 `auto_private_listener_loop()`。
3. 禁用前端 Notification 和实时私聊 SSE。
4. 把私聊页面改成缓存只读或隐藏入口。
5. 本地构建验证。
6. 备份线上代码和数据库。
7. 部署。
8. 线上确认日志不再出现自动私聊监听。

## 12. 给接手 AI 的一句话需求

请在 `E:\telegram_workspace\telegram_folder_sync` 中移除/默认关闭实时私聊监听功能。不要删除账号、session、加群、广告任务、公司权限和 AI Bot 通知。默认不要让后台自动连接所有 Telegram 用户账号监听私聊；前端也不要再显示浏览器私聊弹窗。私聊后续将迁移到 `E:\telegram_bot_workspace` 的 Bot 中转方案。

