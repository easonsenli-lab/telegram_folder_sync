import os
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import html
import json
import time
import hmac
import hashlib
import secrets
import asyncio
import threading
import subprocess
import datetime
from zoneinfo import ZoneInfo

def get_beijing_time_str() -> str:
    return datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

def is_banned_or_deactivated_error(exc: Exception) -> bool:
    from telethon.errors import UserDeactivatedError, AuthKeyUnregisteredError
    if isinstance(exc, (UserDeactivatedError, AuthKeyUnregisteredError)):
        return True
    err_str = str(exc).lower()
    return any(
        marker in err_str
        for marker in [
            "user_deactivated",
            "auth_key_unregistered",
            "authkeyunregistered",
            "user deactivated",
            "auth key unregistered",
            "session revoked",
            "user_deactivated_ban"
        ]
    )

async def handle_deactivated_or_banned_account(account_id: str, exc: Exception):
    from db import engine, AccountDb, Session
    try:
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account and db_account.is_available:
                db_account.is_available = False
                session.add(db_account)
                session.commit()
                session.refresh(db_account)
                
                # Sync changes to JSON configs
                try:
                    from account_manager import account_config_path, save_json
                    path = account_config_path(db_account.id)
                    save_json(path, db_account.to_dict())
                except Exception as e:
                    print(f"[BanDetector] Failed to sync toggled account to json config: {e}")
                
                # Update memory store status
                set_account_status(
                    account_id,
                    {
                        "is_available": False,
                        "availability_status": "occupied",
                        "is_authorized": False,
                        "auth_status": "unauthorized",
                        "error": f"电报官方账号封禁/注销: {exc}"
                    },
                    source="ban-detector"
                )
                
                # Send HTML notification card via AI Bot
                phone = db_account.id
                account_name = db_account.account_name or "未知账号"
                owner = db_account.owner_username or db_account.created_by or "admin"
                err_type = type(exc).__name__
                err_detail = str(exc)
                bj_time = get_beijing_time_str()
                
                alert_text = (
                    f"⚠️ <b>【防封系统预警】托管账号已被电报官方封禁/拉黑/注销</b>\n\n"
                    f"● <b>账号姓名</b>: <code>{account_name}</code>\n"
                    f"● <b>注册手机</b>: <code>+{phone}</code>\n"
                    f"● <b>账号ID</b>: <code>{account_id}</code>\n"
                    f"● <b>归属管理员</b>: <code>{owner}</code>\n"
                    f"● <b>限制类型</b>: <code>{err_type}</code>\n"
                    f"● <b>详细报错</b>: <code>{err_detail}</code>\n"
                    f"● <b>当前状态</b>: 🚫 <b>已自动将该账号评分状态修改为不可用（is_available=False），并下线 Session</b>\n"
                    f"● <b>发生时间</b>: <code>{bj_time}</code>"
                )
                send_ops_bot_notification(alert_text)
    except Exception as db_err:
        print(f"[BanDetector] Error updating DB/sending notification: {db_err}")

from collections import deque
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Depends, Header, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

# Ensure we can import from the root directory
sys.path.append(str(Path(__file__).resolve().parent))

from sync_folder_groups import (
    build_client,
    check_account_status,
    normalize_title,
)
from static_proxy_pool import (
    STATIC_PROXY_HOSTS,
    ensure_safe_telegram_proxy_config,
    safe_proxy_summary,
    static_proxy_usage_counts,
    telegram_httpx_proxy_url,
    telegram_requests_proxy_kwargs,
)
from account_manager import (
    list_accounts,
    account_config_path,
    build_account_config,
    save_json,
    load_json,
)
from private_dm_events import append_private_dm_event, read_private_dm_events, register_private_dm_event_listener
from telethon import TelegramClient, functions, types, errors, utils
from telethon.errors import SessionPasswordNeededError, UserDeactivatedError

ENABLE_REALTIME_PRIVATE_DM = os.getenv("ROSEPAY_ENABLE_REALTIME_PRIVATE_DM", "1").strip().lower() not in {"0", "false", "off", "no"}
private_relay_enabled = ENABLE_REALTIME_PRIVATE_DM



# Stage 2 Modular Imports
from services.maintenance_service import (
    load_expansion_config,
    save_expansion_config,
    get_company_expansion_task,
    run_business_expansion_loop,
    run_account_cleanup_process
)
from services.scraping_service import (
    sync_groups_status,
    analyze_group_category_with_ai,
    stream_groups_sync,
    classify_group_category_for_import,
    resolve_group,
    get_company_scraper_task,
    get_gemini_api_key,
    save_gemini_api_key,
    get_deepseek_api_key,
    save_deepseek_api_key,
    run_group_scraping_task
)
# --- MODULAR SERVICES IMPORTS ---
from services.shared_state import (
    account_operation_locks,
    active_clients,
    active_clients_last_accessed,
    client_locks,
    active_campaign_tasks,
    active_campaign_schedules,
    active_join_tasks,
    last_join_task_id,
    active_scraper_tasks,
    active_expansion_tasks,
    bg_connect_tasks,
    connection_errors,
    background_tasks,
    registered_listeners,
    active_account_operations,
    active_processes,
    campaign_process_cache,
    spambot_cache,
    account_status_store,
    account_status_subscribers,
    private_dm_subscribers,
    account_task_registry,
    private_unread_cache,
    auto_private_listener_accounts,
    auto_private_listener_cooldowns,
    login_connection_logs,
    captured_login_codes,
    official_messages_store,
    dm_folder_peer_cache,
    DM_FOLDER_NAME,
    TASK_BUSY_PRIORITY,
    scan_campaign_processes_cached,
    find_campaign_process,
    is_campaign_running_for_account,
    get_registered_account_task,
    get_account_busy_status,
    is_account_busy_with_task,
    is_account_executable_for_task,
    filter_executable_accounts_for_task,
    publish_account_status,
    normalize_account_status_patch,
    set_account_status,
    get_cached_auth_state,
    is_placeholder_me_info,
    account_saved_profile_display,
    set_login_status_check_failed,
    publish_task_status_for_accounts,
    register_account_task_usage,
    release_account_task_usage
)

from services.client_manager import (
    get_client,
    _disconnect_client_safely,
    close_active_client_after_config_change,
    get_account_operation_lock,
    get_account_operation_block_reason,
    account_operation_guard,
    clean_idle_clients_loop,
    mark_account_runtime_status,
    validate_telegram_connection_config,
    account_has_session_file
)
import services.client_manager

from services.campaign_service import (
    campaign_worker_task,
    scheduled_campaign_runner,
    launch_campaign_task,
    check_can_speak,
    campaign_now_utc,
    campaign_now_beijing,
    parse_campaign_scheduled_start,
    campaign_task_config,
    campaign_task_schedule_utc,
    campaign_duration_text,
    parse_campaign_account_ids,
    parse_campaign_phones,
    campaign_account_lines,
    send_campaign_start_notification
)

from services.join_service import (
    join_worker_task,
    JoinTaskRequest,
    LogList,
    persistent_task_resume_enabled,
    normalize_loaded_join_task,
    serialize_join_task,
    save_join_task_file,
    save_last_join_task,
    join_group_or_channel_get_entity_only,
    join_group_or_channel,
    try_create_folder_early,
    determine_group_folder_name,
    clean_and_convert_peers_async,
    add_peer_to_folder
)

from services.listener_service import (
    ensure_private_listener_for_account,
    auto_private_listener_loop,
    auto_connect_bg_task,
    account_status_monitor_loop
)

# Register login code listener callback to prevent circular imports
import web_server
services.client_manager.login_code_listener_callback = lambda acc_id, client: web_server.register_login_code_listener(acc_id, client)
app = FastAPI(title="Telegram Control Panel API", version="1.0.0")


def telegram_api_get(url: str, **kwargs):
    kwargs.update(telegram_requests_proxy_kwargs("web_server_bot_api"))
    return requests.get(url, **kwargs)


def telegram_api_post(url: str, **kwargs):
    kwargs.update(telegram_requests_proxy_kwargs("web_server_bot_api"))
    return requests.post(url, **kwargs)


def telegram_httpx_client_kwargs(service_key: str = "web_server_bot_api") -> dict:
    return {"proxy": telegram_httpx_proxy_url(service_key)}

# Initialize SQLite Database tables and run migrations
from db import init_db
init_db()

def get_secret_key() -> str:
    secret_file = Path("data/secret.key")
    if secret_file.exists():
        try:
            return secret_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    key = secrets.token_hex(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(key, encoding="utf-8")
    except Exception:
        pass
    return key

SECRET_KEY = get_secret_key()

# Headshot/Avatar Library folder setup
AVATARS_DIR = Path("data/avatars")
AVATARS_DIR.mkdir(parents=True, exist_ok=True)


def generate_token(username: str, role: str) -> str:
    payload = f"{username}:{role}:{int(time.time())}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"

def verify_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None
        username, role, timestamp_str, signature = parts
        payload = f"{username}:{role}:{timestamp_str}"
        expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        # Expiry 24 hours
        if time.time() - int(timestamp_str) > 86400:
            return None
        return {"username": username, "role": role}
    except Exception:
        return None

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或 Token 无效")
    token = authorization.split(" ")[1]
    user_payload = verify_token(token)
    if not user_payload:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    from db import engine, AdminDb, Session, select
    with Session(engine) as session:
        db_user = session.exec(select(AdminDb).where(AdminDb.username == user_payload["username"])).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return {
            "username": db_user.username,
            "role": db_user.role,
            "company": db_user.company or "admin"
        }

async def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="没有管理员权限，拒绝访问")
    return user



def check_account_company(account_id: str, user: dict):
    from db import engine, AccountDb, AdminDb, Session, select
    with Session(engine) as session:
        db_acc = session.get(AccountDb, account_id)
        if not db_acc:
            raise HTTPException(status_code=404, detail="Account not found")
        if user["role"] != "admin":
            owner_company = ""
            if db_acc.owner_username:
                owner_user = session.exec(select(AdminDb).where(AdminDb.username == db_acc.owner_username)).first()
                owner_company = owner_user.company or "admin" if owner_user else ""
            if (
                db_acc.owner_username != user["username"]
                and db_acc.created_by != user["username"]
                and db_acc.company != user["company"]
                and owner_company != user["company"]
            ):
                raise HTTPException(status_code=403, detail="没有权限访问此账号")
        return db_acc

def check_account_company_scope(account_id: str, user: dict):
    """Lightweight pre-check for runtime guards; endpoint-specific checks still run inside handlers."""
    from db import engine, AccountDb, AdminDb, Session, select
    with Session(engine) as session:
        db_acc = session.get(AccountDb, account_id)
        if not db_acc:
            raise HTTPException(status_code=404, detail="Account not found")
        if user["role"] == "admin" or user["username"] in ("eason", "admin") or user["company"] == "admin":
            return db_acc
        owner_company = ""
        if db_acc.owner_username:
            owner_user = session.exec(select(AdminDb).where(AdminDb.username == db_acc.owner_username)).first()
            owner_company = owner_user.company or "admin" if owner_user else ""
        if (
            db_acc.owner_username != user["username"]
            and db_acc.created_by != user["username"]
            and db_acc.company != user["company"]
            and owner_company != user["company"]
        ):
            raise HTTPException(status_code=403, detail="没有权限访问此账号")
        return db_acc

def query_allowed_accounts(session, user):
    from db import AccountDb, AdminDb, select
    from sqlmodel import or_
    if user["role"] == "admin":
        return select(AccountDb)
    else:
        same_company_users = session.exec(select(AdminDb.username).where(AdminDb.company == user["company"])).all()
        return select(AccountDb).where(
            or_(
                AccountDb.owner_username == user["username"],
                AccountDb.owner_username.in_(same_company_users),
                AccountDb.created_by == user["username"],
                AccountDb.company == user["company"],
            )
        )

def query_accounts_for_view_scope(session, user, scope: str = "mine"):
    from db import AccountDb, select
    from sqlmodel import and_, or_

    normalized_scope = (scope or "mine").strip().lower()
    if normalized_scope not in {"mine", "all"}:
        normalized_scope = "mine"

    if normalized_scope == "all":
        if user["role"] == "admin":
            return select(AccountDb)
        from db import AdminDb
        same_company_users = session.exec(select(AdminDb.username).where(AdminDb.company == user["company"])).all()
        return select(AccountDb).where(
            or_(
                AccountDb.company == user["company"],
                AccountDb.owner_username == user["username"],
                AccountDb.owner_username.in_(same_company_users),
                and_(
                    or_(AccountDb.owner_username == None, AccountDb.owner_username == ""),
                    AccountDb.created_by == user["username"],
                ),
            )
        )

    # "Mine" means accounts explicitly assigned to the current user. For old
    # records without owner_username, created_by is treated as the owner fallback.
    return select(AccountDb).where(
        or_(
            AccountDb.owner_username == user["username"],
            and_(
                or_(AccountDb.owner_username == None, AccountDb.owner_username == ""),
                AccountDb.created_by == user["username"],
            ),
        )
    )

def sync_db_and_files():
    from db import engine, AccountDb, Session, select
    from account_manager import account_config_path, save_json, ACCOUNTS_DIR, load_json

    ACCOUNTS_DIR.mkdir(exist_ok=True)

    with Session(engine) as session:
        db_accounts = session.exec(select(AccountDb)).all()
        db_account_ids = {acc.id for acc in db_accounts}

        for acc in db_accounts:
            path = account_config_path(acc.id)
            save_json(path, acc.to_dict())

        for json_file in ACCOUNTS_DIR.glob("*.json"):
            account_id = json_file.stem
            if account_id not in db_account_ids:
                try:
                    data = load_json(json_file)
                    db_acc = AccountDb.from_dict(account_id, data)
                    session.add(db_acc)
                    session.commit()
                    print(f"Synced account '{account_id}' from disk to DB.")
                except Exception as e:
                    print(f"Failed to sync manual account '{account_id}': {e}")

sync_db_and_files()

# Enable CORS for local development (restrict allowed origins for security)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    started_at = time.time()
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Server"] = "RosePay-Secure-Server"
    elapsed_ms = int((time.time() - started_at) * 1000)
    if elapsed_ms >= 500 or request.url.path in {"/api/accounts", "/api/accounts/private-unread-summary"} or "private-dialogs" in request.url.path:
        print(f"[HTTP {elapsed_ms}ms] {request.method} {request.url.path}")
    return response


# Active Telethon clients in memory: {account_id: TelegramClient}
ALLOW_DIRECT_TELEGRAM_CONNECTIONS = os.environ.get("ROSEPAY_ALLOW_DIRECT_TELEGRAM", "").lower() in {"1", "true", "yes"}


def account_api_operation(operation: str, *, label: str = "", block_task_busy: bool = True):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            account_id = kwargs.get("account_id")
            if not account_id:
                return await func(*args, **kwargs)
            user = kwargs.get("user") or kwargs.get("admin_user")
            if user:
                check_account_company_scope(str(account_id), user)
            async with account_operation_guard(str(account_id), operation, label=label or operation, block_task_busy=block_task_busy):
                return await func(*args, **kwargs)
        return wrapper
    return decorator

private_unread_refreshing: set[str] = set()
PRIVATE_UNREAD_CACHE_TTL_SECONDS = 8
PRIVATE_DM_ACK_FILE = Path("data/private_dm_event_ack.json")
PRIVATE_SENDER_CACHE_FILE = Path("data/private_sender_cache.json")
PRIVATE_WELCOME_SENT_FILE = Path("data/private_welcome_sent.json")
pending_private_sends: Dict[str, deque] = {}
private_send_queue_locks: Dict[str, asyncio.Lock] = {}
AUTO_PRIVATE_LISTENER_STARTUP_DELAY_SECONDS = 8
AUTO_PRIVATE_LISTENER_INTERVAL_SECONDS = 60
AUTO_PRIVATE_LISTENER_CONNECT_GAP_SECONDS = 4
AUTO_PRIVATE_LISTENER_FAILURE_COOLDOWN_SECONDS = 300
PRIVATE_LISTENER_TRANSPORT_429_COOLDOWN_SECONDS = 900


def is_telegram_transport_rate_error(exc: Exception) -> bool:
    err = str(exc)
    return (
        "HTTP code 429" in err
        or "Invalid response buffer" in err
        or "FloodWait" in err
        or "A wait of" in err
    )


def mark_private_listener_cooldown(account_id: str, exc: Exception, context: str = "private-listener") -> None:
    wait_time = getattr(exc, "seconds", None)
    if not wait_time:
        wait_time = PRIVATE_LISTENER_TRANSPORT_429_COOLDOWN_SECONDS if is_telegram_transport_rate_error(exc) else AUTO_PRIVATE_LISTENER_FAILURE_COOLDOWN_SECONDS
    wait_time = max(60, int(wait_time))
    auto_private_listener_cooldowns[account_id] = time.time() + wait_time
    auto_private_listener_accounts.discard(account_id)
    set_account_status(
        account_id,
        {
            "private_listener": False,
            "private_listener_source": None,
            "last_error": f"{context} 进入冷却 {wait_time} 秒: {exc}",
        },
        source="private-listener-cooldown",
    )
    print(f"[PrivateListener] {account_id} cooldown {wait_time}s after {context}: {exc}")


def load_private_dm_ack() -> Dict[str, float]:
    if not PRIVATE_DM_ACK_FILE.exists():
        return {}
    try:
        raw = load_json(PRIVATE_DM_ACK_FILE)
        return {str(k): float(v or 0) for k, v in raw.items()}
    except Exception:
        return {}


def save_private_dm_ack(data: Dict[str, float]) -> None:
    try:
        PRIVATE_DM_ACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_json(PRIVATE_DM_ACK_FILE, data)
    except Exception as exc:
        print(f"Failed to save private DM ack file: {exc}")


private_dm_event_ack: Dict[str, float] = load_private_dm_ack()


def load_private_sender_cache() -> Dict[str, dict]:
    if not PRIVATE_SENDER_CACHE_FILE.exists():
        return {}
    try:
        raw = load_json(PRIVATE_SENDER_CACHE_FILE)
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_private_sender_cache() -> None:
    try:
        PRIVATE_SENDER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_json(PRIVATE_SENDER_CACHE_FILE, private_sender_cache)
    except Exception as exc:
        print(f"Failed to save private sender cache: {exc}")


def private_sender_cache_key(sender_id: Any) -> str:
    return str(sender_id or "").strip()


def get_private_sender_cache(sender_id: Any) -> Optional[dict]:
    key = private_sender_cache_key(sender_id)
    if not key:
        return None
    item = private_sender_cache.get(key)
    return item if isinstance(item, dict) else None


def cache_private_sender_info(account_id: str, sender_id: int, sender_name: str, sender_username: str = "", sender_is_bot: bool = False) -> None:
    key = private_sender_cache_key(sender_id)
    if not key:
        return
    sender_name = (sender_name or "").strip() or key
    sender_username = (sender_username or "").strip()
    if sender_name == key and not sender_username:
        return
    private_sender_cache[key] = {
        "sender_id": int(sender_id),
        "sender_name": sender_name,
        "sender_username": sender_username,
        "sender_is_bot": bool(sender_is_bot),
        "first_seen_account_id": str(account_id),
        "updated_at": time.time(),
    }
    save_private_sender_cache()


def cache_private_sender_entity(account_id: str, sender) -> None:
    if sender is None:
        return
    sender_id = int(getattr(sender, "id", 0) or 0)
    if sender_id <= 0:
        return
    cache_private_sender_info(
        account_id,
        sender_id,
        private_user_display_name(sender),
        f"@{sender.username}" if getattr(sender, "username", None) else "",
        bool(getattr(sender, "bot", False)),
    )


def load_private_welcome_sent() -> Dict[str, float]:
    if not PRIVATE_WELCOME_SENT_FILE.exists():
        return {}
    try:
        raw = load_json(PRIVATE_WELCOME_SENT_FILE)
        return {str(k): float(v or 0) for k, v in raw.items()} if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_private_welcome_sent() -> None:
    try:
        PRIVATE_WELCOME_SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_json(PRIVATE_WELCOME_SENT_FILE, private_welcome_sent)
    except Exception as exc:
        print(f"Failed to save private welcome sent file: {exc}")


def private_welcome_key(account_id: str, sender_id: Any) -> str:
    return f"{account_id}:{sender_id}"


def has_private_welcome_sent(account_id: str, sender_id: Any) -> bool:
    return private_welcome_key(str(account_id), sender_id) in private_welcome_sent


def mark_private_welcome_sent(account_id: str, sender_id: Any) -> None:
    private_welcome_sent[private_welcome_key(str(account_id), sender_id)] = time.time()
    save_private_welcome_sent()


private_sender_cache: Dict[str, dict] = load_private_sender_cache()
private_welcome_sent: Dict[str, float] = load_private_welcome_sent()


def private_dm_event_key(event: dict) -> str:
    account_id = str(event.get("account_id") or "")
    sender_id = str(event.get("sender_id") or "")
    message_id = str(event.get("message_id") or "")
    if account_id and sender_id and message_id and message_id != "0":
        return f"{account_id}:{sender_id}:{message_id}"
    return f"{account_id}:{sender_id}:{event.get('timestamp') or event.get('created_at') or ''}:{event.get('text') or ''}"


def merge_private_dm_event_into_cache(event: dict) -> None:
    account_id = str(event.get("account_id") or "")
    sender_id = str(event.get("sender_id") or "")
    if not account_id:
        return
    cached = private_unread_cache.get(account_id) or {
        "unread_dialogs": 0,
        "unread_messages": 0,
        "error": None,
        "updated_at": time.time(),
    }
    recent_senders = set(cached.get("_event_sender_ids") or [])
    already_seen = private_dm_event_key(event) in set(cached.get("_event_keys") or [])
    event_keys = list(cached.get("_event_keys") or [])
    if not already_seen:
        event_keys.append(private_dm_event_key(event))
        event_keys = event_keys[-200:]
        cached["unread_messages"] = int(cached.get("unread_messages") or 0) + 1
        if sender_id and sender_id not in recent_senders:
            recent_senders.add(sender_id)
            cached["unread_dialogs"] = int(cached.get("unread_dialogs") or 0) + 1
    cached["_event_sender_ids"] = list(recent_senders)[-200:]
    cached["_event_keys"] = event_keys
    cached["external_unread_messages"] = int(cached.get("external_unread_messages") or cached.get("unread_messages") or 0)
    cached["external_unread_dialogs"] = int(cached.get("external_unread_dialogs") or cached.get("unread_dialogs") or 0)
    cached["last_private_event"] = event
    cached["updated_at"] = time.time()
    cached["loading"] = False
    cached["stale"] = False
    private_unread_cache[account_id] = cached


def publish_private_dm_event(event: dict) -> None:
    if bool(event.get("out", False)) or not bool(event.get("notify", False)):
        return
    merge_private_dm_event_into_cache(event)
    payload = json.dumps({"type": "private_dm", "event": event}, ensure_ascii=False)
    for queue in list(private_dm_subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(payload)
            except Exception:
                pass


# Active login states: {account_id: {"phone": str, "phone_code_hash": str}}
login_states: Dict[str, Dict[str, str]] = {}

# Active campaign subprocesses: {account_id: subprocess.Popen}

OPS_NOTIFY_DEDUP_FILE = Path("data/ops_notify_dedup.json")


def load_env_file_values(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as exc:
        print(f"[OpsNotify] Failed to read env file {path}: {exc}")
    return values


def ai_bot_workspace() -> Path:
    configured = os.getenv("ROSEPAY_AI_BOT_WORKSPACE", "").strip()
    if configured:
        return Path(configured)
    linux_bot_path = Path("/opt/rosepay-telegram-bot")
    if linux_bot_path.exists():
        return linux_bot_path
    return Path("E:/telegram_bot_workspace")


def get_ops_notify_bot_token() -> str:
    token = os.getenv("ROSEPAY_OPS_BOT_TOKEN", "").strip() or os.getenv("BOT_TOKEN", "").strip()
    if token:
        return token
    env_values = load_env_file_values(ai_bot_workspace() / ".env")
    return env_values.get("BOT_TOKEN", "").strip()


def parse_chat_id_list(raw: Any) -> List[int]:
    ids: List[int] = []
    if isinstance(raw, str):
        parts = re.split(r"[,;\s]+", raw)
    elif isinstance(raw, list):
        parts = raw
    else:
        parts = []
    for item in parts:
        try:
            text = str(item).strip()
            if text:
                ids.append(int(text))
        except Exception:
            continue
    return list(dict.fromkeys(ids))


def get_ops_notify_chat_ids() -> List[int]:
    env_values = load_env_file_values(ai_bot_workspace() / ".env")
    chat_ids = parse_chat_id_list(os.getenv("ROSEPAY_OPS_NOTIFY_CHAT_IDS", ""))
    chat_ids += parse_chat_id_list(env_values.get("ROSEPAY_OPS_NOTIFY_CHAT_IDS", ""))
    chat_ids += parse_chat_id_list(env_values.get("OPS_NOTIFY_CHAT_IDS", ""))
    notify_path = ai_bot_workspace() / "notify_config.json"
    try:
        config = load_json(notify_path)
        chat_ids += parse_chat_id_list(config.get("ops_notify_chat_ids", []))
        notify_chat_id = config.get("notify_chat_id")
        if notify_chat_id:
            chat_ids += parse_chat_id_list([notify_chat_id])
    except Exception as exc:
        print(f"[OpsNotify] Failed to read AI bot notify config: {exc}")
    return list(dict.fromkeys(chat_ids))


def ops_events_path() -> Path:
    return ai_bot_workspace() / "data" / "ops_events.json"


def ops_users_path() -> Path:
    return ai_bot_workspace() / "data" / "ops_users.json"


def html_line(label: str, value: Any) -> str:
    return f"<b>{html.escape(label)}:</b> {html.escape(str(value if value is not None else ''))}"


def get_user_notify_label(username: str) -> str:
    username = str(username or "").strip()
    if not username:
        return "未设置"
    try:
        from db import engine, AdminDb, Session, select
        with Session(engine) as session:
            admin = session.exec(select(AdminDb).where(AdminDb.username == username)).first()
            contact = (getattr(admin, "telegram_contact", "") or "").strip() if admin else ""
            if contact:
                return f"{username} ({contact})"
    except Exception:
        pass
    return username


def get_user_telegram_contact(username: str) -> str:
    username = str(username or "").strip()
    if not username:
        return ""
    try:
        from db import engine, AdminDb, Session, select
        with Session(engine) as session:
            admin = session.exec(select(AdminDb).where(AdminDb.username == username)).first()
            return (getattr(admin, "telegram_contact", "") or "").strip() if admin else ""
    except Exception:
        return ""


def get_ops_target_mention(username: str) -> str:
    contact = get_user_telegram_contact(username)
    return contact if contact.startswith("@") else f"@{username}"


def get_registered_ops_user_id(username: str) -> Optional[int]:
    contact = get_user_telegram_contact(username).strip()
    candidates = []
    if contact:
        candidates.extend([contact.lower(), contact.lstrip("@").lower()])
    username = str(username or "").strip()
    if username:
        candidates.extend([username.lower(), f"@{username.lower()}"])
    try:
        path = ops_users_path()
        if not path.exists():
            return None
        data = load_json(path)
        users = data.get("users", {}) if isinstance(data, dict) else {}
        for key in candidates:
            item = users.get(key)
            if not item:
                continue
            user_id = int(item.get("user_id") or 0)
            if user_id:
                return user_id
    except Exception as exc:
        print(f"[OpsNotify] Failed to read registered bot users: {exc}")
    try:
        path = ops_events_path()
        if not path.exists():
            return None
        data = load_json(path)
        events = data.get("events", {}) if isinstance(data, dict) else {}
        matches = []
        for event in events.values():
            if str(event.get("owner_username") or "").strip().lower() != username.lower():
                continue
            registered_user_id = int(event.get("registered_user_id") or 0)
            if not registered_user_id:
                continue
            matches.append((float(event.get("created_at", 0) or 0), registered_user_id))
        if matches:
            matches.sort(reverse=True)
            return matches[0][1]
    except Exception as exc:
        print(f"[OpsNotify] Failed to read registered ops events: {exc}")
    return None


def get_account_notify_label(account_id: str) -> str:
    try:
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            acc = session.get(AccountDb, str(account_id))
            if acc:
                name = acc.account_name or str(account_id)
                owner = acc.owner_username or acc.created_by or ""
                return f"{name} / +{acc.id} / 归属 {get_user_notify_label(owner)}"
    except Exception:
        pass
    return f"+{account_id}"


def ops_event_time() -> str:
    return get_beijing_time_str()


def should_send_ops_event(key: str, cooldown_seconds: int = 300) -> bool:
    if not key:
        return True
    try:
        data = load_json(OPS_NOTIFY_DEDUP_FILE) if OPS_NOTIFY_DEDUP_FILE.exists() else {}
        now = time.time()
        last = float(data.get(key, 0) or 0)
        if now - last < cooldown_seconds:
            return False
        data[key] = now
        OPS_NOTIFY_DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_json(OPS_NOTIFY_DEDUP_FILE, data)
    except Exception as exc:
        print(f"[OpsNotify] Dedup failed: {exc}")
    return True


def send_ops_bot_notification(text: str, dedup_key: str = "", cooldown_seconds: int = 0) -> None:
    if dedup_key and cooldown_seconds > 0 and not should_send_ops_event(dedup_key, cooldown_seconds):
        return
    token = get_ops_notify_bot_token()
    chat_ids = get_ops_notify_chat_ids()
    if not token or not chat_ids:
        print("[OpsNotify] Skip: missing AI bot token or notify chat id. Use /set_notify_group in the AI bot group.")
        return

    def worker():
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for chat_id in chat_ids:
            try:
                resp = telegram_api_post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=8,
                )
                if not resp.ok:
                    print(f"[OpsNotify] sendMessage failed chat={chat_id}: {resp.status_code} {resp.text[:200]}")
            except Exception as exc:
                print(f"[OpsNotify] sendMessage exception chat={chat_id}: {exc}")

    threading.Thread(target=worker, daemon=True).start()


def save_ops_event(event: dict) -> str:
    event_id = event.get("id") or secrets.token_hex(8)
    event = {**event, "id": event_id, "created_at": time.time()}
    path = ops_events_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = load_json(path) if path.exists() else {"events": {}}
        data.setdefault("events", {})[event_id] = event
        # Keep the file bounded.
        events = data.get("events", {})
        if len(events) > 500:
            sorted_items = sorted(events.items(), key=lambda kv: float(kv[1].get("created_at", 0) or 0))
            data["events"] = dict(sorted_items[-500:])
        save_json(path, data)
    except Exception as exc:
        print(f"[OpsNotify] Failed to save ops event: {exc}")
    return event_id


def format_ops_event_detail_html(event: dict) -> str:
    summary = event.get("summary") or {}
    event_type = event.get("type")
    title = "📦 <b>加群任务详情</b>" if event_type == "join" else "📣 <b>广告轰炸任务详情</b>"
    lines = [
        title,
        "",
        "👤 <b>任务信息</b>",
        f"• <b>任务ID:</b> <code>{html.escape(str(event.get('task_id') or ''))}</code>",
        f"• <b>状态:</b> {html.escape(str(event.get('status') or ''))}",
        f"• <b>归属用户:</b> {html.escape(get_user_notify_label(event.get('owner_username') or ''))}",
        f"• <b>公司:</b> {html.escape(str(event.get('company') or ''))}",
    ]
    if event_type == "join":
        lines.extend([
            "",
            "📊 <b>执行范围</b>",
            f"• <b>账号个数:</b> {html.escape(str(summary.get('account_count', 0)))}",
            f"• <b>目标群组:</b> {html.escape(str(summary.get('target_groups', 0)))}",
            f"• <b>排重个数:</b> {html.escape(str(summary.get('dedup_skipped', 0)))}",
            f"• <b>排重后待处理:</b> {html.escape(str(summary.get('todo_total', summary.get('total', 0))))}",
            "",
            "✅ <b>结果统计</b>",
            f"• <b>总处理:</b> {html.escape(str(summary.get('total', 0)))}",
            f"• <b>成功/已在群:</b> {html.escape(str(summary.get('success', 0)))}",
            f"• <b>失败:</b> {html.escape(str(summary.get('failed', 0)))}",
            f"• <b>失效群组:</b> {html.escape(str(summary.get('invalid', 0)))}",
            f"• <b>超时:</b> {html.escape(str(summary.get('timeout', 0)))}",
        ])
        invalid_groups = event.get("invalid_groups") or []
        if invalid_groups:
            lines.extend(["", "🗑 <b>失效群组预览:</b>"])
            for item in invalid_groups[:20]:
                title = item.get("title") or item.get("link") or item.get("id") or ""
                lines.append(f"• {html.escape(str(title))} ({html.escape(str(item.get('id') or ''))})")
            if len(invalid_groups) > 20:
                lines.append(f"• ... +{len(invalid_groups) - 20}")
    elif event_type == "campaign":
        lines.extend([
            "",
            "📊 <b>执行范围</b>",
            f"• <b>轰炸轮数:</b> {html.escape(str(summary.get('rounds', 0)))}",
            f"• <b>目标群数:</b> {html.escape(str(summary.get('groups', 0)))}",
            f"• <b>发送记录:</b> {html.escape(str(summary.get('log_rows', 0)))}",
            "",
            "✅ <b>结果统计</b>",
            f"• <b>成功:</b> {html.escape(str(summary.get('success', 0)))}",
            f"• <b>失败:</b> {html.escape(str(summary.get('failed', 0)))}",
            f"• <b>每轮平均成功率:</b> {html.escape(str(summary.get('avg_success_rate', 0)))}%",
            f"• <b>每轮平均失败率:</b> {html.escape(str(summary.get('avg_failed_rate', 0)))}%",
        ])
    account_labels = event.get("account_labels") or []
    if account_labels:
        lines.extend(["", "📱 <b>执行账号</b>"])
        for label in account_labels[:10]:
            lines.append(f"• {html.escape(str(label))}")
        if len(account_labels) > 10:
            lines.append(f"• ... +{len(account_labels) - 10}")
    lines.extend(["", html_line("时间", ops_event_time())])
    return "\n".join(lines)


def get_ops_bot_username(token: str) -> str:
    try:
        resp = telegram_api_get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        if not resp.ok:
            print(f"[OpsNotify] getMe failed: {resp.status_code} {resp.text[:200]}")
            return ""
        data = resp.json()
        return str((data.get("result") or {}).get("username") or "").strip()
    except Exception as exc:
        print(f"[OpsNotify] getMe exception: {exc}")
        return ""


def format_ops_group_entry_html(event: dict) -> str:
    event_type = event.get("type")
    task_label = "加群任务" if event_type == "join" else "广告轰炸任务"
    owner_username = str(event.get("owner_username") or "")
    target_mention = get_ops_target_mention(owner_username)
    summary = event.get("summary") or {}
    lines = [
        "📬 <b>后台任务已完成</b>",
        f"{html.escape(target_mention)} 你在后台有一个任务结束了。",
        html_line("任务类型", task_label),
        html_line("状态", event.get("status") or ""),
    ]
    if event_type == "join":
        lines.extend([
            html_line("账号个数", summary.get("account_count", 0)),
            html_line("目标群组", summary.get("target_groups", 0)),
            html_line("排重个数", summary.get("dedup_skipped", 0)),
            html_line("成功/已在群", summary.get("success", 0)),
            html_line("失败", summary.get("failed", 0)),
            html_line("失效群组", summary.get("invalid", 0)),
        ])
    elif event_type == "campaign":
        lines.extend([
            html_line("轰炸轮数", summary.get("rounds", 0)),
            html_line("目标群数", summary.get("groups", 0)),
            html_line("成功", summary.get("success", 0)),
            html_line("失败", summary.get("failed", 0)),
        ])
    lines.extend(["", "👇 点击下方按钮打开 bot 查看日志。"])
    return "\n".join(lines)


def send_ops_bot_notification_with_buttons(text: str, event: dict, buttons: List[List[dict]]) -> None:
    event_id = save_ops_event(event)
    token = get_ops_notify_bot_token()
    chat_ids = get_ops_notify_chat_ids()
    if not token or not chat_ids:
        print("[OpsNotify] Skip button notification: missing AI bot token or notify chat id.")
        return
    reply_markup = {
        "inline_keyboard": [
            [
                {**button, "callback_data": button["callback_data"].format(event_id=event_id)}
                for button in row
            ]
            for row in buttons
        ]
    }
    direct_user_id = get_registered_ops_user_id(str(event.get("owner_username") or ""))
    direct_buttons = [
        [
            {**button, "callback_data": button["callback_data"].format(event_id=event_id)}
            for button in row
            if not str(button.get("callback_data", "")).startswith("opslog:")
        ]
        for row in buttons
    ]
    direct_buttons = [row for row in direct_buttons if row]

    def worker():
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        if direct_user_id:
            payload = {
                "chat_id": direct_user_id,
                "text": format_ops_event_detail_html(event),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if direct_buttons:
                payload["reply_markup"] = {"inline_keyboard": direct_buttons}
            try:
                resp = telegram_api_post(url, json=payload, timeout=8)
                if resp.ok:
                    return
                print(f"[OpsNotify] direct send failed user={direct_user_id}: {resp.status_code} {resp.text[:200]}")
            except Exception as exc:
                print(f"[OpsNotify] direct send exception user={direct_user_id}: {exc}")
        bot_username = get_ops_bot_username(token)
        group_reply_markup = reply_markup
        group_text = text
        if bot_username:
            group_text = format_ops_group_entry_html(event)
            group_reply_markup = {
                "inline_keyboard": [[
                    {
                        "text": "打开 bot 查看日志",
                        "url": f"https://t.me/{bot_username}?start=opslog_{event_id}",
                    }
                ]]
            }
        for chat_id in chat_ids:
            try:
                resp = telegram_api_post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": group_text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                        "reply_markup": group_reply_markup,
                    },
                    timeout=8,
                )
                if not resp.ok:
                    print(f"[OpsNotify] sendMessage buttons failed chat={chat_id}: {resp.status_code} {resp.text[:200]}")
            except Exception as exc:
                print(f"[OpsNotify] sendMessage buttons exception chat={chat_id}: {exc}")

    threading.Thread(target=worker, daemon=True).start()


# Scraper default page ID
DEFAULT_SCRAPER_PAGE_ID = "aca5195e-d583-410a-9781-d51351c30083"

class AccountCreateRequest(BaseModel):
    name: str

class ProxyConfig(BaseModel):
    enabled: bool
    type: str
    host: str
    port: int
    username: str = ""
    password: str = ""

class AccountConfigRequest(BaseModel):
    account_name: str
    folder_name: str
    proxy: ProxyConfig
    owner_username: Optional[str] = None

class LoginStartRequest(BaseModel):
    account_id: str
    phone: str
    page_id: Optional[str] = None

class LoginSubmitRequest(BaseModel):
    account_id: str
    code: str
    pass2fa: Optional[str] = None

class QuickImportRequest(BaseModel):
    import_string: str

class LocalCredentialsRequest(BaseModel):
    pass2fa: Optional[str] = None
    page_id: Optional[str] = None

class CampaignStartRequest(BaseModel):
    account_id: str
    folder_name: str
    message_text: str
    task_interval_minutes: int
    group_interval_seconds: int
    is_strategy: Optional[bool] = False

class CampaignGroupInfo(BaseModel):
    chat_id: int
    title: str
    username: Optional[str] = None
    group_type: Optional[str] = None

class GroupCategoryUpdateRequest(BaseModel):
    id: str
    category: str

class MessageCampaignTaskRequest(BaseModel):
    account_id: str
    account_ids: Optional[List[str]] = None
    max_cycles: int  # 0 = infinite
    round_interval_minutes: int
    group_interval_seconds: int
    is_safety: bool
    multi_account_safety_enabled: bool = False
    strategy_enabled: bool = False
    message: str
    target_groups: List[CampaignGroupInfo]
    scheduled_start_at: Optional[str] = None

class ProfileNameRequest(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    about: Optional[str] = None

class ProfileAboutRequest(BaseModel):
    about: str

class ProfileUsernameRequest(BaseModel):
    username: str

class ProfileIdentityRequest(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    about: Optional[str] = None

class KickDeviceRequest(BaseModel):
    hash: str

class PrivateMessageSendRequest(BaseModel):
    message: str

class PrivateListenerStartRequest(BaseModel):
    account_ids: Optional[List[str]] = None

class BatchUpdateProfileRequest(BaseModel):
    account_ids: List[str]
    last_name: Optional[str] = ""
    virtual_modify: Optional[bool] = True
    custom_first_name: Optional[str] = ""
    custom_username_prefix: Optional[str] = ""
    about: Optional[str] = None
    only_about: Optional[bool] = False

class Update2faRequest(BaseModel):
    current_password: Optional[str] = ""
    new_password: str
    hint: Optional[str] = ""

class BatchUpdate2faRequest(BaseModel):
    account_ids: List[str]
    current_password: Optional[str] = ""
    new_password_mode: str  # "same" or "auto"
    custom_new_password: Optional[str] = ""
    hint: Optional[str] = ""

class CreateFolderRequest(BaseModel):
    title: str
    categories: List[str]

class GroupModel(BaseModel):
    id: str
    title: str
    username: str
    type: str
    enabled: bool
    memberCount: int
    category: str
    price: float = 0.0
    quality_score: int = 0
    relevance_score: int = 0
    activity_score: int = 0
    engagement_score: int = 0
    bot_rules_summary: Optional[str] = None
    bot_rules_raw_logs: Optional[str] = None

class GroupToggleRequest(BaseModel):
    id: str
    enabled: bool

class GroupResolveRequest(BaseModel):
    link: str
    category: Optional[str] = None
    price: Optional[float] = 0.0

class BatchDeleteRequest(BaseModel):
    ids: List[str]

class BatchCategoryRequest(BaseModel):
    ids: List[str]
    category: str

class GroupPriceUpdateRequest(BaseModel):
    id: str
    price: float

class GroupCategoryModel(BaseModel):
    id: Optional[int] = None
    name: str
    company: str

class AddCategoryRequest(BaseModel):
    name: str

class RenameCategoryRequest(BaseModel):
    old_name: str
    new_name: str

class BotStepRequest(BaseModel):
    input_text: str



# InMemory storage for parsed login codes: {account_id: [{"code": str, "timestamp": float, "text": str}]}
captured_login_codes: Dict[str, List[dict]] = {}
official_messages_store: Dict[str, List[dict]] = {}
login_connection_logs: Dict[str, List[str]] = {}
registered_listeners = set()
DM_FOLDER_NAME = "DM"
dm_folder_peer_cache: Dict[str, set[int]] = {}

def add_login_log(account_id: str, message: str):
    import datetime
    try:
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        log_line = f"[{time_str}] {message}"
        if account_id not in login_connection_logs:
            login_connection_logs[account_id] = []
        login_connection_logs[account_id].append(log_line)
        login_connection_logs[account_id] = login_connection_logs[account_id][-20:]
        print(f"[{account_id}] LOG: {message}")
    except Exception as e:
        print(f"Failed to add log: {e}")

def register_login_code_listener(account_id: str, client: TelegramClient):
    from telethon import events

    # Check if already registered
    for handler, event in client.list_event_handlers():
        if getattr(handler, "__name__", "") == "login_code_message_handler":
            return

    @client.on(events.NewMessage(incoming=True))
    async def login_code_message_handler(event):
        try:
            cooldown_until = auto_private_listener_cooldowns.get(account_id, 0)
            if cooldown_until > time.time():
                return
            account_is_busy = is_account_busy_with_task(account_id)
            sender_id = event.sender_id
            is_official = (sender_id == 777000)
            if not is_official and event.message.peer_id:
                is_official = (getattr(event.message.peer_id, "user_id", None) == 777000)

            if is_official:
                text = event.message.message
                if not text:
                    return

                add_login_log(account_id, "监听到新的官方通知消息！")

                import datetime
                msg_date = event.message.date
                if isinstance(msg_date, datetime.datetime):
                    timestamp = msg_date.timestamp()
                else:
                    timestamp = time.time()

                if account_id not in official_messages_store:
                    official_messages_store[account_id] = []

                # Avoid duplicates
                exists = any(m["text"] == text and abs(m["timestamp"] - timestamp) < 5 for m in official_messages_store[account_id])
                if not exists:
                    official_messages_store[account_id].append({
                        "text": text,
                        "timestamp": timestamp
                    })
                    official_messages_store[account_id] = sorted(
                        official_messages_store[account_id],
                        key=lambda x: x["timestamp"],
                        reverse=True
                    )[:5]

                # Match "Login code: 45001" or other patterns
                match = re.search(r"Login code\s*:?\s*(\d+)", text, re.IGNORECASE)
                if not match:
                    match = re.search(r"(?:code|验证码)[:：\s]+(\d+)", text, re.IGNORECASE)
                if not match:
                    match = re.search(r"\b(\d{5,6})\b", text)

                if match:
                    code = match.group(1)
                    if account_id not in captured_login_codes:
                        captured_login_codes[account_id] = []

                    exists_code = any(c["code"] == code and abs(c["timestamp"] - timestamp) < 10 for c in captured_login_codes[account_id])
                    if not exists_code:
                        captured_login_codes[account_id].append({
                            "code": code,
                            "timestamp": timestamp,
                            "text": text
                        })
                        # Keep last 10 codes
                        captured_login_codes[account_id] = captured_login_codes[account_id][-10:]
                        try:
                            print(f"[{account_id}] Captured official login code: {code}")
                        except Exception:
                            pass

            if is_official:
                return

            if not getattr(event, "is_private", False):
                return

            sender_id_int = int(sender_id or 0)
            if sender_id_int <= 0:
                return

            cached_sender = get_private_sender_cache(sender_id_int)
            sender = None
            if cached_sender:
                if bool(cached_sender.get("sender_is_bot", False)):
                    return
                sender_name = str(cached_sender.get("sender_name") or sender_id_int)
                sender_username = str(cached_sender.get("sender_username") or "")
                sender_is_bot = False
            else:
                try:
                    sender = await asyncio.wait_for(event.get_sender(), timeout=8)
                except Exception as sender_exc:
                    if is_telegram_transport_rate_error(sender_exc):
                        mark_private_listener_cooldown(account_id, sender_exc, "get first private sender")
                        return
                    print(f"[PrivateListener] Failed to resolve first sender {sender_id_int} for {account_id}: {sender_exc}")
                    sender = None

                if sender is not None and not isinstance(sender, types.User):
                    return
                if sender is not None and bool(getattr(sender, "bot", False)):
                    cache_private_sender_entity(account_id, sender)
                    return

                sender_name = private_user_display_name(sender) if sender is not None else str(sender_id_int)
                sender_username = f"@{sender.username}" if sender is not None and getattr(sender, "username", None) else ""
                sender_is_bot = bool(getattr(sender, "bot", False)) if sender is not None else False
                if sender is not None:
                    cache_private_sender_entity(account_id, sender)

            try:
                msg = getattr(event, "message", None)
                msg_date = getattr(msg, "date", None)
                private_event = {
                    "account_id": str(account_id),
                    "account_label": str(account_id),
                    "source": "web_server",
                    "sender_id": sender_id_int,
                    "sender_name": sender_name,
                    "sender_username": sender_username,
                    "sender_is_bot": sender_is_bot,
                    "message_id": int(getattr(msg, "id", 0) or 0),
                    "text": message_preview_text(msg),
                    "out": False,
                    "notify": True,
                    "timestamp": msg_date.timestamp() if msg_date else time.time(),
                    "created_at": time.time(),
                }
                append_private_dm_event(private_event)
                publish_private_dm_event(private_event)

                # --- 自动首问欢迎语回复逻辑（穿透 Telegram 官方云端历史判定） ---
                try:
                    cache_key = f"{account_id}:{sender_id_int}"
                    from private_dm_events import first_chat_notified_set
                    if not has_private_welcome_sent(account_id, sender_id_int) and cache_key not in first_chat_notified_set:
                        print(f"[Welcome Check] Sender {sender_id_int} has no local welcome marker. Preparing one-time welcome text.")
                        first_chat_notified_set.add(cache_key)

                        welcome_text = ""
                        try:
                            import sqlite3
                            import random
                            from db import DB_PATH
                            with sqlite3.connect(str(DB_PATH)) as conn:
                                cursor = conn.cursor()
                                # 读取当前 bot 对应激活的自动回复模板
                                cursor.execute("SELECT reply_text FROM bot_auto_replies WHERE bot_type = 'ai_bot' AND is_enabled = 1;")
                                rows = cursor.fetchall()
                                if rows:
                                    welcome_text = random.choice(rows)[0]
                                    print(f"[Welcome] Selected random welcome template from {len(rows)} enabled options.")
                        except Exception as db_err:
                            print(f"[Welcome] Failed to query welcome templates from database: {db_err}")

                        if not welcome_text:
                            welcome_text = (
                                "🌹 <b>Hello! Welcome to RosePay!</b>\n\n"
                                "Please join our group first: https://t.me/RosePayChatGroup\n\n"
                                "⚠️ <b>Anti-Scam & Security Notice</b>:\n"
                                "RosePay customer support and administrators will <b>NEVER private message (DM) you first</b>. "
                                "Anyone who DMs you first is a scammer. Please verify carefully to protect your assets!\n\n"
                                "💬 Please state your specific business needs here. Our support team will get back to you shortly. "
                                "Have a great day!"
                            )
                        welcome_target = sender if sender is not None else sender_id_int
                        await client.send_message(welcome_target, welcome_text, parse_mode="HTML")
                        mark_private_welcome_sent(account_id, sender_id_int)
                        print(f"[Welcome] Auto sent first-chat welcome message to {sender_id_int} from account {account_id}.")
                except RuntimeError as welcome_skip:
                    if str(welcome_skip) != "skip-heavy-private-listener-work-while-account-busy":
                        print(f"[Welcome] Skipped: {welcome_skip}")
                except Exception as welcome_err:
                    try:
                        first_chat_notified_set.discard(cache_key)
                    except Exception:
                        pass
                    if is_telegram_transport_rate_error(welcome_err):
                        mark_private_listener_cooldown(account_id, welcome_err, "welcome private message")
                    print(f"[Welcome] Failed to send welcome message: {welcome_err}")
            except Exception as event_exc:
                if is_telegram_transport_rate_error(event_exc):
                    mark_private_listener_cooldown(account_id, event_exc, "private event handling")
                else:
                    print(f"[PrivateListener] Failed to process private event for {account_id}: {event_exc}")

            if not account_is_busy and sender is not None:
                cache = dm_folder_peer_cache.setdefault(account_id, set())
                if sender_id_int not in cache:
                    try:
                        await add_peer_to_folder(client, sender, DM_FOLDER_NAME)
                        cache.add(sender_id_int)
                        print(f"[{account_id}] Added private dialog {sender_id_int} to {DM_FOLDER_NAME} folder.")
                    except Exception as folder_exc:
                        if is_telegram_transport_rate_error(folder_exc):
                            mark_private_listener_cooldown(account_id, folder_exc, "dm folder sync")
                        else:
                            print(f"[{account_id}] Failed to add private dialog {sender_id_int} to {DM_FOLDER_NAME}: {folder_exc}")

        except Exception as e:
            if is_telegram_transport_rate_error(e):
                mark_private_listener_cooldown(account_id, e, "login/private listener")
            print(f"Error handling login code listener for {account_id}: {e}")

def mark_account_runtime_status(account_id: str, *, is_connected: bool, is_authorized: Optional[bool] = None, me: Optional[str] = None):
    """Keep account-management runtime state aligned with actual Telethon activity."""
    patch = {"is_connected": is_connected}
    if is_connected:
        patch["error"] = None
        patch["last_error"] = None
    cached = spambot_cache.get(account_id)
    if is_authorized is not None:
        patch["is_authorized"] = is_authorized
    if me is not None:
        patch["me"] = me
    else:
        patch["me"] = "已连接" if is_connected else "未登录"
    if cached:
        patch.setdefault("spambot_status", cached.get("status", "unknown"))
        patch.setdefault("spambot_details", cached.get("details", ""))
        patch.setdefault("spambot_time", cached.get("timestamp", None))
    set_account_status(account_id, patch, source="runtime")

async def get_client(account_id: str, ignore_proxy: bool = False) -> TelegramClient:
    """Gets or initializes the Telethon client for an account."""
    active_operation = active_account_operations.get(account_id)
    current_task_id = id(asyncio.current_task()) if asyncio.current_task() else None
    if active_operation and active_operation.get("task_id") != current_task_id:
        raise HTTPException(
            status_code=409,
            detail=f"该账号正在执行操作: {active_operation.get('label') or active_operation.get('operation') or 'active'}，请稍后再试。"
        )

    is_subprocess_campaign_running = account_id in active_processes and active_processes[account_id].poll() is None
    if not is_subprocess_campaign_running:
        is_subprocess_campaign_running = find_campaign_process(account_id) is not None
    if is_subprocess_campaign_running:
        raise HTTPException(
            status_code=400,
            detail="该账号正在后台运行独立广告子进程。为了防止电报 Session 数据库冲突锁死，请先暂停广告进程后再进行此操作。"
        )

    if account_id not in client_locks:
        client_locks[account_id] = asyncio.Lock()

    async with client_locks[account_id]:
        active_clients_last_accessed[account_id] = time.time()
        if account_id in active_clients:
            client = active_clients[account_id]
            cached_ignore = getattr(client, "_is_proxy_ignored", False)
            if cached_ignore != ignore_proxy:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                active_clients.pop(account_id, None)
            else:
                if not client.is_connected():
                    await asyncio.wait_for(client.connect(), timeout=20)
                mark_account_runtime_status(account_id, is_connected=True)
                if account_id not in registered_listeners:
                    try:
                        register_login_code_listener(account_id, client)
                        registered_listeners.add(account_id)
                    except Exception as e:
                        print(f"Failed to register login code listener: {e}")
                return client

        config_path = account_config_path(account_id)
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Account config file not found")

        config = load_json(config_path)
        base_dir = config_path.parent.parent

        if ignore_proxy:
            config = config.copy()
            if "proxy" in config and isinstance(config["proxy"], dict):
                config["proxy"] = config["proxy"].copy()
                config["proxy"]["enabled"] = False

        validate_telegram_connection_config(account_id, config, ignore_proxy=ignore_proxy)

        # Use the builder from sync_folder_groups
        client = await build_client(config, base_dir)
        client._is_proxy_ignored = ignore_proxy
        await asyncio.wait_for(client.connect(), timeout=20)
        active_clients[account_id] = client
        mark_account_runtime_status(account_id, is_connected=True)

        if account_id not in registered_listeners:
            try:
                register_login_code_listener(account_id, client)
                registered_listeners.add(account_id)
            except Exception as e:
                print(f"Failed to register login code listener: {e}")

        return client

class LoginRequest(BaseModel):
    username: str
    password: str

class SetupAdminRequest(BaseModel):
    username: str
    password: str
    company: Optional[str] = "admin"

class CompanyCreateRequest(BaseModel):
    name: str

class CompanyUpdateRequest(BaseModel):
    name: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str # admin or user
    company: Optional[str] = "admin"
    telegram_contact: Optional[str] = ""
    forum_chat_id: Optional[str] = None

def normalize_telegram_contact(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    match = re.fullmatch(r"@([A-Za-z0-9_]{5,32})", raw)
    if not match:
        match = re.fullmatch(r"https://(?:t\.me|telegram\.me)/([A-Za-z0-9_]{5,32})/?", raw, re.IGNORECASE)
    if not match:
        raise HTTPException(status_code=400, detail="电报ID格式错误，请输入 @username 或 https://t.me/username")
    return f"@{match.group(1)}"

def sync_translation_bot_config():
    import json
    import os
    import sqlite3

    json_path = "/opt/rosepay-translate-bot/data/translate_access.json"
    if not os.path.exists(json_path):
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)

        old_allowed_chats = [cid for cid in old_data.get("allowed_chat_ids", [])]
        old_owner_ids = [oid for oid in old_data.get("owner_chat_ids", []) if oid < 0]

        from db import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_chat_id, role FROM bot_authorized_users WHERE bot_type = 'translate_bot' AND is_active = 1;")
        rows = cursor.fetchall()
        conn.close()

        new_allowed_users = []
        new_owner_users = []

        for chat_id_str, role in rows:
            try:
                cid = int(chat_id_str)
                if cid > 0:
                    if role == "admin":
                        new_owner_users.append(cid)
                    else:
                        new_allowed_users.append(cid)
            except ValueError:
                pass

        final_owners = sorted(list(set(old_owner_ids + new_owner_users + [8302461675])))
        final_allowed = sorted(list(set(new_allowed_users)))

        new_data = {
            "allowed_usernames": [],
            "allowed_user_ids": final_allowed,
            "allowed_chat_ids": old_allowed_chats,
            "owner_chat_ids": final_owners
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2)

        os.system("systemctl restart rosepay-translate-bot.service")
    except Exception as exc:
        print("sync_translation_bot_config failed:", exc)

# --- BOT AUTHORIZATIONS & DEEPSEEK MONITOR APIs ---
from pydantic import BaseModel
from typing import Optional

class BotAuthPayload(BaseModel):
    telegram_chat_id: str
    bot_type: str
    telegram_username: Optional[str] = None
    role: str = "employee"
    owner_username: Optional[str] = None
    is_active: int = 1

@app.get("/api/bot/authorizations")
def get_bot_authorizations(user: dict = Depends(get_current_user)):
    from db import BotAuthorizedUserDb, engine
    from sqlmodel import Session, select
    with Session(engine) as session:
        stmt = select(BotAuthorizedUserDb)
        rows = session.exec(stmt).all()
        result = []
        for r in rows:
            display_name = ""
            role_label = r.role
            owner_label = r.owner_username or ""
            acc_status = "unknown"
            is_system_linked = False

            # 优先关联查询 accounts 托管表获取具体账号名称（如 RosePay Frank）与状态
            cursor = session.connection().connection.cursor()
            cursor.execute("SELECT account_name, is_available, owner_username FROM accounts WHERE id = ?", (r.telegram_chat_id,))
            acc_row = cursor.fetchone()
            if acc_row:
                acc_name, is_available, owner = acc_row
                acc_status = "online" if is_available else "offline"
                display_name = acc_name
                role_label = "external"
                is_system_linked = True
                if not owner_label:
                    owner_label = owner or ""
            else:
                # 关联查询 admins 表获取系统账号绑定关系
                cursor.execute("SELECT username, role, telegram_contact FROM admins WHERE telegram_chat_id = ?", (r.telegram_chat_id,))
                admin_row = cursor.fetchone()
                if admin_row:
                    admin_username, admin_role, admin_contact = admin_row
                    display_name = admin_contact if admin_contact else f"@{admin_username}"
                    if admin_username == "eason" or admin_role == "admin":
                        role_label = "admin"
                    else:
                        role_label = "employee"
                    is_system_linked = True

            # 兜底：如果都没有关联上，则使用创建时记录的用户名，但标记 system_linked = False
            if not display_name or display_name.strip() == "":
                display_name = r.telegram_username or ""

            result.append({
                "telegram_chat_id": r.telegram_chat_id,
                "bot_type": r.bot_type,
                "telegram_username": display_name,
                "role": role_label,
                "owner_username": owner_label,
                "approved_at": r.approved_at,
                "approved_by": r.approved_by,
                "is_active": r.is_active,
                "account_status": acc_status,
                "is_system_linked": is_system_linked
            })
        return result


@app.post("/api/bot/authorizations")
def create_or_update_bot_authorization(payload: BotAuthPayload, user: dict = Depends(get_current_user)):
    from db import BotAuthorizedUserDb, engine
    from sqlmodel import Session
    with Session(engine) as session:
        db_auth = session.get(BotAuthorizedUserDb, (payload.telegram_chat_id, payload.bot_type))
        if db_auth:
            db_auth.telegram_username = payload.telegram_username
            db_auth.role = payload.role
            db_auth.owner_username = payload.owner_username
            db_auth.is_active = payload.is_active
        else:
            import datetime
            db_auth = BotAuthorizedUserDb(
                telegram_chat_id=payload.telegram_chat_id,
                bot_type=payload.bot_type,
                telegram_username=payload.telegram_username,
                role=payload.role,
                owner_username=payload.owner_username,
                approved_at=datetime.datetime.now().isoformat(),
                approved_by="console_admin",
                is_active=payload.is_active
            )
        session.add(db_auth)
        session.commit()
        if payload.bot_type == 'translate_bot':
            try:
                sync_translation_bot_config()
            except Exception as ex:
                pass
        return {"status": "success", "message": "Bot 授权信息更新成功"}

@app.delete("/api/bot/authorizations/{telegram_chat_id}/{bot_type}")
def delete_bot_authorization(telegram_chat_id: str, bot_type: str, user: dict = Depends(get_current_user)):
    from db import BotAuthorizedUserDb, engine
    from sqlmodel import Session
    with Session(engine) as session:
        db_auth = session.get(BotAuthorizedUserDb, (telegram_chat_id, bot_type))
        if db_auth:
            session.delete(db_auth)
            session.commit()
            if bot_type == 'translate_bot':
                try:
                    sync_translation_bot_config()
                except Exception as ex:
                    pass
            return {"status": "success", "message": "已成功解除授权"}
        return {"status": "error", "message": "未找到对应的授权记录"}

@app.get("/api/bot/deepseek-balance")
def get_deepseek_balance(user: dict = Depends(get_current_user)):
    import urllib.request
    import json
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        env_paths = [
            Path(__file__).resolve().parent / ".env",
            Path("/opt/rosepay-telegram-bot/.env"),
            Path("/opt/rosepay-translate-bot/.env"),
            Path("E:/telegram_translate_bot_workspace/.env")
        ]
        for p in env_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            if "DEEPSEEK_API_KEY" in line:
                                parts = line.split("=", 1)
                                if len(parts) > 1:
                                    api_key = parts[1].strip().strip('"').strip("'")
                                    break
                except Exception:
                    pass
            if api_key:
                break

    if not api_key:
        return {"error": "未配置 DEEPSEEK_API_KEY 环境变量，无法查询余额"}

    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data)
    except Exception as exc:
        return {"error": f"连接 DeepSeek 官方或接口返回异常: {exc}"}


@app.get("/api/config/global-active-proxies")
def get_global_active_proxies(user: dict = Depends(get_current_user)):
    """Returns a global map of active proxy IPs to prevent allocation conflicts across companies."""
    from db import engine, AccountDb, Session, select
    with Session(engine) as session:
        accounts = session.exec(select(AccountDb).where(AccountDb.proxy_enabled == 1)).all()
        mapping = {}
        for acc in accounts:
            if acc.proxy_host:
                label = f"{acc.account_name or acc.id}"
                if acc.company and acc.company != "admin":
                    label += f" ({acc.company})"
                mapping[acc.proxy_host] = label
        return mapping

@app.get("/api/config/static-proxies")
def get_static_proxy_pool(user: dict = Depends(get_current_user)):
    counts = static_proxy_usage_counts()
    return {
        "hosts": STATIC_PROXY_HOSTS,
        "usage": {host: counts.get(host, 0) for host in STATIC_PROXY_HOSTS},
        "policy": {
            "direct_telegram_blocked": True,
            "when_all_busy": "borrow_least_used",
        },
    }

@app.get("/api/config/default-proxy")
def get_default_proxy():
    """Gets default proxy settings from config.json if available."""
    template_path = Path("config.json")
    if template_path.exists():
        try:
            config = load_json(template_path)
            proxy = config.get("proxy", {})
            return {
                "enabled": proxy.get("enabled", True),
                "type": proxy.get("type", "http"),
                "host": proxy.get("host", "127.0.0.1"),
                "port": proxy.get("port", 8800),
                "username": proxy.get("username", ""),
                "password": proxy.get("password", "")
            }
        except Exception:
            pass
    return {
        "enabled": True,
        "type": "http",
        "host": "127.0.0.1",
        "port": 8800,
        "username": "",
        "password": ""
    }

# --- AUTHENTICATION APIs ---

@app.get("/api/auth/status")
def get_auth_status():
    from db import engine, AdminDb, Session, select
    with Session(engine) as session:
        stmt = select(AdminDb)
        has_admin = session.exec(stmt).first() is not None
    return {"initialized": has_admin}

@app.post("/api/auth/setup-admin")
def setup_first_admin(req: SetupAdminRequest):
    from db import engine, AdminDb, Session, select, hash_password
    from datetime import datetime, timezone
    with Session(engine) as session:
        stmt = select(AdminDb)
        if session.exec(stmt).first() is not None:
            raise HTTPException(status_code=400, detail="管理员已配置，不允许重复初始化")

        username = req.username.strip()
        password = req.password
        if not username or len(password) < 6:
            raise HTTPException(status_code=400, detail="用户名不能为空，密码长度必须不小于 6 位")

        pwd_hash, salt = hash_password(password)
        admin_user = AdminDb(
            username=username,
            password_hash=pwd_hash,
            salt=salt,
            role="admin",
            company=req.company.strip() if req.company else "admin",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(admin_user)
        session.commit()
    return {"status": "success", "message": "管理员配置成功"}

@app.post("/api/auth/login")
def login(req: LoginRequest):
    from db import engine, AdminDb, RolePermissionDb, Session, select, verify_password
    username = req.username.strip()
    password = req.password

    with Session(engine) as session:
        stmt = select(AdminDb).where(AdminDb.username == username)
        user = session.exec(stmt).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not verify_password(password, user.salt, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # Get allowed tabs
        perm = session.get(RolePermissionDb, user.role)
        allowed = [x.strip() for x in perm.allowed_tabs.split(",") if x.strip()] if perm else []
        if user.role == "admin":
            if "bot_auth" not in allowed:
                allowed.append("bot_auth")
            if "bots" not in allowed:
                allowed.append("bots")

        token = generate_token(user.username, user.role)
        return {
            "status": "success",
            "token": token,
            "username": user.username,
            "role": user.role,
            "company": user.company or "admin",
            "allowed_tabs": allowed
        }

@app.get("/api/auth/current")
def get_current_logged_in_user(user: dict = Depends(get_current_user)):
    from db import engine, RolePermissionDb, Session
    with Session(engine) as session:
        perm = session.get(RolePermissionDb, user["role"])
        allowed = [x.strip() for x in perm.allowed_tabs.split(",") if x.strip()] if perm else []
        if user["role"] == "admin":
            if "bot_auth" not in allowed:
                allowed.append("bot_auth")
            if "bots" not in allowed:
                allowed.append("bots")
    return {
        "username": user["username"],
        "role": user["role"],
        "company": user["company"],
        "allowed_tabs": allowed
    }

class VerifyPasswordRequest(BaseModel):
    password: str

@app.post("/api/auth/verify-password")
def verify_admin_password(req: VerifyPasswordRequest, user: dict = Depends(get_current_user)):
    """Verifies the currently logged-in user's password."""
    from db import engine, AdminDb, Session, select, verify_password
    with Session(engine) as session:
        db_user = session.exec(select(AdminDb).where(AdminDb.username == user["username"])).first()
        if not db_user:
            return {"valid": False}
        is_valid = verify_password(req.password, db_user.salt, db_user.password_hash)
        return {"valid": is_valid}

# --- COMPANY MANAGEMENT APIs ---

@app.get("/api/admin/companies")
def get_admin_companies(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, CompanyDb, Session, select
    with Session(engine) as session:
        stmt = select(CompanyDb).order_by(CompanyDb.name.asc())
        results = session.exec(stmt).all()
        return [{"id": c.id, "name": c.name, "created_at": c.created_at} for c in results]

@app.post("/api/admin/companies")
def create_admin_company(req: CompanyCreateRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, CompanyDb, Session, select
    from datetime import datetime, timezone
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="公司名称不能为空")

    with Session(engine) as session:
        dup = session.exec(select(CompanyDb).where(CompanyDb.name == name)).first()
        if dup:
            raise HTTPException(status_code=400, detail="公司名称已存在")

        new_company = CompanyDb(
            name=name,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(new_company)
        session.commit()
    return {"status": "success", "message": "添加公司成功"}

@app.put("/api/admin/companies/{company_id}")
def update_admin_company(company_id: int, req: CompanyUpdateRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, CompanyDb, Session, select
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="公司名称不能为空")

    with Session(engine) as session:
        company = session.get(CompanyDb, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="公司不存在")

        if company.name == "admin":
            raise HTTPException(status_code=400, detail="不能修改admin")

        dup = session.exec(select(CompanyDb).where(CompanyDb.name == name).where(CompanyDb.id != company_id)).first()
        if dup:
            raise HTTPException(status_code=400, detail="公司名称已存在")

        company.name = name
        session.add(company)
        session.commit()
    return {"status": "success", "message": "修改公司成功"}

@app.delete("/api/admin/companies/{company_id}")
def delete_admin_company(company_id: int, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, CompanyDb, AdminDb, AccountDb, Session, select
    with Session(engine) as session:
        company = session.get(CompanyDb, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="公司不存在")

        if company.name == "admin":
            raise HTTPException(status_code=400, detail="不能删除admin")

        # Check if any admin/user belongs to this company
        user_dup = session.exec(select(AdminDb).where(AdminDb.company == company.name)).first()
        if user_dup:
            raise HTTPException(status_code=400, detail="该公司下有系统用户，无法删除")

        # Check if any accounts belong to this company
        account_dup = session.exec(select(AccountDb).where(AccountDb.company == company.name)).first()
        if account_dup:
            raise HTTPException(status_code=400, detail="该公司下有 Telegram 账号，无法删除")

        session.delete(company)
        session.commit()
    return {"status": "success", "message": "删除公司成功"}

# --- ADMIN MANAGEMENT APIs ---

@app.get("/api/admin/users")
def get_admin_users(user: dict = Depends(get_current_user)):
    from db import engine, AdminDb, Session, select
    with Session(engine) as session:
        if user["role"] == "admin":
            stmt = select(AdminDb)
        else:
            stmt = select(AdminDb).where(AdminDb.company == user["company"])
        results = session.exec(stmt).all()
        return [{
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "company": u.company or "admin",
            "telegram_contact": getattr(u, "telegram_contact", "") or "",
            "forum_chat_id": getattr(u, "forum_chat_id", "") or "",
            "created_at": u.created_at
        } for u in results]

@app.post("/api/admin/users")
def create_admin_user(req: UserCreateRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, AdminDb, Session, select, hash_password
    from datetime import datetime, timezone
    username = req.username.strip()
    password = req.password
    if req.role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 user")
    if not username or len(password) < 6:
        raise HTTPException(status_code=400, detail="用户名不能为空，密码长度必须不小于 6 位")
    telegram_contact = normalize_telegram_contact(req.telegram_contact)

    company_name = req.company.strip() if req.company else ""
    if username not in ("eason", "admin") and not company_name:
        raise HTTPException(status_code=400, detail="除了 eason 用户外，其他用户必须绑定公司")

    forum_chat_id = req.forum_chat_id.strip() if req.forum_chat_id else ""

    with Session(engine) as session:
        from db import CompanyDb
        if company_name:
            company_exists = session.exec(select(CompanyDb).where(CompanyDb.name == company_name)).first()
            if not company_exists:
                raise HTTPException(status_code=400, detail=f"绑定的公司 '{company_name}' 不存在")

        dup = session.exec(select(AdminDb).where(AdminDb.username == username)).first()
        if dup:
            raise HTTPException(status_code=400, detail="用户名已存在")

        if telegram_contact:
            dup_contact = session.exec(select(AdminDb).where(AdminDb.telegram_contact == telegram_contact)).first()
            if dup_contact:
                raise HTTPException(status_code=400, detail="该电报用户名已被系统内其他用户绑定")

        if forum_chat_id:
            dup_forum = session.exec(select(AdminDb).where(AdminDb.forum_chat_id == forum_chat_id)).first()
            if dup_forum:
                raise HTTPException(status_code=400, detail="该超级群 ID 已被系统内其他用户占用")

        pwd_hash, salt = hash_password(password)
        new_user = AdminDb(
            username=username,
            password_hash=pwd_hash,
            salt=salt,
            role=req.role,
            company=company_name,
            telegram_contact=telegram_contact,
            forum_chat_id=forum_chat_id,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(new_user)
        session.commit()

        # 自动激活暂存账号所有权
        if telegram_contact:
            clean_contact = telegram_contact.strip().lstrip("@").lower()
            from db import AccountDb
            pending_tag = f"pending_tg_username:{clean_contact}"
            stmt_update = select(AccountDb).where(AccountDb.owner_username == pending_tag)
            pending_accs = session.exec(stmt_update).all()
            for acc in pending_accs:
                acc.owner_username = username
                session.add(acc)
            session.commit()

    return {"status": "success", "message": "添加用户成功"}

class UserUpdateRequest(BaseModel):
    role: str
    company: str
    password: Optional[str] = None
    telegram_contact: Optional[str] = ""
    forum_chat_id: Optional[str] = None

@app.put("/api/admin/users/{user_id}")
def update_admin_user(user_id: int, req: UserUpdateRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, AdminDb, Session, select, hash_password

    role = req.role.strip()
    company_name = req.company.strip() if req.company else ""
    telegram_contact = normalize_telegram_contact(req.telegram_contact)
    forum_chat_id = req.forum_chat_id.strip() if req.forum_chat_id else ""

    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 user")

    with Session(engine) as session:
        target_user = session.get(AdminDb, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="用户不存在")

        username = target_user.username
        if username not in ("eason", "admin") and not company_name:
            raise HTTPException(status_code=400, detail="除了 eason 用户外，其他用户必须绑定公司")

        if telegram_contact:
            dup_contact = session.exec(
                select(AdminDb).where(AdminDb.telegram_contact == telegram_contact).where(AdminDb.id != user_id)
            ).first()
            if dup_contact:
                raise HTTPException(status_code=400, detail="该电报用户名已被系统内其他用户绑定")

        if forum_chat_id:
            dup_forum = session.exec(
                select(AdminDb).where(AdminDb.forum_chat_id == forum_chat_id).where(AdminDb.id != user_id)
            ).first()
            if dup_forum:
                raise HTTPException(status_code=400, detail="该超级群 ID 已被系统内其他用户占用")

        if company_name:
            from db import CompanyDb
            company_exists = session.exec(select(CompanyDb).where(CompanyDb.name == company_name)).first()
            if not company_exists:
                raise HTTPException(status_code=400, detail=f"绑定的公司 '{company_name}' 不存在")

        target_user.role = role
        target_user.company = company_name
        if getattr(target_user, "telegram_contact", "") != telegram_contact:
            target_user.telegram_chat_id = None
        target_user.telegram_contact = telegram_contact
        target_user.forum_chat_id = forum_chat_id

        if req.password:
            password = req.password.strip()
            if len(password) < 6:
                raise HTTPException(status_code=400, detail="密码长度必须不小于 6 位")
            pwd_hash, salt = hash_password(password)
            target_user.password_hash = pwd_hash
            target_user.salt = salt

        session.add(target_user)
        session.commit()

        # 自动激活暂存账号所有权
        if telegram_contact:
            clean_contact = telegram_contact.strip().lstrip("@").lower()
            from db import AccountDb
            pending_tag = f"pending_tg_username:{clean_contact}"
            stmt_update = select(AccountDb).where(AccountDb.owner_username == pending_tag)
            pending_accs = session.exec(stmt_update).all()
            for acc in pending_accs:
                acc.owner_username = username
                session.add(acc)
            session.commit()

    return {"status": "success", "message": "修改用户成功"}

@app.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: int, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, AdminDb, Session
    with Session(engine) as session:
        u = session.get(AdminDb, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="用户不存在")
        if u.username == user["username"]:
            raise HTTPException(status_code=400, detail="不允许删除当前登录账号")

        session.delete(u)
        session.commit()
    return {"status": "success", "message": "删除用户成功"}

class ChangeUserPasswordRequest(BaseModel):
    old_password: Optional[str] = ""
    password: str

@app.post("/api/admin/users/{user_id}/password")
def change_user_password(user_id: int, req: ChangeUserPasswordRequest, user: dict = Depends(get_current_user)):
    from db import engine, AdminDb, RolePermissionDb, Session, select, hash_password, verify_password
    with Session(engine) as session:
        target_user = session.get(AdminDb, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="目标用户不存在")

        is_self = user["id"] == target_user.id or user["username"] == target_user.username
        is_super = user["username"] in ("eason", "admin")

        has_permission = False
        if is_self or is_super:
            has_permission = True
        else:
            if user["role"] == "admin":
                role_perm = session.get(RolePermissionDb, "admin")
                if role_perm:
                    allowed = [x.strip() for x in role_perm.allowed_tabs.split(",") if x.strip()]
                    if "change_password" in allowed:
                        has_permission = True

        if not has_permission:
            raise HTTPException(status_code=403, detail="没有修改他人密码的权限")

        new_pwd = req.password.strip()
        if len(new_pwd) < 6:
            raise HTTPException(status_code=400, detail="新密码长度不能小于6位")

        # Check if new password is identical to current password
        if verify_password(new_pwd, target_user.salt, target_user.password_hash):
            raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

        # Verify old password if modifying own password
        if is_self:
            old_pwd = req.old_password
            if not old_pwd:
                raise HTTPException(status_code=400, detail="修改个人密码必须输入原密码")
            if not verify_password(old_pwd, target_user.salt, target_user.password_hash):
                raise HTTPException(status_code=401, detail="原密码输入错误")

        pwd_hash, salt = hash_password(new_pwd)
        target_user.password_hash = pwd_hash
        target_user.salt = salt
        session.add(target_user)
        session.commit()

    return {"status": "success", "message": "密码修改成功"}

class RolePermissionRequest(BaseModel):
    role: str
    allowed_tabs: List[str]

@app.get("/api/admin/permissions")
def get_role_permissions(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")
    from db import engine, RolePermissionDb, Session, select
    with Session(engine) as session:
        stmt = select(RolePermissionDb)
        results = session.exec(stmt).all()
        return [
            {
                "role": p.role,
                "allowed_tabs": [x.strip() for x in p.allowed_tabs.split(",") if x.strip()]
            }
            for p in results
        ]

@app.post("/api/admin/permissions")
def update_role_permissions(req: RolePermissionRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="拒绝访问")

    role = req.role.strip()
    allowed_list = [x.strip() for x in req.allowed_tabs if x.strip()]

    # Safety Check: Prevent admins from accidentally disabling 'users' or 'permissions' for themselves
    if role == "admin":
        if "users" not in allowed_list:
            allowed_list.append("users")
        if "permissions" not in allowed_list:
            allowed_list.append("permissions")
        if "bot_auth" not in allowed_list:
            allowed_list.append("bot_auth")
        if "bots" not in allowed_list:
            allowed_list.append("bots")

    allowed_tabs_str = ",".join(allowed_list)

    from db import engine, RolePermissionDb, Session
    with Session(engine) as session:
        perm = session.get(RolePermissionDb, role)
        if not perm:
            perm = RolePermissionDb(role=role, allowed_tabs=allowed_tabs_str)
        else:
            perm.allowed_tabs = allowed_tabs_str
        session.add(perm)
        session.commit()

    return {"status": "success", "message": f"角色 {role} 的权限已更新"}

# --- FRONTEND ROUTE ---

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve static assets (Vite React app assets) from frontend/dist/assets
frontend_dist_dir = Path(__file__).resolve().parent / "frontend" / "dist"
assets_dir = frontend_dist_dir / "assets"

if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    frontend_index = frontend_dist_dir / "index.html"
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if frontend_index.exists():
        return HTMLResponse(content=frontend_index.read_text(encoding="utf-8"), status_code=200, headers=headers)

    index_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Index HTML not found")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200, headers=headers)

@app.get("/{filename}")
async def serve_public_file(filename: str):
    # Security: Prevent path traversal (e.g. filename = "../data/rosepay.db")
    try:
        # Check in frontend dist folder
        file_path = (frontend_dist_dir / filename).resolve()
        if file_path.is_file() and str(file_path).startswith(str(frontend_dist_dir.resolve())):
            # Block access to configuration/build files
            if filename in (".env", "config.json", "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts"):
                raise HTTPException(status_code=403, detail="Access denied")
            return FileResponse(file_path)

        # Fallback to check legacy templates folder
        legacy_dir = Path(__file__).resolve().parent / "templates"
        legacy_path = (legacy_dir / filename).resolve()
        if legacy_path.is_file() and str(legacy_path).startswith(str(legacy_dir.resolve())):
            return FileResponse(legacy_path)
    except HTTPException as he:
        raise he
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="File not found")


# --- SCRAPER API ---

def _auto_save_2fa_to_db(pid: str, pass2fa: str):
    """Helper to automatically save extracted 2FA password to the database."""
    if not pass2fa or not pass2fa.strip():
        return
    try:
        from db import engine, AccountDb, Session, select
        import re
        with Session(engine) as session:
            # 1. Try exact match on page_id
            stmt = select(AccountDb).where(AccountDb.page_id == pid)
            db_accs = session.exec(stmt).all()

            # 2. If no match, try extracting UUID token and matching
            if not db_accs:
                token_match = re.search(r"token=([a-zA-Z0-9\-]+)", pid)
                token_val = token_match.group(1) if token_match else pid
                stmt = select(AccountDb).where((AccountDb.page_id == token_val) | (AccountDb.page_id.like(f"%{token_val}%")))
                db_accs = session.exec(stmt).all()

            for db_acc in db_accs:
                if db_acc.pass2fa != pass2fa:
                    db_acc.pass2fa = pass2fa
                    session.add(db_acc)
                    # Sync to config.json file
                    try:
                        config_path = account_config_path(db_acc.id)
                        if config_path.exists():
                            config = load_json(config_path)
                            config["pass2fa"] = pass2fa
                            save_json(config_path, config)
                    except Exception as e:
                        print(f"Error syncing 2FA to config json: {e}")
            session.commit()
    except Exception as e:
        print(f"Error in _auto_save_2fa_to_db: {e}")

@app.get("/api/scraper/fetch")
async def fetch_scraper_data(page_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Fetches device verification code and 2fa password from the old target scraping URL."""
    pid = (page_id or DEFAULT_SCRAPER_PAGE_ID).strip()

    # 如果是新接码平台链接，不进行自动爬取，直接返回空以等待用户手动输入
    if "add4533.com" in pid or "onlinestore-fx-jm" in pid:
        return {
            "code": None,
            "pass2fa": None,
            "login_time": None
        }

    code = None
    pass2fa = None
    login_time = None

    try:
        # 旧版 HTML 平台 (feijige.shop) 爬虫
        uuid_val = pid
        if "http" in pid:
            uuid_match = re.search(r"/([a-zA-Z0-9\-]{36})", pid)
            if uuid_match:
                uuid_val = uuid_match.group(1)

        url = f"https://tgapi.feijige.shop/{uuid_val}/GetHTML"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=8))
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        code_input = soup.find('input', id='code')
        if code_input:
            code = code_input.get('value')
        pass2fa_input = soup.find('input', id='pass2fa')
        if pass2fa_input:
            pass2fa = pass2fa_input.get('value')
        time_label = soup.find(string=lambda t: t and "登录时间" in t)
        if time_label:
            parent = time_label.find_parent('div', class_='form-group')
            if parent:
                inp = parent.find('input')
                if inp:
                    login_time = inp.get('value')
    except Exception as e:
        print(f"[Scraper] Old platform fetch failed: {e}")

    if pass2fa:
        _auto_save_2fa_to_db(pid, pass2fa)

    return {
        "code": code,
        "pass2fa": pass2fa,
        "login_time": login_time
    }

# --- ACCOUNT MANAGEMENT APIs ---

def cleanup_stale_unauthorized_accounts():
    """Disabled safety hook.

    Runtime auth status can be empty after a restart, so deleting accounts here
    can remove real account rows and session files by mistake.
    """
    return

@app.get("/api/accounts")
def get_accounts(scope: str = "mine", user: dict = Depends(get_current_user)):
    """Lists all configured Telegram accounts from database."""
    cleanup_stale_unauthorized_accounts()
    from db import engine, AccountDb, Session, select
    started_at = time.time()
    campaign_scan_ms = 0
    busy_scan_ms = 0
    with Session(engine) as session:
        db_accounts = session.exec(query_accounts_for_view_scope(session, user, scope)).all()
        result = []
        for acc in db_accounts:
            campaign_started = time.time()
            is_campaign_running = is_campaign_running_for_account(acc.id)
            campaign_scan_ms += int((time.time() - campaign_started) * 1000)

            # Fetch status from account_status_store
            # Check persistent spambot cache as fallback if not in store yet
            cached = spambot_cache.get(acc.id)
            default_spambot_status = cached.get("status", "unknown") if cached else "unknown"
            default_spambot_details = cached.get("details", "") if cached else ""
            default_spambot_time = cached.get("timestamp", None) if cached else None

            status = account_status_store.get(acc.id, {
                "is_connected": False,
                "is_authorized": False,
                "me": "未初始化（等待检测）",
                "spambot_status": default_spambot_status,
                "spambot_details": default_spambot_details,
                "spambot_time": default_spambot_time
            })

            busy_started = time.time()
            busy_status = get_account_busy_status(acc.id)
            busy_scan_ms += int((time.time() - busy_started) * 1000)
            live_client = active_clients.get(acc.id)
            live_connected = bool(live_client and live_client.is_connected())
            active_operation = active_account_operations.get(acc.id)
            private_listener_active = (acc.id in auto_private_listener_accounts and live_connected) if ENABLE_REALTIME_PRIVATE_DM else False
            display_me = status.get("me", "未初始化（等待检测）")
            if is_placeholder_me_info(display_me):
                saved_display = account_saved_profile_display(acc)
                if saved_display:
                    display_me = saved_display

            result.append({
                "id": acc.id,
                "name": acc.account_name,
                "is_available": acc.is_available,
                "company": acc.company,
                "created_by": acc.created_by,
                "owner_username": acc.owner_username,
                "bot_setup_status": acc.bot_setup_status or "not_started",
                "config": acc.to_dict(),
                "campaign_running": is_campaign_running,
                "is_busy": is_account_busy_with_task(acc.id),
                "busy_status": busy_status,
                "active_operation": active_operation.get("operation") if active_operation else None,
                "active_operation_label": active_operation.get("label") if active_operation else None,
                "private_listener": private_listener_active,
                "private_listener_source": "auto" if private_listener_active else None,
                "is_connected": live_connected,
                "is_authorized": status.get("is_authorized", False),
                "isAuthorized": status.get("is_authorized", False),
                "meInfo": display_me,
                "spambot_status": status.get("spambot_status", "unknown"),
                "spambot_details": status.get("spambot_details", ""),
                "spambot_time": status.get("spambot_time", None),
                "is_deactivated": status.get("is_deactivated", False),
                "connection_status": status.get("connection_status", "connected" if live_connected else "disconnected"),
                "auth_status": status.get("auth_status", "authorized" if status.get("is_authorized", False) else "unauthorized"),
                "task_status": busy_status,
                "availability_status": "available" if acc.is_available else "occupied",
                "last_checked_at": status.get("last_checked_at", None),
                "last_error": status.get("last_error", status.get("error", None)),
                "source": status.get("source", "accounts")
            })
        total_ms = int((time.time() - started_at) * 1000)
        print(f"[AccountsTiming] total={total_ms}ms count={len(result)} campaign_scan={campaign_scan_ms}ms busy_scan={busy_scan_ms}ms")
        return result


def private_user_display_name(entity) -> str:
    first_name = getattr(entity, "first_name", "") or ""
    last_name = getattr(entity, "last_name", "") or ""
    name = f"{first_name} {last_name}".strip()
    username = getattr(entity, "username", "") or ""
    if name:
        return name
    if username:
        return f"@{username}"
    return str(getattr(entity, "id", "Unknown"))


def message_preview_text(message) -> str:
    if not message:
        return ""
    text = getattr(message, "message", "") or ""
    if text:
        return text.replace("\n", " ").strip()
    if getattr(message, "media", None):
        return "[media]"
    return ""


def serialize_private_dialog(dialog) -> Optional[dict]:
    if not getattr(dialog, "is_user", False):
        return None
    entity = dialog.entity
    if not isinstance(entity, types.User):
        return None
    if bool(getattr(entity, "bot", False)):
        return None
    peer_id = str(entity.id)
    cache_private_sender_entity("", entity)
    last_message = dialog.message
    last_date = getattr(last_message, "date", None)
    return {
        "peer_id": peer_id,
        "name": private_user_display_name(entity),
        "username": f"@{entity.username}" if getattr(entity, "username", None) else "",
        "phone": getattr(entity, "phone", "") or "",
        "is_bot": bool(getattr(entity, "bot", False)),
        "unread_count": int(getattr(dialog, "unread_count", 0) or 0),
        "last_message": message_preview_text(last_message),
        "last_message_at": last_date.isoformat() if last_date else None,
    }


def serialize_private_message(message) -> dict:
    date = getattr(message, "date", None)
    text = getattr(message, "message", "") or ""
    return {
        "id": message.id,
        "text": text,
        "out": bool(getattr(message, "out", False)),
        "date": date.isoformat() if date else None,
        "has_media": bool(getattr(message, "media", None)),
    }


def event_to_private_message(event: dict) -> dict:
    timestamp = float(event.get("timestamp") or event.get("created_at") or time.time())
    message_id = int(event.get("message_id") or 0)
    if message_id <= 0:
        message_id = -int(timestamp * 1000)
    return {
        "id": message_id,
        "text": event.get("text") or "",
        "out": bool(event.get("out", False)),
        "date": datetime.datetime.fromtimestamp(timestamp).isoformat(),
        "has_media": (event.get("text") or "") in ("", "[media]"),
    }


def is_bot_private_event(event: dict) -> bool:
    if bool(event.get("sender_is_bot", False)) or bool(event.get("is_bot", False)):
        return True
    username = str(event.get("sender_username") or event.get("username") or "").strip().lstrip("@").lower()
    return bool(username and username.endswith("bot"))


def get_cached_private_dialogs(account_id: str, limit: int = 30) -> List[dict]:
    raw_events = read_private_dm_events({str(account_id)}, limit=2000)
    events = list({private_dm_event_key(event): event for event in raw_events}.values())
    dialogs_by_peer: Dict[str, dict] = {}
    ack_ts = float(private_dm_event_ack.get(str(account_id), 0) or 0)
    unread_by_peer: Dict[str, int] = {}
    for event in events:
        if is_bot_private_event(event):
            continue
        peer_id = str(event.get("sender_id") or event.get("peer_id") or "")
        if not peer_id:
            continue
        cached_sender = get_private_sender_cache(peer_id) or {}
        timestamp = float(event.get("timestamp") or event.get("created_at") or 0)
        if timestamp > ack_ts and not bool(event.get("out", False)):
            unread_by_peer[peer_id] = unread_by_peer.get(peer_id, 0) + 1
        current = dialogs_by_peer.get(peer_id)
        if current and float(current.get("_timestamp") or 0) >= timestamp:
            continue
        dialogs_by_peer[peer_id] = {
            "peer_id": peer_id,
            "name": cached_sender.get("sender_name") or event.get("sender_name") or event.get("sender_username") or f"ID {peer_id}",
            "username": cached_sender.get("sender_username") or event.get("sender_username") or "",
            "phone": "",
            "is_bot": False,
            "unread_count": unread_by_peer.get(peer_id, 0),
            "last_message": event.get("text") or "[media]",
            "last_message_at": datetime.datetime.fromtimestamp(timestamp or time.time()).isoformat(),
            "_timestamp": timestamp,
            "cached": True,
        }
    for peer_id, dialog in dialogs_by_peer.items():
        dialog["unread_count"] = unread_by_peer.get(peer_id, 0)
        dialog.pop("_timestamp", None)
    dialogs = sorted(dialogs_by_peer.values(), key=lambda item: item.get("last_message_at") or "", reverse=True)
    return dialogs[:max(1, min(limit, 200))]


def get_cached_private_messages(account_id: str, peer_id: str, limit: int = 30) -> List[dict]:
    events = [
        event for event in read_private_dm_events({str(account_id)}, limit=3000)
        if str(event.get("sender_id") or event.get("peer_id") or "") == str(peer_id) and not is_bot_private_event(event)
    ]
    events_by_key = {private_dm_event_key(event): event for event in events}
    ordered = sorted(events_by_key.values(), key=lambda event: float(event.get("timestamp") or event.get("created_at") or 0))
    messages = [event_to_private_message(event) for event in ordered]
    return messages[-max(1, min(limit, 200)):]


def cache_private_message(account_id: str, peer: types.User, message) -> None:
    if not isinstance(peer, types.User) or bool(getattr(peer, "bot", False)):
        return
    cache_private_sender_entity(account_id, peer)
    msg_date = getattr(message, "date", None)
    timestamp = msg_date.timestamp() if msg_date else time.time()
    is_out = bool(getattr(message, "out", False))
    peer_id = int(getattr(peer, "id", 0) or 0)
    event = {
        "account_id": str(account_id),
        "account_label": str(account_id),
        "source": "message_cache",
        "sender_id": peer_id,
        "peer_id": peer_id,
        "sender_name": private_user_display_name(peer),
        "sender_username": f"@{peer.username}" if getattr(peer, "username", None) else "",
        "sender_is_bot": bool(getattr(peer, "bot", False)),
        "message_id": int(getattr(message, "id", 0) or 0),
        "text": message_preview_text(message),
        "out": is_out,
        "notify": False,
        "timestamp": timestamp,
        "created_at": time.time(),
    }
    append_private_dm_event(event)


def queued_private_message_payload(queue_id: str, text: str) -> dict:
    return {
        "id": -int(time.time() * 1000),
        "text": text,
        "out": True,
        "date": datetime.datetime.now().isoformat(),
        "has_media": False,
        "status": "queued",
        "queue_id": queue_id,
    }


def private_queue_item_from_record(record) -> dict:
    return {
        "id": record.id,
        "account_id": str(record.account_id),
        "peer_id": str(record.peer_id),
        "text": record.text,
        "created_by": record.created_by or "",
        "created_at": float(record.created_at or time.time()),
        "status": record.status or "queued",
    }


def save_private_send_queue_record(item: dict) -> None:
    from db import engine, PrivateSendQueueDb, Session
    now = time.time()
    with Session(engine) as session:
        record = session.get(PrivateSendQueueDb, str(item["id"]))
        if record is None:
            record = PrivateSendQueueDb(
                id=str(item["id"]),
                account_id=str(item["account_id"]),
                peer_id=str(item["peer_id"]),
                text=str(item["text"]),
                status=str(item.get("status") or "queued"),
                created_by=str(item.get("created_by") or ""),
                created_at=float(item.get("created_at") or now),
                updated_at=now,
            )
        else:
            record.status = str(item.get("status") or record.status or "queued")
            record.updated_at = now
        record.error = item.get("error")
        sent_message = item.get("sent_message")
        if sent_message:
            record.sent_message_id = int(sent_message.get("id") or 0) or None
            record.sent_message_json = json.dumps(sent_message, ensure_ascii=False)
            record.sent_at = now
        session.add(record)
        session.commit()


def update_private_send_queue_record(queue_id: str, status: str, *, error: Optional[str] = None, sent_message: Optional[dict] = None) -> None:
    from db import engine, PrivateSendQueueDb, Session
    now = time.time()
    with Session(engine) as session:
        record = session.get(PrivateSendQueueDb, str(queue_id))
        if record is None:
            return
        record.status = status
        record.updated_at = now
        record.error = error
        if sent_message:
            record.sent_message_id = int(sent_message.get("id") or 0) or None
            record.sent_message_json = json.dumps(sent_message, ensure_ascii=False)
            record.sent_at = now
        session.add(record)
        session.commit()


def load_pending_private_sends_from_db() -> None:
    from db import engine, PrivateSendQueueDb, Session, select
    try:
        with Session(engine) as session:
            records = session.exec(
                select(PrivateSendQueueDb).where(PrivateSendQueueDb.status.in_(["queued", "sending"]))
            ).all()
            loaded = 0
            for record in records:
                if record.status == "sending":
                    record.status = "queued"
                    record.updated_at = time.time()
                    session.add(record)
                pending_private_sends.setdefault(str(record.account_id), deque()).append(private_queue_item_from_record(record))
                loaded += 1
            if loaded:
                session.commit()
                print(f"[PrivateSendQueue] Restored {loaded} pending private send(s) from DB.")
    except Exception as exc:
        print(f"[PrivateSendQueue] Failed to restore pending queue: {exc}")


def enqueue_private_send(account_id: str, peer_id: str, text: str, created_by: str = "") -> dict:
    queue_id = secrets.token_hex(8)
    item = {
        "id": queue_id,
        "account_id": str(account_id),
        "peer_id": str(peer_id),
        "text": text,
        "created_by": created_by,
        "created_at": time.time(),
        "status": "queued",
    }
    pending_private_sends.setdefault(str(account_id), deque()).append(item)
    try:
        save_private_send_queue_record(item)
    except Exception as exc:
        print(f"[PrivateSendQueue] Failed to persist queued send {queue_id}: {exc}")
    return item


async def send_private_message_with_client(account_id: str, client: TelegramClient, peer_id: str, text: str, reply_to_msg_id: Optional[int] = None) -> dict:
    if not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="账号未登录")
    peer_key = str(peer_id)
    entity = None
    try:
        peer_ref = int(peer_key)
    except ValueError:
        peer_ref = peer_key
    try:
        sent = await client.send_message(peer_ref, text, reply_to=reply_to_msg_id)
    except Exception:
        try:
            entity = await client.get_entity(peer_ref)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"私聊对象不存在: {exc}")
        if not isinstance(entity, types.User):
            raise HTTPException(status_code=400, detail="只支持私聊用户，不支持群聊或频道")
        if bool(getattr(entity, "bot", False)):
            raise HTTPException(status_code=400, detail="已排除 Bot 私聊")
        sent = await client.send_message(entity, text, reply_to=reply_to_msg_id)
    try:
        if entity is None and not get_private_sender_cache(peer_key):
            entity = await client.get_entity(peer_ref)
        if entity is not None:
            cache_private_sender_entity(account_id, entity)
            cache_private_message(account_id, entity, sent)
    except Exception:
        pass
    message = serialize_private_message(sent)
    message["status"] = "sent"
    return message


async def drain_pending_private_sends(account_id: str, client: Optional[TelegramClient] = None, max_items: int = 5) -> int:
    account_id = str(account_id)
    queue = pending_private_sends.get(account_id)
    if not queue:
        return 0
    lock = private_send_queue_locks.setdefault(account_id, asyncio.Lock())
    if lock.locked():
        return 0
    sent_count = 0
    async with lock:
        if client is None:
            client = await get_client(account_id)
        while queue and sent_count < max_items:
            item = queue[0]
            try:
                item["status"] = "sending"
                update_private_send_queue_record(str(item["id"]), "sending")

                # 从 created_by 解析 reply_to_msg_id
                created_by = str(item.get("created_by") or "")
                reply_to_msg_id = None
                if created_by.startswith("bot:reply_to:"):
                    try:
                        reply_to_msg_id = int(created_by.split("bot:reply_to:", 1)[1])
                    except Exception:
                        pass

                sent_message = await send_private_message_with_client(
                    account_id,
                    client,
                    str(item["peer_id"]),
                    str(item["text"]),
                    reply_to_msg_id=reply_to_msg_id
                )
                item["status"] = "sent"
                item["sent_message"] = sent_message
                update_private_send_queue_record(str(item["id"]), "sent", sent_message=sent_message)
                sent_count += 1
                queue.popleft()
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = getattr(exc, "detail", None) or str(exc)
                update_private_send_queue_record(str(item["id"]), "failed", error=item["error"])
                queue.popleft()
                print(f"[PrivateSendQueue] Failed account={account_id} peer={item.get('peer_id')}: {item['error']}")
        if not queue:
            pending_private_sends.pop(account_id, None)
    return sent_count


def get_private_poll_skip_reason(account_id: str) -> Optional[str]:
    """Avoid opening a controller client while another task owns the account session."""
    active_op = active_account_operations.get(account_id)
    if active_op:
        return f"账号正在执行操作: {active_op.get('label') or active_op.get('operation') or 'active'}"

    busy_status = get_account_busy_status(account_id)
    if busy_status and busy_status != "idle":
        return f"账号正在执行任务: {busy_status}"

    if is_campaign_running_for_account(account_id):
        return "账号正在执行广告任务"
    return None


def get_external_private_dm_unread(account_id: str) -> dict:
    ack_ts = float(private_dm_event_ack.get(str(account_id), 0) or 0)
    raw_events = [
        item for item in read_private_dm_events({str(account_id)}, limit=1000)
        if float(item.get("timestamp") or item.get("created_at") or 0) > ack_ts and not bool(item.get("out", False))
    ]
    events_by_key = {}
    for item in raw_events:
        sender_id = str(item.get("sender_id") or "")
        message_id = str(item.get("message_id") or "")
        if sender_id and message_id and message_id != "0":
            key = f"{sender_id}:{message_id}"
        else:
            key = f"{sender_id}:{item.get('timestamp') or item.get('created_at') or ''}:{item.get('text') or ''}"
        events_by_key[key] = item
    events = list(events_by_key.values())
    sender_ids = {str(item.get("sender_id") or "") for item in events if item.get("sender_id")}
    last_event = max(events, key=lambda item: float(item.get("timestamp") or item.get("created_at") or 0), default=None)
    return {
        "external_unread_messages": len(events),
        "external_unread_dialogs": len(sender_ids),
        "last_private_event": last_event,
    }


def mark_private_dm_events_read(account_id: str) -> None:
    events = read_private_dm_events({str(account_id)}, limit=1000)
    max_event_ts = max(
        [float(item.get("timestamp") or item.get("created_at") or 0) for item in events] or [0]
    )
    private_dm_event_ack[str(account_id)] = max(time.time(), max_event_ts + 1)
    save_private_dm_ack(private_dm_event_ack)
    cached = private_unread_cache.get(str(account_id), {})
    private_unread_cache[str(account_id)] = {
        **cached,
        "unread_dialogs": 0,
        "unread_messages": 0,
        "external_unread_dialogs": 0,
        "external_unread_messages": 0,
        "last_private_event": None,
        "loading": False,
        "stale": False,
        "error": None,
        "updated_at": time.time(),
        "_event_sender_ids": [],
        "_event_keys": list(cached.get("_event_keys") or [])[-200:],
    }


async def compute_private_unread_summary(account_id: str) -> dict:
    external_unread = get_external_private_dm_unread(account_id)
    return {
        "unread_dialogs": int(external_unread["external_unread_dialogs"] or 0),
        "unread_messages": int(external_unread["external_unread_messages"] or 0),
        **external_unread,
        "error": None,
        "updated_at": time.time(),
        "loading": False,
        "stale": False,
    }


async def refresh_private_unread_cache(account_id: str) -> None:
    if account_id in private_unread_refreshing:
        return
    private_unread_refreshing.add(account_id)
    try:
        private_unread_cache[account_id] = await compute_private_unread_summary(account_id)
    finally:
        private_unread_refreshing.discard(account_id)


@app.get("/api/accounts/private-unread-summary")
async def get_private_unread_summary(force: bool = False, scope: str = "mine", user: dict = Depends(get_current_user)):
    """Return unread private chat counts from the local DM event cache."""
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_accounts = session.exec(query_accounts_for_view_scope(session, user, scope)).all()

    result = {}
    for acc in db_accounts:
        cached = private_unread_cache.get(acc.id)
        external_unread = get_external_private_dm_unread(acc.id)
        skip_reason = get_private_poll_skip_reason(acc.id)
        base = cached or {"unread_dialogs": 0, "unread_messages": 0, "error": None, "updated_at": None}
        unread_dialogs = int(external_unread["external_unread_dialogs"] or 0)
        unread_messages = int(external_unread["external_unread_messages"] or 0)
        result[acc.id] = {
            **base,
            "unread_dialogs": unread_dialogs,
            "unread_messages": unread_messages,
            "external_unread_dialogs": unread_dialogs,
            "external_unread_messages": unread_messages,
            "last_private_event": external_unread["last_private_event"],
            "stale": False,
            "loading": False,
            "busy": bool(skip_reason),
            "error": skip_reason if skip_reason else base.get("error"),
            "updated_at": time.time(),
        }
    return result


@app.post("/api/accounts/{account_id}/private-dm-events/read")
async def mark_private_dm_events_read_api(account_id: str, user: dict = Depends(get_current_user)):
    check_account_company(account_id, user)
    mark_private_dm_events_read(account_id)
    return {"ok": True}


@app.post("/api/accounts/private-listeners/start-idle")
async def start_idle_private_listeners(req: Optional[PrivateListenerStartRequest] = Body(default=None), user: dict = Depends(get_current_user)):
    """Bring idle account clients online so private-message listeners can receive DMs."""
    global private_relay_enabled
    if not ENABLE_REALTIME_PRIVATE_DM:
        return {
            "started": [],
            "skipped": [],
            "failed": [],
            "disabled": True,
            "message": "实时私聊监听已关闭，请使用 Bot 通知/中转方案"
        }
    private_relay_enabled = True
    import services.shared_state
    services.shared_state.private_relay_enabled = True
    from db import engine, Session
    with Session(engine) as session:
        db_accounts = session.exec(query_allowed_accounts(session, user)).all()

    target_ids = set(req.account_ids or []) if req else set()
    started = []
    skipped = []
    failed = []

    for acc in db_accounts:
        if target_ids and acc.id not in target_ids:
            continue

        if getattr(acc, "is_available", True) is False:
            skipped.append({"account_id": acc.id, "name": acc.account_name, "reason": "账号当前为占用状态"})
            continue

        if not account_has_session_file(acc.id, acc):
            skipped.append({"account_id": acc.id, "name": acc.account_name, "reason": "未找到有效 session"})
            continue

        skip_reason = get_private_poll_skip_reason(acc.id)
        if skip_reason:
            skipped.append({"account_id": acc.id, "name": acc.account_name, "reason": skip_reason})
            continue

        try:
            ok = await ensure_private_listener_for_account(acc.id, acc.account_name or acc.id)
            if not ok:
                failed.append({"account_id": acc.id, "name": acc.account_name, "error": "账号未登录"})
                continue
            started.append({"account_id": acc.id, "name": acc.account_name})
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            failed.append({"account_id": acc.id, "name": acc.account_name, "error": detail})

    return {"started": started, "skipped": skipped, "failed": failed}


@app.post("/api/accounts/private-listeners/stop")
async def stop_private_listeners(user: dict = Depends(get_current_user)):
    """Stop realtime private-message relay listeners without touching account sessions on disk."""
    global private_relay_enabled
    private_relay_enabled = False
    import services.shared_state
    services.shared_state.private_relay_enabled = False


    stopped = []
    skipped = []
    target_ids = list(auto_private_listener_accounts)
    auto_private_listener_accounts.clear()
    auto_private_listener_cooldowns.clear()

    for account_id in target_ids:
        busy_reason = get_private_poll_skip_reason(account_id)
        client = active_clients.get(account_id)
        if busy_reason:
            skipped.append({"account_id": account_id, "reason": busy_reason})
            set_account_status(
                account_id,
                {"private_listener": False, "private_listener_source": None},
                source="private-listener-stop-busy"
            )
            continue

        if client:
            try:
                active_clients.pop(account_id, None)
                active_clients_last_accessed.pop(account_id, None)
                registered_listeners.discard(account_id)
                await _disconnect_client_safely(account_id, client)
                stopped.append({"account_id": account_id})
                set_account_status(
                    account_id,
                    {
                        "is_connected": False,
                        "private_listener": False,
                        "private_listener_source": None,
                    },
                    source="private-listener-stop"
                )
            except Exception as exc:
                skipped.append({"account_id": account_id, "reason": str(exc)})
                set_account_status(
                    account_id,
                    {"private_listener": False, "private_listener_source": None, "last_error": str(exc)},
                    source="private-listener-stop-error"
                )
        else:
            stopped.append({"account_id": account_id})
            set_account_status(
                account_id,
                {"private_listener": False, "private_listener_source": None},
                source="private-listener-stop"
            )

    return {"stopped": stopped, "skipped": skipped, "enabled": private_relay_enabled}


@app.get("/api/accounts/{account_id}/private-dialogs")
async def get_private_dialogs(account_id: str, limit: int = 30, cache_only: bool = False, user: dict = Depends(get_current_user)):
    check_account_company(account_id, user)
    if not ENABLE_REALTIME_PRIVATE_DM:
        cache_only = True
    started_at = time.time()
    cached_dialogs = get_cached_private_dialogs(account_id, limit)
    if cache_only:
        print(f"[PrivateDialogsTiming] account={account_id} total={int((time.time() - started_at) * 1000)}ms cache_only=1 count={len(cached_dialogs)}")
        return {"account_id": account_id, "dialogs": cached_dialogs, "cached": True, "cache_only": True}
    skip_reason = get_private_poll_skip_reason(account_id)
    if skip_reason:
        mark_private_dm_events_read(account_id)
        print(f"[PrivateDialogsTiming] account={account_id} total={int((time.time() - started_at) * 1000)}ms cache_only=1 reason={skip_reason} count={len(cached_dialogs)}")
        return {"account_id": account_id, "dialogs": cached_dialogs, "cached": True, "busy": True, "notice": skip_reason}

    async with account_operation_guard(account_id, "private_dialogs", label="读取私聊"):
        t0 = time.time()
        client = await get_client(account_id)
        get_client_ms = int((time.time() - t0) * 1000)
        t0 = time.time()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="账号未登录")
        auth_ms = int((time.time() - t0) * 1000)

        dialogs = []
        t0 = time.time()
        async for dialog in client.iter_dialogs(limit=max(1, min(limit, 200))):
            item = serialize_private_dialog(dialog)
            if item:
                dialogs.append(item)
        iter_ms = int((time.time() - t0) * 1000)
        cached_by_peer = {item["peer_id"]: item for item in cached_dialogs}
        for item in dialogs:
            cached_by_peer[item["peer_id"]] = item
        dialogs = list(cached_by_peer.values())
        dialogs.sort(key=lambda item: ((item.get("unread_count") or 0) > 0, item.get("last_message_at") or ""), reverse=True)
        t0 = time.time()
        mark_private_dm_events_read(account_id)
        ack_ms = int((time.time() - t0) * 1000)
        print(f"[PrivateDialogsTiming] account={account_id} total={int((time.time() - started_at) * 1000)}ms get_client={get_client_ms}ms auth={auth_ms}ms iter={iter_ms}ms ack={ack_ms}ms count={len(dialogs)}")
        return {"account_id": account_id, "dialogs": dialogs}


@app.get("/api/accounts/{account_id}/private-dialogs/{peer_id}/messages")
async def get_private_messages(account_id: str, peer_id: str, limit: int = 30, cache_only: bool = False, user: dict = Depends(get_current_user)):
    check_account_company(account_id, user)
    if not ENABLE_REALTIME_PRIVATE_DM:
        cache_only = True
    started_at = time.time()
    cached_messages = get_cached_private_messages(account_id, peer_id, limit)
    if cache_only:
        print(f"[PrivateMessagesTiming] account={account_id} peer={peer_id} total={int((time.time() - started_at) * 1000)}ms cache_only=1 count={len(cached_messages)}")
        return {"account_id": account_id, "peer_id": peer_id, "messages": cached_messages, "cached": True, "cache_only": True}
    skip_reason = get_private_poll_skip_reason(account_id)
    if skip_reason:
        mark_private_dm_events_read(account_id)
        print(f"[PrivateMessagesTiming] account={account_id} peer={peer_id} total={int((time.time() - started_at) * 1000)}ms cache_only=1 reason={skip_reason} count={len(cached_messages)}")
        return {"account_id": account_id, "peer_id": peer_id, "messages": cached_messages, "cached": True, "busy": True, "notice": skip_reason}

    async with account_operation_guard(account_id, "private_messages", label="读取私聊消息"):
        t0 = time.time()
        client = await get_client(account_id)
        get_client_ms = int((time.time() - t0) * 1000)
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="账号未登录")
        try:
            t0 = time.time()
            entity = await client.get_entity(int(peer_id))
            entity_ms = int((time.time() - t0) * 1000)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"私聊对象不存在: {exc}")
        if not isinstance(entity, types.User):
            raise HTTPException(status_code=400, detail="只支持私聊用户，不支持群聊或频道")
        if bool(getattr(entity, "bot", False)):
            raise HTTPException(status_code=400, detail="已排除 Bot 私聊")

        t0 = time.time()
        raw_messages = [msg async for msg in client.iter_messages(entity, limit=max(1, min(limit, 200)))]
        for msg in raw_messages:
            try:
                cache_private_message(account_id, entity, msg)
            except Exception:
                pass
        messages = [serialize_private_message(msg) for msg in raw_messages]
        iter_ms = int((time.time() - t0) * 1000)
        messages.reverse()
        cached_by_id = {str(msg.get("id")): msg for msg in cached_messages}
        for msg in messages:
            cached_by_id[str(msg.get("id"))] = msg
        messages = sorted(cached_by_id.values(), key=lambda msg: msg.get("date") or "")
        try:
            t0 = time.time()
            await client.send_read_acknowledge(entity)
            ack_tg_ms = int((time.time() - t0) * 1000)
        except Exception:
            ack_tg_ms = -1
        t0 = time.time()
        mark_private_dm_events_read(account_id)
        ack_local_ms = int((time.time() - t0) * 1000)
        print(f"[PrivateMessagesTiming] account={account_id} peer={peer_id} total={int((time.time() - started_at) * 1000)}ms get_client={get_client_ms}ms entity={entity_ms}ms iter={iter_ms}ms tg_ack={ack_tg_ms}ms local_ack={ack_local_ms}ms count={len(messages)}")
        return {"account_id": account_id, "peer_id": peer_id, "messages": messages}


@app.post("/api/accounts/{account_id}/private-dialogs/{peer_id}/send")
async def send_private_message(account_id: str, peer_id: str, req: PrivateMessageSendRequest, user: dict = Depends(get_current_user)):
    check_account_company(account_id, user)
    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="消息不能为空")
    busy_reason = get_private_poll_skip_reason(account_id)
    if busy_reason:
        queued = enqueue_private_send(account_id, peer_id, text, user.get("username", ""))
        return {
            "ok": True,
            "queued": True,
            "queue_id": queued["id"],
            "message": queued_private_message_payload(queued["id"], text),
            "notice": f"{busy_reason}，消息已加入高优先级发送队列。",
        }

    async with account_operation_guard(account_id, "private_send", label="发送私聊"):
        client = await get_client(account_id)
        message = await send_private_message_with_client(account_id, client, peer_id, text)
        return {"ok": True, "queued": False, "message": message}


class BotReplyPrivateDmRequest(BaseModel):
    account_id: str
    customer_id: str
    reply_text: str
    reply_to_msg_id: Optional[int] = None

@app.post("/api/bot/reply-private-dm")
async def bot_reply_private_dm(req: BotReplyPrivateDmRequest):
    account_id = req.account_id
    customer_id = req.customer_id
    reply_text = req.reply_text
    reply_to_msg_id = req.reply_to_msg_id

    # 检查逻辑忙碌状态
    busy_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if busy_reason:
        # 账号逻辑上正忙，将消息放入待发送私聊队列
        created_by_str = "bot"
        if reply_to_msg_id is not None:
            created_by_str = f"bot:reply_to:{reply_to_msg_id}"

        try:
            item = enqueue_private_send(
                account_id=account_id,
                peer_id=str(customer_id),
                text=reply_text,
                created_by=created_by_str
            )
            # 立即在后台触发一次清空尝试（若此时刚好在冷却期，物理锁未占，将立刻秒发）
            asyncio.create_task(drain_pending_private_sends(account_id))
            return {"ok": True, "queued": True, "queue_id": item["id"]}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"加入发送队列失败: {exc}")

    # 若账号闲置，直接并发安全发送，实现毫秒级送达
    async with account_operation_guard(account_id, "bot_reply", label="Bot中转回复"):
        try:
            client = await get_client(account_id)
            if not await client.is_user_authorized():
                raise HTTPException(status_code=401, detail="账号未登录")

            sent_msg = await send_private_message_with_client(
                account_id,
                client,
                str(customer_id),
                reply_text,
                reply_to_msg_id=reply_to_msg_id,
            )
            return {"ok": True, "queued": False, "message_id": sent_msg.get("id")}
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            if "Could not find the input entity" in detail:
                detail = "找不到目标用户的实体缓存(Could not find the input entity)。原因：此用户 ID 可能是测试脚本模拟的虚拟 ID，或者该账号的 Telethon Session 尚未与此用户建立过真实的私聊会话。请使用真实的小号主动私聊托管账号来进行测试。"
            raise HTTPException(status_code=500, detail=f"发送失败: {detail}")


class BotReplyViaThreadRequest(BaseModel):
    thread_id: int
    reply_text: str
    chat_id: Optional[int] = None


@app.post("/api/bot/reply-via-thread")
async def bot_reply_via_thread(req: BotReplyViaThreadRequest):
    thread_id = req.thread_id
    reply_text = req.reply_text
    chat_id = req.chat_id

    from private_dm_events import get_info_by_thread_id
    info = get_info_by_thread_id(thread_id, chat_id=chat_id)
    if not info:
        raise HTTPException(status_code=404, detail="找不到该主题(Thread)对应的会话映射，请确保已通过系统建立会话")

    account_id, customer_id = info

    sub_req = BotReplyPrivateDmRequest(
        account_id=account_id,
        customer_id=str(customer_id),
        reply_text=reply_text,
        reply_to_msg_id=None
    )
    return await bot_reply_private_dm(sub_req)


@app.get("/api/bot/export-folders")
async def bot_export_folders(account_id: str):
    busy_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if busy_reason:
        raise HTTPException(status_code=400, detail=f"账号当前正忙 ({busy_reason})，请稍后再试。")

    async with account_operation_guard(account_id, "export_folders", label="导出文件夹"):
        try:
            client = await get_client(account_id)
            if not await client.is_user_authorized():
                raise HTTPException(status_code=401, detail="账号未登录")

            result = await client(functions.messages.GetDialogFiltersRequest())
            raw_filters = getattr(result, "filters", result)
            filters = [
                item
                for item in raw_filters
                if isinstance(item, (types.DialogFilter, types.DialogFilterChatlist))
            ]

            from sync_folder_groups import collect_records, normalize_title
            include_types = {"group", "supergroup", "channel"}

            from db import engine, AccountDb, Session
            db_account_name = account_id
            with Session(engine) as db_session:
                acc_rec = db_session.get(AccountDb, account_id)
                if acc_rec and acc_rec.account_name:
                    db_account_name = acc_rec.account_name

            output_lines = [
                f"=========================================",
                f" 托管账号: {db_account_name} (ID: {account_id})",
                f" 导出时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"=========================================",
                ""
            ]
            for item in filters:
                folder_title = normalize_title(item.title)
                output_lines.append(f"{folder_title} (文件夹)")

                try:
                    records = await collect_records(client, item, include_types)
                    if records:
                        for r in records:
                            info_str = r.title
                            if r.username:
                                info_str += f" (t.me/{r.username})"
                            output_lines.append(f"- {info_str}")
                    else:
                        output_lines.append("- (空)")
                except Exception as e:
                    output_lines.append(f"- (读取出错: {e})")
                output_lines.append("")

            txt_content = "\n".join(output_lines)
            return {"ok": True, "content": txt_content}
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            raise HTTPException(status_code=500, detail=f"获取文件夹失败: {detail}")


@app.get("/api/bot/get-private-messages")
async def bot_get_private_messages(account_id: str, peer_id: str, limit: int = 15):
    cached_messages = get_cached_private_messages(account_id, peer_id, limit)

    if len(cached_messages) < 3:
        try:
            async with account_operation_guard(account_id, "bot_private_messages", label="Bot读取私聊历史"):
                client = await get_client(account_id)
                if await client.is_user_authorized():
                    try:
                        peer = int(peer_id)
                    except ValueError:
                        peer = peer_id
                    entity = await client.get_entity(peer)
                    raw_messages = [msg async for msg in client.iter_messages(entity, limit=limit)]
                    for msg in raw_messages:
                        try:
                            cache_private_message(account_id, entity, msg)
                        except Exception:
                            pass
                    cached_messages = [serialize_private_message(msg) for msg in raw_messages]
                    cached_messages.reverse()
        except Exception as exc:
            print(f"[BotGetMessages] Failed to fetch live messages: {exc}")

    return {"ok": True, "messages": cached_messages}


@app.get("/api/accounts/{account_id}/private-send-queue/{queue_id}")
def get_private_send_queue_status(account_id: str, queue_id: str, user: dict = Depends(get_current_user)):
    check_account_company(account_id, user)
    from db import engine, PrivateSendQueueDb, Session
    with Session(engine) as session:
        record = session.get(PrivateSendQueueDb, queue_id)
        if not record or str(record.account_id) != str(account_id):
            raise HTTPException(status_code=404, detail="排队消息不存在")
        sent_message = None
        if record.sent_message_json:
            try:
                sent_message = json.loads(record.sent_message_json)
            except Exception:
                sent_message = None
        return {
            "ok": True,
            "queue_id": record.id,
            "account_id": record.account_id,
            "peer_id": record.peer_id,
            "text": record.text,
            "status": record.status,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "sent_at": record.sent_at,
            "error": record.error,
            "message": sent_message,
        }


@app.get("/api/account-status/stream")
async def stream_account_status(token: Optional[str] = None):
    """Streams lightweight account status updates for the account-management page."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user_payload = verify_token(token)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    from db import engine, AdminDb, AccountDb, Session
    from sqlmodel import select
    with Session(engine) as session:
        db_user = session.exec(select(AdminDb).where(AdminDb.username == user_payload["username"])).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")
        user = {
            "username": db_user.username,
            "role": db_user.role,
            "company": db_user.company or "admin"
        }
        db_accounts = session.exec(query_allowed_accounts(session, user)).all()
        allowed_ids = {acc.id for acc in db_accounts}
        initial_payload = []
        for acc in db_accounts:
            status = normalize_account_status_patch(acc.id, account_status_store.get(acc.id, {}))
            initial_payload.append({
                "account_id": acc.id,
                "patch": {
                    **status,
                    "is_available": acc.is_available,
                    "availability_status": "available" if acc.is_available else "occupied",
                    "bot_setup_status": acc.bot_setup_status or status.get("bot_setup_status", "not_started")
                }
            })

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    account_status_subscribers.add(queue)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'initial', 'accounts': initial_payload}, ensure_ascii=False)}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=25)
                    try:
                        decoded = json.loads(payload)
                        if decoded.get("account_id") not in allowed_ids:
                            continue
                    except Exception:
                        pass
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            account_status_subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/private-dm/stream")
async def stream_private_dm_events(token: Optional[str] = None):
    """Streams private DM events to the account-management page."""
    if not ENABLE_REALTIME_PRIVATE_DM:
        async def disabled_generator():
            yield "data: {\"type\": \"info\", \"message\": \"实时私聊已关闭\"}\n\n"
            while True:
                await asyncio.sleep(60)
                yield "event: ping\ndata: {}\n\n"
        return StreamingResponse(disabled_generator(), media_type="text/event-stream")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user_payload = verify_token(token)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    from db import engine, AdminDb, Session
    from sqlmodel import select
    with Session(engine) as session:
        db_user = session.exec(select(AdminDb).where(AdminDb.username == user_payload["username"])).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")
        user = {
            "username": db_user.username,
            "role": db_user.role,
            "company": db_user.company or "admin"
        }
        allowed_accounts = session.exec(query_allowed_accounts(session, user)).all()
        allowed_ids = {acc.id for acc in allowed_accounts}
        allowed_account_meta = {
            str(acc.id): {
                "account_label": acc.account_name or acc.id,
                "account_owner_username": acc.owner_username or "",
                "account_created_by": acc.created_by or "",
                "account_company": acc.company or "",
            }
            for acc in allowed_accounts
        }

    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    private_dm_subscribers.add(queue)
    sent_keys: set[str] = set()
    stream_started_at = time.time()
    last_file_seen_at = stream_started_at

    async def event_generator():
        nonlocal last_file_seen_at
        try:
            yield f"data: {json.dumps({'type': 'ready'}, ensure_ascii=False)}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=2)
                    try:
                        decoded = json.loads(payload)
                        event = decoded.get("event") or {}
                        if str(event.get("account_id") or "") not in allowed_ids:
                            continue
                        event.update(allowed_account_meta.get(str(event.get("account_id") or ""), {}))
                        key = private_dm_event_key(event)
                        if key in sent_keys:
                            continue
                        sent_keys.add(key)
                    except Exception:
                        pass
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    emitted = False
                    for event in read_private_dm_events(allowed_ids, limit=200):
                        account_id = str(event.get("account_id") or "")
                        event_time = float(event.get("created_at") or event.get("timestamp") or 0)
                        ack_ts = float(private_dm_event_ack.get(account_id, 0) or 0)
                        if event_time <= max(last_file_seen_at, ack_ts):
                            continue
                        if bool(event.get("out", False)):
                            continue
                        if not bool(event.get("notify", False)):
                            continue
                        event = {**event, **allowed_account_meta.get(account_id, {})}
                        key = private_dm_event_key(event)
                        if key in sent_keys:
                            continue
                        sent_keys.add(key)
                        merge_private_dm_event_into_cache(event)
                        yield f"data: {json.dumps({'type': 'private_dm', 'event': event}, ensure_ascii=False)}\n\n"
                        emitted = True
                    last_file_seen_at = time.time()
                    if not emitted:
                        yield "event: ping\ndata: {}\n\n"
        finally:
            private_dm_subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/accounts/{account_id}/toggle-status")
def toggle_account_status(account_id: str, user: dict = Depends(get_current_user)):
    """Toggles the availability status (is_available) of a configured account."""
    block_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if block_reason:
        raise HTTPException(status_code=409, detail=f"{block_reason}，请等待完成后再切换账号状态。")
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)
        if not db_account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Check permissions
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and db_account.company != user["company"]:
            raise HTTPException(status_code=403, detail="Permission denied")

        db_account.is_available = not db_account.is_available
        session.add(db_account)
        session.commit()
        session.refresh(db_account)

        # Sync changes to JSON configs
        try:
            from account_manager import account_config_path, save_json
            path = account_config_path(db_account.id)
            save_json(path, db_account.to_dict())
        except Exception as e:
            print(f"Failed to sync toggled account to json config: {e}")
        set_account_status(
            account_id,
            {
                "is_available": db_account.is_available,
                "availability_status": "available" if db_account.is_available else "occupied"
            },
            source="toggle-status"
        )

        return {"status": "success", "is_available": db_account.is_available}

@app.post("/api/accounts/{account_id}/reset-lock")
def reset_account_lock(account_id: str, user: dict = Depends(get_current_user)):
    """Manually clear stale in-memory operation locks for an account."""
    check_account_company_scope(account_id, user)
    active_account_operations.pop(account_id, None)
    lock = account_operation_locks.get(account_id)
    if lock and lock.locked():
        # asyncio.Lock has no owner tracking; replacing a stale lock is safer
        # than trying to release a lock that may belong to an active request.
        account_operation_locks[account_id] = asyncio.Lock()
    set_account_status(
        account_id,
        {
            "active_operation": None,
            "active_operation_label": None,
            "error": None,
            "last_error": None,
        },
        source="reset-lock",
    )
    return {"status": "success"}

# --- TELEGRAM BOT COOPERATION API ---

def check_local_bot_approval(telegram_id: int, phone: str) -> bool:
    try:
        import json
        from pathlib import Path
        bot_dir = Path("E:/telegram_translate_bot_workspace")
        access_path = bot_dir / "data" / "translate_access.json"

        # Check translate_access.json
        if access_path.exists():
            with open(access_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                allowed_ids = data.get("allowed_user_ids", [])
                if telegram_id in allowed_ids or str(telegram_id) in allowed_ids:
                    return True

        # Check access_requests.json
        requests_path = bot_dir / "data" / "access_requests.json"
        if requests_path.exists():
            with open(requests_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                requests = data.get("requests", {})
                for uid, req in requests.items():
                    if req.get("status") == "approved":
                        # Check telegram_id
                        if req.get("user_id") == telegram_id or str(req.get("user_id")) == str(telegram_id):
                            return True
                        # Check phone match
                        req_phone = str(req.get("phone_number", "")).replace("+", "").replace(" ", "").strip()
                        clean_phone = str(phone).replace("+", "").replace(" ", "").strip()
                        if req_phone == clean_phone:
                            return True
    except Exception as e:
        print(f"Error checking local bot approval status: {e}")
    return False

def approve_local_bot_access(telegram_id: int, phone: str, name: str, username: str):
    try:
        import json
        import time
        from pathlib import Path
        bot_dir = Path("E:/telegram_translate_bot_workspace")
        data_dir = bot_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # 1. Update translate_access.json
        access_path = data_dir / "translate_access.json"
        access_data = {"allowed_usernames": [], "allowed_user_ids": [], "allowed_chat_ids": [], "owner_chat_ids": []}
        if access_path.exists():
            try:
                with open(access_path, "r", encoding="utf-8") as f:
                    access_data = json.load(f)
            except Exception:
                pass

        allowed_ids = access_data.setdefault("allowed_user_ids", [])
        if telegram_id not in allowed_ids:
            allowed_ids.append(telegram_id)
        access_data["allowed_user_ids"] = sorted(list(set(allowed_ids)))

        with open(access_path, "w", encoding="utf-8") as f:
            json.dump(access_data, f, indent=2, ensure_ascii=False)

        # 2. Update access_requests.json
        requests_path = data_dir / "access_requests.json"
        requests_data = {"requests": {}}
        if requests_path.exists():
            try:
                with open(requests_path, "r", encoding="utf-8") as f:
                    requests_data = json.load(f)
            except Exception:
                pass

        requests = requests_data.setdefault("requests", {})
        clean_phone = phone if phone.startswith("+") else f"+{phone}"
        requests[str(telegram_id)] = {
            "user_id": telegram_id,
            "name": name,
            "username": username if username.startswith("@") else f"@{username}" if username else "(no username)",
            "phone_number": clean_phone,
            "status": "approved",
            "created_at": int(time.time()),
            "reviewed_at": int(time.time())
        }

        with open(requests_path, "w", encoding="utf-8") as f:
            json.dump(requests_data, f, indent=2, ensure_ascii=False)

        print(f"Successfully wrote local bot authorization for Telegram ID {telegram_id} ({phone})")
    except Exception as e:
        print(f"Error writing local bot authorization: {e}")

async def auto_trigger_bot_setup_for_account(account_id: str, client):
    try:
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_acc = session.get(AccountDb, account_id)
            if not db_acc:
                return
            if db_acc.bot_setup_status == "approved":
                return

            bot_username = "RosePay_translation_bot"
            import asyncio
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                return

            me = await client.get_me()
            if not me or not me.phone:
                return

            # 1. Check if already approved locally
            if check_local_bot_approval(me.id, me.phone):
                db_acc.bot_setup_status = "approved"
                db_acc.bot_username = bot_username
                session.add(db_acc)
                session.commit()
                try:
                    from account_manager import account_config_path, save_json
                    save_json(account_config_path(db_acc.id), db_acc.to_dict())
                except Exception:
                    pass
                return

            # 2. Send /start
            bot_entity = await client.get_input_entity(bot_username)
            await client.send_message(bot_entity, "/start")

            # 3. Wait 1.5 seconds
            await asyncio.sleep(1.5)

            # 4. Click the "apply_access" callback button if present
            try:
                messages = await client.get_messages(bot_entity, limit=5)
                for msg in messages:
                    if msg.buttons:
                        clicked = False
                        for row in msg.buttons:
                            for button in row:
                                if button.data == b'apply_access':
                                    await msg.click(button)
                                    clicked = True
                                    break
                            if clicked:
                                break
                        if clicked:
                            break
            except Exception as btn_ex:
                print(f"Failed to click callback button: {btn_ex}")

            # 5. Wait 1.5 seconds
            await asyncio.sleep(1.5)

            # 6. Send contact card
            from telethon import types
            await client.send_message(
                bot_entity,
                file=types.InputMediaContact(
                    phone_number=me.phone,
                    first_name=me.first_name or "",
                    last_name=me.last_name or "",
                    vcard=""
                )
            )

            # 7. Wait 1.5 seconds for bot to process
            await asyncio.sleep(1.5)

            # 8. Pin Dialog
            try:
                from telethon.tl.functions.messages import ToggleDialogPinRequest
                try:
                    await client(ToggleDialogPinRequest(peer=bot_entity, pinned=True))
                except Exception:
                    pass
            except Exception:
                pass

            # 9. Write local authorization to files
            name = f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}"
            username = me.username or ""
            approve_local_bot_access(me.id, me.phone, name, username)

            # 10. Send message from bot
            bot_token = None
            try:
                from pathlib import Path
                env_path = Path("E:/telegram_translate_bot_workspace/.env")
                if env_path.exists():
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("BOT_TOKEN="):
                                bot_token = line.split("=", 1)[1].strip()
                                break
            except Exception:
                pass
            if not bot_token:
                bot_token = "8998918901:AAFSSlT0P1pWUdXgpVZ4weDFMUdcmTdCheI"

            if bot_token:
                try:
                    import httpx
                    notification_text = "✅ 你的 RosePay 翻译机器人使用权限已通过。\n现在可以直接发送文字或使用 /tr 翻译。"
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    async with httpx.AsyncClient(**telegram_httpx_client_kwargs("web_server_translate_bot_api")) as http_client:
                        await http_client.post(url, json={
                            "chat_id": me.id,
                            "text": notification_text
                        })
                except Exception:
                    pass

            # 11. Update DB to approved
            db_acc.bot_setup_status = "approved"
            db_acc.bot_username = bot_username
            db_acc.bot_step_1_input = me.phone
            session.add(db_acc)
            session.commit()

            # Sync to disk
            try:
                from account_manager import account_config_path, save_json
                save_json(account_config_path(db_acc.id), db_acc.to_dict())
            except Exception:
                pass

            print(f"Successfully auto-configured BOT for imported/logged in account {account_id}")
    except Exception as e:
        print(f"Failed to auto-configure BOT for account {account_id}: {e}")

async def check_and_update_bot_approval_status(account_id: str, client, session) -> str:
    """Checks local bot files and dialog history with @RosePay_translation_bot to see if it is approved.
    Updates the database status to 'approved' or 'pending_approval' if needed.
    Acquires the account client lock safely.
    Returns the current/new status.
    """
    from db import AccountDb
    from telethon import types

    db_acc = session.get(AccountDb, account_id)
    if not db_acc:
        return "not_started"

    current_status = db_acc.bot_setup_status or "not_started"
    if current_status == "approved":
        return "approved"

    bot_username = db_acc.bot_username or "RosePay_translation_bot"

    # 1. First check if logged in and check local bot authorization files
    try:
        if client.is_connected() and await client.is_user_authorized():
            me = await client.get_me()
            if me:
                if check_local_bot_approval(me.id, me.phone):
                    db_acc.bot_setup_status = "approved"
                    db_acc.bot_username = bot_username
                    session.add(db_acc)
                    session.commit()
                    try:
                        from account_manager import account_config_path, save_json
                        save_json(account_config_path(db_acc.id), db_acc.to_dict())
                    except Exception:
                        pass
                    return "approved"
    except Exception as local_ex:
        print(f"Error in check_local_bot_approval within check_and_update: {local_ex}")

    # 2. Fallback to Telegram message check
    if account_id not in client_locks:
        client_locks[account_id] = asyncio.Lock()

    try:
        async with client_locks[account_id]:
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                return current_status

            # Get last 10 messages from bot
            messages = await client.get_messages(bot_username, limit=10)

            is_approved = False
            has_contact_card = False

            for m in messages:
                text = m.text or ""
                if "使用权限已通过" in text or "拥有使用权限" in text:
                    is_approved = True
                    break
                # Check if a contact card was sent by current account (outgoing)
                if m.out and getattr(m, 'media', None):
                    if isinstance(m.media, types.MessageMediaContact):
                        has_contact_card = True

            new_status = current_status
            if is_approved:
                new_status = "approved"
                # Since we found it is approved on telegram, sync it to local bot files as well!
                try:
                    me = await client.get_me()
                    if me:
                        name = f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}"
                        username = me.username or ""
                        approve_local_bot_access(me.id, me.phone, name, username)
                except Exception as sync_ex:
                    print(f"Failed to sync approved state to local files: {sync_ex}")
            elif has_contact_card and current_status == "not_started":
                new_status = "pending_approval"

            if new_status != current_status:
                db_acc.bot_setup_status = new_status
                db_acc.bot_username = bot_username
                session.add(db_acc)
                session.commit()
                # Sync to JSON config
                try:
                    from account_manager import account_config_path, save_json
                    save_json(account_config_path(db_acc.id), db_acc.to_dict())
                except Exception as e:
                    print(f"Failed to sync bot status to config: {e}")

            return new_status
    except Exception as e:
        print(f"Error checking bot approval status for {account_id}: {e}")
        return current_status

@app.get("/api/accounts/{account_id}/bot/status")
@account_api_operation("bot_status", label="检查 Bot 授权")
async def get_account_bot_status(account_id: str, user: dict = Depends(get_current_user)):
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_acc = session.get(AccountDb, account_id)
        if not db_acc:
            raise HTTPException(status_code=404, detail="Account not found")
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and db_acc.company != user["company"]:
            raise HTTPException(status_code=403, detail="Permission denied")

        bot_username = db_acc.bot_username or "RosePay_translation_bot"
        current_status = db_acc.bot_setup_status or "not_started"

        # If it is not approved yet, check message history with the bot to see if approval text exists
        if current_status != "approved":
            try:
                client = await get_client(account_id)
                if client:
                    current_status = await check_and_update_bot_approval_status(account_id, client, session)
            except Exception as e:
                print(f"Error checking bot approval status for {account_id}: {e}")

        return {
            "account_id": account_id,
            "bot_setup_status": current_status,
            "bot_username": bot_username
        }

@app.post("/api/accounts/{account_id}/bot/start")
@account_api_operation("bot_setup", label="配置 Bot")
async def start_account_bot_setup(account_id: str, user: dict = Depends(get_current_user)):
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_acc = session.get(AccountDb, account_id)
        if not db_acc:
            raise HTTPException(status_code=404, detail="Account not found")
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and db_acc.company != user["company"]:
            raise HTTPException(status_code=403, detail="Permission denied")

        bot_username = "RosePay_translation_bot"
        try:
            import asyncio
            client = await get_client(account_id)
            async with client_locks[account_id]:
                if not client.is_connected():
                    await client.connect()
                if not await client.is_user_authorized():
                    raise HTTPException(status_code=400, detail="账号未登录，无法配置 Bot")

                me = await client.get_me()
                if not me or not me.phone:
                    raise HTTPException(status_code=400, detail="获取当前账号手机号失败")

                # 1. Check if already approved locally
                if check_local_bot_approval(me.id, me.phone):
                    db_acc.bot_setup_status = "approved"
                    db_acc.bot_username = bot_username
                    session.add(db_acc)
                    session.commit()
                    try:
                        from account_manager import account_config_path, save_json
                        save_json(account_config_path(db_acc.id), db_acc.to_dict())
                    except Exception:
                        pass
                    return {"status": "success", "bot_setup_status": "approved"}

                # 2. Send /start
                bot_entity = await client.get_input_entity(bot_username)
                await client.send_message(bot_entity, "/start")

                # 3. Wait 1.5 seconds
                await asyncio.sleep(1.5)

                # 4. Click the "apply_access" callback button if present
                try:
                    messages = await client.get_messages(bot_entity, limit=5)
                    for msg in messages:
                        if msg.buttons:
                            clicked = False
                            for row in msg.buttons:
                                for button in row:
                                    if button.data == b'apply_access':
                                        await msg.click(button)
                                        clicked = True
                                        break
                                if clicked:
                                    break
                            if clicked:
                                break
                except Exception as btn_ex:
                    print(f"Failed to click callback button: {btn_ex}")

                # 5. Wait 1.5 seconds
                await asyncio.sleep(1.5)

                # 6. Send contact card
                from telethon import types
                await client.send_message(
                    bot_entity,
                    file=types.InputMediaContact(
                        phone_number=me.phone,
                        first_name=me.first_name or "",
                        last_name=me.last_name or "",
                        vcard=""
                    )
                )

                # 7. Wait 1.5 seconds for bot to process
                await asyncio.sleep(1.5)

                # 8. Pin Dialog
                try:
                    from telethon.tl.functions.messages import ToggleDialogPinRequest
                    from telethon.tl.types import InputDialogPeer
                    try:
                        await client(ToggleDialogPinRequest(
                            peer=InputDialogPeer(peer=bot_entity),
                            pinned=True
                        ))
                    except Exception:
                        await client(ToggleDialogPinRequest(
                            peer=bot_entity,
                            pinned=True
                        ))
                except Exception as pin_ex:
                    print(f"Pin dialog failed for {account_id}: {pin_ex}")

                # 9. Programmatically write local authorization to files
                name = f"{me.first_name or ''} {me.last_name or ''}".strip() or f"User_{me.id}"
                username = me.username or ""
                approve_local_bot_access(me.id, me.phone, name, username)

                # 10. Send a message to the user from the bot using HTTP API
                bot_token = None
                try:
                    from pathlib import Path
                    env_path = Path("E:/telegram_translate_bot_workspace/.env")
                    if env_path.exists():
                        with open(env_path, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip().startswith("BOT_TOKEN="):
                                    bot_token = line.split("=", 1)[1].strip()
                                    break
                except Exception as env_ex:
                    print(f"Failed to read BOT_TOKEN from bot .env: {env_ex}")

                if not bot_token:
                    bot_token = "8998918901:AAFSSlT0P1pWUdXgpVZ4weDFMUdcmTdCheI"

                if bot_token:
                    try:
                        import httpx
                        notification_text = "✅ 你的 RosePay 翻译机器人使用权限已通过。\n现在可以直接发送文字或使用 /tr 翻译。"
                        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                        async with httpx.AsyncClient(**telegram_httpx_client_kwargs("web_server_translate_bot_api")) as http_client:
                            resp = await http_client.post(url, json={
                                "chat_id": me.id,
                                "text": notification_text
                            })
                            if resp.status_code == 200:
                                print(f"Sent approval notification to chat {me.id} successfully")
                            else:
                                print(f"Failed to send approval notification: {resp.text}")
                    except Exception as notify_ex:
                        print(f"Notification send exception: {notify_ex}")

            # 11. Update DB to approved
            db_acc.bot_setup_status = "approved"
            db_acc.bot_username = bot_username
            db_acc.bot_step_1_input = me.phone
            session.add(db_acc)
            session.commit()

            # Sync to disk
            try:
                from account_manager import account_config_path, save_json
                save_json(account_config_path(db_acc.id), db_acc.to_dict())
            except Exception:
                pass

            return {"status": "success", "bot_setup_status": "approved"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"与 Bot 静默配置并自动审批失败: {str(e)}")

@app.post("/api/accounts/{account_id}/bot/step1")
async def submit_bot_step1(account_id: str, req: BotStepRequest, user: dict = Depends(get_current_user)):
    return {"status": "success", "bot_setup_status": "approved"}

@app.post("/api/accounts/{account_id}/bot/step2")
async def submit_bot_step2(account_id: str, req: BotStepRequest, user: dict = Depends(get_current_user)):
    return {"status": "success", "bot_setup_status": "approved"}

@app.post("/api/accounts/{account_id}/bot/approve")
async def approve_bot_setup(account_id: str, user: dict = Depends(get_current_user)):
    return {"status": "success", "bot_setup_status": "approved"}


@app.post("/api/accounts/create")
def create_new_account(req: AccountCreateRequest, user: dict = Depends(get_current_user)):
    """Creates a new account configuration."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Account name cannot be empty")

    # Generate account ID
    from account_manager import account_id_from_name
    account_id = account_id_from_name(name)

    # Check if exists in DB
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        existing = session.get(AccountDb, account_id)
        if existing:
            raise HTTPException(status_code=400, detail="Account ID already exists")

        template_path = Path(__file__).resolve().parent / "config.json"
        if not template_path.exists():
            template_path = Path(__file__).resolve().parent / "config.example.json"

        if not template_path.exists():
            template = {
                "auth_mode": "builtin_telegram_desktop",
                "folder_name": "广告",
                "connection_timeout_seconds": 12,
                "connection_retries": 2,
                "proxy": {"enabled": False, "type": "http", "host": "127.0.0.1", "port": 8800, "username": "", "password": ""}
            }
        else:
            template = load_json(template_path)

        config = build_account_config(account_id, name, template)
        config["company"] = user["company"]
        config["created_by"] = user["username"]
        config["updated_by"] = user["username"]
        config["owner_username"] = user["username"]

        # Save to DB
        db_account = AccountDb.from_dict(account_id, config)
        session.add(db_account)
        session.commit()

        # Sync to disk
        path = account_config_path(account_id)
        save_json(path, db_account.to_dict())

    return {"id": account_id, "name": name}

@app.post("/api/accounts/{account_id}/config")
def update_account_config(account_id: str, req: AccountConfigRequest, user: dict = Depends(get_current_user)):
    """Updates proxy and details for an account configuration."""
    db_account = check_account_company(account_id, user)
    block_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if block_reason:
        raise HTTPException(status_code=409, detail=f"{block_reason}，请等待完成后再修改配置。")
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)
        old_owner_username = db_account.owner_username or db_account.created_by or ""

        db_account.account_name = req.account_name
        db_account.folder_name = req.folder_name
        db_account.proxy_enabled = req.proxy.enabled
        db_account.proxy_type = req.proxy.type
        db_account.proxy_host = req.proxy.host
        db_account.proxy_port = req.proxy.port
        db_account.proxy_username = req.proxy.username
        db_account.proxy_password = req.proxy.password
        db_account.updated_by = user["username"]

        if user["role"] == "admin":
            if req.owner_username is not None:
                db_account.owner_username = req.owner_username.strip()
        else:
            if req.owner_username is not None:
                target_owner = req.owner_username.strip()
                if target_owner == "":
                    db_account.owner_username = db_account.created_by or "admin"
                else:
                    from db import AdminDb
                    target_user = session.exec(select(AdminDb).where(AdminDb.username == target_owner)).first()
                    if not target_user or target_user.company != user["company"]:
                        raise HTTPException(status_code=403, detail="只能指派归属给同公司的成员")
                    db_account.owner_username = target_owner

        session.add(db_account)
        session.commit()

        config = db_account.to_dict()

        # Sync to disk
        path = account_config_path(account_id)
        save_json(path, config)

    # Close any active client in memory to force reloading config
    close_active_client_after_config_change(account_id)

    new_owner_username = config.get("owner_username") or config.get("created_by") or ""
    if new_owner_username != old_owner_username:
        send_ops_bot_notification(
            "\n".join([
                "👤 <b>账号归属已变更</b>",
                html_line("账号", get_account_notify_label(account_id)),
                html_line("原归属", get_user_notify_label(old_owner_username)),
                html_line("新归属", get_user_notify_label(new_owner_username)),
                html_line("操作人", get_user_notify_label(user["username"])),
                html_line("时间", ops_event_time()),
            ])
        )

    return {"status": "success", "config": config}

@app.post("/api/accounts/{account_id}/local-credentials")
def update_local_credentials(account_id: str, req: LocalCredentialsRequest, user: dict = Depends(get_current_user)):
    """Saves page_id or pass2fa directly to database and config file locally without modifying Telegram settings."""
    db_account = check_account_company(account_id, user)
    block_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if block_reason:
        raise HTTPException(status_code=409, detail=f"{block_reason}，请等待完成后再修改本地凭据。")
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)

        if req.pass2fa is not None:
            db_account.pass2fa = req.pass2fa.strip() or None
        if req.page_id is not None:
            db_account.page_id = req.page_id.strip() or None
        db_account.updated_by = user["username"]

        session.add(db_account)
        session.commit()

        config = db_account.to_dict()
        path = account_config_path(account_id)
        save_json(path, config)

    return {"status": "success", "config": config}

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str, user: dict = Depends(get_current_user)):
    """Deletes an account configuration and its session files.
    Admins can delete any account. Normal users (employees) can only delete accounts that are NOT authorized (never logged in successfully)."""
    db_account = check_account_company(account_id, user)

    # 权限校验：如果当前账号已经是已登录成功状态，普通员工无权删除
    is_auth = False
    try:
        status = get_account_status(account_id)
        is_auth = bool(status.get("is_authorized") or status.get("auth_status") == "authorized")
    except Exception:
        pass

    if is_auth and user.get("role") != "admin" and user.get("username") not in ("eason", "admin"):
        raise HTTPException(status_code=403, detail="只有管理员才能删除已成功登录的托管账号")

    block_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if block_reason:
        raise HTTPException(status_code=409, detail=f"{block_reason}，请等待完成后再删除账号。")
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)

    # 1. Stop active campaign process
    if account_id in active_processes:
        process = active_processes[account_id]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        active_processes.pop(account_id, None)

    # 2. Disconnect active Telethon client
    if account_id in active_clients:
        client = active_clients.pop(account_id)
        registered_listeners.discard(account_id)
        try:
            await client.disconnect()
        except Exception:
            pass

    # 3. Delete config file
    config_path = account_config_path(account_id)
    if config_path.exists():
        try:
            config_path.unlink()
        except Exception as e:
            print(f"Failed to delete config file: {e}")

    # 4. Delete from DB
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)
        if db_account:
            session.delete(db_account)
            session.commit()

    # 5. Delete session files
    base_dir = config_path.parent.parent
    session_path = base_dir / "sessions" / account_id / "telegram_user"
    for suffix in ["", ".session", ".session-journal"]:
        target = session_path.parent / f"{session_path.name}{suffix}"
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass

    # Also delete sessions directory if empty
    sessions_dir = base_dir / "sessions" / account_id
    if sessions_dir.exists() and sessions_dir.is_dir():
        import shutil
        try:
            shutil.rmtree(sessions_dir, ignore_errors=True)
        except Exception:
            pass

    return {"status": "success", "message": f"Account {account_id} deleted successfully"}

@app.post("/api/accounts/{account_id}/clear-session")
@account_api_operation("clear_session", label="清理 Session")
async def clear_account_session(account_id: str, user: dict = Depends(get_current_user)):
    """Clears the session files for an account, forcing re-authentication."""
    db_account = check_account_company(account_id, user)
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)

    # 1. Disconnect active Telethon client
    if account_id in active_clients:
        client = active_clients.pop(account_id)
        registered_listeners.discard(account_id)
        try:
            await client.disconnect()
        except Exception:
            pass

    config_path = account_config_path(account_id)
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Account not found")

    # 2. Delete session files
    base_dir = config_path.parent.parent
    session_path = base_dir / "sessions" / account_id / "telegram_user"
    deleted_some = False
    for suffix in ["", ".session", ".session-journal"]:
        target = session_path.parent / f"{session_path.name}{suffix}"
        if target.exists():
            try:
                target.unlink()
                deleted_some = True
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to delete session file: {str(e)}")

    return {"status": "success", "message": "Session cleared successfully" if deleted_some else "No active session found"}

@app.post("/api/accounts/{account_id}/profile/name")
@account_api_operation("profile_name", label="修改资料")
async def update_profile_name(account_id: str, req: ProfileNameRequest, user: dict = Depends(get_current_user)):
    """Updates Telegram profile first name, last name and bio."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        about_text = req.about.strip() if req.about is not None else None
        if about_text and len(about_text) > 70:
            about_text = about_text[:70]

        await client(functions.account.UpdateProfileRequest(
            first_name=req.first_name,
            last_name=req.last_name or "",
            about=about_text
        ))

        # Update database
        from db import engine, AccountDb, Session
        new_name = f"{req.first_name} {req.last_name or ''}".strip()
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                db_account.account_name = new_name
                db_account.profile_modified = True
                db_account.profile_modified_name = new_name
                db_account.updated_by = user["username"]
                session.add(db_account)
                session.commit()
                # sync config JSON
                path = account_config_path(account_id)
                save_json(path, db_account.to_dict())

        # Update runtime status store
        status = account_status_store.get(account_id, {})
        me_str = status.get("me", "")
        username_part = ""
        if "(" in me_str and me_str.endswith(")"):
            username_part = me_str[me_str.find("("):]
        set_account_status(
            account_id,
            {
                "is_connected": True,
                "is_authorized": True,
                "me": f"{new_name} {username_part}".strip()
            },
            source="profile-name"
        )

        return {"status": "success", "message": "Profile name updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile name: {str(e)}")

@app.post("/api/accounts/{account_id}/profile/about")
@account_api_operation("profile_about", label="修改简介")
async def update_profile_about(account_id: str, req: ProfileAboutRequest, user: dict = Depends(get_current_user)):
    """Updates Telegram profile description / bio / about."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        about_text = req.about.strip()
        if len(about_text) > 70:
            raise HTTPException(status_code=400, detail="Bio must not exceed 70 characters")

        await client(functions.account.UpdateProfileRequest(
            about=about_text
        ))

        # Update database
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                db_account.profile_modified = True
                db_account.updated_by = user["username"]
                session.add(db_account)
                session.commit()
                # sync config JSON
                path = account_config_path(account_id)
                save_json(path, db_account.to_dict())

        return {"status": "success", "message": "Profile bio updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile bio: {str(e)}")

@app.post("/api/accounts/{account_id}/profile/username")
@account_api_operation("profile_username", label="修改用户名")
async def update_profile_username(account_id: str, req: ProfileUsernameRequest, user: dict = Depends(get_current_user)):
    """Updates Telegram username."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        new_username = req.username.strip().replace("@", "")
        await client(functions.account.UpdateUsernameRequest(
            username=new_username
        ))

        # Update database
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                db_account.profile_modified = True
                db_account.profile_modified_username = new_username
                db_account.updated_by = user["username"]
                session.add(db_account)
                session.commit()
                # sync config JSON
                path = account_config_path(account_id)
                save_json(path, db_account.to_dict())

        # Update runtime status store
        status = account_status_store.get(account_id, {})
        me_str = status.get("me", "")
        display_name = me_str
        if "(" in me_str:
            display_name = me_str[:me_str.find("(")].strip()
        set_account_status(
            account_id,
            {
                "is_connected": True,
                "is_authorized": True,
                "me": f"{display_name} (@{new_username})" if new_username else display_name
            },
            source="profile-username"
        )

        return {"status": "success", "message": "Username updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update username: {str(e)}")

def profile_name_to_username_part(value: str, *, keep_case: bool = False) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        from pypinyin import lazy_pinyin
        converted = "".join(lazy_pinyin(raw))
    except Exception:
        known = {item["name"]: item["pinyin"] for item in HISTORICAL_FIGURES}
        converted = known.get(raw, raw)
    converted = re.sub(r"[^a-zA-Z0-9]+", "", converted)
    if not keep_case:
        converted = converted.lower()
    return converted

def build_profile_username(first_name: str, last_name: str) -> str:
    first_part = profile_name_to_username_part(first_name, keep_case=True)
    last_part = profile_name_to_username_part(last_name, keep_case=False)
    base = f"{first_part}_{last_part}" if last_part else first_part
    base = re.sub(r"_+", "_", base).strip("_")
    if len(base) < 5:
        base = (base + "00000")[:5]
    return base[:32]

def append_username_suffix(base_username: str, suffix: str) -> str:
    suffix = str(suffix)
    max_base_len = max(1, 32 - len(suffix))
    return f"{base_username[:max_base_len].rstrip('_')}{suffix}"

async def set_available_profile_username(client: TelegramClient, base_username: str) -> Tuple[str, int]:
    import random
    import string

    base_username = re.sub(r"[^a-zA-Z0-9_]", "", base_username or "")
    if len(base_username) < 5:
        base_username = (base_username + "00000")[:5]
    candidates = [base_username[:32]]
    for _ in range(18):
        suffix = random.choice(string.ascii_lowercase + string.digits)
        candidates.append(append_username_suffix(base_username, suffix))
    for _ in range(12):
        suffix = f"_{random.randint(10, 99)}"
        candidates.append(append_username_suffix(base_username, suffix))

    last_error = ""
    for attempt, candidate in enumerate(dict.fromkeys(candidates), start=1):
        try:
            available = await client(functions.account.CheckUsernameRequest(username=candidate))
            if not available:
                last_error = f"{candidate} 已被占用"
                continue
        except Exception as check_exc:
            last_error = str(check_exc)
            if any(token in last_error.lower() for token in ["occupied", "taken", "usernameoccupied"]):
                continue
        try:
            await client(functions.account.UpdateUsernameRequest(username=candidate))
            return candidate, attempt
        except Exception as update_exc:
            last_error = str(update_exc)
            if any(token in last_error.lower() for token in ["occupied", "taken", "usernameoccupied"]):
                continue
            if any(token in last_error.lower() for token in ["invalid", "usernameinvalid"]):
                continue
            continue
    raise HTTPException(status_code=409, detail=f"自动生成用户名失败，最后错误：{last_error or '候选用户名均不可用'}")

@app.post("/api/accounts/{account_id}/profile/identity")
@account_api_operation("profile_identity", label="修改资料")
async def update_profile_identity(account_id: str, req: ProfileIdentityRequest, user: dict = Depends(get_current_user)):
    """Updates display name and auto-generates a Telegram username from the two name fields."""
    check_account_company(account_id, user)
    first_name = req.first_name.strip()
    last_name = (req.last_name or "").strip()
    if not first_name:
        raise HTTPException(status_code=400, detail="名字不能为空")

    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        about_text = req.about.strip() if req.about is not None else None
        if about_text and len(about_text) > 70:
            about_text = about_text[:70]

        await client(functions.account.UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name,
            about=about_text,
        ))

        base_username = build_profile_username(first_name, last_name)
        new_username, attempts = await set_available_profile_username(client, base_username)

        from db import engine, AccountDb, Session
        new_name = f"{first_name} {last_name}".strip()
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                db_account.account_name = new_name
                db_account.profile_modified = True
                db_account.profile_modified_name = new_name
                db_account.profile_modified_username = new_username
                db_account.updated_by = user["username"]
                session.add(db_account)
                session.commit()
                path = account_config_path(account_id)
                save_json(path, db_account.to_dict())

        set_account_status(
            account_id,
            {
                "is_connected": True,
                "is_authorized": True,
                "me": f"{new_name} (@{new_username})",
            },
            source="profile-identity",
        )

        return {
            "status": "success",
            "message": "Profile identity updated successfully",
            "name": new_name,
            "username": new_username,
            "base_username": base_username,
            "attempts": attempts,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile identity: {str(e)}")

@app.get("/api/accounts/{account_id}/profile/check-username")
@account_api_operation("check_username", label="检测用户名")
async def check_telegram_username(account_id: str, username: str, user: dict = Depends(get_current_user)):
    """Checks if a username is available on Telegram using CheckUsernameRequest."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_auth = await client.is_user_authorized()
        if not is_auth:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        clean_username = username.strip().replace("@", "")
        if len(clean_username) < 5:
            return {"available": False, "reason": "用户名必须至少5个字符"}

        from telethon.tl import functions
        result = await client(functions.account.CheckUsernameRequest(username=clean_username))
        return {"available": bool(result)}
    except Exception as e:
        return {"available": False, "reason": f"检测返回: {str(e)}"}

# Preset database of Chinese historical figures and stars for fake profiles
CELEBRITIES = [
    {"name": "李世民", "pinyin": "lishimin"},
    {"name": "秦始皇", "pinyin": "qinshihuang"},
    {"name": "汉武帝", "pinyin": "hanwudi"},
    {"name": "朱元璋", "pinyin": "zhuyuanzhang"},
    {"name": "刘邦", "pinyin": "liubang"},
    {"name": "康熙", "pinyin": "kangxi"},
    {"name": "曹操", "pinyin": "caocao"},
    {"name": "刘备", "pinyin": "liubei"},
    {"name": "诸葛亮", "pinyin": "zhugeliang"},
    {"name": "关羽", "pinyin": "guanyu"},
    {"name": "张飞", "pinyin": "zhangfei"},
    {"name": "赵云", "pinyin": "zhaoyun"},
    {"name": "李白", "pinyin": "libai"},
    {"name": "杜甫", "pinyin": "dufu"},
    {"name": "苏轼", "pinyin": "sushi"},
    {"name": "岳飞", "pinyin": "yuefei"},
    {"name": "刘德华", "pinyin": "liudehua"},
    {"name": "周杰伦", "pinyin": "zhoujielun"},
    {"name": "成龙", "pinyin": "chenglong"},
    {"name": "周星驰", "pinyin": "zhouxingchi"},
    {"name": "梁朝伟", "pinyin": "liangchaowei"},
    {"name": "张国荣", "pinyin": "zhangguorong"},
    {"name": "王菲", "pinyin": "wangfei"},
    {"name": "黎明", "pinyin": "liming"},
    {"name": "郭富城", "pinyin": "guofucheng"},
    {"name": "林青霞", "pinyin": "linqingxia"},
    {"name": "古天乐", "pinyin": "gutianle"},
    {"name": "甄子丹", "pinyin": "zhenzidan"},
    {"name": "吴京", "pinyin": "wujing"},
    {"name": "胡歌", "pinyin": "huge"},
    {"name": "彭于晏", "pinyin": "pengyuyan"},
    {"name": "周润发", "pinyin": "zhourunfa"}, # Keep original
    {"name": "刘亦菲", "pinyin": "liuyifei"},
    {"name": "杨幂", "pinyin": "yangmi"},
    {"name": "赵丽颖", "pinyin": "zhaoliying"},
    {"name": "迪丽热巴", "pinyin": "dilireba"},
    {"name": "沈腾", "pinyin": "shenteng"},
    {"name": "徐峥", "pinyin": "xuzheng"},
    {"name": "黄渤", "pinyin": "huangbo"},
    {"name": "肖战", "pinyin": "xiaozhan"},
    {"name": "王一博", "pinyin": "wangyibo"},
    {"name": "易烊千玺", "pinyin": "yiyangqianxi"},
    {"name": "蔡徐坤", "pinyin": "caixukun"},
    {"name": "鹿晗", "pinyin": "luhan"},
    {"name": "张艺兴", "pinyin": "zhangyixing"},
    {"name": "章子怡", "pinyin": "zhangziyi"},
    {"name": "高圆圆", "pinyin": "gaoyuanyuan"},
    {"name": "杨紫", "pinyin": "yangzi"},
    {"name": "赵露思", "pinyin": "zhaolusi"},
    {"name": "白鹿", "pinyin": "bailu"},
    {"name": "虞书欣", "pinyin": "yushuxin"}
]
# Fix typo for zhourunfa pinyin if needed
for c in CELEBRITIES:
    if c["name"] == "周润发":
        c["pinyin"] = "zhourunfa"

def generate_unique_fake_name(used_names: set) -> dict:
    import random
    from historical_names import HISTORICAL_FIGURES

    # Filter candidates to avoid using names that are already taken
    candidates = [x for x in HISTORICAL_FIGURES if x["name"] not in used_names]

    if candidates:
        return random.choice(candidates)

    # Fallback to avoid infinite loops if the entire database of 400+ names is exhausted
    base = random.choice(HISTORICAL_FIGURES)
    suffix = str(random.randint(2, 99))
    return {
        "name": f"{base['name']}{suffix}",
        "pinyin": f"{base['pinyin']}{suffix}"
    }

@app.post("/api/accounts/batch-update-profile")
async def batch_update_profiles(req: BatchUpdateProfileRequest, user: dict = Depends(get_current_user)):
    """Batch updates names and usernames for selected Telegram accounts."""
    from telethon.tl import functions
    from db import engine, AccountDb, Session, select
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user).where(AccountDb.id.in_(req.account_ids))
        db_accounts = session.exec(stmt).all()
        allowed_ids = {acc.id for acc in db_accounts}
        if len(allowed_ids) != len(set(req.account_ids)):
            raise HTTPException(status_code=404, detail="One or more accounts not found or unauthorized")

    import random
    success_list = []
    failed_list = []

    used_names_set = set()
    try:
        from db import engine, AccountDb, Session, select
        with Session(engine) as session:
            all_db_accs = session.exec(select(AccountDb)).all()
            for acc in all_db_accs:
                if acc.profile_modified_name:
                    parts = acc.profile_modified_name.split()
                    if len(parts) > 1:
                        used_names_set.add(parts[-1].strip())
                    else:
                        used_names_set.add(acc.profile_modified_name.strip())
    except Exception as dbe:
        print(f"Failed to fetch existing used names: {dbe}")

    for idx, account_id in enumerate(req.account_ids):
        try:
            client = await get_client(account_id)
            is_authorized = await client.is_user_authorized()
            if not is_authorized:
                failed_list.append({"account_id": account_id, "error": "账号未登录"})
                continue

            if req.only_about:
                about_text = req.about.strip() if req.about is not None else ""
                if len(about_text) > 70:
                    about_text = about_text[:70]
                await client(functions.account.UpdateProfileRequest(
                    about=about_text
                ))

                # Update database and local configuration
                try:
                    from db import engine, AccountDb, Session
                    with Session(engine) as session:
                        db_account = session.get(AccountDb, account_id)
                        if db_account:
                            db_account.profile_modified = True
                            db_account.updated_by = user["username"]
                            session.add(db_account)
                            session.commit()

                            path = account_config_path(account_id)
                            save_json(path, db_account.to_dict())

                    set_account_status(
                        account_id,
                        {"is_connected": True, "is_authorized": True},
                        source="profile-batch"
                    )
                except Exception as se:
                    print(f"Failed to save modified flag in DB: {str(se)}")

                success_list.append({"account_id": account_id})
                continue

            last_name = req.last_name.strip()

            username_success = False
            username_to_try = ""
            first_name = ""
            username_error = "未知错误"

            # Try up to 8 different names to find a completely unique available username
            for attempt_name in range(8):
                if req.virtual_modify:
                    cel = generate_unique_fake_name(used_names_set)
                    first_name = cel["name"]
                    pinyin_name = cel["pinyin"]
                    base_username = f"{last_name}_{pinyin_name}".strip().replace("@", "")
                else:
                    first_name = req.custom_first_name.strip() or "User"
                    prefix = req.custom_username_prefix.strip() or f"{last_name}_user"
                    base_username = f"{prefix}_{idx + attempt_name + 1}".strip().replace("@", "")

                username_cleaned = re.sub(r'[^a-zA-Z0-9_]', '', base_username)
                if len(username_cleaned) < 5:
                    username_cleaned = username_cleaned.ljust(5, '0')

                username_to_try = username_cleaned

                # Check username availability directly on Telegram
                try:
                    from telethon.tl import functions
                    available = await client(functions.account.CheckUsernameRequest(username=username_to_try))
                    if not available:
                        if req.virtual_modify:
                            used_names_set.add(first_name)
                        continue
                except Exception as ce:
                    print(f"CheckUsernameRequest failed for {username_to_try}: {ce}")

                # Attempt to set the username
                try:
                    await client(functions.account.UpdateUsernameRequest(username=username_to_try))
                    username_success = True
                    if req.virtual_modify:
                        used_names_set.add(first_name)
                    break
                except Exception as ue:
                    username_error = str(ue)
                    print(f"UpdateUsernameRequest failed for {username_to_try}: {ue}")
                    if req.virtual_modify:
                        used_names_set.add(first_name)

            # Suffix fallback if all 8 names are occupied
            if not username_success and username_to_try:
                for fallback_attempt in range(5):
                    suffix = f"_{random.randint(100, 999)}"
                    fallback_username = f"{username_to_try}{suffix}"
                    try:
                        await client(functions.account.UpdateUsernameRequest(username=fallback_username))
                        username_to_try = fallback_username
                        username_success = True
                        if req.virtual_modify:
                            used_names_set.add(first_name)
                        break
                    except Exception as fe:
                        username_error = str(fe)

            # Now set the profile display name and about on Telegram
            about_text = req.about.strip() if req.about is not None else None
            if about_text and len(about_text) > 70:
                about_text = about_text[:70]

            from telethon.tl import functions
            await client(functions.account.UpdateProfileRequest(
                first_name=last_name,
                last_name=first_name,
                about=about_text
            ))

            # Update database and local configuration
            try:
                from db import engine, AccountDb, Session
                new_name = f"{last_name} {first_name}".strip()
                with Session(engine) as session:
                    db_account = session.get(AccountDb, account_id)
                    if db_account:
                        db_account.account_name = new_name
                        db_account.profile_modified = True
                        db_account.profile_modified_name = new_name
                        db_account.profile_modified_username = username_to_try if username_success else ""
                        db_account.updated_by = user["username"]
                        session.add(db_account)
                        session.commit()

                        path = account_config_path(account_id)
                        save_json(path, db_account.to_dict())

                username_str = f"@{username_to_try}" if (username_success and username_to_try) else ""
                set_account_status(
                    account_id,
                    {
                        "is_connected": True,
                        "is_authorized": True,
                        "me": f"{new_name} ({username_str})" if username_str else new_name
                    },
                    source="profile-batch"
                )
            except Exception as se:
                print(f"Failed to save modified flag in DB: {str(se)}")

            if username_success:
                success_list.append({
                    "account_id": account_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username_to_try
                })
            else:
                success_list.append({
                    "account_id": account_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": "修改失败: " + username_error
                })

        except Exception as e:
            failed_list.append({"account_id": account_id, "error": str(e)})

    return {
        "status": "success",
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success_details": success_list,
        "failed_details": failed_list
    }

def compress_avatar(image_bytes: bytes) -> bytes:
    import io
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((640, 640), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=85)
        return out_buf.getvalue()
    except Exception as e:
        print(f"Failed to compress avatar, using original: {e}")
        return image_bytes

@app.post("/api/accounts/{account_id}/profile/avatar")
@account_api_operation("profile_avatar", label="修改头像")
async def update_profile_avatar(
    account_id: str,
    file: Optional[UploadFile] = File(None),
    library_filename: Optional[str] = Form(None),
    user: dict = Depends(get_current_user)
):
    """Uploads and sets profile photo/avatar for a single Telegram account from upload or library."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="账号未登录")

        if library_filename:
            if '/' in library_filename or '\\' in library_filename:
                raise HTTPException(status_code=400, detail="非法文件名")
            target_path = AVATARS_DIR / library_filename
            if not target_path.exists():
                raise HTTPException(status_code=404, detail="所选头像在头像库中不存在")
            content = target_path.read_bytes()
        elif file:
            content = await file.read()
        else:
            raise HTTPException(status_code=400, detail="未提供头像文件或头像库文件名")

        content = compress_avatar(content)
        safe_filename = "avatar.jpg"
        uploaded_file = await client.upload_file(content, file_name=safe_filename)
        from telethon.tl import functions
        await client(functions.photos.UploadProfilePhotoRequest(
            file=uploaded_file
        ))
        return {"status": "success", "message": "头像修改成功"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改头像失败: {str(e)}")

@app.post("/api/accounts/batch-update-avatar")
async def batch_update_avatars(
    account_ids: str = Form(...),  # JSON array of account IDs
    files: Optional[List[UploadFile]] = File(None),
    library_filenames: Optional[str] = Form(None),
    user: dict = Depends(get_current_user)
):
    """Batch updates profile photos/avatars for multiple Telegram accounts (round-robin / random distribution) from upload or library."""
    import json
    try:
        acc_ids = json.loads(account_ids)
    except Exception:
        raise HTTPException(status_code=400, detail="account_ids 格式错误，应为 JSON 数组")

    from db import engine, AccountDb, Session, select
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user).where(AccountDb.id.in_(acc_ids))
        db_accounts = session.exec(stmt).all()
        allowed_ids = {acc.id for acc in db_accounts}
        if len(allowed_ids) != len(set(acc_ids)):
            raise HTTPException(status_code=404, detail="One or more accounts not found or unauthorized")

    file_contents = []

    # 1. Process library files if specified
    if library_filenames:
        try:
            lib_files = json.loads(library_filenames)
            for lf in lib_files:
                if '/' in lf or '\\' in lf:
                    continue
                target_path = AVATARS_DIR / lf
                if target_path.exists():
                    compressed = compress_avatar(target_path.read_bytes())
                    file_contents.append(compressed)
        except Exception:
            raise HTTPException(status_code=400, detail="library_filenames 格式错误")

    # 2. Process local files if uploaded
    if files:
        for f in files:
            if f.filename:
                content = await f.read()
                compressed = compress_avatar(content)
                file_contents.append(compressed)

    if not file_contents:
        raise HTTPException(status_code=400, detail="未提供任何头像文件或头像库文件名")

    success_list = []
    failed_list = []

    for idx, account_id in enumerate(acc_ids):
        try:
            client = await get_client(account_id)
            is_authorized = await client.is_user_authorized()
            if not is_authorized:
                failed_list.append({"account_id": account_id, "error": "账号未登录"})
                continue

            # Assign avatar round-robin
            avatar_bytes = file_contents[idx % len(file_contents)]
            safe_filename = f"avatar_{idx}.jpg"
            uploaded_file = await client.upload_file(avatar_bytes, file_name=safe_filename)
            from telethon.tl import functions
            await client(functions.photos.UploadProfilePhotoRequest(
                file=uploaded_file
            ))
            success_list.append(account_id)
        except Exception as e:
            failed_list.append({"account_id": account_id, "error": str(e)})

    return {
        "status": "success",
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success_details": success_list,
        "failed_details": failed_list
    }

# --- AVATAR LIBRARY ENDPOINTS ---

class RenameRequest(BaseModel):
    old_name: str
    new_name: str

@app.get("/api/avatar-library")
async def get_avatar_library(user: dict = Depends(get_current_user)):
    """Lists all images in the avatar library."""
    try:
        files_list = []
        if AVATARS_DIR.exists():
            for f in AVATARS_DIR.iterdir():
                if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'):
                    stat = f.stat()
                    files_list.append({
                        "name": f.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    })
        # Sort by mtime descending
        files_list.sort(key=lambda x: x["mtime"], reverse=True)
        return files_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取头像库失败: {str(e)}")

@app.post("/api/avatar-library")
async def upload_to_avatar_library(
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user)
):
    """Uploads files to the avatar library. Limit 10MB per file."""
    uploaded_files = []
    try:
        for file in files:
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"文件 {file.filename} 超过10MB大小限制")

            # Sanitize filename
            safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', file.filename)
            if not safe_name or safe_name.startswith('.'):
                safe_name = f"avatar_{int(time.time())}.jpg"

            base, ext = os.path.splitext(safe_name)
            # Ensure unique name
            counter = 1
            filename = safe_name
            while (AVATARS_DIR / filename).exists():
                filename = f"{base}_{counter}{ext}"
                counter += 1

            target_path = AVATARS_DIR / filename
            target_path.write_bytes(content)
            uploaded_files.append(filename)
        return {"status": "success", "files": uploaded_files}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传到头像库失败: {str(e)}")

@app.delete("/api/avatar-library/{filename}")
async def delete_from_avatar_library(filename: str, user: dict = Depends(get_current_user)):
    """Deletes a file from the avatar library."""
    if '/' in filename or '\\' in filename or filename in ('.', '..'):
        raise HTTPException(status_code=400, detail="非法文件名")

    target_path = AVATARS_DIR / filename
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        target_path.unlink()
        return {"status": "success", "message": "删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@app.post("/api/avatar-library/rename")
async def rename_in_avatar_library(req: RenameRequest, user: dict = Depends(get_current_user)):
    """Renames a file in the avatar library."""
    old_name = req.old_name.strip()
    new_name = req.new_name.strip()

    if '/' in old_name or '\\' in old_name or old_name in ('.', '..'):
        raise HTTPException(status_code=400, detail="非法旧文件名")
    if '/' in new_name or '\\' in new_name or new_name in ('.', '..'):
        raise HTTPException(status_code=400, detail="非法新文件名")

    old_path = AVATARS_DIR / old_name
    if not old_path.exists():
        raise HTTPException(status_code=404, detail="原文件不存在")

    # Sanitize new_name
    new_name_clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', new_name)
    old_base, old_ext = os.path.splitext(old_name)
    new_base, new_ext = os.path.splitext(new_name_clean)

    # Force original extension if missing or altered
    if new_ext.lower() != old_ext.lower():
        new_name_clean = new_base + old_ext

    new_path = AVATARS_DIR / new_name_clean
    if new_path.exists() and old_name != new_name_clean:
        raise HTTPException(status_code=400, detail="目标文件名已存在")

    try:
        old_path.rename(new_path)
        return {"status": "success", "filename": new_name_clean}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重命名失败: {str(e)}")

@app.get("/api/avatar-library/file/{filename}")
async def serve_avatar_file(filename: str):
    """Serves a file from the avatar library for previewing."""
    if '/' in filename or '\\' in filename or filename in ('.', '..'):
        raise HTTPException(status_code=400, detail="非法文件名")

    target_path = AVATARS_DIR / filename
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(target_path)

class LoginLogCreate(BaseModel):
    phone: str
    api_link: Optional[str] = None
    original_password: Optional[str] = None
    current_password: Optional[str] = None
    login_type: str
    status: str
    error_detail: Optional[str] = None

@app.post("/api/login/logs")
def create_login_log(req: LoginLogCreate, user: dict = Depends(get_current_user)):
    from db import engine, LoginLogDb, Session
    from datetime import datetime
    with Session(engine) as session:
        new_log = LoginLogDb(
            company=user["company"],
            timestamp=get_beijing_time_str(),
            phone=req.phone,
            api_link=req.api_link,
            original_password=req.original_password,
            current_password=req.current_password,
            login_type=req.login_type,
            status=req.status,
            error_detail=req.error_detail
        )
        session.add(new_log)
        session.commit()
    return {"status": "success"}

@app.get("/api/login/logs")
def get_login_logs(limit: int = 100, user: dict = Depends(get_current_user)):
    from db import engine, LoginLogDb, AccountDb, Session, select
    import time
    from datetime import datetime
    with Session(engine) as session:
        # Check if log table has any records for this company (unless eason)
        if user["username"] in ("eason", "admin") or user["company"] == "admin":
            stmt_check = select(LoginLogDb).limit(1)
        else:
            stmt_check = select(LoginLogDb).where(LoginLogDb.company == user["company"]).limit(1)
        has_logs = session.exec(stmt_check).first()

        if not has_logs:
            # Pre-populate with existing successful accounts from DB for this company (unless eason)
            stmt_accounts = query_allowed_accounts(session, user)
            accounts = session.exec(stmt_accounts).all()
            if accounts:
                for idx, acc in enumerate(accounts):
                    t = datetime.fromtimestamp(time.time() - (len(accounts) - idx) * 60, tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
                    new_log = LoginLogDb(
                        company=acc.company,
                        timestamp=t,
                        phone=acc.account_name or acc.id,
                        api_link=f"https://tgapi.feijige.shop/{acc.page_id}/GetHTML" if acc.page_id else None,
                        original_password=acc.pass2fa,
                        current_password=acc.pass2fa,
                        login_type="import",
                        status="success"
                    )
                    session.add(new_log)
                session.commit()

        if user["role"] == "admin":
            stmt = select(LoginLogDb).order_by(LoginLogDb.id.desc()).limit(limit)
        else:
            stmt_acc = query_allowed_accounts(session, user)
            allowed_accs = session.exec(stmt_acc).all()
            allowed_identifiers = []
            for acc in allowed_accs:
                allowed_identifiers.append(acc.id)
                allowed_identifiers.append(acc.account_name)
            stmt = select(LoginLogDb).where(LoginLogDb.phone.in_(allowed_identifiers)).order_by(LoginLogDb.id.desc()).limit(limit)
        results = session.exec(stmt).all()
        return [log.model_dump() for log in results]

@app.delete("/api/login/logs")
def clear_login_logs(user: dict = Depends(get_current_user)):
    from db import engine, LoginLogDb, Session
    from sqlmodel import delete
    try:
        with Session(engine) as session:
            if user["role"] == "admin":
                session.exec(delete(LoginLogDb))
            else:
                stmt_acc = query_allowed_accounts(session, user)
                allowed_ids = [acc.id for acc in session.exec(stmt_acc).all()]
                session.exec(delete(LoginLogDb).where(LoginLogDb.phone.in_(allowed_ids)))
            session.commit()
        return {"status": "success", "message": "已成功清空所有登录记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空登录日志失败: {str(e)}")

@app.post("/api/accounts/{account_id}/profile/2fa")
@account_api_operation("profile_2fa", label="修改 2FA")
async def update_account_2fa(account_id: str, req: Update2faRequest, user: dict = Depends(get_current_user)):
    """Updates or sets the Telegram 2FA password for an account."""
    check_account_company(account_id, user)
    current_pwd = req.current_password.strip() if req.current_password else None
    new_pwd = req.new_password.strip()
    hint = req.hint.strip() if (req.hint and req.hint.strip()) else "rosepay"
    if not new_pwd:
        raise HTTPException(status_code=400, detail="新两步验证密码不能为空")

    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="账号未登录")

        # Get cached password from database as fallback current password
        cached_pwd = None
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                cached_pwd = db_account.pass2fa

        actual_current_pwd = current_pwd if current_pwd is not None else cached_pwd

        from telethon import errors
        try:
            # Call Telethon edit_2fa
            await client.edit_2fa(
                current_password=actual_current_pwd,
                new_password=new_pwd,
                hint=hint
            )
        except errors.PasswordHashInvalidError as e:
            if current_pwd and cached_pwd and current_pwd != cached_pwd:
                await client.edit_2fa(
                    current_password=cached_pwd,
                    new_password=new_pwd,
                    hint=hint
                )
            else:
                raise e

        # Update pass2fa in SQLite Database & Account config json
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                db_account.pass2fa = new_pwd
                db_account.updated_by = user["username"]
                db_account.profile_modified = (new_pwd != "" and new_pwd != "0000")
                session.add(db_account)
                session.commit()
                # Sync back to json config file
                path = account_config_path(account_id)
                save_json(path, db_account.to_dict())
        return {"status": "success", "message": "两步验证密码修改成功，已同步至系统配置"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改两步验证密码失败: {str(e)}")
@app.post("/api/accounts/batch-update-2fa")
async def batch_update_accounts_2fa(req: BatchUpdate2faRequest, user: dict = Depends(get_current_user)):
    """Batch updates 2FA passwords for selected Telegram accounts."""
    from db import engine, AccountDb, Session, select
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user).where(AccountDb.id.in_(req.account_ids))
        db_accounts = session.exec(stmt).all()
        allowed_ids = {acc.id for acc in db_accounts}
        if len(allowed_ids) != len(set(req.account_ids)):
            raise HTTPException(status_code=404, detail="One or more accounts not found or unauthorized")

    import secrets
    import string
    success_list = []
    failed_list = []

    current_pwd = req.current_password.strip() if req.current_password else None
    hint = req.hint.strip() if (req.hint and req.hint.strip()) else "rosepay"
    def generate_secure_password(length=12):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    from db import engine, AccountDb, Session
    for account_id in req.account_ids:
        try:
            client = await get_client(account_id)
            is_authorized = await client.is_user_authorized()
            if not is_authorized:
                failed_list.append({"account_id": account_id, "error": "账号未登录"})
                continue
            # Determine new password
            if req.new_password_mode == "auto":
                new_pwd = generate_secure_password()
            else:
                new_pwd = req.custom_new_password.strip()
            if not new_pwd:
                failed_list.append({"account_id": account_id, "error": "新密码未配置"})
                continue
            # Get cached password from database as fallback current password
            cached_pwd = None
            with Session(engine) as session:
                db_account = session.get(AccountDb, account_id)
                if db_account:
                    cached_pwd = db_account.pass2fa

            actual_current_pwd = current_pwd if current_pwd is not None else cached_pwd

            from telethon import errors
            try:
                # Call Telethon edit_2fa
                await client.edit_2fa(
                    current_password=actual_current_pwd,
                    new_password=new_pwd,
                    hint=hint
                )
            except errors.PasswordHashInvalidError as e:
                if current_pwd and cached_pwd and current_pwd != cached_pwd:
                    await client.edit_2fa(
                        current_password=cached_pwd,
                        new_password=new_pwd,
                        hint=hint
                    )
                else:
                    raise e

            # Update DB and JSON config
            with Session(engine) as session:
                db_account = session.get(AccountDb, account_id)
                if db_account:
                    db_account.pass2fa = new_pwd
                    db_account.updated_by = user["username"]
                    session.add(db_account)
                    session.commit()

                    path = account_config_path(account_id)
                    save_json(path, db_account.to_dict())
            success_list.append({
                "account_id": account_id,
                "new_password": new_pwd
            })

        except Exception as e:
            failed_list.append({"account_id": account_id, "error": str(e)})
    return {
        "status": "success",
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success_details": success_list,
        "failed_details": failed_list
    }
def load_groups(company: str | None = None) -> List[Dict[str, Any]]:
    from db import engine, GroupDb, Session, select
    try:
        with Session(engine) as session:
            if company and company != "admin":
                stmt = select(GroupDb).where(GroupDb.company == company)
            else:
                stmt = select(GroupDb)
            results = session.exec(stmt).all()
            return dedupe_group_rows_for_api([g.model_dump() for g in results])
    except Exception as e:
        print(f"Failed to load groups from DB: {e}")
        return []

def canonical_group_identity(group: Dict[str, Any]) -> str:
    username = (group.get("username") or "").strip().lstrip("@").lower()
    if username:
        return f"u:{username}"
    group_id = str(group.get("id") or "").strip()
    if group_id.startswith("-100"):
        group_id = group_id[4:]
    return f"id:{group_id}"

def group_row_preference_score(group: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
    group_id = str(group.get("id") or "")
    return (
        1 if group_id.startswith("-100") else 0,
        1 if group.get("company") != "admin" else 0,
        1 if group.get("enabled") else 0,
        int(group.get("quality_score") or 0),
        int(group.get("memberCount") or 0),
    )

def dedupe_group_rows_for_api(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for group in groups:
        key = canonical_group_identity(group)
        if not key or key == "id:":
            key = f"row:{group.get('company')}:{group.get('id')}:{len(order)}"
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = group
            order.append(key)
        elif group_row_preference_score(group) > group_row_preference_score(existing):
            deduped[key] = group
    return [deduped[key] for key in order]

def normalized_group_username(value: Any) -> str:
    return str(value or "").strip().lstrip("@").lower()

def find_group_by_username_or_id(session: Any, group_id: Any, username: Any, company: Optional[str] = None):
    from db import GroupDb, select
    clean_username = normalized_group_username(username)
    stmt = None
    if clean_username:
        stmt = select(GroupDb).where(
            (GroupDb.username.ilike(clean_username)) |
            (GroupDb.username.ilike(f"@{clean_username}"))
        )
    elif group_id is not None:
        stmt = select(GroupDb).where(GroupDb.id == str(group_id))
    if stmt is None:
        return None
    if company and company != "admin":
        stmt = stmt.where(GroupDb.company == company)
    return session.exec(stmt).first()

def find_group_rows_by_public_identity(session: Any, group_id: Any, company: Optional[str] = None) -> List[Any]:
    from db import GroupDb, select
    target = find_group_by_username_or_id(session, group_id, None, company)
    if not target:
        return []
    clean_username = normalized_group_username(getattr(target, "username", None))
    if clean_username:
        stmt = select(GroupDb).where(
            (GroupDb.username.ilike(clean_username)) |
            (GroupDb.username.ilike(f"@{clean_username}"))
        )
    else:
        stmt = select(GroupDb).where(GroupDb.id == str(group_id))
    if company and company != "admin":
        stmt = stmt.where(GroupDb.company == company)
    return session.exec(stmt).all()

def calculate_group_library_scores(member_count: int = 0, group_type: str = "group", has_username: bool = False, is_valid: bool = True) -> Dict[str, int]:
    """Cheap sync-time score for the group library; deep message analysis stays in scraper/expansion."""
    if not is_valid:
        return {
            "quality_score": 0,
            "relevance_score": 0,
            "activity_score": 0,
            "engagement_score": 0,
        }

    members = max(0, int(member_count or 0))
    if members >= 10000:
        activity = 80
    elif members >= 5000:
        activity = 70
    elif members >= 1000:
        activity = 58
    elif members >= 100:
        activity = 42
    elif members > 0:
        activity = 25
    else:
        activity = 10

    if group_type == "supergroup":
        engagement = 70
    elif group_type == "group":
        engagement = 58
    elif group_type == "channel":
        engagement = 28
    else:
        engagement = 35

    relevance = 55 if has_username else 45
    quality = round(activity * 0.55 + engagement * 0.25 + relevance * 0.20)
    return {
        "quality_score": max(0, min(100, quality)),
        "relevance_score": max(0, min(100, relevance)),
        "activity_score": max(0, min(100, activity)),
        "engagement_score": max(0, min(100, engagement)),
    }

def apply_group_library_scores(group: Any, is_valid: bool = True) -> Dict[str, int]:
    scores = calculate_group_library_scores(
        member_count=getattr(group, "memberCount", 0) or 0,
        group_type=getattr(group, "type", "group") or "group",
        has_username=bool(getattr(group, "username", "") or ""),
        is_valid=is_valid,
    )
    group.quality_score = scores["quality_score"]
    group.relevance_score = scores["relevance_score"]
    group.activity_score = scores["activity_score"]
    group.engagement_score = scores["engagement_score"]
    return scores

def format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def get_user_from_stream_token(token: Optional[str]) -> Dict[str, str]:
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user_payload = verify_token(token)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    from db import engine, AdminDb, Session, select
    with Session(engine) as session:
        db_user = session.exec(select(AdminDb).where(AdminDb.username == user_payload["username"])).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "username": db_user.username,
            "role": db_user.role,
            "company": db_user.company or "admin"
        }

def save_groups(groups: List[Dict[str, Any]]):
    pass

@app.post("/api/groups/{group_id}/re-audit")
async def re_audit_group_rules(group_id: str, user: dict = Depends(get_current_user)):
    from db import engine, GroupDb, Session, select
    from services.scraping_service import query_allowed_accounts, get_read_only_probe_client
    from services.shared_state import filter_executable_accounts_for_task
    from bot_rules_auditor import audit_group_bot_rules
    import json
    
    with Session(engine) as session:
        db_groups = find_group_rows_by_public_identity(session, group_id, user["company"])
        if not db_groups:
            raise HTTPException(status_code=404, detail="未找到指定的群组记录")
        db_group = db_groups[0]
        
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user)
        allowed_account_ids = {a.id for a in filter_executable_accounts_for_task(session.exec(stmt).all())}
        
    logs = []
    client, selected_account_id = await get_read_only_probe_client(allowed_account_ids, logs)
    if not client:
        raise HTTPException(
            status_code=400,
            detail="当前没有可用的电报账号可以执行探测，请先登录一个账号。"
        )
        
    try:
        rules_summary_json, rules_raw_logs = await audit_group_bot_rules(
            client, 
            db_group.id, 
            db_group.title or group_id, 
            db_group.username
        )
        
        with Session(engine) as session:
            for g in find_group_rows_by_public_identity(session, group_id, user["company"]):
                g.bot_rules_summary = rules_summary_json
                g.bot_rules_raw_logs = rules_raw_logs
                g.updated_by = user["username"]
                session.add(g)
            session.commit()
            
        return {
            "status": "success", 
            "bot_rules_summary": json.loads(rules_summary_json),
            "bot_rules_raw_logs": rules_raw_logs,
            "logs": logs
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"重新拉取群规则失败：{exc}"
        )

@app.get("/api/groups", response_model=List[GroupModel])
def get_api_groups(user: dict = Depends(get_current_user)):
    return load_groups(user["company"])

@app.post("/api/groups/toggle")
def toggle_group(req: GroupToggleRequest, user: dict = Depends(get_current_user)):
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        db_groups = find_group_rows_by_public_identity(session, req.id, user["company"])
        for db_group in db_groups:
            db_group.enabled = req.enabled
            db_group.updated_by = user["username"]
            session.add(db_group)
        session.commit()
    return {"status": "success", "groups": load_groups(user["company"])}

@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str, admin_user: dict = Depends(require_admin)):
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        db_groups = find_group_rows_by_public_identity(session, group_id, admin_user["company"])
        for db_group in db_groups:
            session.delete(db_group)
        session.commit()
    return {"status": "success", "groups": load_groups(admin_user["company"])}

@app.post("/api/groups/batch-delete")
@app.post("/api/groups/batch-remove")
def batch_delete_groups(req: BatchDeleteRequest, admin_user: dict = Depends(require_admin)):
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        for id_ in req.ids:
            for db_group in find_group_rows_by_public_identity(session, id_, admin_user["company"]):
                session.delete(db_group)
        session.commit()
    return {"status": "success", "groups": load_groups(admin_user["company"])}

@app.post("/api/groups/batch-update-category")
def batch_update_category(req: BatchCategoryRequest, user: dict = Depends(get_current_user)):
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        for id_ in req.ids:
            for db_group in find_group_rows_by_public_identity(session, id_, user["company"]):
                db_group.category = req.category
                db_group.updated_by = user["username"]
                session.add(db_group)
        session.commit()
    return {"status": "success", "groups": load_groups(user["company"])}

@app.post("/api/groups/update-price")
def update_group_price(req: GroupPriceUpdateRequest, user: dict = Depends(get_current_user)):
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        if user["company"] == "admin":
            db_group = session.exec(select(GroupDb).where(GroupDb.id == str(req.id))).first()
        else:
            db_group = session.get(GroupDb, (str(req.id), user["company"]))
        if db_group:
            db_group.price = req.price
            db_group.updated_by = user["username"]
            session.add(db_group)
            session.commit()
    return {"status": "success", "groups": load_groups(user["company"])}

@app.post("/api/groups/update-category")
def update_group_category(req: GroupCategoryUpdateRequest, user: dict = Depends(get_current_user)):
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        if user["company"] == "admin":
            db_group = session.exec(select(GroupDb).where(GroupDb.id == str(req.id))).first()
        else:
            db_group = session.get(GroupDb, (str(req.id), user["company"]))
        if db_group:
            db_group.category = req.category
            db_group.updated_by = user["username"]
            session.add(db_group)
            session.commit()
    return {"status": "success", "groups": load_groups(user["company"])}

@app.get("/api/group-categories", response_model=List[GroupCategoryModel])
def get_group_categories(user: dict = Depends(get_current_user)):
    from db import engine, GroupCategoryDb, Session, select
    with Session(engine) as session:
        if user["company"] == "admin":
            stmt = select(GroupCategoryDb)
        else:
            stmt = select(GroupCategoryDb).where((GroupCategoryDb.company == user["company"]) | (GroupCategoryDb.company == "admin"))
        results = session.exec(stmt).all()
        return [GroupCategoryModel(id=c.id, name=c.name, company=c.company) for c in results]

@app.post("/api/group-categories")
def add_group_category(req: AddCategoryRequest, user: dict = Depends(get_current_user)):
    from db import engine, GroupCategoryDb, Session, select
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="类型名称不能为空")
    with Session(engine) as session:
        existing = session.exec(select(GroupCategoryDb).where(GroupCategoryDb.name == name)).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"类型 '{name}' 已存在")
        new_cat = GroupCategoryDb(name=name, company=user["company"])
        session.add(new_cat)
        session.commit()
    return {"status": "success"}

@app.delete("/api/group-categories/{name}")
def delete_group_category(name: str, user: dict = Depends(get_current_user)):
    from db import engine, GroupCategoryDb, GroupDb, Session, select
    with Session(engine) as session:
        stmt = select(GroupCategoryDb).where(GroupCategoryDb.name == name)
        cat = session.exec(stmt).first()
        if not cat:
            raise HTTPException(status_code=404, detail="未找到该类型")

        # Check if in use by groups
        group_using = session.exec(select(GroupDb).where(GroupDb.category == name)).first()
        if group_using:
            raise HTTPException(status_code=400, detail=f"类型 '{name}' 正在被群组使用，请先修改这些群组的类型后再删除。")

        session.delete(cat)
        session.commit()
    return {"status": "success"}

@app.post("/api/group-categories/rename")
def rename_group_category(req: RenameCategoryRequest, user: dict = Depends(get_current_user)):
    from db import engine, GroupCategoryDb, GroupDb, Session, select
    old_name = req.old_name.strip()
    new_name = req.new_name.strip()
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    if old_name == new_name:
        return {"status": "success"}
    with Session(engine) as session:
        cat = session.exec(select(GroupCategoryDb).where(GroupCategoryDb.name == old_name)).first()
        if not cat:
            raise HTTPException(status_code=404, detail="未找到该类型")

        existing = session.exec(select(GroupCategoryDb).where(GroupCategoryDb.name == new_name)).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"类型 '{new_name}' 已存在")

        cat.name = new_name
        session.add(cat)

        # Update all groups using this category
        groups_to_update = session.exec(select(GroupDb).where(GroupDb.category == old_name)).all()
        for g in groups_to_update:
            g.category = new_name
            session.add(g)

        session.commit()
    return {"status": "success"}


@app.post("/api/groups/sync")
async def sync_groups_from_folders(user: dict = Depends(get_current_user)):
    """
    Queries Telegram API for all logged-in accounts, finds the groups in their configured
    folders, and synchronizes them directly into the groups_library table.
    """
    from db import engine, AccountDb, GroupDb, Session, select
    from sync_folder_groups import collect_records

    # 1. Get all accounts from database for this company
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user)
        db_accounts = filter_executable_accounts_for_task(session.exec(stmt).all())

    if not db_accounts:
        raise HTTPException(status_code=400, detail="没有绑定任何账号")
    synced_count = 0
    added_count = 0
    skipped_count = 0
    errors = []
    logs = []
    logs.append("开始同步聊天文件夹中的群组。")

    for acc in db_accounts:
        account_id = acc.id
        folder_name = acc.folder_name or ""
        account_label = acc.account_name or account_id
        logs.append(f"账号 {account_label} 开始执行，目标文件夹：{folder_name or '未配置'}。")

        try:
            client = await get_client(account_id)
            if not await client.is_user_authorized():
                logs.append(f"账号 {account_label} 未授权登录，跳过。")
                continue
            # Fetch folders
            result = await client(functions.messages.GetDialogFiltersRequest())
            raw_filters = getattr(result, "filters", result)
            # Find the matching folder
            folder = next((item for item in raw_filters if isinstance(item, (types.DialogFilter, types.DialogFilterChatlist)) and normalize_title(item.title) == folder_name), None)

            if not folder:
                errors.append(f"账号 {acc.account_name}: 未找到文件夹 '{folder_name}'")
                logs.append(f"账号 {account_label} 未找到文件夹 {folder_name}，跳过。")
                continue

            # Collect records
            include_types = set([x.strip() for x in acc.include_types.split(",") if x.strip()])
            if not include_types:
                include_types = {"group", "supergroup"}
            records = await collect_records(client, folder, include_types)
            logs.append(f"账号 {account_label} 读取到 {len(records)} 个群组，开始写入群组库。")
            # Upsert into groups_library
            with Session(engine) as session:
                for record in records:
                    group_id = str(record.chat_id)
                    db_group = find_group_by_username_or_id(session, group_id, record.username, user["company"])
                    if db_group:
                        db_group.id = group_id
                        db_group.title = record.title
                        db_group.username = record.username or ""
                        db_group.type = record.type
                        db_group.category = record.folder or db_group.category
                        db_group.updated_by = user["username"]
                        session.add(db_group)
                        skipped_count += 1
                        logs.append(f"账号 {account_label} 更新已有群组：{record.title} ({record.username or group_id})。")
                    else:
                        new_group = GroupDb(
                            id=group_id,
                            company=user["company"],
                            title=record.title,
                            username=record.username or "",
                            type=record.type,
                            enabled=True,
                            memberCount=0,
                            category=record.folder or "中文广告",
                            created_by=user["username"],
                            updated_by=user["username"]
                        )
                        session.add(new_group)
                        added_count += 1
                        logs.append(f"账号 {account_label} 新增群组：{record.title} ({record.username or group_id})。")
                session.commit()
            synced_count += len(records)
            logs.append(f"账号 {account_label} 文件夹同步完成：读取 {len(records)} 个群组。")
        except Exception as e:
            errors.append(f"账号 {acc.account_name} 同步失败: {str(e)}")
            logs.append(f"账号 {account_label} 同步失败：{str(e)}。")

    logs.append(f"文件夹同步结束：读取 {synced_count} 个，新增 {added_count} 个，更新已有 {skipped_count} 个。")
    return {
        "status": "success",
        "synced_count": synced_count,
        "added_count": added_count,
        "skipped_count": skipped_count,
        "errors": errors,
        "logs": logs,
        "groups": load_groups(user["company"])
    }
# Extracted sync_groups_status

# Extracted analyze_group_category_with_ai


# Extracted stream_groups_sync


def map_telegram_error(e: Exception, default_msg: str) -> str:
    err_str = str(e)
    if "UsernameNotOccupied" in err_str or "No user has" in err_str:
        return "该 Telegram 用户名/群组/频道链接不存在或已失效"
    if "ChannelPrivate" in err_str:
        return "该频道/群组为私有且当前账号未加入"
    if "InviteHashExpired" in err_str or "InviteHashExpiredError" in err_str:
        return "该私有邀请链接已过期或失效"
    if "InviteHashInvalid" in err_str or "InviteHashInvalidError" in err_str:
        return "私有邀请链接无效，哈希校验不通过"
    if "ChatInvalid" in err_str or "ChatIdInvalid" in err_str:
        return "无效的群组/频道 ID"
    if "FloodWait" in err_str:
        return "触发 Telegram 接口频率限制，请稍后重试"
    return f"{default_msg}: {err_str}"

def normalize_group_identifier(link: str):
    import re
    identifier = (link or "").strip()
    identifier = re.sub(r"^https?:/*", "", identifier, flags=re.IGNORECASE)
    identifier = re.sub(r"^(?:t\.me|telegram\.me)/", "", identifier, flags=re.IGNORECASE)
    identifier = identifier.split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    if identifier.startswith("@"):
        identifier = identifier[1:]
    return identifier

def classify_group_category_from_text(title: str, messages: List[str]) -> str:
    import re
    clean_messages = [m for m in messages if m]
    msg_lengths = [len(m) for m in clean_messages]
    is_short_ad = bool(msg_lengths) and max(msg_lengths) < 200
    has_chinese_name = bool(re.search(r"[\u4e00-\u9fa5]", title or "")) or "🇨🇳" in (title or "")
    has_chinese_messages = bool(re.search(r"[\u4e00-\u9fa5]", "".join(clean_messages)))
    is_chinese = has_chinese_messages if clean_messages else has_chinese_name
    if is_chinese:
        return "中文短" if is_short_ad else "中文长"
    return "英文短" if is_short_ad else "英文长"

# Extracted classify_group_category_for_import

# Extracted resolve_group

async def update_account_name_from_tg(account_id: str, client):
    """Automatically updates AccountDb.account_name with the Telegram profile name if it is currently just a phone number or empty."""
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            if me:
                first_name = me.first_name or ''
                last_name = me.last_name or ''
                tg_name = f"{first_name} {last_name}".strip()
                if not tg_name:
                    tg_name = me.username or "未命名电报号"

                from db import engine, AccountDb, Session
                with Session(engine) as session:
                    db_account = session.get(AccountDb, account_id)
                    if db_account:
                        curr_name = db_account.account_name.strip() if db_account.account_name else ""
                        username_changed = False
                        name_changed = False

                        if curr_name != tg_name:
                            db_account.account_name = tg_name
                            name_changed = True

                        # Keep profile_modified_name in sync with tg_name if different
                        if db_account.profile_modified_name != tg_name:
                            db_account.profile_modified_name = tg_name
                            name_changed = True

                        # Save the current username in DB (even if deleted on TG)
                        clean_username = me.username.strip() if me.username else ""
                        current_db_username = db_account.profile_modified_username or ""
                        if current_db_username != clean_username:
                            db_account.profile_modified_username = clean_username if clean_username else None
                            username_changed = True

                        if name_changed or username_changed:

                            session.add(db_account)
                            session.commit()

                            # Also sync to disk JSON config
                            try:
                                path = account_config_path(account_id)
                                if path.exists():
                                    config = db_account.to_dict()
                                    save_json(path, config)
                            except Exception as ex:
                                print(f"Failed to sync updated name to config file: {ex}")
                            print(f"Updated account {account_id} cache fields to: Name='{tg_name}', Username='@{clean_username}'")
    except Exception as e:
        print(f"Failed to update account name from TG for {account_id}: {e}")

# --- TELEGRAM INTERACTIVE LOGIN APIs ---

async def get_spambot_status(client) -> dict:
    """Sends /start to @SpamBot and checks its response for account restrictions."""
    try:
        # Resolve spambot entity
        entity = await client.get_input_entity('spambot')
        # Send /start
        await client.send_message(entity, '/start')

        # Wait a short moment for response to arrive
        import asyncio
        await asyncio.sleep(1.5)

        # Fetch the latest message from @SpamBot
        messages = await client.get_messages(entity, limit=1)
        if messages:
            msg = messages[0]
            if not msg.out:
                text = msg.message
                lower_text = text.lower()
                # Parse the response text
                if "no limits" in lower_text or "no restrictions" in lower_text or "free as a bird" in lower_text:
                    return {"status": "free", "details": text}
                else:
                    return {"status": "restricted", "details": text}
        return {"status": "unknown", "details": "没有收到 SpamBot 响应"}
    except Exception as e:
        return {"status": "unknown", "details": f"SpamBot 检测失败: {str(e)}"}

@app.get("/api/login/status/{account_id}")
@account_api_operation("login_status", label="检测登录状态")
async def get_login_status(account_id: str, force: bool = False, user: dict = Depends(get_current_user)):
    """Checks the connection and authorization status of a Telegram account."""
    check_account_company(account_id, user)
    try:
        client = await asyncio.wait_for(get_client(account_id), timeout=15)
        is_connected = client.is_connected()
        is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=8) if is_connected else False
        me_info = None
        spambot_status = "unknown"
        spambot_details = ""
        spambot_time = None
        db_acc = None
        check_warnings = []

        if is_authorized:
            try:
                me = await asyncio.wait_for(client.get_me(), timeout=8)
                if me:
                    username = f"@{me.username}" if me.username else ""
                    me_info = f"{me.first_name or ''} {me.last_name or ''} {username} (ID: {me.id})".strip()
                    # 只有在 force=True 时才才去同步账号名到 TG（或更新数据库），日常同步避免该重型操作
                    if force:
                        try:
                            await asyncio.wait_for(update_account_name_from_tg(account_id, client), timeout=5)
                        except asyncio.TimeoutError:
                            warning = "账号名同步超时，登录状态已确认"
                            check_warnings.append(warning)
                            print(f"[LoginStatus] update_account_name timeout for {account_id}")
            except Exception as e:
                warning = f"读取账号资料失败，登录状态已确认: {e}"
                check_warnings.append(warning)
                print(f"[LoginStatus] get_me failed for {account_id}: {e}")

            # Check and update translation bot status (只有 force=True 时才执行重型检测)
            if force:
                try:
                    from db import engine, AccountDb, Session
                    with Session(engine) as db_session:
                        db_acc = db_session.get(AccountDb, account_id)
                        if db_acc and db_acc.bot_setup_status != "approved":
                            await asyncio.wait_for(check_and_update_bot_approval_status(account_id, client, db_session), timeout=8)
                except Exception as e:
                    warning = f"Bot 授权状态检查失败，登录状态已确认: {e}"
                    check_warnings.append(warning)
                    print(f"Error checking bot status in login/status check: {e}")

            # Fetch or use cached spambot status (日常 force=False 的检测不重新查 SpamBot 以规避限流)
            import time
            cached = spambot_cache.get(account_id)
            if cached and not force:
                # 日常同步直接复用历史缓存，不查 SpamBot
                spambot_status = cached["status"]
                spambot_details = cached["details"]
                spambot_time = cached["timestamp"]
            elif cached and force and (time.time() - cached["timestamp"] < 300):
                # 即使 force=True，如果 5 分钟内刚查过，也复用缓存，防止频率过高被限流
                spambot_status = cached["status"]
                spambot_details = cached["details"]
                spambot_time = cached["timestamp"]
            else:
                # 只有没有缓存，或 force=True 且缓存过期时才去查重型的 get_spambot_status
                try:
                    res = await asyncio.wait_for(get_spambot_status(client), timeout=12)
                    spambot_status = res["status"]
                    spambot_details = res["details"]
                    spambot_time = time.time()
                    spambot_cache[account_id] = {
                        "status": spambot_status,
                        "details": spambot_details,
                        "timestamp": spambot_time
                    }
                    save_spambot_cache(spambot_cache)
                except Exception as e:
                    warning = f"SpamBot 检测失败，登录状态已确认: {e}"
                    check_warnings.append(warning)
                    if cached:
                        spambot_status = cached.get("status", "unknown")
                        spambot_details = cached.get("details", "")
                        spambot_time = cached.get("timestamp")
                    print(f"[LoginStatus] spambot check failed for {account_id}: {e}")

        status_res = {
            "is_connected": is_connected,
            "is_authorized": is_authorized,
            "me": me_info,
            "spambot_status": spambot_status,
            "spambot_details": spambot_details,
            "spambot_time": spambot_time,
            "bot_setup_status": db_acc.bot_setup_status if db_acc and is_authorized else "not_started",
            "error": "; ".join(check_warnings) if check_warnings else None,
            "last_error": "; ".join(check_warnings) if check_warnings else None,
            "status_check_failed": bool(check_warnings),
            "status_check_warnings": check_warnings,
        }
        status_res = set_account_status(account_id, status_res, source="login-status")
        if is_authorized and spambot_status == "restricted":
            send_ops_bot_notification(
                "\n".join([
                    "🚨 <b>账号可能被限制</b>",
                    html_line("账号", get_account_notify_label(account_id)),
                    html_line("状态", "SpamBot restricted"),
                    html_line("详情", spambot_details[:800] if spambot_details else "未知"),
                    html_line("时间", ops_event_time()),
                ]),
                dedup_key=f"spambot_restricted:{account_id}",
                cooldown_seconds=1800,
            )
        return status_res
    except asyncio.TimeoutError:
        return set_login_status_check_failed(
            account_id,
            "检测登录状态超时，已保留上一次登录状态；请稍后重试，或检查代理/Telegram 限流。",
            source="login-status-timeout",
            is_connected=bool(active_clients.get(account_id) and active_clients[account_id].is_connected()),
        )
    except Exception as e:
        err_msg = str(e).lower()
        is_deactivated = False
        if "deactivated" in err_msg or "deleted" in err_msg or "deactive" in err_msg or isinstance(e, UserDeactivatedError):
            is_deactivated = True
        is_auth_lost = any(
            marker in err_msg
            for marker in [
                "auth key unregistered",
                "authkeyunregistered",
                "session revoked",
                "user deactivated",
                "unauthorized",
                "not authorized",
            ]
        )
        if not is_deactivated and not is_auth_lost:
            return set_login_status_check_failed(
                account_id,
                f"检测登录状态失败，已保留上一次登录状态: {str(e)}",
                source="login-status-error",
                is_connected=bool(active_clients.get(account_id) and active_clients[account_id].is_connected()),
            )

        # Handle deactivated or banned account by updating DB/config, memory store, and notifying via Bot
        await handle_deactivated_or_banned_account(account_id, e)

        status_res = {
            "is_connected": False,
            "is_authorized": False,
            "is_deactivated": is_deactivated,
            "error": str(e),
            "last_error": str(e),
            "status_check_failed": True,
        }
        status_res = set_account_status(account_id, status_res, source="login-status-error")
        return status_res

@app.post("/api/login/send-code")
async def login_send_code(req: LoginStartRequest, user: dict = Depends(get_current_user)):
    """Initializes connection and requests login verification code."""
    account_id = req.account_id
    phone = req.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    try:
        # Check if config exists in DB first
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)

        config_path = account_config_path(account_id)
        if not db_account:
            # Create config in DB and sync to disk
            template_path = Path(__file__).resolve().parent / "config.json"
            if not template_path.exists():
                template_path = Path(__file__).resolve().parent / "config.example.json"

            if not template_path.exists():
                template = {
                    "auth_mode": "builtin_telegram_desktop",
                    "folder_name": "广告",
                    "connection_timeout_seconds": 12,
                    "connection_retries": 2,
                    "proxy": {"enabled": False, "type": "http", "host": "127.0.0.1", "port": 8800, "username": "", "password": ""}
                }
            else:
                template = load_json(template_path)

            config = build_account_config(account_id, phone, template)
            config["company"] = user["company"]
            config["created_by"] = user["username"]
            config["updated_by"] = user["username"]
            config["owner_username"] = user["username"]
            if req.page_id:
                config["page_id"] = req.page_id

            with Session(engine) as session:
                new_db_acc = AccountDb.from_dict(account_id, config)
                session.add(new_db_acc)
                session.commit()
                # sync
                save_json(config_path, new_db_acc.to_dict())
        else:
            if user["role"] != "admin":
                if db_account.owner_username != user["username"] and db_account.created_by != user["username"]:
                    raise HTTPException(status_code=403, detail="该账号已被其他用户绑定，无权操作")
            with Session(engine) as session:
                db_acc = session.get(AccountDb, account_id)
                if req.page_id:
                    db_acc.page_id = req.page_id
                db_acc.created_by = user["username"]
                db_acc.company = user["company"]
                db_acc.updated_by = user["username"]
                session.add(db_acc)
                session.commit()
                save_json(config_path, db_acc.to_dict())

        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if is_authorized:
            return {"status": "authorized", "message": "Already authorized"}

        result = await client.send_code_request(phone)
        login_states[account_id] = {
            "phone": phone,
            "phone_code_hash": result.phone_code_hash
        }
        return {"status": "code_sent", "message": "Verification code sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send code: {str(e)}")

@app.post("/api/login/submit-code")
async def login_submit_code(req: LoginSubmitRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Submits the code and 2fa password to sign in."""
    account_id = req.account_id
    code = req.code.strip()
    pass2fa = req.pass2fa.strip() if req.pass2fa else None

    if account_id not in login_states:
        raise HTTPException(status_code=400, detail="Login session not initialized. Send code first.")

    state = login_states[account_id]
    phone = state["phone"]
    phone_code_hash = state["phone_code_hash"]

    try:
        client = await get_client(account_id)
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            # Login successful
            login_states.pop(account_id, None)
            await update_account_name_from_tg(account_id, client)
            try:
                me = await client.get_me()
                me_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
                if not me_info:
                    me_info = me.username or "已登录"
                if me.username:
                    me_info += f" (@{me.username})"
                set_account_status(account_id, {
                    "is_connected": True,
                    "is_authorized": True,
                    "me": me_info,
                    "spambot_status": "unknown",
                    "spambot_details": "",
                    "spambot_time": None
                }, source="login-submit")
            except Exception:
                pass

            # Check and update translation bot status
            try:
                from db import engine, AccountDb, Session
                with Session(engine) as db_session:
                    await check_and_update_bot_approval_status(account_id, client, db_session)
            except Exception as e:
                print(f"Error checking bot status in submit-code: {e}")

            # Automatically trigger BOT setup in background
            background_tasks.add_task(auto_trigger_bot_setup_for_account, account_id, client)

            return {"status": "success", "message": "Logged in successfully"}
        except SessionPasswordNeededError:
            if not pass2fa:
                return {"status": "2fa_required", "message": "Two-factor authentication (2FA) password is required"}

            # Submit 2FA password
            await client.sign_in(password=pass2fa)
            login_states.pop(account_id, None)

            # Save the 2FA password to the database and config json
            from db import engine, AccountDb, Session
            with Session(engine) as session:
                db_account = session.get(AccountDb, account_id)
                if db_account:
                    db_account.pass2fa = pass2fa
                    db_account.updated_by = user["username"]
                    db_account.profile_modified = (pass2fa != "" and pass2fa != "0000")
                    session.add(db_account)
                    session.commit()

                    # Sync back to json config file
                    path = account_config_path(account_id)
                    save_json(path, db_account.to_dict())

            await update_account_name_from_tg(account_id, client)
            try:
                me = await client.get_me()
                me_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
                if not me_info:
                    me_info = me.username or "已登录"
                if me.username:
                    me_info += f" (@{me.username})"
                set_account_status(account_id, {
                    "is_connected": True,
                    "is_authorized": True,
                    "me": me_info,
                    "spambot_status": "unknown",
                    "spambot_details": "",
                    "spambot_time": None
                }, source="login-submit")
            except Exception:
                pass

            # Check and update translation bot status
            try:
                from db import engine, AccountDb, Session
                with Session(engine) as db_session:
                    await check_and_update_bot_approval_status(account_id, client, db_session)
            except Exception as e:
                print(f"Error checking bot status in submit-code (2fa): {e}")

            # Automatically trigger BOT setup in background
            background_tasks.add_task(auto_trigger_bot_setup_for_account, account_id, client)

            return {"status": "success", "message": "Logged in successfully with 2FA"}

    except Exception as e:
        set_account_status(
            account_id,
            {"error": str(e), "last_error": str(e), "status_check_failed": True},
            source="login-submit-error",
        )
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.post("/api/login/quick-import")
async def login_quick_import(req: QuickImportRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    import_str = req.import_string.strip()
    if "----" not in import_str:
        raise HTTPException(status_code=400, detail="导入格式不正确。应为: 手机号----接码网址或UUID")

    parts = import_str.split("----")
    phone = parts[0].strip()
    page_id = parts[1].strip()

    # Clean phone number
    if phone.startswith("+"):
        phone_clean = "+" + "".join([c for c in phone[1:] if c.isdigit()])
    else:
        phone_clean = "".join([c for c in phone if c.isdigit()])
        if not phone_clean.startswith("+"):
            phone_clean = "+" + phone_clean

    phone = phone_clean

    from account_manager import account_id_from_name
    account_id = account_id_from_name(phone)

    # Check if exists in DB first
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        db_account = session.get(AccountDb, account_id)

    config_path = account_config_path(account_id)

    if not db_account:
        # Create default config for this phone number
        template_path = Path(__file__).resolve().parent / "config.json"
        if not template_path.exists():
            template_path = Path(__file__).resolve().parent / "config.example.json"

        if not template_path.exists():
            template = {
                "auth_mode": "builtin_telegram_desktop",
                "folder_name": "广告",
                "connection_timeout_seconds": 12,
                "connection_retries": 2,
                "proxy": {"enabled": False, "type": "http", "host": "127.0.0.1", "port": 8800, "username": "", "password": ""}
            }
        else:
            template = load_json(template_path)

        config = build_account_config(account_id, phone, template)
        config["company"] = user["company"]
        config["page_id"] = page_id
        config["created_by"] = user["username"]
        config["updated_by"] = user["username"]
        config["owner_username"] = user["username"]
        with Session(engine) as session:
            new_db_acc = AccountDb.from_dict(account_id, config)
            session.add(new_db_acc)
            session.commit()
            # sync to disk
            save_json(config_path, new_db_acc.to_dict())
    else:
        if user["role"] != "admin" and db_account.owner_username != user["username"] and db_account.created_by != user["username"]:
            raise HTTPException(status_code=403, detail="该账号已被其他用户绑定，无权操作")
        with Session(engine) as session:
            db_acc = session.get(AccountDb, account_id)
            db_acc.page_id = page_id
            db_acc.created_by = user["username"]
            db_acc.company = user["company"]
            db_acc.updated_by = user["username"]
            session.add(db_acc)
            session.commit()
            save_json(config_path, db_acc.to_dict())

    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if is_authorized:
            # Check and update translation bot status
            try:
                from db import engine, AccountDb, Session
                with Session(engine) as db_session:
                    await check_and_update_bot_approval_status(account_id, client, db_session)
            except Exception as e:
                print(f"Error checking bot status in quick-import: {e}")

            # Automatically trigger BOT setup in background
            background_tasks.add_task(auto_trigger_bot_setup_for_account, account_id, client)

            return {
                "status": "authorized",
                "account_id": account_id,
                "phone": phone,
                "page_id": page_id,
                "message": "Already authorized"
            }

        result = await client.send_code_request(phone)
        login_states[account_id] = {
            "phone": phone,
            "phone_code_hash": result.phone_code_hash
        }
        return {
            "status": "code_sent",
            "account_id": account_id,
            "phone": phone,
            "page_id": page_id,
            "message": "Verification code sent successfully"
        }
    except Exception as e:
        set_account_status(
            account_id,
            {"error": str(e), "last_error": str(e), "status_check_failed": True},
            source="quick-import-error",
        )
        raise HTTPException(status_code=500, detail=f"Failed to send code during quick import: {str(e)}")

# Global storage for background client connection tasks and errors
bg_connect_tasks = {}
connection_errors = {}

async def fetch_recent_official_codes(account_id: str, client: TelegramClient):
    """Proactively retrieves recent official login code messages from 777000 history."""
    add_login_log(account_id, "正在获取官方通知 (777000) 历史消息...")
    try:
        if not client.is_connected():
            add_login_log(account_id, "获取历史消息失败：客户端未连接")
            return
        if not await client.is_user_authorized():
            add_login_log(account_id, "获取历史消息失败：账号未授权")
            return

        # Get messages from official sender 777000
        messages = await client.get_messages(777000, limit=5)
        if not messages:
            add_login_log(account_id, "未发现官方通知历史消息")
            return

        import datetime
        added_count = 0
        for msg in messages:
            if msg and msg.message:
                text = msg.message
                msg_date = msg.date
                if isinstance(msg_date, datetime.datetime):
                    timestamp = msg_date.timestamp()
                else:
                    timestamp = time.time()

                if account_id not in official_messages_store:
                    official_messages_store[account_id] = []

                # Avoid duplicates
                exists = any(m["text"] == text and abs(m["timestamp"] - timestamp) < 5 for m in official_messages_store[account_id])
                if not exists:
                    official_messages_store[account_id].append({
                        "text": text,
                        "timestamp": timestamp
                    })
                    added_count += 1

                # Also check for codes
                match = re.search(r"Login code\s*:?\s*(\d+)", text, re.IGNORECASE)
                if not match:
                    match = re.search(r"(?:code|验证码)[:：\s]+(\d+)", text, re.IGNORECASE)
                if not match:
                    match = re.search(r"\b(\d{5,6})\b", text)

                if match:
                    code = match.group(1)
                    if account_id not in captured_login_codes:
                        captured_login_codes[account_id] = []

                    exists_code = any(c["code"] == code and abs(c["timestamp"] - timestamp) < 10 for c in captured_login_codes[account_id])
                    if not exists_code:
                        captured_login_codes[account_id].append({
                            "code": code,
                            "timestamp": timestamp,
                            "text": text
                        })
                        # Keep last 10 codes
                        captured_login_codes[account_id] = captured_login_codes[account_id][-10:]

        if account_id in official_messages_store:
            official_messages_store[account_id] = sorted(
                official_messages_store[account_id],
                key=lambda x: x["timestamp"],
                reverse=True
            )[:5]

        add_login_log(account_id, f"成功同步官方历史通知消息，共加载 {len(official_messages_store[account_id])} 条。")
    except Exception as e:
        error_msg = str(e)
        add_login_log(account_id, f"获取历史消息失败: {error_msg}")

async def bg_connect_client(account_id: str):
    try:
        connection_errors.pop(account_id, None)
        login_connection_logs[account_id] = []
        add_login_log(account_id, "开始连接电报客户端 (后台任务启动)...")

        client = await get_client(account_id)
        add_login_log(account_id, "连接电报服务成功！")

        # Fetch the official codes once connected in case the event listener was offline
        await fetch_recent_official_codes(account_id, client)
        add_login_log(account_id, "已开启实时新消息监听，等待接收验证码...")
    except Exception as e:
        error_msg = str(e)
        add_login_log(account_id, f"后台连接失败: {error_msg}")
        connection_errors[account_id] = error_msg

@app.get("/api/accounts/{account_id}/login-code")
async def get_captured_login_code(account_id: str, user: dict = Depends(get_current_user)):
    """Fetches captured Telegram official login codes for an account."""
    check_account_company(account_id, user)

    is_connected = False
    client = None

    # Initialize logs if not present
    if account_id not in login_connection_logs:
        login_connection_logs[account_id] = []

    # Ensure client is connected and listening in the background if authorized
    try:
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)

        if db_account:
            session_name = db_account.session_name
            from sync_folder_groups import resolve_path
            from pathlib import Path
            config_path = account_config_path(account_id)
            base_dir = config_path.parent.parent
            session_path = resolve_path(base_dir, session_name)

            session_file = Path(f"{session_path}.session")
            if not session_file.exists():
                session_file = Path(session_path)

            if session_file.exists() and session_file.stat().st_size > 0:
                # Account is authorized, check if client is already connected
                if account_id in active_clients:
                    client = active_clients[account_id]
                    if client.is_connected():
                        is_connected = True

                # If not connected and no task is running, start connection task
                if not is_connected:
                    task = bg_connect_tasks.get(account_id)
                    if not task or task.done():
                        bg_connect_tasks[account_id] = asyncio.create_task(bg_connect_client(account_id))
            else:
                add_login_log(account_id, "错误: 未找到该账号的在线Session文件 (可能已注销或文件丢失)。请重新登录。")
        else:
            add_login_log(account_id, "错误: 数据库中不存在此账号。")
    except Exception as e:
        add_login_log(account_id, f"触发后台连接失败: {e}")

    # If client is connected and logs are empty, log that it is connected
    if is_connected and not login_connection_logs[account_id]:
        add_login_log(account_id, "客户端已在线连接。")

    # If the client is already connected, proactively trigger history check in background
    if is_connected and client:
        asyncio.create_task(fetch_recent_official_codes(account_id, client))

    # Get official messages
    raw_msgs = official_messages_store.get(account_id, [])
    sorted_msgs = sorted(raw_msgs, key=lambda x: x["timestamp"], reverse=True)[:5]

    # Get error if any
    error = connection_errors.get(account_id, None)

    # Check if currently connecting
    is_connecting = False
    task = bg_connect_tasks.get(account_id)
    if task and not task.done():
        is_connecting = True

    return {
        "status": "success",
        "raw_messages": sorted_msgs,
        "logs": login_connection_logs.get(account_id, []),
        "error": error,
        "is_connecting": is_connecting
    }



background_tasks = set()

@app.on_event("startup")
async def startup_event():
    """Backgrounds auto-connection and online loop on startup to complete startup instantly."""
    t1 = asyncio.create_task(auto_connect_bg_task())
    background_tasks.add(t1)
    t1.add_done_callback(background_tasks.discard)

    t2 = asyncio.create_task(clean_idle_clients_loop())
    background_tasks.add(t2)
    t2.add_done_callback(background_tasks.discard)

    t3 = asyncio.create_task(account_status_monitor_loop())
    background_tasks.add(t3)
    t3.add_done_callback(background_tasks.discard)

    if ENABLE_REALTIME_PRIVATE_DM:
        t4 = asyncio.create_task(auto_private_listener_loop())
        background_tasks.add(t4)
        t4.add_done_callback(background_tasks.discard)
    else:
        print("[Startup] Realtime private DM listener is DISABLED.")
    load_pending_private_sends_from_db()
    resume_persistent_tasks_on_startup()

    # 0. Migrate predefined_ads table to support group_type column
    try:
        import sqlite3
        from db import DB_PATH
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(predefined_ads)")
            cols = [col[1] for col in cursor.fetchall()]
            if "group_type" not in cols:
                cursor.execute("ALTER TABLE predefined_ads ADD COLUMN group_type TEXT DEFAULT '英文短';")
                conn.commit()
                print("[Startup Migration] Successfully added 'group_type' column to 'predefined_ads' table.")
    except Exception as em:
        print(f"[Startup Migration] Failed to migrate predefined_ads table: {em}")

    # Perform startup database sync: Category auto-fill and Channel deletion
    try:
        from db import engine, GroupDb, GroupCategoryDb, Session, select
        with Session(engine) as session:
            # 1. Scan the current group list, and if there are channels, delete them.
            stmt_channels = select(GroupDb).where(GroupDb.type == "channel")
            channels_to_delete = session.exec(stmt_channels).all()
            if channels_to_delete:
                print(f"[Startup Cleanup] Found {len(channels_to_delete)} channels in groups library. Deleting them...")
                for ch in channels_to_delete:
                    session.delete(ch)
                session.commit()

            # 2. Compare all current group categories to see if any are not in the category list, and automatically add them.
            stmt_groups = select(GroupDb)
            all_groups = session.exec(stmt_groups).all()

            stmt_categories = select(GroupCategoryDb)
            all_categories = session.exec(stmt_categories).all()

            # GroupCategoryDb.name is globally unique in the current schema.
            # Keep startup sync aligned with that constraint instead of trying
            # to create the same category name once per company.
            existing_category_names = {
                cat.name.strip().lower()
                for cat in all_categories
                if cat.name and cat.name.strip()
            }

            for g in all_groups:
                if not g.category:
                    continue
                g_cat_clean = g.category.strip()
                g_cat_lower = g_cat_clean.lower()

                if g_cat_lower not in existing_category_names:
                    new_cat = GroupCategoryDb(name=g_cat_clean, company=g.company)
                    session.add(new_cat)
                    try:
                        session.commit()
                        existing_category_names.add(g_cat_lower)
                        print(f"[Startup Category Sync] Added missing category '{g_cat_clean}' for company '{g.company}'")
                    except Exception as insert_err:
                        session.rollback()
                        if "UNIQUE constraint failed" in str(insert_err):
                            existing_category_names.add(g_cat_lower)
                        else:
                            raise

    except Exception as se:
        print(f"[Startup Sync] Error running category/channel sync: {se}")

# --- TELEGRAM FOLDER LISTING API ---

@app.get("/api/accounts/{account_id}/folders")
@account_api_operation("read_folders", label="读取文件夹")
async def get_account_folders(account_id: str, user: dict = Depends(get_current_user)):
    """Lists all Telegram folders (dialog filters) for an authorized account."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result)
        folders = [
            normalize_title(item.title)
            for item in raw_filters
            if isinstance(item, (types.DialogFilter, types.DialogFilterChatlist))
        ]
        return folders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch folders: {str(e)}")

# --- DYNAMIC CAMPAIGN TASK SYSTEM ---

active_campaign_tasks: Dict[str, asyncio.Task] = {}
active_campaign_schedules: Dict[str, asyncio.Task] = {}

def is_campaign_task_running(task) -> bool:
    # 1. Task Mode (asyncio Task in main process)
    if task.id in active_campaign_tasks and not active_campaign_tasks[task.id].done():
        return True
    # 2. Subprocess Mode (Classic Mode)
    try:
        acc_ids = parse_campaign_account_ids(task)
        for acc_id in acc_ids:
            if is_campaign_running_for_account(acc_id):
                return True
    except Exception:
        pass
    return False


BEIJING_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = ZoneInfo("UTC")


@app.get("/api/accounts/{account_id}/folders-groups")
@account_api_operation("read_folder_groups", label="读取文件夹群组")
async def get_account_folders_groups(account_id: str, user: dict = Depends(get_current_user)):
    """Fetches Telegram folders and retrieves list of group chats inside each folder in real-time."""
    check_account_company(account_id, user)
    from sync_folder_groups import normalize_title, entity_type
    from telethon.tl.types import DialogFilter, DialogFilterChatlist
    from telethon import utils

    try:
        client = await get_client(account_id)
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Account is not authorized")

        # 1. Fetch filters (folders)
        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result)
        filters = [
            item
            for item in raw_filters
            if isinstance(item, (DialogFilter, DialogFilterChatlist))
        ]

        # 2. Fetch dialogs once to lookup
        dialogs = await client.get_dialogs()

        # 3. Scan
        include_types = {"group", "supergroup"}
        folders_groups = {}
        for folder in filters:
            folder_title = normalize_title(folder.title)
            folder_groups = []

            explicit_peers = list(getattr(folder, "include_peers", []) or []) + list(getattr(folder, "pinned_peers", []) or [])
            exclude_peers = list(getattr(folder, "exclude_peers", []) or [])

            exclude_ids = set()
            for p in exclude_peers:
                try:
                    exclude_ids.add(utils.get_peer_id(p))
                except Exception:
                    pass

            seen_ids = set()

            # Resolve explicit peers
            for peer in explicit_peers:
                peer_id = None
                try:
                    peer_id = utils.get_peer_id(peer)
                except Exception:
                    pass
                if not peer_id or peer_id in seen_ids or peer_id in exclude_ids:
                    continue

                dlg = next((d for d in dialogs if utils.get_peer_id(d.entity) == peer_id), None)
                if dlg:
                    t = entity_type(dlg.entity)
                    if t in include_types:
                        seen_ids.add(peer_id)
                        folder_groups.append({
                            "chat_id": peer_id,
                            "title": dlg.name or "未命名群组",
                            "username": getattr(dlg.entity, "username", None) or ""
                        })

            # Dynamic rules
            has_dynamic_groups = bool(getattr(folder, "groups", False))
            if has_dynamic_groups:
                for dlg in dialogs:
                    peer_id = utils.get_peer_id(dlg.entity)
                    if peer_id in seen_ids or peer_id in exclude_ids:
                        continue
                    t = entity_type(dlg.entity)
                    if t in include_types:
                        seen_ids.add(peer_id)
                        folder_groups.append({
                            "chat_id": peer_id,
                            "title": dlg.name or "未命名群组",
                            "username": getattr(dlg.entity, "username", None) or ""
                        })

            folders_groups[folder_title] = folder_groups

        # Build virtual folders for all groups and non-folder groups
        all_groups = []
        for dlg in dialogs:
            peer_id = utils.get_peer_id(dlg.entity)
            t = entity_type(dlg.entity)
            if t in include_types:
                all_groups.append({
                    "chat_id": peer_id,
                    "title": dlg.name or "未命名群组",
                    "username": getattr(dlg.entity, "username", None) or ""
                })

        all_folder_group_ids = set()
        for folder_groups in folders_groups.values():
            for g in folder_groups:
                all_folder_group_ids.add(g["chat_id"])

        uncategorized_groups = [g for g in all_groups if g["chat_id"] not in all_folder_group_ids]

        final_folders = {}
        if all_groups:
            final_folders["所有群组"] = all_groups

        for k, v in folders_groups.items():
            final_folders[k] = v

        if uncategorized_groups:
            final_folders["非文件夹群组"] = uncategorized_groups

        return final_folders
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取文件夹及群组失败: {str(e)}")

@app.post("/api/campaign/tasks")
async def create_campaign_task(req: MessageCampaignTaskRequest, user: dict = Depends(get_current_user)):
    requested_account_ids = req.account_ids or [req.account_id]
    requested_account_ids = [str(x).strip() for x in requested_account_ids if str(x).strip()]
    requested_account_ids = list(dict.fromkeys(requested_account_ids))
    if not requested_account_ids:
        raise HTTPException(status_code=400, detail="请选择至少一个执行账号。")

    for selected_account_id in requested_account_ids:
        if is_account_busy_with_task(selected_account_id):
            raise HTTPException(status_code=400, detail=f"账号 {selected_account_id} 有未完成的任务，无法启动新任务。")

    if req.group_interval_seconds < 5:
        raise HTTPException(status_code=400, detail="单个群发送间隔不能小于 5 秒，以防触发 Telegram 风控锁定！")

    selected_accounts = []
    for selected_account_id in requested_account_ids:
        db_account = check_account_company(selected_account_id, user)
        if getattr(db_account, "is_available", True) is False:
            raise HTTPException(status_code=400, detail=f"账号 {db_account.account_name or selected_account_id} 当前为占用/禁用状态，无法启动轰炸任务。")
        selected_accounts.append(db_account)

    primary_account = selected_accounts[0]
    primary_account_id = primary_account.id
    phone = primary_account.account_name or primary_account_id
    phones_by_id = {
        acc.id: (acc.account_name or acc.id)
        for acc in selected_accounts
    }

    from db import engine, CampaignTaskDb, Session
    import uuid
    import json
    from datetime import datetime

    scheduled_utc, scheduled_bj_label = parse_campaign_scheduled_start(req.scheduled_start_at)
    is_scheduled_task = scheduled_utc is not None

    # Save last params
    try:
        last_params_path = Path("data/campaign_last_params.json")
        last_params_path.parent.mkdir(parents=True, exist_ok=True)

        last_params = {}
        if last_params_path.exists():
            try:
                last_params = json.loads(last_params_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        for selected_account_id in requested_account_ids:
            last_params[selected_account_id] = {
            "max_cycles": req.max_cycles,
            "round_interval_minutes": req.round_interval_minutes,
            "group_interval_seconds": req.group_interval_seconds,
            "is_safety": req.is_safety,
            "message": req.message,
            "target_groups": [g.model_dump() for g in req.target_groups],
            "account_ids": requested_account_ids,
            "multi_account_safety_enabled": req.multi_account_safety_enabled,
            "strategy_enabled": req.strategy_enabled,
            "scheduled_start_at": req.scheduled_start_at or ""
            }
        last_params_path.write_text(json.dumps(last_params, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Failed to save last campaign params: {e}")

    task_id = str(uuid.uuid4())
    now_str = get_beijing_time_str()
    task_config = {
        "multi_account_safety_enabled": req.multi_account_safety_enabled,
        "strategy_enabled": req.strategy_enabled,
    }
    if is_scheduled_task and scheduled_utc and scheduled_bj_label:
        task_config.update({
            "scheduled_start_at_utc": scheduled_utc.isoformat(),
            "scheduled_start_at_beijing": scheduled_bj_label,
        })

    with Session(engine) as session:
        new_task = CampaignTaskDb(
            id=task_id,
            owner_username=user["username"],
            company=user["company"],
            account_id=primary_account_id,
            phone=phone,
            account_ids_json=json.dumps(requested_account_ids, ensure_ascii=False),
            phones_json=json.dumps(phones_by_id, ensure_ascii=False),
            status="scheduled" if is_scheduled_task else "running",
            max_cycles=req.max_cycles,
            current_cycle=0,
            round_interval_minutes=req.round_interval_minutes,
            group_interval_seconds=req.group_interval_seconds,
            is_safety=req.is_safety,
            message=req.message,
            target_groups_json=json.dumps([g.model_dump() for g in req.target_groups], ensure_ascii=False),
            task_config_json=json.dumps(task_config, ensure_ascii=False),
            success_count=0,
            fail_count=0,
            created_at=now_str,
            updated_at=now_str,
            created_by=user["username"],
            updated_by=user["username"]
        )
        session.add(new_task)
        session.commit()

    if is_scheduled_task:
        t = asyncio.create_task(scheduled_campaign_runner(task_id))
        active_campaign_schedules[task_id] = t
        delay_seconds = max(0, int((scheduled_utc - campaign_now_utc()).total_seconds())) if scheduled_utc else 0
        return {
            "status": "scheduled",
            "task_id": task_id,
            "scheduled_start_at_beijing": scheduled_bj_label,
            "remaining_seconds": delay_seconds,
            "remaining_text": campaign_duration_text(delay_seconds),
        }

    await launch_campaign_task(task_id, scheduled=False)

    return {"status": "success", "task_id": task_id}

@app.get("/api/campaign/tasks")
def list_campaign_tasks(user: dict = Depends(get_current_user)):
    from db import engine, AccountDb, CampaignTaskDb, Session, select
    with Session(engine) as session:
        if user["role"] == "admin":
            stmt = select(CampaignTaskDb).order_by(CampaignTaskDb.created_at.desc())
            results = session.exec(stmt).all()
        else:
            stmt_acc = query_allowed_accounts(session, user)
            allowed_ids = {acc.id for acc in session.exec(stmt_acc).all()}
            stmt = select(CampaignTaskDb).order_by(CampaignTaskDb.created_at.desc())
            results = [
                task for task in session.exec(stmt).all()
                if any(acc_id in allowed_ids for acc_id in parse_campaign_account_ids(task))
            ]
        
        # Auto-Recovery & State Sync for Zombie Tasks
        needs_commit = False
        for task in results:
            if task.status == "running":
                has_active = is_campaign_task_running(task)
                if not has_active:
                    task.status = "stopped"
                    task.error_detail = "检测到发送进程已异常退出，已自动同步状态为停止。"
                    task.updated_at = get_beijing_time_str()
                    session.add(task)
                    needs_commit = True
        if needs_commit:
            session.commit()
            # Refresh the list to reflect database changes
            if user["role"] == "admin":
                results = session.exec(stmt).all()
            else:
                results = [
                    task for task in session.exec(stmt).all()
                    if any(acc_id in allowed_ids for acc_id in parse_campaign_account_ids(task))
                ]
        
        return [task.model_dump() for task in results]

@app.post("/api/campaign/tasks/{task_id}/stop")
async def stop_campaign_task(task_id: str, user: dict = Depends(get_current_user)):
    from db import engine, CampaignTaskDb, Session, AccountDb
    from datetime import datetime

    with Session(engine) as session:
        task = session.get(CampaignTaskDb, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if user["role"] != "admin":
            allowed_ids = {acc.id for acc in session.exec(query_allowed_accounts(session, user)).all()}
            if not any(acc_id in allowed_ids for acc_id in parse_campaign_account_ids(task)):
                raise HTTPException(status_code=403, detail="没有权限操作此任务")
        affected_account_ids = parse_campaign_account_ids(task)

        t = active_campaign_tasks.get(task_id)
        if t:
            t.cancel()
        scheduled_t = active_campaign_schedules.get(task_id)
        if scheduled_t:
            scheduled_t.cancel()
            active_campaign_schedules.pop(task_id, None)

        if task.status in {"running", "scheduled"}:
            task.status = "stopped"
            task.updated_at = get_beijing_time_str()
            task.updated_by = user["username"]
            session.add(task)
            session.commit()
        release_account_task_usage(task_id, affected_account_ids, source="campaign-task-stop")

    return {"status": "success"}

@app.post("/api/campaign/stop-all")
async def stop_all_campaigns(user: dict = Depends(get_current_user)):
    from db import engine, AccountDb, CampaignTaskDb, Session, select
    from datetime import datetime

    with Session(engine) as session:
        if user["role"] == "admin":
            stmt = select(CampaignTaskDb).where(CampaignTaskDb.status.in_(["running", "scheduled"]))
            running_tasks = session.exec(stmt).all()
        else:
            stmt_acc = query_allowed_accounts(session, user)
            allowed_ids = {acc.id for acc in session.exec(stmt_acc).all()}
            stmt = select(CampaignTaskDb).where(CampaignTaskDb.status.in_(["running", "scheduled"]))
            running_tasks = [
                task for task in session.exec(stmt).all()
                if any(acc_id in allowed_ids for acc_id in parse_campaign_account_ids(task))
            ]
        stopped_task_accounts = []
        for task in running_tasks:
            t = active_campaign_tasks.get(task.id)
            if t:
                t.cancel()
                try:
                    del active_campaign_tasks[task.id]
                except KeyError:
                    pass
            scheduled_t = active_campaign_schedules.get(task.id)
            if scheduled_t:
                scheduled_t.cancel()
                try:
                    del active_campaign_schedules[task.id]
                except KeyError:
                    pass
            task.status = "stopped"
            task.updated_at = get_beijing_time_str()
            task.updated_by = user["username"]
            stopped_task_accounts.append((task.id, parse_campaign_account_ids(task)))
            session.add(task)
        session.commit()
    for stopped_task_id, account_ids in stopped_task_accounts:
        release_account_task_usage(stopped_task_id, account_ids, source="campaign-stop-all")

    return {"status": "success"}

@app.get("/api/campaign/tasks/{task_id}/logs")
def get_campaign_task_logs(task_id: str, limit: int = 200, user: dict = Depends(get_current_user)):
    from db import engine, CampaignLogDb, CampaignTaskDb, PredefinedAdDb, Session, select, AccountDb
    with Session(engine) as session:
        task = session.get(CampaignTaskDb, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if user["role"] != "admin":
            allowed_ids = {acc.id for acc in session.exec(query_allowed_accounts(session, user)).all()}
            if not any(acc_id in allowed_ids for acc_id in parse_campaign_account_ids(task)):
                raise HTTPException(status_code=403, detail="没有权限操作此任务")

        stmt = select(CampaignLogDb).where(CampaignLogDb.task_id == task_id).order_by(CampaignLogDb.id.desc()).limit(limit)
        results = session.exec(stmt).all()
        target_groups = []
        try:
            target_groups = json.loads(task.target_groups_json or "[]")
            if not isinstance(target_groups, list):
                target_groups = []
        except Exception:
            target_groups = []

        def normalize_group_id(value: Any) -> str:
            return str(value or "").strip().removeprefix("-100").removeprefix("-")

        def normalize_username(value: Any) -> str:
            raw = str(value or "").strip()
            if not raw:
                return ""
            raw = re.sub(r"^https?://t\.me/", "", raw, flags=re.I)
            raw = raw.lstrip("@").split("/")[0].split("?")[0].split("#")[0]
            return f"@{raw}" if raw else ""

        def infer_group_username(log_data: dict) -> str:
            existing = normalize_username(log_data.get("group_username"))
            if existing:
                return existing
            if len(target_groups) == 1:
                only = target_groups[0]
                return normalize_username(only.get("username") or only.get("link") or only.get("title"))
            log_gid = normalize_group_id(log_data.get("group_id"))
            log_title = str(log_data.get("group_title") or "").strip()
            for group in target_groups:
                candidate_ids = [
                    normalize_group_id(group.get("chat_id")),
                    normalize_group_id(group.get("group_id")),
                    normalize_group_id(group.get("id")),
                    normalize_group_id(group.get("peer_id")),
                ]
                same_id = bool(log_gid) and log_gid in candidate_ids
                same_title = bool(log_title) and log_title == str(group.get("title") or "").strip()
                if same_id or same_title:
                    return normalize_username(group.get("username") or group.get("link") or group.get("title"))
            return ""

        task_ad_pool = []
        try:
            parsed_message = json.loads(task.message or "")
            if isinstance(parsed_message, list):
                task_ad_pool = [str(item) for item in parsed_message if str(item).strip()]
        except Exception:
            pass
        if not task_ad_pool and task.message:
            task_ad_pool = [str(task.message)]

        predefined_ad_cache: dict[int, str] = {}

        def resolve_ad_text(log_data: dict) -> str:
            ref = str(log_data.get("ad_ref") or "").strip()
            if ref.startswith("pool:"):
                try:
                    idx = int(ref.split(":", 1)[1])
                    if 0 <= idx < len(task_ad_pool):
                        return task_ad_pool[idx]
                except Exception:
                    return ""
            if ref.startswith("predefined:"):
                try:
                    ad_id = int(ref.split(":", 1)[1])
                except Exception:
                    return ""
                if ad_id not in predefined_ad_cache:
                    ad_item = session.get(PredefinedAdDb, ad_id)
                    predefined_ad_cache[ad_id] = ad_item.content if ad_item else ""
                return predefined_ad_cache.get(ad_id, "")
            if ref == "fallback":
                return "🌹 RosePay 广告投放中"
            # Backward compatibility for older rows written with detail preview.
            detail = str(log_data.get("detail") or "")
            preview_match = re.search(r"\s*\[预览:\s*([\s\S]+?)\]\s*$", detail)
            if preview_match:
                return preview_match.group(1).strip()
            return ""

        payload = []
        for log in results:
            item = log.model_dump()
            item["group_username"] = infer_group_username(item)
            item["ad_text"] = resolve_ad_text(item)
            payload.append(item)
        return payload

@app.get("/api/campaign/accounts/{account_id}/last-params")
def get_campaign_last_params(account_id: str, user: dict = Depends(get_current_user)):
    check_account_company(account_id, user)
    import json
    last_params_path = Path("data/campaign_last_params.json")
    if last_params_path.exists():
        try:
            last_params = json.loads(last_params_path.read_text(encoding="utf-8"))
            if account_id in last_params:
                return last_params[account_id]
        except Exception:
            pass
    return {"status": "none"}

class PredefinedAdRequest(BaseModel):
    description: str
    content: str
    group_type: str = "英文短"

@app.get("/api/predefined-ads")
def list_predefined_ads(user: dict = Depends(get_current_user)):
    from db import engine, PredefinedAdDb, Session, select
    with Session(engine) as session:
        if user["username"] in ("eason", "admin"):
            stmt = select(PredefinedAdDb)
        else:
            stmt = select(PredefinedAdDb).where(PredefinedAdDb.company == user["company"])
        results = session.exec(stmt).all()
        return [item.model_dump() for item in results]

@app.post("/api/predefined-ads")
def create_predefined_ad(req: PredefinedAdRequest, user: dict = Depends(get_current_user)):
    from db import engine, PredefinedAdDb, Session
    desc = req.description.strip()
    cnt = req.content.strip()
    gtype = req.group_type.strip()
    if not desc:
        raise HTTPException(status_code=400, detail="描述不能为空")
    if not cnt:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if gtype not in ("中文长", "中文短", "英文长", "英文短"):
        raise HTTPException(status_code=400, detail="非法的群组类型")

    content_len = len(cnt)
    content_bytes = len(cnt.encode("utf-8"))
    if content_bytes > 350:
        raise HTTPException(status_code=400, detail=f"广告内容不能超过 350 UTF-8字节（当前 {content_bytes} 字节）")
    if "..." in cnt or "…" in cnt:
        raise HTTPException(status_code=400, detail="广告内容包含 ... 或 …，请改成完整收尾后再保存")
    if "短" in gtype:
        if content_len >= 200:
            raise HTTPException(status_code=400, detail=f"短广告内容长度必须在 200 字以下（当前 {content_len} 字）")
    elif "长" in gtype:
        if content_len < 200:
            raise HTTPException(status_code=400, detail=f"长广告内容长度必须在 200 字及以上（当前 {content_len} 字）")

    with Session(engine) as session:
        new_ad = PredefinedAdDb(
            description=desc,
            content=cnt,
            group_type=gtype,
            company=user["company"],
            created_by=user["username"],
            updated_by=user["username"]
        )
        session.add(new_ad)
        session.commit()
        session.refresh(new_ad)
        return new_ad.model_dump()

@app.put("/api/predefined-ads/{ad_id}")
def update_predefined_ad(ad_id: int, req: PredefinedAdRequest, user: dict = Depends(get_current_user)):
    from db import engine, PredefinedAdDb, Session
    desc = req.description.strip()
    cnt = req.content.strip()
    gtype = req.group_type.strip()
    if not desc:
        raise HTTPException(status_code=400, detail="描述不能为空")
    if not cnt:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if gtype not in ("中文长", "中文短", "英文长", "英文短"):
        raise HTTPException(status_code=400, detail="非法的群组类型")

    content_len = len(cnt)
    content_bytes = len(cnt.encode("utf-8"))
    if content_bytes > 350:
        raise HTTPException(status_code=400, detail=f"广告内容不能超过 350 UTF-8字节（当前 {content_bytes} 字节）")
    if "..." in cnt or "…" in cnt:
        raise HTTPException(status_code=400, detail="广告内容包含 ... 或 …，请改成完整收尾后再保存")
    if "短" in gtype and content_len >= 200:
        raise HTTPException(status_code=400, detail=f"短广告内容长度必须在 200 字以下（当前 {content_len} 字）")
    if "长" in gtype and content_len < 200:
        raise HTTPException(status_code=400, detail=f"长广告内容长度必须在 200 字及以上（当前 {content_len} 字）")

    with Session(engine) as session:
        ad_item = session.get(PredefinedAdDb, ad_id)
        if not ad_item:
            raise HTTPException(status_code=404, detail="广告内容未找到")
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and ad_item.company != user["company"]:
            raise HTTPException(status_code=404, detail="广告内容未找到")
        ad_item.description = desc
        ad_item.content = cnt
        ad_item.group_type = gtype
        ad_item.updated_by = user["username"]
        session.add(ad_item)
        session.commit()
        session.refresh(ad_item)
        return ad_item.model_dump()

@app.delete("/api/predefined-ads/{ad_id}")
def delete_predefined_ad(ad_id: int, user: dict = Depends(get_current_user)):
    from db import engine, PredefinedAdDb, Session
    with Session(engine) as session:
        ad_item = session.get(PredefinedAdDb, ad_id)
        if not ad_item:
            raise HTTPException(status_code=404, detail="广告内容未找到")
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and ad_item.company != user["company"]:
            raise HTTPException(status_code=404, detail="广告内容未找到")
        session.delete(ad_item)
        session.commit()
        return {"status": "success"}

class SendStrategyMessageRequest(BaseModel):
    chat_id: str
    gtype: str
    fallback_message: str
    company: str

@app.post("/api/internal/send-strategy-message")
async def send_strategy_message(req: SendStrategyMessageRequest):
    """
    Internal API called by ad_sender.py to send a strategy message to a group.
    It selects a random online account and a random matched ad template.
    """
    from db import engine, PredefinedAdDb, Session, select
    import random

    chat_id = req.chat_id
    gtype = req.gtype
    fallback_message = req.fallback_message
    company = req.company

    # 1. Find all logged-in and active accounts for this company
    allowed_clients = []
    for account_id, client in list(active_clients.items()):
        try:
            if client.is_connected() and await client.is_user_authorized():
                # Verify if this account belongs to the user's company or is admin
                from db import AccountDb
                with Session(engine) as session:
                    db_acc = session.get(AccountDb, account_id)
                    if db_acc and (db_acc.company == company or company in ("admin", "rosepay")):
                        allowed_clients.append((account_id, client, db_acc.account_name or account_id))
        except Exception:
            continue

    if not allowed_clients:
        raise HTTPException(status_code=400, detail="没有可用的在线电报账号")

    # Randomly pick an account client
    selected_account_id, selected_client, selected_account_name = random.choice(allowed_clients)

    # 2. Select a random ad matching the gtype from predefined_ads
    selected_message = fallback_message
    try:
        with Session(engine) as session:
            stmt = select(PredefinedAdDb).where(
                PredefinedAdDb.group_type == gtype,
                PredefinedAdDb.company == company
            )
            ads = session.exec(stmt).all()
            if ads:
                selected_message = random.choice(ads).content
            else:
                # Fallback to admin global ads of this gtype
                stmt_admin = select(PredefinedAdDb).where(
                    PredefinedAdDb.group_type == gtype,
                    PredefinedAdDb.company == "admin"
                )
                ads_admin = session.exec(stmt_admin).all()
                if ads_admin:
                    selected_message = random.choice(ads_admin).content
    except Exception as e:
        print(f"Error fetching predefined ads in internal API: {e}")

    # 3. Perform sending message using the selected client
    try:
        try:
            peer = int(chat_id)
        except ValueError:
            peer = chat_id

        if not await check_can_speak(selected_client, peer):
            raise Exception("无该群发言权限，已跳过未发送")
        await selected_client.send_message(peer, selected_message)

        # Log this send operation
        try:
            from db import AdLogDb
            from datetime import datetime, timezone
            with Session(engine) as session:
                new_log = AdLogDb(
                    time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    folder=gtype,
                    chat_id=str(chat_id),
                    title=f"[策略] {gtype}",
                    action="发送",
                    status="成功",
                    detail=f"执行账号: {selected_account_name} ({selected_account_id})；message_id={audit.get('message_id')}；{audit.get('reason')}{audit_hint}",
                    company=company
                )
                session.add(new_log)
                session.commit()
        except Exception as log_err:
            print(f"Failed to write strategy ad log: {log_err}")

        return {
            "status": "success",
            "account_id": selected_account_id,
            "account_name": selected_account_name,
            "message_sent": selected_message,
            "audit": audit,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"发送失败(使用账号 {selected_account_name}): {str(exc)}")

# --- CAMPAIGN MANAGEMENT APIs ---

@app.post("/api/campaign/start")
async def start_campaign(req: CampaignStartRequest, user: dict = Depends(get_current_user)):
    """Configures and runs a subprocess campaign task for an account using SQLite config."""
    account_id = req.account_id
    if is_account_busy_with_task(account_id):
        raise HTTPException(status_code=400, detail="该账号有未完成的任务，无法启动新任务。")

    folder_name = req.folder_name.strip()
    message_text = req.message_text.strip()
    task_interval_minutes = req.task_interval_minutes
    group_interval_seconds = req.group_interval_seconds
    is_strategy = getattr(req, "is_strategy", False)

    if not folder_name:
        raise HTTPException(status_code=400, detail="Folder name is required")
    if not is_strategy and not message_text:
        raise HTTPException(status_code=400, detail="Message text is required")

    # Stop any active process for this account first
    if account_id in active_processes:
        process = active_processes[account_id]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except Exception:
                process.kill()

    # 1. Update SQLite AccountDb settings
    db_account = check_account_company(account_id, user)
    if getattr(db_account, "is_available", True) is False:
        raise HTTPException(status_code=400, detail="该账号当前为禁用状态，无法启动任务。")
    from db import engine, AccountDb, Session
    with Session(engine) as session:
        # Re-fetch in local session context to write changes safely
        db_account = session.get(AccountDb, account_id)

        db_account.campaign_folder = folder_name
        db_account.campaign_message = message_text
        db_account.campaign_interval_minutes = task_interval_minutes
        db_account.campaign_group_interval_seconds = group_interval_seconds

        session.add(db_account)
        session.commit()

        # Sync the .json file so that CLI scripts can also run if needed
        path = account_config_path(account_id)
        save_json(path, db_account.to_dict())

    # Disconnect active client in web server to prevent SQLite session locks
    if account_id in active_clients:
        try:
            client = active_clients.pop(account_id, None)
            registered_listeners.discard(account_id)
            active_clients_last_accessed.pop(account_id, None)
            set_account_status(account_id, {"is_connected": False}, source="campaign-disconnect")
            if client and client.is_connected():
                print(f"Disconnecting active client {account_id} before starting campaign to prevent database lock...")
                await client.disconnect()
        except Exception as e:
            print(f"Error disconnecting client {account_id} before campaign: {e}")

    # 2. Launch subprocess using --account parameter (DB config)
    root_dir = Path(__file__).resolve().parent
    python_exe = str(root_dir / ".venv" / "Scripts" / "python.exe")
    if not os.path.exists(python_exe):
        python_exe = str(root_dir / ".venv" / "bin" / "python")
        if not os.path.exists(python_exe):
            python_exe = sys.executable

    script_path = str(root_dir / "ad_sender.py")

    command = [
        python_exe,
        script_path,
        "--account", account_id,
        "--folder", folder_name,
        "--send",
        "--no-confirm"
    ]
    if is_strategy:
        command.append("--strategy")

    try:
        process = subprocess.Popen(
            command,
            cwd=str(root_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        active_processes[account_id] = process
        return {"status": "started", "pid": process.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start campaign: {str(e)}")

@app.post("/api/campaign/stop")
def stop_campaign(account_id: str = Body(..., embed=True), user: dict = Depends(get_current_user)):
    """Stops the active campaign task for an account."""
    check_account_company(account_id, user)
    stopped = False
    if account_id in active_processes:
        process = active_processes[account_id]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        active_processes.pop(account_id, None)
        stopped = True

    # OS level fallback
    pid = find_campaign_process(account_id)
    if pid:
        try:
            import os, signal
            os.kill(pid, signal.SIGTERM)
            stopped = True
        except Exception:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                stopped = True
            except Exception:
                pass

    if stopped:
        return {"status": "stopped", "message": "Campaign stopped successfully"}
    else:
        return {"status": "stopped", "message": "No campaign running for this account"}

@app.get("/api/campaign/status/{account_id}")
def get_campaign_status(account_id: str, user: dict = Depends(get_current_user)):
    """Checks whether a campaign is currently running for an account."""
    check_account_company(account_id, user)
    is_running = is_campaign_running_for_account(account_id)
    return {"is_running": is_running}

@app.get("/api/campaign/logs")
def get_campaign_logs(limit: int = 50, user: dict = Depends(get_current_user)):
    from db import engine, AdLogDb, Session, select
    try:
        with Session(engine) as session:
            if user["username"] in ("eason", "admin") or user["company"] == "admin":
                stmt = select(AdLogDb).order_by(AdLogDb.id.desc()).limit(limit)
            else:
                stmt = select(AdLogDb).where(AdLogDb.company == user["company"]).order_by(AdLogDb.id.desc()).limit(limit)
            results = session.exec(stmt).all()
            return [log.model_dump() for log in results]
    except Exception as e:
        print(f"Failed to read logs from SQLite: {e}")
        return []

# --- AUTO JOIN GROUP API & ENGINE ---

class JoinTaskRequest(BaseModel):
    account_ids: List[str]
    links: List[str]
    mode: str  # "simultaneous" or "sequential"
    strategy: str  # "fixed" or "safety"
    fixed_delay: int = 30
    safety_groups: int = 5
    safety_minutes: int = 30
    move_to_folder: Optional[bool] = False
    target_folder_name: Optional[str] = ""
    folder_by_type: Optional[bool] = False
    max_rounds: Optional[int] = None
    groups_per_round: int = 10
    round_interval_minutes: int = 5


def resume_persistent_tasks_on_startup():
    """Resume durable tasks that were running before a server restart."""
    resume_enabled = persistent_task_resume_enabled()
    if not resume_enabled:
        paused_count = 0
        for task_id, task_data in list(active_join_tasks.items()):
            if task_data.get("status") == "running":
                if not isinstance(task_data.get("logs"), LogList):
                    task_data["logs"] = LogList(task_data.get("logs", []))
                task_data["status"] = "paused"
                task_data["logs"].append("服务器启动恢复已关闭，历史入群任务已暂停。")
                save_last_join_task(task_id)
                paused_count += 1
        print(f"[Startup Resume] Disabled by RESUME_PERSISTENT_TASKS=0; paused {paused_count} loaded join task(s).")

    try:
        from db import engine, CampaignTaskDb, Session, select
        with Session(engine) as session:
            if resume_enabled:
                stmt = select(CampaignTaskDb).where(CampaignTaskDb.status == "running")
                running_campaigns = session.exec(stmt).all()
                for task in running_campaigns:
                    if task.id not in active_campaign_tasks:
                        active_campaign_tasks[task.id] = asyncio.create_task(campaign_worker_task(task.id))
                        print(f"[Startup Resume] Resumed campaign task {task.id} for account {task.account_id}")
            scheduled_stmt = select(CampaignTaskDb).where(CampaignTaskDb.status == "scheduled")
            scheduled_campaigns = session.exec(scheduled_stmt).all()
            for task in scheduled_campaigns:
                if task.id not in active_campaign_schedules:
                    active_campaign_schedules[task.id] = asyncio.create_task(scheduled_campaign_runner(task.id))
                    print(f"[Startup Resume] Restored scheduled campaign task {task.id} for account {task.account_id}")
    except Exception as e:
        print(f"[Startup Resume] Failed to resume campaign tasks: {e}")

    if not resume_enabled:
        return

    for task_id, task_data in list(active_join_tasks.items()):
        try:
            if task_data.get("status") != "running":
                continue
            params = task_data.get("params") or {}
            if not params.get("account_ids") or not params.get("links"):
                task_data["status"] = "failed"
                task_data.setdefault("logs", LogList()).append("服务器启动恢复失败：任务参数不完整。")
                save_last_join_task(task_id)
                continue
            if not isinstance(task_data.get("logs"), LogList):
                task_data["logs"] = LogList(task_data.get("logs", []))
            task_data["logs"].append("服务器启动，自动恢复入群任务。")
            req = JoinTaskRequest(**params)
            asyncio.create_task(join_worker_task(task_id, req))
            print(f"[Startup Resume] Resumed join task {task_id}")
        except Exception as e:
            task_data["status"] = "failed"
            task_data.setdefault("logs", LogList()).append(f"服务器启动恢复失败：{e}")
            save_last_join_task(task_id)
            print(f"[Startup Resume] Failed to resume join task {task_id}: {e}")



@app.post("/api/groups/join-task")
def start_join_task(req: JoinTaskRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Starts a new group joining task in the background."""
    # Check if user has access to all account_ids
    from db import AccountDb, Session, select, engine
    with Session(engine) as session:
        for acc_id in req.account_ids:
            acc = check_account_company(acc_id, user)
            if getattr(acc, "is_available", True) is False:
                raise HTTPException(status_code=400, detail=f"账号 {acc_id} 当前为占用/禁用状态，无法启动入群任务。")
            if is_account_busy_with_task(acc_id):
                raise HTTPException(status_code=400, detail=f"账号 {acc_id} 有未完成的任务，无法启动新任务。")

    # Check if there is already a running task for this company
    for tid, t in active_join_tasks.items():
        if t.get("status") == "running" and t.get("company") == user["company"]:
            raise HTTPException(status_code=400, detail="当前已有正在运行的入群任务，请先手动停止当前任务，再启动新任务。")

    # Safety Check: Reject if average interval is less than 30 seconds
    if req.strategy == "fixed":
        if req.fixed_delay < 30:
            raise HTTPException(status_code=400, detail="时间间隔不能小于 30 秒，以防触发 Telegram 风控锁定！")
    else:
        # safety strategy: safety_minutes * 60 / safety_groups
        avg_delay = (req.safety_minutes * 60) / req.safety_groups
        if avg_delay < 30:
            raise HTTPException(status_code=400, detail=f"安全模式的平均时间间隔 ({avg_delay:.1f} 秒) 小于 30 秒限额，已被系统拦截，请增加间隔分钟数或减少群组数量。")

    global last_join_task_id
    import uuid
    import datetime
    task_id = str(uuid.uuid4())
    last_join_task_id = task_id
    active_join_tasks[task_id] = {
        "status": "running",
        "company": user["company"],
        "owner_username": user["username"],
        "created_at": datetime.datetime.now().isoformat(),
        "progress": {"current": 0, "total": 0},
        "results": [],
        "logs": LogList(),
        "params": {
            "account_ids": req.account_ids,
            "links": req.links,
            "mode": req.mode,
            "strategy": req.strategy,
            "fixed_delay": req.fixed_delay,
            "safety_groups": req.safety_groups,
            "safety_minutes": req.safety_minutes,
            "move_to_folder": req.move_to_folder,
            "folder_by_type": req.folder_by_type,
            "target_folder_name": req.target_folder_name,
            "max_rounds": req.max_rounds,
            "groups_per_round": req.groups_per_round,
            "round_interval_minutes": req.round_interval_minutes
        }
    }
    save_last_join_task(task_id)
    register_account_task_usage(
        "join",
        task_id,
        req.account_ids,
        {"company": user["company"], "owner_username": user["username"]},
    )

    background_tasks.add_task(join_worker_task, task_id, req)
    return {"status": "started", "task_id": task_id}

@app.get("/api/groups/join-task/status/{task_id}")
def get_join_task_status(task_id: str, user: dict = Depends(get_current_user)):
    """Retrieves progress, logs, and results of a joining task."""
    if task_id not in active_join_tasks:
        f = Path("data/join_tasks") / f"{task_id}.json"
        if f.exists():
            try:
                with open(f, "r", encoding="utf-8") as file:
                    task_data = json.load(file)
                task_data = normalize_loaded_join_task(
                    task_id,
                    task_data,
                    "读取历史任务时检测到无运行 worker，已暂停。"
                )
                active_join_tasks[task_id] = task_data
                if task_data.get("status") == "paused":
                    save_join_task_file(task_id, task_data)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read task data: {e}")
        else:
            raise HTTPException(status_code=404, detail="Task not found")

    task = active_join_tasks[task_id]
    if user["username"] not in ("eason", "admin") and user["company"] != "admin" and task.get("company") != user["company"]:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/groups/join-task/stop")
def stop_join_task(task_id: str = Body(..., embed=True), user: dict = Depends(get_current_user)):
    """Manually stops a running joining task."""
    if task_id not in active_join_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = active_join_tasks[task_id]
    if user["username"] not in ("eason", "admin") and user["company"] != "admin" and task.get("company") != user["company"]:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] == "running":
        task["status"] = "stopped"
        task["logs"].append("入群任务已被手动停止！")
        save_last_join_task(task_id)
        release_account_task_usage(task_id, task.get("params", {}).get("account_ids", []), source="join-task-stop")
    return {"status": "stopped", "message": "Task stopping initiated"}

@app.get("/api/groups/join-task/last")
def get_last_join_task(user: dict = Depends(get_current_user)):
    """Retrieves the last created join task id and status."""
    company = user["company"]
    company_tasks = [
        (tid, t) for tid, t in active_join_tasks.items()
        if t.get("company") == company
    ]
    if company_tasks:
        # Sort by created_at desc
        company_tasks.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
        latest_tid, latest_task = company_tasks[0]
        return {
            "task_id": latest_tid,
            "status": latest_task.get("status"),
            "progress": latest_task.get("progress"),
            "results": latest_task.get("results"),
            "logs": list(latest_task.get("logs")),
            "params": latest_task.get("params")
        }

    # Try reading from company-specific last file
    sanitized_company = "".join(c for c in company if c.isalnum() or c in "._-")
    task_file = Path("data") / f"last_join_task_{sanitized_company}.json"
    if task_file.exists():
        try:
            with open(task_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            tid = state.get("last_task_id")
            task_data = state.get("task_data")
            if tid and task_data:
                if tid not in active_join_tasks:
                    task_data = normalize_loaded_join_task(
                        tid,
                        task_data,
                        "读取历史任务时检测到无运行 worker，已暂停。"
                    )
                    active_join_tasks[tid] = task_data
                    if task_data.get("status") == "paused":
                        save_last_join_task(tid)
                return {
                    "task_id": tid,
                    "status": task_data.get("status"),
                    "progress": task_data.get("progress"),
                    "results": task_data.get("results"),
                    "logs": list(task_data.get("logs")),
                    "params": task_data.get("params")
                }
        except Exception:
            pass

    return {"status": "none"}

@app.get("/api/groups/join-task/history")
def get_join_task_history(user: dict = Depends(get_current_user)):
    """Retrieves metadata of all saved join tasks."""
    data_dir = Path("data/join_tasks")
    if not data_dir.exists():
        return []
    history = []
    for f in data_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                task = json.load(file)
            task_id = task.get("task_id") or f.stem
            original_status = task.get("status")
            task = normalize_loaded_join_task(
                task_id,
                task,
                "读取历史任务列表时检测到无运行 worker，已暂停。"
            )
            if original_status == "running" and task.get("status") == "paused":
                save_join_task_file(task_id, task)
            if user["username"] not in ("eason", "admin") and user["company"] != "admin" and task.get("company") != user["company"]:
                continue
            history.append({
                "task_id": task.get("task_id"),
                "created_at": task.get("created_at"),
                "status": task.get("status"),
                "owner_username": task.get("owner_username", "rosepay"),
                "account_count": len(task.get("params", {}).get("account_ids", [])),
                "links_count": len(task.get("params", {}).get("links", [])),
                "success_count": len([r for r in task.get("results", []) if r.get("status") == "success"]),
                "total_count": task.get("progress", {}).get("total", 0),
                "current_count": task.get("progress", {}).get("current", 0)
            })
        except Exception as e:
            print(f"Failed to read task history file {f.name}: {e}")
    history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return history

@app.get("/api/groups/join-task/history/{task_id}")
def get_join_task_history_detail(task_id: str, user: dict = Depends(get_current_user)):
    """Retrieves full details of a specific join task from disk or memory."""
    if task_id in active_join_tasks:
        task = active_join_tasks[task_id]
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and task.get("company") != user["company"]:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "task_id": task_id,
            "created_at": task.get("created_at"),
            "status": task.get("status"),
            "progress": task.get("progress"),
            "results": task.get("results"),
            "logs": list(task.get("logs")),
            "params": task.get("params")
        }
    f = Path("data/join_tasks") / f"{task_id}.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        with open(f, "r", encoding="utf-8") as file:
            task = json.load(file)
        original_status = task.get("status")
        task = normalize_loaded_join_task(
            task_id,
            task,
            "读取历史任务详情时检测到无运行 worker，已暂停。"
        )
        if original_status == "running" and task.get("status") == "paused":
            save_join_task_file(task_id, task)
        if user["username"] not in ("eason", "admin") and user["company"] != "admin" and task.get("company") != user["company"]:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load task file: {str(e)}")

@app.get("/api/accounts/{account_id}/devices")
@account_api_operation("read_devices", label="读取设备")
async def get_account_devices(account_id: str, user: dict = Depends(get_current_user)):
    """Fetches all active login sessions/devices for an account."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        authorizations = await client(functions.account.GetAuthorizationsRequest())
        devices = []
        for auth in authorizations.authorizations:
            devices.append({
                "hash": str(auth.hash),
                "device_model": auth.device_model,
                "platform": auth.platform,
                "system_version": auth.system_version,
                "api_id": auth.api_id,
                "app_name": auth.app_name,
                "app_version": auth.app_version,
                "date_created": auth.date_created.isoformat() if hasattr(auth.date_created, 'isoformat') else str(auth.date_created),
                "date_active": auth.date_active.isoformat() if hasattr(auth.date_active, 'isoformat') else str(auth.date_active),
                "ip": auth.ip,
                "country": auth.country,
                "region": auth.region,
                "current": bool(auth.current)
            })
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active devices: {str(e)}")

@app.post("/api/accounts/{account_id}/devices/kick")
@account_api_operation("kick_device", label="移除设备")
async def kick_account_device(account_id: str, req: KickDeviceRequest, user: dict = Depends(get_current_user)):
    """Kicks/terminates a specific active session/device of the account."""
    check_account_company(account_id, user)
    try:
        client = await get_client(account_id)
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Account is not authorized")

        session_hash = int(req.hash)
        await client(functions.account.ResetAuthorizationRequest(hash=session_hash))
        return {"status": "success", "message": "Device terminated successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session hash format")
    except Exception as e:
        err_msg = str(e).lower()
        if "session is too new" in err_msg or "fresh_reset_authorisation_forbidden" in err_msg:
            raise HTTPException(
                status_code=400,
                detail="新登录设备安全限制：您刚登录当前设备，电报官方安全策略规定，新会话必须持续在线满 24 小时后才能剔除其他活跃设备。请 24 小时后再试，或者直接在您手机/电脑客户端的“活跃会话”中将其下线。"
            )
        raise HTTPException(status_code=500, detail=f"Failed to terminate device session: {str(e)}")


@app.post("/api/accounts/{account_id}/toggle-profile-modified")
async def toggle_profile_modified(account_id: str, user: dict = Depends(get_current_user)):
    """Toggles the profile_modified boolean status of the account."""
    check_account_company(account_id, user)
    block_reason = get_account_operation_block_reason(account_id, block_task_busy=True)
    if block_reason:
        raise HTTPException(status_code=409, detail=f"{block_reason}，请等待完成后再切换资料状态。")
    try:
        from db import engine, AccountDb, Session
        from account_manager import account_config_path, save_json
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if not db_account:
                raise HTTPException(status_code=404, detail="Account not found")

            db_account.profile_modified = not db_account.profile_modified
            db_account.updated_by = user["username"]
            session.add(db_account)
            session.commit()

            path = account_config_path(account_id)
            if os.path.exists(path):
                save_json(path, db_account.to_dict())

            return {
                "status": "success",
                "profile_modified": db_account.profile_modified
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle profile modified status: {str(e)}")


# --- SMART FINDER / TELEGRAM GROUP SCRAPER & AI EVALUATOR ---

from pydantic import BaseModel
from typing import List, Optional
import asyncio
import re

class GeminiApiKeyRequest(BaseModel):
    api_key: str

class DeepseekApiKeyRequest(BaseModel):
    api_key: str

class ScrapedGroupsSearchRequest(BaseModel):
    keywords: List[str]
    min_members: int = 1000
    max_pages: int = 5
    continuous: Optional[bool] = False
    interval_minutes: Optional[int] = 30
    auto_join: Optional[bool] = False
    auto_join_min_score: Optional[int] = 70
    max_rounds: Optional[int] = None
    groups_per_round: Optional[int] = 10
    round_interval_minutes: Optional[int] = 5

class ScrapedGroupsBatchActionRequest(BaseModel):
    ids: List[str]
    action: str  # 'join', 'ignore', 'delete'
    category_to_assign: Optional[str] = "中文广告"

def load_scraper_config() -> tuple[List[str], int, int, bool, int]:
    config_path = Path(__file__).resolve().parent / "config.json"
    default_keywords = []
    default_min_members = 1000
    default_max_pages = 5
    default_continuous = False
    default_interval_minutes = 30
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            keywords = data.get("scraper_keywords", default_keywords)
            min_members = data.get("scraper_min_members", default_min_members)
            max_pages = data.get("scraper_max_pages", default_max_pages)
            continuous = data.get("scraper_continuous", default_continuous)
            interval_minutes = data.get("scraper_interval_minutes", default_interval_minutes)
            return keywords, min_members, max_pages, continuous, interval_minutes
        except Exception:
            pass
    return default_keywords, default_min_members, default_max_pages, default_continuous, default_interval_minutes

def save_scraper_config(keywords: List[str], min_members: int, max_pages: int, continuous: bool, interval_minutes: int):
    config_path = Path(__file__).resolve().parent / "config.json"
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["scraper_keywords"] = keywords
    data["scraper_min_members"] = min_members
    data["scraper_max_pages"] = max_pages
    data["scraper_continuous"] = continuous
    data["scraper_interval_minutes"] = interval_minutes
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save scraper config: {e}")

init_keywords, init_min_members, init_max_pages, init_continuous, init_interval_minutes = load_scraper_config()

# Global task states keyed by company
# Removed variable active_scraper_tasks

# Extracted get_company_scraper_task

class StartExpansionRequest(BaseModel):
    target_desc: str
    loop_interval_minutes: Optional[int] = 15
    auto_join: Optional[bool] = False
    auto_join_min_score: Optional[int] = 70
    max_rounds: Optional[int] = None
    groups_per_round: Optional[int] = 10
    round_interval_minutes: Optional[int] = 5

# Extracted load_expansion_config

# Extracted save_expansion_config

init_target, init_interval = load_expansion_config()

# Global expansion task states keyed by company
# Removed variable active_expansion_tasks

# Extracted get_company_expansion_task


# Extracted get_gemini_api_key

# Extracted save_gemini_api_key

# Extracted get_deepseek_api_key

# Extracted save_deepseek_api_key

# Extracted run_group_scraping_task

@app.post("/api/config/gemini")
def update_gemini_config(req: GeminiApiKeyRequest, user: dict = Depends(get_current_user)):
    """Saves the Gemini API Key globally in config.json."""
    save_gemini_api_key(req.api_key)
    return {"status": "success", "message": "Gemini API Key 保存成功"}

@app.get("/api/config/gemini")
def get_gemini_config(user: dict = Depends(get_current_user)):
    """Gets the saved Gemini API Key (masked for security)."""
    key = get_gemini_api_key()
    masked_key = ""
    if key:
        if len(key) > 8:
            masked_key = key[:4] + "..." + key[-4:]
        else:
            masked_key = "..."
    return {"has_key": bool(key), "key_preview": masked_key}

@app.post("/api/config/deepseek")
def update_deepseek_config(req: DeepseekApiKeyRequest, user: dict = Depends(get_current_user)):
    """Saves the DeepSeek API Key globally in config.json."""
    save_deepseek_api_key(req.api_key)
    return {"status": "success", "message": "DeepSeek API Key 保存成功"}

@app.get("/api/config/deepseek")
def get_deepseek_config(user: dict = Depends(get_current_user)):
    """Gets the saved DeepSeek API Key (masked for security)."""
    key = get_deepseek_api_key()
    masked_key = ""
    if key:
        if len(key) > 8:
            masked_key = key[:4] + "..." + key[-4:]
        else:
            masked_key = "..."
    return {"has_key": bool(key), "key_preview": masked_key}

@app.post("/api/scraped-groups/search-task")
def start_scraped_groups_search_task(req: ScrapedGroupsSearchRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Spawns the group scraper and AI analysis task in the background."""
    active_scraper_task = get_company_scraper_task(user["company"])
    if active_scraper_task["status"] == "running":
        raise HTTPException(status_code=400, detail="当前已有正在运行的搜群任务")

    save_scraper_config(req.keywords, req.min_members, req.max_pages, req.continuous or False, req.interval_minutes or 30)
    active_scraper_task["keywords"] = req.keywords
    active_scraper_task["min_members"] = req.min_members
    active_scraper_task["max_pages"] = req.max_pages
    active_scraper_task["continuous"] = req.continuous or False
    active_scraper_task["interval_minutes"] = req.interval_minutes or 30

    background_tasks.add_task(
        run_group_scraping_task,
        req.keywords,
        req.min_members,
        req.max_pages,
        user["company"],
        req.continuous or False,
        req.interval_minutes or 30,
        req.auto_join or False,
        req.auto_join_min_score or 70,
        req.max_rounds,
        req.groups_per_round or 10,
        req.round_interval_minutes or 5,
        user["username"] if user["role"] != "admin" else None
    )
    return {"status": "started"}

@app.get("/api/scraped-groups/task-status")
def get_scraped_groups_task_status(user: dict = Depends(get_current_user)):
    """Retrieves the current search task progress, status and logs."""
    return get_company_scraper_task(user["company"])

@app.post("/api/scraped-groups/search-task/stop")
def stop_scraped_groups_search_task(user: dict = Depends(get_current_user)):
    """Stops the current search task."""
    active_scraper_task = get_company_scraper_task(user["company"])
    if active_scraper_task["status"] == "running":
        active_scraper_task["status"] = "stopped"
        release_account_task_usage(f"scraper:{user['company']}", source="scraper-task-stop")
        return {"status": "success", "message": "任务已停止"}
    return {"status": "success", "message": "没有运行中的任务"}

@app.get("/api/scraped-groups")
def list_scraped_groups(
    category: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    keyword: Optional[str] = None,
    sort_by: Optional[str] = "default",
    user: dict = Depends(get_current_user)
):
    """Retrieves all scraped group records from database with filters and sorting."""
    from db import engine, ScrapedGroupDb, Session, select
    with Session(engine) as session:
        if user["username"] in ("eason", "admin") or user["company"] == "admin":
            stmt = select(ScrapedGroupDb)
        else:
            stmt = select(ScrapedGroupDb).where(ScrapedGroupDb.company == user["company"])
        if category:
            stmt = stmt.where(ScrapedGroupDb.category == category)
        if status:
            stmt = stmt.where(ScrapedGroupDb.status == status)
        if min_score is not None:
            stmt = stmt.where(ScrapedGroupDb.quality_score >= min_score)
        if keyword:
            stmt = stmt.where(ScrapedGroupDb.keyword.contains(keyword))

        if sort_by == "score":
            stmt = stmt.order_by(ScrapedGroupDb.quality_score.desc())
        elif sort_by == "date":
            stmt = stmt.order_by(ScrapedGroupDb.created_at.desc())
        else:
            # Default sorting: starred/important pinned first, then by created_at desc
            stmt = stmt.order_by(ScrapedGroupDb.is_important.desc(), ScrapedGroupDb.created_at.desc())

        results = session.exec(stmt).all()
        return results

@app.post("/api/scraped-groups/{group_id}/toggle-important")
def toggle_scraped_group_important(group_id: str, user: dict = Depends(get_current_user)):
    """Toggles the is_important status of a scraped group."""
    from db import engine, ScrapedGroupDb, Session
    with Session(engine) as session:
        db_group = session.get(ScrapedGroupDb, group_id)
        is_admin = user["username"] in ("eason", "admin") or user["company"] == "admin"
        if not db_group or (not is_admin and db_group.company != user["company"]):
            raise HTTPException(status_code=404, detail="未找到该群组")
        db_group.is_important = not db_group.is_important
        session.add(db_group)
        session.commit()
        return {"status": "success", "is_important": db_group.is_important}

@app.post("/api/scraped-groups/batch-action")
def batch_action_scraped_groups(req: ScrapedGroupsBatchActionRequest, user: dict = Depends(get_current_user)):
    """Applies action (join, ignore, delete) on multiple scraped groups."""
    from db import engine, ScrapedGroupDb, GroupDb, Session, select

    with Session(engine) as session:
        is_admin = user["username"] in ("eason", "admin") or user["company"] == "admin"
        stmt = select(ScrapedGroupDb).where(ScrapedGroupDb.id.in_(req.ids))
        if not is_admin:
            stmt = stmt.where(ScrapedGroupDb.company == user["company"])
        scraped_items = session.exec(stmt).all()

        if not scraped_items:
            return {"status": "success", "count": 0}

        count = 0
        for item in scraped_items:
            if req.action == "delete":
                session.delete(item)
                count += 1
            elif req.action == "ignore":
                item.status = "ignored"
                session.add(item)
                count += 1
            elif req.action == "unignore" or req.action == "pending":
                item.status = "pending"
                session.add(item)
                count += 1
            elif req.action == "join":
                if getattr(item, 'group_type', '') == "channel":
                    continue
                # Check if group already in main GroupDb library
                group_id_str = str(item.id)
                existing = session.get(GroupDb, (group_id_str, user["company"]))
                if not existing:
                    # Ensure category exists in GroupCategoryDb
                    if req.category_to_assign:
                        from db import GroupCategoryDb
                        cat_name = req.category_to_assign.strip()
                        if cat_name:
                            existing_cat = session.exec(
                                select(GroupCategoryDb)
                                .where(GroupCategoryDb.company == user["company"])
                                .where(GroupCategoryDb.name == cat_name)
                            ).first()
                            if not existing_cat:
                                existing_admin = session.exec(
                                    select(GroupCategoryDb)
                                    .where(GroupCategoryDb.company == "admin")
                                    .where(GroupCategoryDb.name == cat_name)
                                ).first()
                                if not existing_admin:
                                    new_cat = GroupCategoryDb(name=cat_name, company=user["company"])
                                    session.add(new_cat)

                    # Insert new group to GroupDb
                    new_group = GroupDb(
                        id=group_id_str,
                        company=user["company"],
                        title=item.title or item.id,
                        username=item.id,
                        type="supergroup",  # default
                        enabled=True,
                        memberCount=item.member_count or 0,
                        category=req.category_to_assign
                    )
                    session.add(new_group)

                # Mark scraped status as joined
                item.status = "joined"
                session.add(item)
                count += 1

        session.commit()
        return {"status": "success", "count": count}


# --- BUSINESS EXPANSION AUTONOMOUS AGENT ---

# Extracted run_business_expansion_loop


@app.post("/api/expansion/start")
async def start_business_expansion(req: StartExpansionRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    active_expansion_task = get_company_expansion_task(user["company"])
    from datetime import datetime

    interval = req.loop_interval_minutes or 15
    save_expansion_config(req.target_desc, interval)

    active_expansion_task["target_desc"] = req.target_desc
    active_expansion_task["interval_minutes"] = interval

    if active_expansion_task["status"] == "running":
        return {"status": "success", "message": "业务拓展目标已更新"}

    if active_expansion_task["status"] == "paused":
        active_expansion_task["status"] = "running"
        timestamp = datetime.now().strftime("%m-%d %H:%M:%S")
        active_expansion_task["logs"].append(f"[{timestamp}] 业务拓展已恢复运行。")
        return {"status": "success", "message": "业务拓展已恢复运行"}

    background_tasks.add_task(
        run_business_expansion_loop,
        req.target_desc,
        interval,
        user["company"],
        req.auto_join or False,
        req.auto_join_min_score or 70,
        req.max_rounds,
        req.groups_per_round or 10,
        req.round_interval_minutes or 5
    )
    return {"status": "success", "message": "业务拓展已启动"}


@app.post("/api/expansion/pause")
def pause_business_expansion(user: dict = Depends(get_current_user)):
    active_expansion_task = get_company_expansion_task(user["company"])
    from datetime import datetime
    if active_expansion_task["status"] == "running":
        active_expansion_task["status"] = "paused"
        timestamp = datetime.now().strftime("%m-%d %H:%M:%S")
        active_expansion_task["logs"].append(f"[{timestamp}] 业务拓展已暂停。")
        release_account_task_usage(f"expansion:{user['company']}", source="expansion-task-pause")
        return {"status": "success", "message": "业务拓展已暂停"}
    return {"status": "success", "message": "当前没有运行中的业务拓展任务"}


@app.get("/api/expansion/status")
def get_business_expansion_status(user: dict = Depends(get_current_user)):
    active_expansion_task = get_company_expansion_task(user["company"])
    logs_slice = active_expansion_task["logs"][-150:]
    return {
        "status": active_expansion_task["status"],
        "target_desc": active_expansion_task["target_desc"],
        "current_keyword": active_expansion_task["current_keyword"],
        "error": active_expansion_task["error"],
        "interval_minutes": active_expansion_task.get("interval_minutes", 15),
        "logs": logs_slice
    }


@app.get("/api/expansion/groups")
def get_business_expansion_groups(user: dict = Depends(get_current_user)):
    """Retrieves high-quality groups found by the business expansion Agent."""
    from db import engine, ScrapedGroupDb, Session, select
    with Session(engine) as session:
        is_admin = user["username"] in ("eason", "admin") or user["company"] == "admin"
        if is_admin:
            stmt = (
                select(ScrapedGroupDb)
                .where(ScrapedGroupDb.quality_score >= 40)
            )
        else:
            stmt = (
                select(ScrapedGroupDb)
                .where(ScrapedGroupDb.company == user["company"])
                .where(ScrapedGroupDb.quality_score >= 40)
            )
        stmt = stmt.order_by(ScrapedGroupDb.is_important.desc(), ScrapedGroupDb.created_at.desc())
        results = session.exec(stmt).all()
        return results


@app.get("/api/internal/bot/status")
def get_internal_bot_status():
    """Internal endpoint for Telegram Bot to query real-time account and task statuses."""
    from db import engine, AccountDb, CampaignTaskDb, Session, select
    import time

    with Session(engine) as session:
        # 1. Fetch all accounts
        db_accounts = session.exec(select(AccountDb)).all()
        accounts_result = []
        for acc in db_accounts:
            # Check memory connection state
            live_client = active_clients.get(acc.id)
            live_connected = bool(live_client and live_client.is_connected())

            # Fetch statuses from memory store
            status = account_status_store.get(acc.id, {
                "is_connected": False,
                "is_authorized": False,
                "me": "（未初始化）",
                "spambot_status": "unknown",
                "spambot_details": "",
                "spambot_time": None
            })

            # Compute listener health state
            health = "disabled"
            cooldown_until = auto_private_listener_cooldowns.get(acc.id, 0)
            if ENABLE_REALTIME_PRIVATE_DM:
                if cooldown_until > time.time():
                    health = "cooldown"
                elif live_connected:
                    if acc.id in registered_listeners:
                        health = "ok"
                    else:
                        health = "zombie"
                else:
                    # If not connectable but marked available
                    if getattr(acc, "is_available", True):
                        health = "error"
                    else:
                        health = "disabled"
            else:
                health = "disabled"

            accounts_result.append({
                "id": acc.id,
                "account_name": acc.account_name or acc.id,
                "owner_username": acc.owner_username or "",
                "is_connected": live_connected or status.get("is_connected", False),
                "is_authorized": status.get("is_authorized", False),
                "spambot_status": status.get("spambot_status", "unknown"),
                "spambot_details": status.get("spambot_details", ""),
                "listener_health": health,
                "cooldown_left": max(0, int(cooldown_until - time.time()))
            })

        # 2. Fetch all campaign tasks
        db_tasks = session.exec(select(CampaignTaskDb)).all()
        tasks_result = []
        for task in db_tasks:
            is_running = is_campaign_task_running(task)

            tasks_result.append({
                "id": task.id,
                "account_id": task.account_id,
                "owner_username": task.owner_username or "",
                "status": task.status,
                "is_running": is_running,
                "success_count": task.success_count,
                "fail_count": task.fail_count,
                "round_interval_minutes": task.round_interval_minutes,
                "message": task.message[:100] if task.message else "",
            })

        return {
            "ok": True,
            "accounts": accounts_result,
            "tasks": tasks_result,
            "registered_listeners": list(registered_listeners)
        }


cleanup_tasks_progress: Dict[str, dict] = {}

# Extracted run_account_cleanup_process


@app.post("/api/internal/cleanup")
async def trigger_cleanup_tasks(background_tasks: BackgroundTasks, payload: dict = Body(...)):
    account_ids = payload.get("account_ids", [])
    if not account_ids:
        raise HTTPException(status_code=400, detail="account_ids is required")

    for acc_id in account_ids:
        background_tasks.add_task(run_account_cleanup_process, acc_id)

    return {"ok": True, "message": f"已提交 {len(account_ids)} 个账号的后台整理任务"}


@app.get("/api/internal/cleanup/progress/{account_id}")
def get_cleanup_progress(account_id: str):
    prog = cleanup_tasks_progress.get(account_id)
    if not prog:
        return {"ok": False, "status": "not_found", "message": "未找到整理记录"}
    return {
        "ok": True,
        "status": prog["status"],
        "started_at": prog["started_at"],
        "logs": prog["logs"][-30:],
        "left_groups": prog["left_groups"],
        "grouped_channels": prog["grouped_channels"],
        "synced_dms": prog["synced_dms"],
        "archived_chats": prog["archived_chats"]
    }

# --- TELEGRAM BOTS CONFIGURATION & CRUD API ---

from pydantic import BaseModel

class TelegramBotRequest(BaseModel):
    bot_username: str
    bot_token: str
    bot_type: str
    title: str
    description: str
    is_active: int = 1

@app.get("/api/bots")
def list_telegram_bots(user: dict = Depends(get_current_user)):
    """列出系统里所有已注册的电报 Bot"""
    from db import engine, Session, select
    import sqlite3

    # 统计每个 Bot 绑定的账号数量
    stats = {}
    try:
        from db import DB_PATH
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_authorized_users';")
            if cursor.fetchone():
                cursor.execute("SELECT bot_type, COUNT(*) FROM bot_authorized_users GROUP BY bot_type;")
                for b_type, count in cursor.fetchall():
                    stats[b_type] = count
    except Exception:
        pass

    with Session(engine) as session:
        import sqlite3
        from db import DB_PATH
        bots = []
        try:
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, bot_username, bot_token, bot_type, title, description, is_active, created_at FROM telegram_bots;")
                for row in cursor.fetchall():
                    b_type = row["bot_type"]
                    linked_count = stats.get(b_type, 0)
                    if b_type == "ai_bot":
                        cursor.execute("SELECT COUNT(*) FROM accounts;")
                        linked_count = cursor.fetchone()[0]
                    elif b_type == "translate_bot":
                        cursor.execute("SELECT COUNT(*) FROM bot_authorized_users WHERE bot_type = 'translate_bot';")
                        linked_count = cursor.fetchone()[0]

                    bots.append({
                        "id": row["id"],
                        "bot_username": row["bot_username"],
                        "bot_token": row["bot_token"],
                        "bot_type": row["bot_type"],
                        "title": row["title"],
                        "description": row["description"],
                        "is_active": row["is_active"],
                        "created_at": row["created_at"],
                        "linked_accounts_count": linked_count
                    })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load bots: {str(e)}")

        return {"bots": bots}

        return bots

@app.post("/api/bots")
def create_telegram_bot(req: TelegramBotRequest, user: dict = Depends(get_current_user)):
    """在控制台里动态创建一个电报 Bot"""
    import sqlite3
    import datetime
    from db import DB_PATH

    bot_username_clean = req.bot_username.strip().lstrip("@")
    now_str = datetime.datetime.now().isoformat()

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO telegram_bots (bot_username, bot_token, bot_type, title, description, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bot_username_clean, req.bot_token.strip(), req.bot_type, req.title.strip(), req.description.strip(), req.is_active, now_str)
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Bot 用户名 @{bot_username_clean} 已经存在，无法重复创建")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Bot 失败: {str(e)}")

    if req.bot_type == "ai_bot" and req.is_active == 1:
        try:
            import subprocess
            import os
            if os.name != "nt":
                subprocess.run(["systemctl", "restart", "rosepay-bot.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    return {"ok": True, "message": "Bot 创建成功"}

@app.put("/api/bots/{bot_id}")
def update_telegram_bot(bot_id: int, req: TelegramBotRequest, user: dict = Depends(get_current_user)):
    """编辑修改现有的电报 Bot 参数"""
    import sqlite3
    from db import DB_PATH

    bot_username_clean = req.bot_username.strip().lstrip("@")

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT bot_token, bot_type, is_active FROM telegram_bots WHERE id = ?", (bot_id,))
            old_row = cursor.fetchone()

            cursor.execute(
                "UPDATE telegram_bots SET bot_username = ?, bot_token = ?, bot_type = ?, title = ?, description = ?, is_active = ? WHERE id = ?",
                (bot_username_clean, req.bot_token.strip(), req.bot_type, req.title.strip(), req.description.strip(), req.is_active, bot_id)
            )
            conn.commit()

            if old_row and (old_row["bot_token"] != req.bot_token.strip() or old_row["bot_type"] != req.bot_type or old_row["is_active"] != req.is_active):
                if req.bot_type == "ai_bot" or old_row["bot_type"] == "ai_bot":
                    try:
                        import subprocess
                        import os
                        if os.name != "nt":
                            subprocess.run(["systemctl", "restart", "rosepay-bot.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 Bot 失败: {str(e)}")

    return {"ok": True, "message": "Bot 更新成功"}

@app.delete("/api/bots/{bot_id}")
def delete_telegram_bot(bot_id: int, user: dict = Depends(get_current_user)):
    """删除已注销的电报 Bot"""
    import sqlite3
    from db import DB_PATH

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM telegram_bots WHERE id = ?", (bot_id,))
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Bot 失败: {str(e)}")

    return {"ok": True, "message": "Bot 已成功删除"}


# --- BOT SPECIFIC AUTHORIZATION MANAGEMENT API ---

class BotAuthRequest(BaseModel):
    telegram_chat_id: str
    telegram_username: str
    role: str
    owner_username: str
    is_active: int = 1

@app.get("/api/bots/{bot_type}/authorizations")
def list_bot_authorizations(bot_type: str, user: dict = Depends(get_current_user)):
    """获取某个特定 Bot 节点下的所有授权账号和群组"""
    import sqlite3
    from db import DB_PATH

    auths = []
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 确保表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_authorized_users (
                    telegram_chat_id TEXT NOT NULL,
                    bot_type TEXT NOT NULL,
                    telegram_username TEXT,
                    role TEXT DEFAULT 'employee',
                    owner_username TEXT,
                    approved_at TEXT,
                    approved_by TEXT,
                    is_active INTEGER DEFAULT 1,
                    PRIMARY KEY (telegram_chat_id, bot_type)
                );
            """)
            cursor.execute(
                "SELECT telegram_chat_id, bot_type, telegram_username, role, owner_username, approved_at, is_active FROM bot_authorized_users WHERE bot_type = ?;",
                (bot_type,)
            )
            for row in cursor.fetchall():
                auths.append({
                    "telegram_chat_id": row["telegram_chat_id"],
                    "bot_type": row["bot_type"],
                    "telegram_username": row["telegram_username"],
                    "role": row["role"],
                    "owner_username": row["owner_username"],
                    "approved_at": row["approved_at"],
                    "is_active": row["is_active"]
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot auths: {str(e)}")

    return {"authorizations": auths}

@app.post("/api/bots/{bot_type}/authorizations")
def create_bot_authorization(bot_type: str, req: BotAuthRequest, user: dict = Depends(get_current_user)):
    """手动免注册新增一个 Bot 授权账号或中转群"""
    import sqlite3
    import datetime
    from db import DB_PATH

    now_str = datetime.datetime.now().isoformat()
    chat_id_clean = req.telegram_chat_id.strip()
    username_clean = req.telegram_username.strip().lstrip("@")

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, approved_at, approved_by, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (chat_id_clean, bot_type, username_clean, req.role, req.owner_username.strip(), now_str, user["username"], req.is_active)
            )

            # 如果角色是系统管理员或普通员工，且关联了后台 admins 表中已有的用户名，同步更新其 telegram_chat_id
            if req.role in ["admin", "employee"] and username_clean:
                cursor.execute("SELECT username FROM admins WHERE username = ? OR telegram_contact = ?", (username_clean, f"@{username_clean}"))
                admin_row = cursor.fetchone()
                if admin_row:
                    cursor.execute("UPDATE admins SET telegram_chat_id = ? WHERE username = ?", (chat_id_clean, admin_row[0]))

            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bot auth: {str(e)}")

    return {"ok": True, "message": "授权添加成功"}

@app.put("/api/bots/{bot_type}/authorizations/{chat_id}")
def update_bot_authorization(bot_type: str, chat_id: str, req: BotAuthRequest, user: dict = Depends(get_current_user)):
    """编辑修改某个 Bot 的授权账号或中转群配置"""
    import sqlite3
    from db import DB_PATH

    username_clean = req.telegram_username.strip().lstrip("@")
    chat_id_clean = req.telegram_chat_id.strip()

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()

            # 如果 Chat ID 发生改变，先删掉旧的再插入新的以保证主键唯一
            if chat_id_clean != chat_id:
                cursor.execute("DELETE FROM bot_authorized_users WHERE telegram_chat_id = ? AND bot_type = ?", (chat_id, bot_type))

            cursor.execute(
                "INSERT OR REPLACE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id_clean, bot_type, username_clean, req.role, req.owner_username.strip(), req.is_active)
            )

            # 同步更新 admins 表的关联
            if req.role in ["admin", "employee"] and username_clean:
                cursor.execute("SELECT username FROM admins WHERE username = ? OR telegram_contact = ?", (username_clean, f"@{username_clean}"))
                admin_row = cursor.fetchone()
                if admin_row:
                    cursor.execute("UPDATE admins SET telegram_chat_id = ? WHERE username = ?", (chat_id_clean, admin_row[0]))

            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update bot auth: {str(e)}")

    return {"ok": True, "message": "授权修改成功"}

@app.delete("/api/bots/{bot_type}/authorizations/{chat_id}")
def delete_bot_authorization(bot_type: str, chat_id: str, user: dict = Depends(get_current_user)):
    """解除某个电报账号或中转群对该 Bot 的授权"""
    import sqlite3
    from db import DB_PATH

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_authorized_users WHERE telegram_chat_id = ? AND bot_type = ?", (chat_id, bot_type))
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bot auth: {str(e)}")

    return {"ok": True, "message": "已解除授权"}


# --- BOT AUTO REPLY TEMPLATE CRUD API ---

class AutoReplyRequest(BaseModel):
    reply_text: str
    is_enabled: int = 1

@app.get("/api/bots/{bot_type}/auto-replies")
def list_bot_auto_replies(bot_type: str, user: dict = Depends(get_current_user)):
    """获取某个 Bot 节点下的所有自动回复模板"""
    import sqlite3
    from db import DB_PATH

    replies = []
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
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
            cursor.execute(
                "SELECT id, bot_type, reply_text, is_enabled, created_at FROM bot_auto_replies WHERE bot_type = ?;",
                (bot_type,)
            )
            for row in cursor.fetchall():
                replies.append({
                    "id": row["id"],
                    "bot_type": row["bot_type"],
                    "reply_text": row["reply_text"],
                    "is_enabled": row["is_enabled"],
                    "created_at": row["created_at"]
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch auto replies: {str(e)}")

    return {"replies": replies}

@app.post("/api/bots/{bot_type}/auto-replies")
def create_bot_auto_reply(bot_type: str, req: AutoReplyRequest, user: dict = Depends(get_current_user)):
    """为某个 Bot 手动新增一条随机自动回复模板"""
    import sqlite3
    import datetime
    from db import DB_PATH

    now_str = datetime.datetime.now().isoformat()

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bot_auto_replies (bot_type, reply_text, is_enabled, created_at) VALUES (?, ?, ?, ?)",
                (bot_type, req.reply_text.strip(), req.is_enabled, now_str)
            )
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create auto reply: {str(e)}")

    return {"ok": True, "message": "添加自动回复模板成功"}

@app.put("/api/bots/{bot_type}/auto-replies/{reply_id}")
def update_bot_auto_reply(bot_type: str, reply_id: int, req: AutoReplyRequest, user: dict = Depends(get_current_user)):
    """编辑修改某个自动回复模板的内容"""
    import sqlite3
    from db import DB_PATH

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE bot_auto_replies SET reply_text = ?, is_enabled = ? WHERE id = ? AND bot_type = ?",
                (req.reply_text.strip(), req.is_enabled, reply_id, bot_type)
            )
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update auto reply: {str(e)}")

    return {"ok": True, "message": "修改自动回复模板成功"}

@app.delete("/api/bots/{bot_type}/auto-replies/{reply_id}")
def delete_bot_auto_reply(bot_type: str, reply_id: int, user: dict = Depends(get_current_user)):
    """删除某个自动回复模板"""
    import sqlite3
    from db import DB_PATH

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_auto_replies WHERE id = ? AND bot_type = ?", (reply_id, bot_type))
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete auto reply: {str(e)}")

    return {"ok": True, "message": "已删除该回复模板"}

# --- Groups Scraping and Syncing API Routes (Stage 2 Delegation) ---
@app.post("/api/groups/sync-status")
async def web_sync_groups_status(user: dict = Depends(get_current_user)):
    return await sync_groups_status(user)

@app.get("/api/groups/sync-stream")
async def web_stream_groups_sync(token: Optional[str] = None):
    user = get_user_from_stream_token(token)
    generator = await stream_groups_sync(user)
    return StreamingResponse(generator, media_type="text/event-stream")

@app.post("/api/groups/resolve", response_model=GroupModel)
async def web_resolve_group(req: GroupResolveRequest, user: dict = Depends(get_current_user)):
    return await resolve_group(req, user)


if __name__ == "__main__":
    import uvicorn
    import os
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    print(f"Starting web server on {host}:{port} (reload={reload})...")
    uvicorn.run("web_server:app", host=host, port=port, reload=reload)


