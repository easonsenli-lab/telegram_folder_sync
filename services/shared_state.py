import asyncio
from pathlib import Path
import json
import os
import sys
import time
import datetime
import re
import subprocess
from zoneinfo import ZoneInfo
from typing import Dict, Any, Set, List, Optional, Tuple

# Timezone helpers
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = ZoneInfo("UTC")

def get_beijing_time_str() -> str:
    return datetime.datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

# Global connection caches and concurrency locks
active_clients = {}  # Dict[str, TelegramClient]
active_clients_last_accessed = {}  # Dict[str, float]
client_locks = {}  # Dict[str, asyncio.Lock]

# Campaign and schedulers task tracking
active_campaign_tasks = {}  # Dict[str, asyncio.Task]
active_campaign_schedules = {}  # Dict[str, asyncio.Task]

# Join group task tracking
active_join_tasks = {}  # Dict[str, dict]
last_join_task_id = None  # str | None

# Scraper and AI expansion tasks tracking
active_scraper_tasks = {}  # Dict[str, asyncio.Task]
active_expansion_tasks = {}  # Dict[str, asyncio.Task]

# Background connections and error tracking
bg_connect_tasks = {}  # Dict[str, asyncio.Task]
connection_errors = {}  # Dict[str, str]

# Global background tasks tracker
background_tasks = set()  # Set[asyncio.Task]

# Registered listeners for private DM events
registered_listeners = set()  # Set[WebSocket]

# Operations registries and process tables
active_account_operations = {}  # Dict[str, dict]
active_processes = {}  # Dict[str, subprocess.Popen]
campaign_process_cache: Dict[str, Any] = {"expires_at": 0.0, "by_account": {}}

# Spambot cache and config paths
SPAMBOT_CACHE_FILE = Path("data/spambot_cache.json")

def load_spambot_cache() -> Dict[str, dict]:
    if SPAMBOT_CACHE_FILE.exists():
        try:
            with open(SPAMBOT_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_spambot_cache(cache: Dict[str, dict]):
    try:
        SPAMBOT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SPAMBOT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save spambot cache: {e}")

spambot_cache = load_spambot_cache()

ENABLE_REALTIME_PRIVATE_DM = os.getenv("ROSEPAY_ENABLE_REALTIME_PRIVATE_DM", "1").strip().lower() not in {"0", "false", "off", "no"}
private_relay_enabled = ENABLE_REALTIME_PRIVATE_DM

# Account status and notification queues
account_status_store = {}  # Dict[str, dict]
account_status_subscribers = set()  # Set[asyncio.Queue]
private_dm_subscribers = set()  # Set[asyncio.Queue]
account_task_registry = {}  # Dict[str, Dict[str, dict]]
private_unread_cache = {}  # Dict[str, dict]

# Active accounts in private DMs listener loop and cooldowns
auto_private_listener_accounts = set()  # Set[str]
auto_private_listener_cooldowns = {}  # Dict[str, float]

# Connection logs for frontend reporting
login_connection_logs = {}  # Dict[str, List[str]]

# InMemory storage for login codes and official messages
captured_login_codes = {}  # Dict[str, List[dict]]
official_messages_store = {}  # Dict[str, List[dict]]
dm_folder_peer_cache = {}  # Dict[str, Set[int]]
DM_FOLDER_NAME = "DM"

TASK_BUSY_PRIORITY = {"join": 10, "campaign": 20, "scraper": 30, "expansion": 40}

# --- PROCESS STATUS UTILITIES ---
def scan_campaign_processes_cached(ttl_seconds: float = 5.0) -> Dict[str, int]:
    now = time.time()
    cached = campaign_process_cache.get("by_account") or {}
    if float(campaign_process_cache.get("expires_at", 0) or 0) > now:
        return cached

    by_account: Dict[str, int] = {}
    try:
        if sys.platform == "win32":
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | Select-Object ProcessId, CommandLine | ConvertTo-Json",
            ]
            output = subprocess.check_output(cmd, text=True, errors="ignore", timeout=3)
            if output.strip():
                data = json.loads(output)
                if isinstance(data, dict):
                    data = [data]
                for proc in data:
                    cmdline = proc.get("CommandLine") or ""
                    if "ad_sender.py" not in cmdline or "--account" not in cmdline:
                        continue
                    match = re.search(r"--account\s+([^\s\"']+)", cmdline)
                    if match:
                        by_account[match.group(1)] = int(proc.get("ProcessId") or 0)
        else:
            output = subprocess.check_output(["ps", "-eo", "pid,args"], text=True, errors="ignore", timeout=3)
            for line in output.strip().split("\n"):
                parts = line.strip().split(None, 1)
                if len(parts) != 2:
                    continue
                pid_str, cmdline = parts
                if "ad_sender.py" not in cmdline or "--account" not in cmdline:
                    continue
                match = re.search(r"--account\s+([^\s\"']+)", cmdline)
                if match:
                    by_account[match.group(1)] = int(pid_str)
    except Exception:
        by_account = cached

    campaign_process_cache["by_account"] = by_account
    campaign_process_cache["expires_at"] = now + ttl_seconds
    return by_account

def find_campaign_process(account_id: str) -> Optional[int]:
    return scan_campaign_processes_cached().get(str(account_id))

def is_campaign_running_for_account(account_id: str) -> bool:
    # 1. Check in-process campaign tasks
    try:
        registry = account_task_registry.get(str(account_id)) or {}
        for task_id, task_info in registry.items():
            if task_info.get("kind") == "campaign" and task_id in active_campaign_tasks:
                return True
    except Exception:
        pass
    # 2. Check active subprocesses
    if account_id in active_processes and active_processes[account_id].poll() is None:
        return True
    # 3. Check OS level processes running ad_sender.py
    if find_campaign_process(account_id) is not None:
        return True
    return False

def campaign_task_uses_account(task_record, account_id: str) -> bool:
    # Mimic original logic
    raw = getattr(task_record, "account_ids_json", "") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            ids = [str(x).strip() for x in parsed if str(x).strip()]
            if ids:
                return account_id in ids
        except Exception:
            pass
    return account_id == str(task_record.account_id)


# --- ACCOUNT TASK REGISTRY UTILITIES ---
def get_registered_account_task(account_id: str) -> Optional[dict]:
    tasks = account_task_registry.get(account_id) or {}
    active_items = [item for item in tasks.values() if item.get("status") == "running"]
    if not active_items:
        return None
    return sorted(active_items, key=lambda item: TASK_BUSY_PRIORITY.get(item.get("kind"), 99))[0]

def get_account_busy_status(account_id: str) -> str:
    registered_task = get_registered_account_task(account_id)
    if registered_task:
        return registered_task.get("kind", "busy")

    # 1. Check active join tasks
    for t in active_join_tasks.values():
        if t.get("status") == "running" and account_id in t.get("params", {}).get("account_ids", []):
            return "join"

    # 2. Check active campaign tasks
    from db import engine, CampaignTaskDb, Session, select
    with Session(engine) as session:
        stmt = select(CampaignTaskDb).where(CampaignTaskDb.status == "running")
        running_tasks = session.exec(stmt).all()
        for task in running_tasks:
            if task.id in active_campaign_tasks and campaign_task_uses_account(task, account_id):
                return "campaign"

    # 3. Check legacy campaign subprocesses
    try:
        process = active_processes.get(account_id)
        if process and process.poll() is None:
            return "campaign"
        if find_campaign_process(account_id) is not None:
            return "campaign"
    except Exception:
        pass

    # 4. Check automatic discovery tasks
    for t in active_scraper_tasks.values():
        if t.get("status") == "running" and t.get("account_id") == account_id:
            return "scraper"
    for t in active_expansion_tasks.values():
        if t.get("status") == "running" and t.get("account_id") == account_id:
            return "expansion"
    return "idle"

def is_account_busy_with_task(account_id: str) -> bool:
    return get_account_busy_status(account_id) != "idle"

def is_account_executable_for_task(account) -> bool:
    if getattr(account, "is_available", True) is False:
        return False
    return not is_account_busy_with_task(account.id)

def filter_executable_accounts_for_task(accounts):
    return [acc for acc in accounts if is_account_executable_for_task(acc)]


# --- STATUS UPDATE & WEBSOCKET PUBLICATION UTILITIES ---
def publish_account_status(account_id: str, patch: dict):
    if not account_status_subscribers:
        return
    payload = json.dumps({"type": "account_status", "account_id": account_id, "patch": patch}, ensure_ascii=False)
    stale_queues = []
    for queue in list(account_status_subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            stale_queues.append(queue)
    for queue in stale_queues:
        account_status_subscribers.discard(queue)

def normalize_account_status_patch(account_id: str, patch: dict) -> dict:
    normalized = dict(patch)
    live_client = active_clients.get(account_id)
    if live_client is not None:
        try:
            normalized["is_connected"] = bool(live_client.is_connected())
        except Exception:
            pass
    if "is_connected" in normalized:
        normalized["connection_status"] = "connected" if normalized.get("is_connected") else "disconnected"
    elif "connection_status" not in normalized:
        normalized["connection_status"] = "unknown"

    if normalized.get("is_deactivated"):
        normalized["auth_status"] = "deactivated"
    elif "is_authorized" in normalized:
        normalized["auth_status"] = "authorized" if normalized.get("is_authorized") else "unauthorized"
    elif "auth_status" not in normalized:
        normalized["auth_status"] = "unknown"

    try:
        busy_status = get_account_busy_status(account_id)
    except Exception:
        busy_status = normalized.get("busy_status", "idle")
    normalized["busy_status"] = busy_status
    normalized["is_busy"] = busy_status != "idle"
    normalized["task_status"] = busy_status
    active_operation = active_account_operations.get(account_id)
    if active_operation:
        normalized["active_operation"] = active_operation.get("operation")
        normalized["active_operation_label"] = active_operation.get("label")
    elif normalized.get("active_operation") is None:
        normalized["active_operation"] = None
        normalized["active_operation_label"] = None

    try:
        from db import engine, AccountDb, Session
        with Session(engine) as session:
            db_account = session.get(AccountDb, account_id)
            if db_account:
                normalized["is_available"] = db_account.is_available
                normalized["availability_status"] = "available" if db_account.is_available else "occupied"
                normalized["bot_setup_status"] = db_account.bot_setup_status or normalized.get("bot_setup_status", "not_started")
    except Exception:
        if "is_available" in normalized:
            normalized["availability_status"] = "available" if normalized.get("is_available") else "occupied"

    normalized["last_checked_at"] = normalized.get("last_checked_at") or time.time()
    return normalized

def set_account_status(account_id: str, patch: dict, source: str = "runtime") -> dict:
    current = account_status_store.get(account_id, {}).copy()
    current.update(patch)
    current["source"] = source
    current = normalize_account_status_patch(account_id, current)
    account_status_store[account_id] = current
    try:
        publish_account_status(account_id, current)
    except Exception as exc:
        print(f"Failed to publish account status for {account_id}: {exc}")
    return current

def get_cached_auth_state(account_id: str) -> Tuple[bool, str]:
    status = account_status_store.get(account_id, {}) or {}
    cached_authorized = bool(status.get("is_authorized") or status.get("auth_status") == "authorized")
    cached_me = status.get("me") or ("已连接" if cached_authorized else "状态未知")
    return cached_authorized, cached_me

def is_placeholder_me_info(value: Optional[str]) -> bool:
    return str(value or "").strip() in {"", "已连接", "未连接", "未登录", "状态未知", "连接状态失败", "未初始化（等待检测）"}

def account_saved_profile_display(acc: Any) -> str:
    name = (getattr(acc, "profile_modified_name", None) or getattr(acc, "account_name", None) or "").strip()
    username = (getattr(acc, "profile_modified_username", None) or "").strip().lstrip("@")
    if username:
        return f"{name} (@{username})".strip()
    return name

def set_login_status_check_failed(account_id: str, message: str, *, source: str, is_connected: Optional[bool] = None) -> dict:
    cached_authorized, cached_me = get_cached_auth_state(account_id)
    patch = {
        "is_authorized": cached_authorized,
        "me": cached_me,
        "error": message,
        "last_error": message,
        "status_check_failed": True,
    }
    if is_connected is not None:
        patch["is_connected"] = is_connected
    return set_account_status(account_id, patch, source=source)

def publish_task_status_for_accounts(account_ids: List[str], source: str = "task-registry"):
    for account_id in set(account_ids or []):
        try:
            busy_status = get_account_busy_status(account_id)
            set_account_status(
                account_id,
                {
                    "busy_status": busy_status,
                    "is_busy": busy_status != "idle",
                    "task_status": busy_status,
                },
                source=source,
            )
        except Exception as exc:
            print(f"Failed to refresh task status for account {account_id}: {exc}")

def register_account_task_usage(kind: str, task_id: str, account_ids: List[str], meta: Optional[dict] = None):
    now = time.time()
    for account_id in set(account_ids or []):
        account_task_registry.setdefault(account_id, {})[task_id] = {
            "kind": kind,
            "task_id": task_id,
            "status": "running",
            "started_at": now,
            "meta": meta or {},
        }
    publish_task_status_for_accounts(account_ids, source=f"{kind}-task-start")

def release_account_task_usage(task_id: str, account_ids: Optional[List[str]] = None, source: str = "task-release"):
    affected = set(account_ids or [])
    if account_ids is None:
        for account_id, tasks in list(account_task_registry.items()):
            if task_id in tasks:
                affected.add(account_id)
    for account_id in list(affected):
        tasks = account_task_registry.get(account_id)
        if not tasks:
            continue
        tasks.pop(task_id, None)
        if not tasks:
            account_task_registry.pop(account_id, None)
    publish_task_status_for_accounts(list(affected), source=source)
