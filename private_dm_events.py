from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from telethon import events, types

# 模块级全局去重集合，防止瞬间重复发送首问欢迎语
first_chat_notified_set = set()


DM_EVENTS_FILE = Path("data/private_dm_events.jsonl")
TOPICS_MAP_FILE = Path(__file__).resolve().parent / "data" / "bot_topics.json"


def get_topic_thread_id(account_id: str, sender_id: int) -> Optional[int]:
    if not TOPICS_MAP_FILE.exists():
        return None
    try:
        with TOPICS_MAP_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            key = f"{account_id}:{sender_id}"
            val = data.get(key)
            if isinstance(val, list):
                return val[1]
            return val
    except Exception:
        return None


def save_topic_thread_id(account_id: str, sender_id: int, chat_id: int, thread_id: int) -> None:
    data = {}
    if TOPICS_MAP_FILE.exists():
        try:
            with TOPICS_MAP_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    key = f"{account_id}:{sender_id}"
    data[key] = [chat_id, thread_id]

    rev_key = f"rev:{chat_id}:{thread_id}"
    data[rev_key] = [account_id, sender_id]

    try:
        TOPICS_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TOPICS_MAP_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Topics] Save error: {e}")


def get_info_by_thread_id(thread_id: int, chat_id: Optional[int] = None) -> Optional[tuple[str, int]]:
    if not TOPICS_MAP_FILE.exists():
        return None
    try:
        with TOPICS_MAP_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

            if chat_id is not None:
                rev_key = f"rev:{chat_id}:{thread_id}"
                val = data.get(rev_key)
                if val:
                    return val[0], int(val[1])

            for k, v in data.items():
                if k.startswith("rev:"):
                    continue
                t_id = v[1] if isinstance(v, list) else v
                if t_id == thread_id:
                    parts = k.split(":")
                    if len(parts) == 2:
                        return parts[0], int(parts[1])
    except Exception:
        return None
    return None


def _send_urllib_request_sync(url: str, data_bytes: bytes, headers: dict, timeout: int = 10) -> dict:
    import json
    import requests

    try:
        from static_proxy_pool import telegram_requests_proxy_kwargs

        response = requests.post(
            url,
            data=data_bytes,
            headers=headers,
            timeout=timeout,
            **telegram_requests_proxy_kwargs("private_dm_bot_api"),
        )
        try:
            parsed = response.json()
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            return parsed
        return {"ok": response.ok, "error_code": response.status_code, "description": response.text}
    except Exception as exc:
        return {"ok": False, "description": str(exc)}


def _topic_send_failed_because_thread_is_stale(response: dict) -> bool:
    description = str(response.get("description") or "").lower()
    return any(
        marker in description
        for marker in (
            "message thread not found",
            "thread not found",
            "topic closed",
            "topic deleted",
        )
    )


def clear_topic_thread_id(account_id: str, sender_id: int, chat_id: Optional[int] = None, thread_id: Optional[int] = None) -> None:
    if not TOPICS_MAP_FILE.exists():
        return
    try:
        with TOPICS_MAP_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.pop(f"{account_id}:{sender_id}", None)
        if chat_id is not None and thread_id is not None:
            data.pop(f"rev:{chat_id}:{thread_id}", None)
        with TOPICS_MAP_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[Topics] Clear error: {exc}")

async def async_notify_admin_of_dm(account_id: str, account_label: str, sender_id: int, sender_name: str, sender_username: str, message_text: str, message_id: int) -> None:
    import sqlite3
    import urllib.request
    import urllib.parse
    import json
    from pathlib import Path
    import os
    import asyncio

    # 1. Query rosepay.db to find the admin details
    db_path = Path(__file__).resolve().parent / "data" / "rosepay.db"
    if not db_path.exists():
        print(f"[NotifyAdmin] DB path not found: {db_path}")
        return

    telegram_chat_id = None
    owner_username = None
    admin_contact = None
    db_account_name = None
    forum_chat_id = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT owner_username, account_name FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if row:
            if row[0]:
                owner_username = row[0]
                cursor.execute("SELECT telegram_chat_id, telegram_contact, forum_chat_id FROM admins WHERE username = ?", (owner_username,))
                admin_row = cursor.fetchone()
                if admin_row:
                    telegram_chat_id = admin_row[0]
                    admin_contact = admin_row[1]
                    forum_chat_id = admin_row[2]
            if row[1]:
                db_account_name = row[1]
        conn.close()
    except Exception as exc:
        print(f"[NotifyAdmin] Failed to query database: {exc}")
        return

    display_account_name = db_account_name if db_account_name else account_label

    # 2. Retrieve Bot Token
    bot_token = None
    try:
        if os.name != "nt":
            bot_env_path = Path("/opt/rosepay-telegram-bot/.env")
        else:
            bot_env_path = Path(__file__).resolve().parent.parent.parent / "telegram_bot_workspace" / ".env"
        if bot_env_path.exists():
            with bot_env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("BOT_TOKEN="):
                        bot_token = line.split("=", 1)[1].strip()
                        break
    except Exception as exc:
        print(f"[NotifyAdmin] Failed to read Bot Token from env: {exc}")

    if not bot_token:
        bot_token = os.getenv("BOT_TOKEN", "").strip()

    if not bot_token:
        print("[NotifyAdmin] Bot token not found, cannot send notification")
        return

    # 3. Read notify_config.json or use user's forum_chat_id
    notify_chat_id = forum_chat_id if forum_chat_id else None
    if not notify_chat_id:
        try:
            if os.name != "nt":
                notify_config_path = Path("/opt/rosepay-telegram-bot/notify_config.json")
            else:
                notify_config_path = Path(__file__).resolve().parent.parent.parent / "telegram_bot_workspace" / "notify_config.json"
            if notify_config_path.exists():
                with notify_config_path.open("r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    notify_chat_id = config_data.get("notify_chat_id")
        except Exception as exc:
            print(f"[NotifyAdmin] Failed to read notify_config.json: {exc}")

    sender_display = sender_username if sender_username else sender_name
    sender_username_clean = sender_username.strip().lstrip("@") if sender_username else ""
    if sender_username_clean:
        sender_display_html = f"<b>{sender_name}</b> (@{sender_username_clean})"
    else:
        sender_display_html = f"<b>{sender_name}</b>"

    # CASE A: Supergroup Forum Topic Mode is configured (Recommended)
    if notify_chat_id:
        thread_id = get_topic_thread_id(account_id, sender_id)
        is_new_topic = False

        # If no thread_id exists, create a new Forum Topic dynamically
        if not thread_id:
            create_url = f"https://api.telegram.org/bot{bot_token}/createForumTopic"
            create_payload = {
                "chat_id": int(notify_chat_id),
                "name": f"[{display_account_name}] {sender_display}"
            }
            try:
                c_data = json.dumps(create_payload).encode("utf-8")
                c_res = await asyncio.to_thread(
                    _send_urllib_request_sync,
                    create_url,
                    c_data,
                    {"Content-Type": "application/json"},
                    10
                )
                if c_res.get("ok"):
                    thread_id = c_res["result"]["message_thread_id"]
                    save_topic_thread_id(account_id, sender_id, int(notify_chat_id), thread_id)
                    is_new_topic = True
                    print(f"[NotifyAdmin] Created new Forum Topic {thread_id} for account {account_id} and sender {sender_id}")
                else:
                    print(f"[NotifyAdmin] Failed to create Forum Topic: {c_res}")
            except Exception as c_exc:
                print(f"[NotifyAdmin] Error creating Forum Topic: {c_exc}")

        if thread_id:
            # If it's a newly created topic, send a beautiful setup card first
            if is_new_topic:
                mention_name = admin_contact if admin_contact else owner_username
                admin_mention = f"@{mention_name.lstrip('@')}" if mention_name else "@admin"
                intro_text = (
                    f"🔔 <b>【托管账号收到新会话】</b>\n\n"
                    f"● <b>托管账号</b>: <b>{display_account_name}</b>\n"
                    f"● <b>归属管理员</b>: {admin_mention}\n"
                    f"● <b>客户</b>: {sender_display_html}\n\n"
                    f"💬 <b>通道已建立。您在此主题直接打字发送，即可实时回复客户！</b>"
                )
                intro_payload = {
                    "chat_id": int(notify_chat_id),
                    "message_thread_id": int(thread_id),
                    "text": intro_text,
                    "parse_mode": "HTML"
                }
                try:
                    await asyncio.to_thread(
                        _send_urllib_request_sync,
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json.dumps(intro_payload).encode("utf-8"),
                        {"Content-Type": "application/json"},
                        10
                    )
                except Exception as intro_exc:
                    print(f"[NotifyAdmin] Error sending intro card: {intro_exc}")

            # Send the actual customer message content to the Topic with a beautiful name and username prefix
            sender_display_name = sender_name.strip()
            sender_display_username = f" (@{sender_username.strip().lstrip('@')})" if sender_username else ""

            # Format: 👤 Name (@username)
            header_prefix = f"👤 <b>{sender_display_name}</b>{sender_display_username}\n"
            formatted_text = f"{header_prefix}{message_text}"

            msg_payload = {
                "chat_id": int(notify_chat_id),
                "message_thread_id": int(thread_id),
                "text": formatted_text,
                "parse_mode": "HTML"
            }
            try:
                resp_data = await asyncio.to_thread(
                    _send_urllib_request_sync,
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json.dumps(msg_payload).encode("utf-8"),
                    {"Content-Type": "application/json"},
                    10
                )
                if resp_data.get("ok"):
                    print(f"[NotifyAdmin] Message successfully forwarded to Topic {thread_id} for account {account_id}")
                    return
                print(f"[NotifyAdmin] Failed to forward message to Topic {thread_id}: {resp_data}")
                if _topic_send_failed_because_thread_is_stale(resp_data):
                    clear_topic_thread_id(account_id, sender_id, int(notify_chat_id), int(thread_id))
                    recreate_payload = {
                        "chat_id": int(notify_chat_id),
                        "name": f"[{display_account_name}] {sender_display}"
                    }
                    recreated = await asyncio.to_thread(
                        _send_urllib_request_sync,
                        f"https://api.telegram.org/bot{bot_token}/createForumTopic",
                        json.dumps(recreate_payload).encode("utf-8"),
                        {"Content-Type": "application/json"},
                        10
                    )
                    if recreated.get("ok"):
                        new_thread_id = recreated["result"]["message_thread_id"]
                        save_topic_thread_id(account_id, sender_id, int(notify_chat_id), new_thread_id)
                        msg_payload["message_thread_id"] = int(new_thread_id)
                        retry_resp = await asyncio.to_thread(
                            _send_urllib_request_sync,
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json.dumps(msg_payload).encode("utf-8"),
                            {"Content-Type": "application/json"},
                            10
                        )
                        if retry_resp.get("ok"):
                            print(f"[NotifyAdmin] Message forwarded after recreating Topic {new_thread_id} for account {account_id}")
                            return
                        print(f"[NotifyAdmin] Retry after recreating Topic failed: {retry_resp}")
                    else:
                        print(f"[NotifyAdmin] Failed to recreate stale Forum Topic: {recreated}")
            except Exception as msg_exc:
                print(f"[NotifyAdmin] Error forwarding message to Topic: {msg_exc}")

        print(f"[NotifyAdmin] Forum group is configured but forwarding failed; skip deprecated direct DM fallback for account {account_id}")
        return

    # CASE B: Fallback to original Direct Chat / Private DM routing if no notify_chat_id group is configured
    if not telegram_chat_id:
        print(f"[NotifyAdmin] No private telegram_chat_id bound and no Forum Group configured for owner of account {account_id}")
        return

    # Call official Telegram Bot API sendMessage to private admin chat
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    html_text = (
        f"🔔 <b>【托管账号收到新私信】</b>\n\n"
        f"● <b>托管账号</b>: <b>{display_account_name}</b>\n"
        f"● <b>客户</b>: {sender_display_html}\n\n"
        f"💬 <b>消息内容</b>:\n"
        f"<blockquote>{message_text}</blockquote>\n\n"
        f"⚙️ <code>ref:{account_id}:{sender_id}:{message_id}</code>"
    )

    reply_callback = f"reply_dm:{account_id}:{sender_id}:{message_id}:{sender_display}"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✍️ 回复客户", "callback_data": reply_callback},
                {"text": "❌ 忽略", "callback_data": f"ignore_dm:{account_id}"}
            ],
            [
                {"text": "📜 历史上下文", "callback_data": f"view_history:{account_id}:{sender_id}:{sender_display}"}
            ]
        ]
    }

    payload = {
        "chat_id": telegram_chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        resp_data = await asyncio.to_thread(
            _send_urllib_request_sync,
            url,
            data,
            {"Content-Type": "application/json"},
            10
        )
        if resp_data.get("ok"):
            print(f"[NotifyAdmin] Direct Notification sent successfully to admin {telegram_chat_id} for account {account_id}")
        else:
            print(f"[NotifyAdmin] Telegram API returned error: {resp_data}")
    except Exception as exc:
        print(f"[NotifyAdmin] Failed to send HTTP request to Telegram Bot API: {exc}")


def append_private_dm_event(event_data: dict) -> None:
    DM_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DM_EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event_data, ensure_ascii=False) + "\n")

    # 如果是发送出去的消息，或者 notify 标记为 False，则只写入本地 jsonl 缓存，不发送 Bot 通知
    if event_data.get("out") or not event_data.get("notify", True):
        return

    # Trigger real-time Bot notification!
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(async_notify_admin_of_dm(
                account_id=str(event_data.get("account_id")),
                account_label=str(event_data.get("account_label") or event_data.get("account_id")),
                sender_id=int(event_data.get("sender_id")),
                sender_name=str(event_data.get("sender_name")),
                sender_username=str(event_data.get("sender_username")),
                message_text=str(event_data.get("text")),
                message_id=int(event_data.get("message_id") or 0)
            ))
        else:
            loop.run_until_complete(async_notify_admin_of_dm(
                account_id=str(event_data.get("account_id")),
                account_label=str(event_data.get("account_label") or event_data.get("account_id")),
                sender_id=int(event_data.get("sender_id")),
                sender_name=str(event_data.get("sender_name")),
                sender_username=str(event_data.get("sender_username")),
                message_text=str(event_data.get("text")),
                message_id=int(event_data.get("message_id") or 0)
            ))
    except Exception as exc:
        # Fallback to threading if no event loop or not running
        import threading
        t = threading.Thread(target=lambda: asyncio.run(async_notify_admin_of_dm(
            account_id=str(event_data.get("account_id")),
            account_label=str(event_data.get("account_label") or event_data.get("account_id")),
            sender_id=int(event_data.get("sender_id")),
            sender_name=str(event_data.get("sender_name")),
            sender_username=str(event_data.get("sender_username")),
            message_text=str(event_data.get("text")),
            message_id=int(event_data.get("message_id") or 0)
        )))
        t.start()


def read_private_dm_events(account_ids: Optional[set[str]] = None, limit: int = 500) -> list[dict]:
    if not DM_EVENTS_FILE.exists():
        return []
    rows: list[dict] = []
    try:
        with DM_EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                account_id = str(item.get("account_id") or "")
                if account_ids and account_id not in account_ids:
                    continue
                rows.append(item)
    except Exception:
        return []
    return rows[-max(1, limit):]


def register_private_dm_event_listener(client: Any, account_id: str, account_label: str = "", source: str = "runtime") -> None:
    handler_name = f"private_dm_event_handler_{account_id}_{source}"
    for handler, _event in client.list_event_handlers():
        if getattr(handler, "__name__", "") == handler_name:
            return

    @client.on(events.NewMessage(incoming=True))
    async def private_dm_event_handler(event):
        try:
            if not getattr(event, "is_private", False):
                return

            sender = await event.get_sender()
            if not isinstance(sender, types.User):
                return
            if bool(getattr(sender, "bot", False)):
                return
            sender_id = int(getattr(sender, "id", 0) or 0)
            if sender_id <= 0 or sender_id == 777000:
                return

            # --- 自动首问欢迎语回复逻辑（穿透 Telegram 官方云端历史判定） ---
            try:
                is_first_chat = False
                # 检查本地去重缓存
                cache_key = f"{account_id}:{sender_id}"
                if cache_key not in first_chat_notified_set:
                    # 实时拉取 Telegram 云端历史消息（限制2条）
                    history_msgs = await client.get_messages(sender_id, limit=2)
                    cloud_count = len(history_msgs) if history_msgs else 0
                    print(f"[Welcome Check] Account {account_id} -> Sender {sender_id}: Cloud message history count is {cloud_count}")
                    # 如果云端获取到的消息数小于或等于1（即只有当前刚收到的这一条），说明此前在电报云端没有任何聊天记录，是绝对的新客！
                    if cloud_count <= 1:
                        is_first_chat = True

                if is_first_chat:
                    print(f"[Welcome Check] Sender {sender_id} is verified as FIRST-TIME chat. Preparing to send welcome text.")
                    first_chat_notified_set.add(cache_key)

                    # 从数据库中拉取所有启用中的自动回复模板列表，并进行随机选择发送
                    welcome_text = ""
                    try:
                        import sqlite3
                        import random
                        from pathlib import Path
                        db_path = Path(__file__).resolve().parent / "data" / "rosepay.db"
                        if db_path.exists():
                            conn = sqlite3.connect(str(db_path))
                            cursor = conn.cursor()
                            cursor.execute("""
                                CREATE TABLE IF NOT EXISTS bot_auto_replies (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    bot_type TEXT NOT NULL,
                                    reply_text TEXT NOT NULL,
                                    is_enabled INTEGER DEFAULT 1,
                                    created_at TEXT
                                );
                            """)
                            # 读取当前 bot 对应激活的自动回复模板
                            cursor.execute("SELECT reply_text FROM bot_auto_replies WHERE bot_type = ? AND is_enabled = 1;", (account_label.split()[0].lower() if "account_label" in locals() else "ai_bot",))
                            rows = cursor.fetchall()
                            if not rows:
                                # 兼容 fallback 到 ai_bot 类别
                                cursor.execute("SELECT reply_text FROM bot_auto_replies WHERE bot_type = 'ai_bot' AND is_enabled = 1;")
                                rows = cursor.fetchall()
                            if rows:
                                welcome_text = random.choice(rows)[0]
                                print(f"[Welcome] Selected random welcome template from {len(rows)} enabled options.")
                            conn.close()
                    except Exception as db_err:
                        print(f"[Welcome] Failed to query welcome templates from database: {db_err}")

                    if not welcome_text:
                        welcome_text = (
                            "🌹 <b>您好，欢迎咨询 RosePay！</b>\n\n"
                            "⚠️ <b>防骗反诈安全提示</b>：\n"
                            "控制台客服及管理员<b>绝不会主动私聊您</b>，任何主动私聊您的都是骗子，请务必仔细甄别，谨防上当受骗！\n\n"
                            "💬 请在此处说明您的具体业务需求，客服人员看到后会立即进行回复，祝您生活愉快！"
                        )
                    await client.send_message(sender_id, welcome_text, parse_mode="HTML")
                    print(f"[Welcome] Auto sent first-chat welcome message to {sender_id} from account {account_id}.")
            except Exception as welcome_err:
                print(f"[Welcome] Failed to send welcome message: {welcome_err}")

            msg = getattr(event, "message", None)
            msg_id = int(getattr(msg, "id", 0) or 0)
            msg_date = getattr(msg, "date", None)
            timestamp = msg_date.timestamp() if msg_date else time.time()
            append_private_dm_event({
                "account_id": str(account_id),
                "account_label": account_label or str(account_id),
                "source": source,
                "sender_id": sender_id,
                "sender_name": _display_name(sender),
                "sender_username": f"@{sender.username}" if getattr(sender, "username", None) else "",
                "sender_is_bot": bool(getattr(sender, "bot", False)),
                "message_id": msg_id,
                "text": _message_preview(msg),
                "out": False,
                "notify": True,
                "timestamp": timestamp,
                "created_at": time.time(),
            })
            print(f"[{account_id}] Private DM event captured from {sender_id} via {source}.")
        except Exception as exc:
            print(f"[{account_id}] Failed to capture private DM event: {exc}")

    private_dm_event_handler.__name__ = handler_name
