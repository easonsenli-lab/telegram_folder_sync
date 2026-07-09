# -*- coding: utf-8 -*-
import asyncio
import os
import time
import sys
from typing import Dict, Any, List, Optional, Tuple

from services.shared_state import (
    auto_private_listener_accounts,
    auto_private_listener_cooldowns,
    active_clients,
    active_clients_last_accessed,
    bg_connect_tasks,
    connection_errors,
    background_tasks,
    set_account_status,
    is_account_busy_with_task,
    get_account_busy_status,
    spambot_cache,
    active_account_operations,
    registered_listeners
)

from services.client_manager import get_client, mark_account_runtime_status, account_has_session_file

# Import helpers from web_server dynamically or statically
def get_private_poll_skip_reason(account_id: str) -> Optional[str]:
    import web_server
    return web_server.get_private_poll_skip_reason(account_id)

def is_banned_or_deactivated_error(exc: Exception) -> bool:
    import web_server
    return web_server.is_banned_or_deactivated_error(exc)

def handle_deactivated_or_banned_account(account_id: str, exc: Exception) -> None:
    import web_server
    return web_server.handle_deactivated_or_banned_account(account_id, exc)

def set_login_status_check_failed(account_id: str, message: str, *, source: str, is_connected: Optional[bool] = None) -> dict:
    import web_server
    return web_server.set_login_status_check_failed(account_id, message, source=source, is_connected=is_connected)

def is_telegram_transport_rate_error(exc: Exception) -> bool:
    import web_server
    return web_server.is_telegram_transport_rate_error(exc)

def mark_private_listener_cooldown(account_id: str, exc: Exception, context: str = "private-listener") -> None:
    import web_server
    return web_server.mark_private_listener_cooldown(account_id, exc, context)

def list_accounts(company: Optional[str] = None) -> List[Any]:
    import web_server
    return web_server.list_accounts()

async def check_account_status(account_or_client: Any, *, run_spambot_check: bool = False, source: str = "manual") -> Any:
    import web_server
    client = account_or_client
    if isinstance(account_or_client, str):
        client = await get_client(account_or_client)
    return await web_server.check_account_status(client)

from account_manager import account_config_path

ENABLE_REALTIME_PRIVATE_DM = os.getenv("ROSEPAY_ENABLE_REALTIME_PRIVATE_DM", "1").strip().lower() not in {"0", "false", "off", "no"}

AUTO_PRIVATE_LISTENER_STARTUP_DELAY_SECONDS = 10
AUTO_PRIVATE_LISTENER_INTERVAL_SECONDS = 30
AUTO_PRIVATE_LISTENER_CONNECT_GAP_SECONDS = 3
AUTO_PRIVATE_LISTENER_FAILURE_COOLDOWN_SECONDS = 180
PRIVATE_LISTENER_TRANSPORT_429_COOLDOWN_SECONDS = 1800

async def ensure_private_listener_for_account(account_id: str, account_label: str = "") -> bool:
    if get_private_poll_skip_reason(account_id):
        return False
    try:
        client = await get_client(account_id)
        if not await client.is_user_authorized():
            return False
    except Exception as exc:
        if is_banned_or_deactivated_error(exc):
            await handle_deactivated_or_banned_account(account_id, exc)
        raise exc
    auto_private_listener_accounts.add(account_id)
    active_clients_last_accessed[account_id] = time.time()
    set_account_status(
        account_id,
        {
            "is_connected": True,
            "is_authorized": True,
            "private_listener": True,
            "private_listener_source": "auto",
        },
        source="private-listener-auto",
    )
    print(f"[PrivateListener] Auto listener active for {account_label or account_id}.")
    return True


async def auto_private_listener_loop():
    """Keeps authorized account listeners available without active heartbeat polling.

    Receiving private DMs does not require periodically calling Telegram APIs.
    Avoiding heartbeat probes prevents a reconnect/request storm while campaign
    tasks are running or when several accounts recover at the same time.
    """
    from db import engine, AccountDb, Session, select
    await asyncio.sleep(AUTO_PRIVATE_LISTENER_STARTUP_DELAY_SECONDS)
    while True:
        try:
            import services.shared_state
            if not services.shared_state.private_relay_enabled:
                await asyncio.sleep(AUTO_PRIVATE_LISTENER_INTERVAL_SECONDS)
                continue

            with Session(engine) as session:
                accounts = session.exec(select(AccountDb)).all()

            now = time.time()
            async def process_single_account(acc):
                account_id = acc.id
                if getattr(acc, "is_available", True) is False:
                    return
                if is_account_busy_with_task(account_id):
                    return
                if active_account_operations.get(account_id):
                    return
                if not account_has_session_file(account_id, acc):
                    return

                live_client = active_clients.get(account_id)
                if live_client and live_client.is_connected():
                    auto_private_listener_accounts.add(account_id)
                    active_clients_last_accessed[account_id] = now
                    set_account_status(
                        account_id,
                        {
                            "is_connected": True,
                            "private_listener": True,
                            "private_listener_source": "auto",
                        },
                        source="private-listener-passive",
                    )
                    return
                if live_client and not live_client.is_connected():
                    auto_private_listener_accounts.discard(account_id)
                    registered_listeners.discard(account_id)
                    set_account_status(
                        account_id,
                        {
                            "is_connected": False,
                            "private_listener": False,
                            "private_listener_source": None,
                        },
                        source="private-listener-disconnected",
                    )

                cooldown_until = auto_private_listener_cooldowns.get(account_id, 0)
                if cooldown_until > now:
                    return

                try:
                    await ensure_private_listener_for_account(account_id, acc.account_name or account_id)
                except Exception as exc:
                    # 如果在静默长连接轮询中发现大号已被官方封禁/注销，立即触发状态置灰并向管理员推送实时 HTML 预警通知！
                    if is_banned_or_deactivated_error(exc):
                        await handle_deactivated_or_banned_account(account_id, exc)
                    mark_private_listener_cooldown(account_id, exc, "auto private listener connect")
                    print(f"[PrivateListener] Failed to auto-connect {account_id}: {exc}")

            # 串行连接，避免多个账号同时重连造成 Telegram transport 429。
            for acc in accounts:
                await process_single_account(acc)
                await asyncio.sleep(AUTO_PRIVATE_LISTENER_CONNECT_GAP_SECONDS)
        except Exception as exc:
            print(f"[PrivateListener] Auto listener loop error: {exc}")

        await asyncio.sleep(AUTO_PRIVATE_LISTENER_INTERVAL_SECONDS)

async def auto_connect_bg_task():
    """Background task to initialize account status store without blocking server startup or connecting to Telegram."""
    from db import engine, AccountDb, Session, select
    await asyncio.sleep(0.5)
    print("Initializing account status store locally...")

    try:
        with Session(engine) as session:
            db_accounts = session.exec(select(AccountDb)).all()
    except Exception as e:
        print(f"Error loading accounts on startup: {e}")
        return

    for acc in db_accounts:
        account_id = acc.id
        try:
            config = acc.to_dict()
            session_name = config.get("session_name", f"sessions/{account_id}/telegram_user")

            from sync_folder_groups import resolve_path
            from pathlib import Path
            config_path = account_config_path(account_id)
            base_dir = config_path.parent.parent
            session_path = resolve_path(base_dir, session_name)

            session_file = Path(f"{session_path}.session")
            if not session_file.exists():
                session_file = Path(session_path)

            cached = spambot_cache.get(account_id)
            default_spambot_status = cached.get("status", "unknown") if cached else "unknown"
            default_spambot_details = cached.get("details", "") if cached else ""
            default_spambot_time = cached.get("timestamp", None) if cached else None

            if session_file.exists() and session_file.stat().st_size > 0:
                name = acc.profile_modified_name or acc.account_name or "已保存"
                username = f" (@{acc.profile_modified_username})" if acc.profile_modified_username else ""
                display_me = f"{name}{username}".strip()
                set_account_status(account_id, {
                    "is_connected": False,
                    "is_authorized": True,
                    "me": display_me,
                    "spambot_status": default_spambot_status,
                    "spambot_details": default_spambot_details,
                    "spambot_time": default_spambot_time
                }, source="startup")
            else:
                set_account_status(account_id, {
                    "is_connected": False,
                    "is_authorized": False,
                    "me": "未登录",
                    "spambot_status": default_spambot_status,
                    "spambot_details": default_spambot_details,
                    "spambot_time": default_spambot_time
                }, source="startup")
        except Exception as e:
            print(f"Failed to check session for account {account_id}: {e}")


async def account_status_monitor_loop():
    """Publishes lightweight status changes without actively connecting to Telegram."""
    last_fingerprint: Dict[str, tuple] = {}
    while True:
        try:
            from db import engine, AccountDb, Session, select
            with Session(engine) as session:
                accounts = session.exec(select(AccountDb)).all()
            for acc in accounts:
                account_id = acc.id
                live_client = active_clients.get(account_id)
                try:
                    live_connected = bool(live_client and live_client.is_connected())
                except Exception:
                    live_connected = False
                busy_status = get_account_busy_status(account_id)
                fingerprint = (
                    live_connected,
                    busy_status,
                    bool(acc.is_available),
                    acc.bot_setup_status or "not_started",
                    account_id in auto_private_listener_accounts,
                )
                if last_fingerprint.get(account_id) != fingerprint:
                    last_fingerprint[account_id] = fingerprint
                    set_account_status(
                        account_id,
                        {
                            "is_connected": live_connected,
                            "busy_status": busy_status,
                            "is_busy": busy_status != "idle",
                            "is_available": acc.is_available,
                            "bot_setup_status": acc.bot_setup_status or "not_started",
                            "private_listener": (account_id in auto_private_listener_accounts and live_connected) if ENABLE_REALTIME_PRIVATE_DM else False,
                            "private_listener_source": ("auto" if account_id in auto_private_listener_accounts and live_connected else None) if ENABLE_REALTIME_PRIVATE_DM else None,
                        },
                        source="status-monitor"
                    )
        except Exception as exc:
            print(f"Account status monitor error: {exc}")
        await asyncio.sleep(5)

