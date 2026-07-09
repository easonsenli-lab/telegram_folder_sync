import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import HTTPException
from telethon import TelegramClient

from sync_folder_groups import build_client
from static_proxy_pool import ensure_safe_telegram_proxy_config, safe_proxy_summary
from account_manager import account_config_path, load_json

from services.shared_state import (
    active_clients,
    active_clients_last_accessed,
    client_locks,
    registered_listeners,
    active_account_operations,
    active_processes,
    find_campaign_process,
    set_account_status,
    is_account_busy_with_task,
    get_account_busy_status,
    auto_private_listener_accounts
)

# Concurrency locks specifically for account operations
account_operation_locks: Dict[str, asyncio.Lock] = {}

# Callback injection to avoid circular imports with register_login_code_listener
login_code_listener_callback = None

def is_campaign_running_for_account(account_id: str) -> bool:
    import web_server
    return web_server.is_campaign_running_for_account(account_id)


def get_account_operation_lock(account_id: str) -> asyncio.Lock:
    if account_id not in account_operation_locks:
        account_operation_locks[account_id] = asyncio.Lock()
    return account_operation_locks[account_id]

async def _disconnect_client_safely(account_id: str, client: TelegramClient):
    if account_id not in client_locks:
        client_locks[account_id] = asyncio.Lock()
    async with client_locks[account_id]:
        try:
            await client.disconnect()
        except Exception as exc:
            print(f"Failed to disconnect client {account_id}: {exc}")

def close_active_client_after_config_change(account_id: str):
    """Drop a cached Telethon client after config changes without failing the API call."""
    client = active_clients.pop(account_id, None)
    registered_listeners.discard(account_id)
    if not client:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_disconnect_client_safely(account_id, client))
    except RuntimeError:
        try:
            asyncio.run(_disconnect_client_safely(account_id, client))
        except Exception as exc:
            print(f"Failed to schedule disconnect for client {account_id}: {exc}")

def account_has_session_file(account_id: str, acc=None) -> bool:
    try:
        config = acc.to_dict() if acc is not None else load_json(account_config_path(account_id))
        session_name = config.get("session_name", f"sessions/{account_id}/telegram_user")
        from sync_folder_groups import resolve_path
        config_path = account_config_path(account_id)
        base_dir = config_path.parent.parent
        session_path = resolve_path(base_dir, session_name)
        candidates = [Path(f"{session_path}.session"), Path(session_path)]
        return any(path.exists() and path.stat().st_size > 0 for path in candidates)
    except Exception:
        return False

def validate_telegram_connection_config(account_id: str, config: dict, *, ignore_proxy: bool = False):
    """Ensure every Telegram connection uses the managed static proxy pool."""
    if ignore_proxy:
        raise HTTPException(
            status_code=409,
            detail="当前已禁止绕过代理直连 Telegram。所有账号操作必须使用静态代理池。",
        )
    try:
        ensure_safe_telegram_proxy_config(config, account_id=account_id)
        print(f"[ProxyPool] {account_id} Telegram 连接代理：{safe_proxy_summary(config)}")
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "无法为账号分配静态代理，已阻止连接 Telegram。"
                f"原因：{exc}"
            ),
        ) from exc

def mark_account_runtime_status(account_id: str, *, is_connected: bool, is_authorized: Optional[bool] = None, me: Optional[str] = None):
    """Keep account-management runtime state aligned with actual Telethon activity."""
    from services.shared_state import spambot_cache
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
                    if login_code_listener_callback:
                        try:
                            login_code_listener_callback(account_id, client)
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
            if login_code_listener_callback:
                try:
                    login_code_listener_callback(account_id, client)
                    registered_listeners.add(account_id)
                except Exception as e:
                    print(f"Failed to register login code listener: {e}")

        return client

def get_account_operation_block_reason(account_id: str, *, block_task_busy: bool = True) -> Optional[str]:
    active_op = active_account_operations.get(account_id)
    if active_op:
        return f"账号正在执行操作: {active_op.get('label') or active_op.get('operation') or 'active'}"
    if block_task_busy:
        busy_status = get_account_busy_status(account_id)
        if busy_status and busy_status != "idle":
            return f"账号正在执行任务: {busy_status}"
    return None

from contextlib import asynccontextmanager

@asynccontextmanager
async def account_operation_guard(account_id: str, operation: str, *, label: str = "", block_task_busy: bool = True):
    reason = get_account_operation_block_reason(account_id, block_task_busy=block_task_busy)
    if reason:
        raise HTTPException(status_code=409, detail=f"{reason}，请等待完成后再操作。")

    lock = get_account_operation_lock(account_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail="该账号正在被其他模块操作，请稍后再试。")

    await lock.acquire()
    active_account_operations[account_id] = {
        "operation": operation,
        "label": label or operation,
        "started_at": time.time(),
        "task_id": id(asyncio.current_task()) if asyncio.current_task() else None,
    }
    try:
        set_account_status(
            account_id,
            {
                "active_operation": operation,
                "active_operation_label": label or operation,
            },
            source="account-operation-start",
        )
    except Exception:
        pass

    try:
        yield
    finally:
        active_account_operations.pop(account_id, None)
        try:
            set_account_status(
                account_id,
                {
                    "active_operation": None,
                    "active_operation_label": None,
                },
                source="account-operation-finish",
            )
        except Exception:
            pass
        lock.release()

async def clean_idle_clients_loop():
    """Periodically disconnects inactive Telethon clients to save memory and socket resources."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for account_id, client in list(active_clients.items()):
            last_time = active_clients_last_accessed.get(account_id, 0)
            if now - last_time > 300:
                if account_id in auto_private_listener_accounts:
                    active_clients_last_accessed[account_id] = now
                    continue

                is_campaign_running = is_campaign_running_for_account(account_id)

                if not is_campaign_running and not is_account_busy_with_task(account_id):
                    try:
                        print(f"Disconnecting idle client {account_id} to free resources...")
                        active_clients.pop(account_id, None)
                        registered_listeners.discard(account_id)
                        active_clients_last_accessed.pop(account_id, None)
                        set_account_status(account_id, {"is_connected": False}, source="idle-disconnect")
                        if client.is_connected():
                            await client.disconnect()
                    except Exception as e:
                        print(f"Error disconnecting client {account_id}: {e}")
