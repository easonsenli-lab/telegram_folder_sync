# -*- coding: utf-8 -*-
import asyncio
import datetime
import html
import json
import time
import re
import os
import random
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from fastapi import HTTPException
from telethon import functions, types, errors

from services.shared_state import (
    active_join_tasks,
    last_join_task_id,
    register_account_task_usage,
    release_account_task_usage,
    set_account_status,
    background_tasks,
    get_beijing_time_str,
    account_status_store
)

from services.client_manager import get_client

# Import helpers from web_server dynamically or statically
def get_account_notify_label(account_id: str) -> str:
    import web_server
    return web_server.get_account_notify_label(account_id)

def get_ops_target_mention(username: str) -> str:
    import web_server
    return web_server.get_ops_target_mention(username)

def send_ops_bot_notification_with_buttons(text: str, event: dict, buttons: List[List[dict]]) -> None:
    import web_server
    return web_server.send_ops_bot_notification_with_buttons(text, event, buttons)

def ops_event_time() -> str:
    import web_server
    return web_server.ops_event_time()

def html_line(label: str, value: Any) -> str:
    import web_server
    return web_server.html_line(label, value)

def get_user_telegram_contact(username: str) -> str:
    import web_server
    return web_server.get_user_telegram_contact(username)

def check_account_company(account_id: str, user: dict):
    import web_server
    return web_server.check_account_company(account_id, user)

def is_account_executable_for_task(account) -> bool:
    import web_server
    return web_server.is_account_executable_for_task(account)

def get_cached_auth_state(account_id: str) -> Tuple[bool, str]:
    import web_server
    return web_server.get_cached_auth_state(account_id)

def set_login_status_check_failed(account_id: str, message: str, *, source: str, is_connected: Optional[bool] = None) -> dict:
    import web_server
    return web_server.set_login_status_check_failed(account_id, message, source=source, is_connected=is_connected)

def find_group_by_username_or_id(
    session,
    group_id: Optional[Any] = None,
    username: Optional[str] = None,
    company: Optional[str] = None,
):
    import web_server
    if username is None and isinstance(group_id, str):
        username = group_id
        group_id = None
    return web_server.find_group_by_username_or_id(session, group_id, username, company)

def is_banned_or_deactivated_error(exc: Exception) -> bool:
    import web_server
    return web_server.is_banned_or_deactivated_error(exc)

async def handle_deactivated_or_banned_account(account_id: str, exc: Exception) -> None:
    import web_server
    return await web_server.handle_deactivated_or_banned_account(account_id, exc)

def mark_account_runtime_status(
    account_id: str,
    is_connected: bool,
    is_authorized: Optional[bool] = None,
    status_msg: Optional[str] = None,
    me: Optional[str] = None,
) -> None:
    import web_server
    if me is None and status_msg is not None:
        me = status_msg
    return web_server.mark_account_runtime_status(
        account_id,
        is_connected=is_connected,
        is_authorized=is_authorized,
        me=me,
    )

async def check_can_speak(client, entity, phone: Optional[str] = None) -> bool:
    import web_server
    return await web_server.check_can_speak(client, entity)


from pydantic import BaseModel
from sync_folder_groups import normalize_title

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

class LogList(list):
    def __init__(self, seq=()):
        super().__init__(seq)

    def append(self, item):
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        if isinstance(item, str) and not re.match(r"^\[\d{2}:\d{2}:\d{2}\]", item):
            super().append(f"[{time_str}] {item}")
        else:
            super().append(item)



def persistent_task_resume_enabled() -> bool:
    return os.getenv("RESUME_PERSISTENT_TASKS", "1").strip().lower() not in {"0", "false", "no", "off"}

def normalize_loaded_join_task(task_id: str, task_data: dict, reason: str = "历史入群任务已暂停。") -> dict:
    """Loaded task history must not be treated as an active worker when auto-resume is disabled."""
    if not isinstance(task_data.get("logs"), LogList):
        task_data["logs"] = LogList(task_data.get("logs", []))
    if not persistent_task_resume_enabled() and task_data.get("status") == "running":
        task_data["status"] = "paused"
        task_data["logs"].append(reason)
    return task_data



def serialize_join_task(task_id: str, task_data: dict) -> dict:
    if "created_at" not in task_data:
        import datetime
        task_data["created_at"] = datetime.datetime.now().isoformat()

    return {
        "task_id": task_id,
        "company": task_data.get("company", "admin"),
        "owner_username": task_data.get("owner_username", "admin"),
        "created_at": task_data.get("created_at"),
        "status": task_data.get("status"),
        "progress": task_data.get("progress"),
        "results": task_data.get("results"),
        "logs": list(task_data.get("logs", [])),
        "params": task_data.get("params")
    }

def save_join_task_file(task_id: str, task_data: dict):
    tasks_dir = Path("data/join_tasks")
    tasks_dir.mkdir(parents=True, exist_ok=True)
    with open(tasks_dir / f"{task_id}.json", "w", encoding="utf-8") as f:
        json.dump(serialize_join_task(task_id, task_data), f, ensure_ascii=False, indent=2)

def save_last_join_task(task_id: str):
    global active_join_tasks
    try:
        task_data = active_join_tasks.get(task_id)
        if task_data:
            serializable_task = serialize_join_task(task_id, task_data)
            save_join_task_file(task_id, task_data)

            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            with open(data_dir / "last_join_task.json", "w", encoding="utf-8") as f:
                json.dump({
                    "last_task_id": task_id,
                    "task_data": serializable_task
                }, f, ensure_ascii=False, indent=2)

            company = serializable_task.get("company", "admin")
            sanitized_company = "".join(c for c in company if c.isalnum() or c in "._-")
            with open(data_dir / f"last_join_task_{sanitized_company}.json", "w", encoding="utf-8") as f:
                json.dump({
                    "last_task_id": task_id,
                    "task_data": serializable_task
                }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save join task {task_id}: {e}")

def cleanup_running_tasks_on_startup():
    try:
        return
    except Exception as e:
        print(f"Failed to execute cleanup_running_tasks_on_startup: {e}")

def load_last_join_task_on_startup():
    global last_join_task_id, active_join_tasks
    try:
        tasks_dir = Path("data/join_tasks")
        if tasks_dir.exists():
            for f in tasks_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        task_data = json.load(file)
                    task_id = task_data.get("task_id") or f.stem
                    task_data = normalize_loaded_join_task(
                        task_id,
                        task_data,
                        "服务器启动恢复已关闭，历史入群任务已暂停。"
                    )
                    active_join_tasks[task_id] = task_data
                    if task_data.get("status") == "paused":
                        save_join_task_file(task_id, task_data)
                except Exception as ex:
                    print(f"Failed to load join task file {f.name}: {ex}")

        task_file = Path("data/last_join_task.json")
        if task_file.exists():
            with open(task_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            last_join_task_id = state.get("last_task_id")
            task_data = state.get("task_data")
            if last_join_task_id and task_data:
                if last_join_task_id not in active_join_tasks:
                    task_data = normalize_loaded_join_task(
                        last_join_task_id,
                        task_data,
                        "服务器启动恢复已关闭，历史入群任务已暂停。"
                    )
                    active_join_tasks[last_join_task_id] = task_data
                else:
                    task_data = active_join_tasks[last_join_task_id]
                if task_data.get("status") == "paused":
                    save_last_join_task(last_join_task_id)
    except Exception as e:
        print(f"Failed to load last join task: {e}")

load_last_join_task_on_startup()



async def join_group_or_channel_get_entity_only(client, link: str):
    import re
    from telethon.tl import functions
    link = link.strip()
    private_match = re.search(r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)([a-zA-Z0-9\-_]+)', link)
    if private_match:
        invite_hash = private_match.group(1)
        invite = await client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
        if hasattr(invite, 'chat'):
            return invite.chat
        elif hasattr(invite, 'chats') and invite.chats:
            return invite.chats[0]
    public_match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,32})', link)
    username = public_match.group(1) if public_match else link.replace("@", "").strip()
    return await client.get_entity(username)

async def join_group_or_channel(client, link: str):
    from telethon.tl import functions, types
    import re
    link = link.strip()
    if not link:
        raise ValueError("链接为空")
    private_match = re.search(r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)([a-zA-Z0-9\-_]+)', link)
    if private_match:
        invite_hash = private_match.group(1)
        updates = await client(functions.messages.ImportChatInviteRequest(hash=invite_hash))
        if hasattr(updates, 'chats') and updates.chats:
            return updates.chats[0]
        dialogs = await client.get_dialogs(limit=5)
        return dialogs[0].entity
    public_match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,32})', link)
    username = public_match.group(1) if public_match else link.replace("@", "").strip()
    entity = await client.get_entity(username)
    await client(functions.channels.JoinChannelRequest(channel=entity))
    return entity

# --- HELPER FUNCTIONS FOR CHAT FOLDER MANAGEMENT ---

async def try_create_folder_early(client, folder_name: str):
    from telethon.tl import functions, types
    try:
        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result) or []

        folder = next((item for item in raw_filters if hasattr(item, "title") and normalize_title(item.title) == folder_name), None)
        if folder:
            return

        existing_ids = {item.id for item in raw_filters if hasattr(item, "id")}
        next_id = 2
        while next_id in existing_ids:
            next_id += 1

        # Try to find a group to seed the folder (Telegram requires at least one peer)
        include_peers = []
        try:
            dialogs = await client.get_dialogs(limit=50)
            for d in dialogs:
                if d.is_group or d.is_channel:
                    try:
                        peer = await client.get_input_entity(d.entity)
                        include_peers = [peer]
                        break
                    except Exception:
                        pass
        except Exception:
            pass

        if not include_peers:
            # Cannot seed folder without a peer - skip creation, will be created on first join
            return

        new_filter = types.DialogFilter(
            id=next_id,
            title=types.TextWithEntities(text=folder_name, entities=[]),
            pinned_peers=[],
            include_peers=include_peers,
            exclude_peers=[],
            contacts=False,
            non_contacts=False,
            groups=False,
            broadcasts=False,
            bots=False
        )
        await client(functions.messages.UpdateDialogFilterRequest(
            id=next_id,
            filter=new_filter
        ))
    except Exception as e:
        print(f"Failed to create folder early: {e}")

async def determine_group_folder_name(client, entity, link: str, company: str) -> str:
    import re
    from db import engine, GroupDb, Session, select

    # 公开群严格按 username 匹配群库分类；不再抓消息临时猜中文/英文长短。
    valid_categories = {"中文长", "中文短", "英文长", "英文短"}
    public_match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,32})', link)
    if public_match:
        username = public_match.group(1)
    else:
        username = getattr(entity, "username", None) or link.replace("@", "").strip()

    try:
        with Session(engine) as session:
            db_group = find_group_by_username_or_id(
                session,
                getattr(entity, "id", None),
                username,
                company,
            )
            if db_group and db_group.category in valid_categories:
                return db_group.category
    except Exception as dbe:
        print(f"Failed to query database for group category: {dbe}")

    # 群库没有维护该 username 时只做保底，避免任务中断。
    g_title = getattr(entity, "title", "") or ""
    has_chinese_name = bool(re.search(r"[\u4e00-\u9fa5]", g_title)) or "🇨🇳" in g_title
    return "中文长" if has_chinese_name else "英文长"

async def clean_and_convert_peers_async(client, peers_list) -> list:
    from telethon.tl import types
    clean_list = []
    if not peers_list:
        return clean_list
    for p in peers_list:
        try:
            inp = await client.get_input_entity(p)
            clean_list.append(inp)
        except Exception:
            pass
    return clean_list

async def add_peer_to_folder(client, entity, folder_name: str):
    from telethon.tl import functions, types
    try:
        peer = await client.get_input_entity(entity)
    except Exception as e:
        print(f"Failed to get input entity for folder: {e}")
        return

    result = await client(functions.messages.GetDialogFiltersRequest())
    raw_filters = getattr(result, "filters", result) or []

    folder = next((item for item in raw_filters if hasattr(item, "title") and normalize_title(item.title) == folder_name), None)
    auto_category_folders = {"中文长", "中文短", "英文长", "英文短"}

    def get_peer_id(p):
        return getattr(p, "channel_id", getattr(p, "chat_id", getattr(p, "user_id", None)))

    new_peer_id = get_peer_id(peer)
    if new_peer_id is None:
        return

    async def remove_peer_from_other_category_folders():
        for item in raw_filters:
            if not isinstance(item, types.DialogFilter):
                continue
            item_title = normalize_title(getattr(item, "title", ""))
            if item_title == folder_name or item_title not in auto_category_folders:
                continue

            include_peers = list(getattr(item, "include_peers", []) or [])
            pinned_peers = list(getattr(item, "pinned_peers", []) or [])
            exclude_peers = list(getattr(item, "exclude_peers", []) or [])

            new_include = [p for p in include_peers if get_peer_id(p) != new_peer_id]
            new_pinned = [p for p in pinned_peers if get_peer_id(p) != new_peer_id]
            if len(new_include) == len(include_peers) and len(new_pinned) == len(pinned_peers):
                continue

            clean_include = await clean_and_convert_peers_async(client, new_include)
            clean_pinned = await clean_and_convert_peers_async(client, new_pinned)
            clean_exclude = await clean_and_convert_peers_async(client, exclude_peers)

            new_filter = types.DialogFilter(
                id=item.id,
                title=item.title if not isinstance(item.title, str) else types.TextWithEntities(text=item.title, entities=[]),
                pinned_peers=clean_pinned,
                include_peers=clean_include,
                exclude_peers=clean_exclude,
                contacts=getattr(item, "contacts", False),
                non_contacts=getattr(item, "non_contacts", False),
                groups=getattr(item, "groups", False),
                broadcasts=getattr(item, "broadcasts", False),
                bots=getattr(item, "bots", False)
            )
            await client(functions.messages.UpdateDialogFilterRequest(
                id=item.id,
                filter=new_filter
            ))

    if folder_name in auto_category_folders:
        await remove_peer_from_other_category_folders()

    if folder:
        if not isinstance(folder, types.DialogFilter):
            print(f"Folder '{folder_name}' exists but is not a standard DialogFilter (type: {type(folder).__name__}), skipping peer add.")
            return

        if not hasattr(folder, "include_peers") or folder.include_peers is None:
            folder.include_peers = []

        already_exists = False
        for p in folder.include_peers:
            if get_peer_id(p) == new_peer_id:
                already_exists = True
                break

        if not already_exists:
            updated_peers = list(folder.include_peers) + [peer]
            clean_include = await clean_and_convert_peers_async(client, updated_peers)
            clean_pinned = await clean_and_convert_peers_async(client, getattr(folder, "pinned_peers", []) or [])
            clean_exclude = await clean_and_convert_peers_async(client, getattr(folder, "exclude_peers", []) or [])

            new_filter = types.DialogFilter(
                id=folder.id,
                title=folder.title if not isinstance(folder.title, str) else types.TextWithEntities(text=folder.title, entities=[]),
                pinned_peers=clean_pinned,
                include_peers=clean_include,
                exclude_peers=clean_exclude,
                contacts=getattr(folder, "contacts", False),
                non_contacts=getattr(folder, "non_contacts", False),
                groups=getattr(folder, "groups", False),
                broadcasts=getattr(folder, "broadcasts", False),
                bots=getattr(folder, "bots", False)
            )
            await client(functions.messages.UpdateDialogFilterRequest(
                id=folder.id,
                filter=new_filter
            ))
    else:
        existing_ids = {item.id for item in raw_filters if hasattr(item, "id")}
        next_id = 2
        while next_id in existing_ids:
            next_id += 1

        new_filter = types.DialogFilter(
            id=next_id,
            title=types.TextWithEntities(text=folder_name, entities=[]),
            pinned_peers=[],
            include_peers=[peer],
            exclude_peers=[],
            contacts=False,
            non_contacts=False,
            groups=False,
            broadcasts=False,
            bots=False
        )
        await client(functions.messages.UpdateDialogFilterRequest(
            id=next_id,
            filter=new_filter
        ))

async def join_worker_task(task_id: str, req: JoinTaskRequest):
    import random
    import traceback
    import asyncio
    task = active_join_tasks[task_id]
    task["status"] = "running"
    task["logs"].append("入群任务已启动...")
    save_last_join_task(task_id)
    register_account_task_usage(
        "join",
        task_id,
        req.account_ids,
        {"company": task.get("company"), "owner_username": task.get("owner_username")},
    )

    results = task["results"]

    try:
        account_ids = req.account_ids
        links = req.links
        mode = req.mode
        strategy = req.strategy

        # New parameters
        max_rounds = req.max_rounds
        groups_per_round = req.groups_per_round if req.groups_per_round > 0 else 10
        round_interval_minutes = req.round_interval_minutes if req.round_interval_minutes > 0 else 5

        if strategy == "fixed":
            base_delay = req.fixed_delay
        else:
            base_delay = (req.safety_minutes * 60) / req.safety_groups

        task["logs"].append(f"基准延迟设为: {base_delay:.1f} 秒")

        from db import engine, AccountDb, Session, GroupDb, select
        accounts_info = []
        with Session(engine) as session:
            for acc_id in req.account_ids:
                db_acc = session.get(AccountDb, acc_id)
                if db_acc:
                    accounts_info.append((acc_id, db_acc.account_name))

        task["logs"].append("开始执行账号已入群检测排重...")
        accounts_todo_links = {}

        async def check_account_todo(acc_id, phone):
            import re
            from telethon.tl import functions, types
            try:
                client = await get_client(acc_id)
                is_auth = await client.is_user_authorized()
                if not is_auth:
                    return acc_id, [], 0

                dialogs = await client.get_dialogs(limit=None)
                joined_usernames = {d.entity.username.lower() for d in dialogs if getattr(d.entity, 'username', None)}
                joined_ids = {d.entity.id for d in dialogs}

                todo_links = []
                skipped_count = 0
                for link in links:
                    is_joined = False
                    private_match = re.search(r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)([a-zA-Z0-9\-_]+)', link)
                    if private_match:
                        invite_hash = private_match.group(1)
                        try:
                            invite = await client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
                            if type(invite).__name__ == 'ChatInviteAlready':
                                is_joined = True
                            elif hasattr(invite, 'chat') and invite.chat:
                                if invite.chat.id in joined_ids:
                                    is_joined = True
                        except Exception:
                            pass
                    else:
                        public_match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,32})', link)
                        username = public_match.group(1) if public_match else link.replace("@", "").strip()
                        if username and username.lower() in joined_usernames:
                            is_joined = True

                    if is_joined:
                        skipped_count += 1
                    else:
                        todo_links.append(link)

                if skipped_count > 0:
                    task["logs"].append(f"账号 {phone} 检测到已加入其中 {skipped_count} 个群组，已自动跳过，不占任务数。")
                return acc_id, todo_links, skipped_count
            except Exception as ex:
                if is_banned_or_deactivated_error(ex):
                    await handle_deactivated_or_banned_account(acc_id, ex)
                task["logs"].append(f"账号 {phone} 检查已加入群组失败: {ex}")
                return acc_id, [], 0

        results_precheck = await asyncio.gather(*(check_account_todo(acc_id, phone) for acc_id, phone in accounts_info))
        precheck_skipped_total = 0
        for acc_id, todo, skipped_count in results_precheck:
            accounts_todo_links[acc_id] = todo
            precheck_skipped_total += int(skipped_count or 0)

        task["progress"]["total"] = sum(len(todo) for todo in accounts_todo_links.values())
        task["precheck"] = {
            "target_groups": len(links),
            "dedup_skipped": precheck_skipped_total,
            "todo_total": task["progress"]["total"],
        }

        if req.move_to_folder:
            target_folders = []
            if req.folder_by_type:
                target_folders = ["中文长", "中文短", "英文长", "英文短"]
            elif req.target_folder_name and req.target_folder_name.strip():
                target_folders = [req.target_folder_name.strip()]

            if target_folders:
                task["logs"].append(f"开始执行前置检测并创建聊天文件夹: {target_folders}...")
                for acc_id, phone in accounts_info:
                    try:
                        client = await get_client(acc_id)
                        is_authorized = await client.is_user_authorized()
                        if is_authorized:
                            mark_account_runtime_status(acc_id, is_connected=True, is_authorized=True)
                            for folder_name_clean in target_folders:
                                await try_create_folder_early(client, folder_name_clean)
                    except Exception as ex:
                        if is_banned_or_deactivated_error(ex):
                            await handle_deactivated_or_banned_account(acc_id, ex)
                        print(f"Failed early folder check/creation for {phone}: {ex}")

        # Keep track of links index per account
        accounts_link_index = {acc_id: 0 for acc_id, _ in accounts_info}

        async def join_single_account_links_this_round(account_id: str, phone: str):
            from db import engine, GroupDb, Session, select
            import re
            from telethon import errors as telethon_errors

            def find_group_id_by_link_or_entity(session, link: str, entity=None) -> tuple[Optional[str], Optional[str]]:
                if entity:
                    stmt = select(GroupDb).where(GroupDb.id == str(entity.id))
                    if task.get("company") != "admin":
                        stmt = stmt.where(GroupDb.company == task.get("company"))
                    db_group = session.exec(stmt).first()
                    if db_group:
                        return db_group.id, db_group.title

                public_match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,32})', link)
                username = public_match.group(1) if public_match else link.replace("@", "").strip()
                if username:
                    stmt = select(GroupDb).where(GroupDb.username.ilike(username))
                    db_group = session.exec(stmt).first()
                    if db_group:
                        return db_group.id, db_group.title
                return None, None

            todo_links = accounts_todo_links.get(account_id, [])
            start_idx = accounts_link_index.get(account_id, 0)

            added_this_round = 0
            idx = start_idx

            while idx < len(todo_links) and added_this_round < groups_per_round:
                status = account_status_store.get(account_id, {})
                if status.get("auth_status") == "unauthorized" or not status.get("is_authorized", True):
                    task["logs"].append(f"⚠️ 账号 {phone} 检测到已处于未登录/封禁状态，终止该账号入群任务。")
                    break

                if task["status"] == "stopped":
                    task["logs"].append(f"账号 {phone} 的入群任务已被手动停止。")
                    break

                link = todo_links[idx]
                idx += 1
                accounts_link_index[account_id] = idx # Update pointer

                task["logs"].append(f"账号 {phone} 正在处理链接 ({idx}/{len(todo_links)}): {link} ...")

                # Not a duplicate, proceed with joining
                task["logs"].append(f"账号 {phone} 正在尝试加入: {link} ...")

                async def join_link_logic():
                    nonlocal added_this_round
                    try:
                        client = await get_client(account_id)
                        is_authorized = await client.is_user_authorized()
                        if not is_authorized:
                            mark_account_runtime_status(account_id, is_connected=client.is_connected(), is_authorized=False)
                            raise Exception("账号未登录")
                        mark_account_runtime_status(account_id, is_connected=True, is_authorized=True)

                        # Pre-check entity restriction
                        entity = None
                        try:
                            entity = await join_group_or_channel_get_entity_only(client, link)
                        except Exception:
                            pass

                        is_restricted = False
                        restriction_reason_str = ""
                        is_channel = False
                        if entity:
                            if getattr(entity, 'restricted', False):
                                is_restricted = True
                                reasons = getattr(entity, 'restriction_reason', []) or []
                                reasons_text = [getattr(r, 'text', '') for r in reasons]
                                restriction_reason_str = "; ".join(filter(None, reasons_text)) or "该群组已被屏蔽限制 (restricted)"

                            from telethon.tl.types import Channel, ChatInvite
                            if isinstance(entity, Channel) and getattr(entity, 'broadcast', False):
                                is_channel = True
                            elif isinstance(entity, ChatInvite) and getattr(entity, 'broadcast', False):
                                is_channel = True

                        if is_channel:
                            task["logs"].append(f"账号 {phone} 检测到 {link} 是频道，触发‘频道不自动加入’规则，跳过。")
                            results.append({
                                "account_id": account_id,
                                "phone": phone,
                                "link": link,
                                "status": "skipped",
                                "error": "频道不自动加入",
                                "group_id": str(entity.id) if hasattr(entity, 'id') else None,
                                "title": getattr(entity, 'title', link)
                            })
                            task["progress"]["current"] += 1
                            save_last_join_task(task_id)
                            return

                        if is_restricted:
                            with Session(engine) as session:
                                db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link, entity)
                            task["logs"].append(f"账号 {phone} 检测到 {link} 是无效限制群组: {restriction_reason_str}")
                            results.append({
                                "account_id": account_id,
                                "phone": phone,
                                "link": link,
                                "status": "invalid",
                                "error": restriction_reason_str,
                                "group_id": db_group_id,
                                "title": db_group_title or getattr(entity, 'title', '')
                            })
                            task["progress"]["current"] += 1
                            save_last_join_task(task_id)
                            return

                        # Try to join
                        entity = await join_group_or_channel(client, link)

                        # Check restriction after join
                        if getattr(entity, 'restricted', False):
                            is_restricted = True
                            reasons = getattr(entity, 'restriction_reason', []) or []
                            reasons_text = [getattr(r, 'text', '') for r in reasons]
                            restriction_reason_str = "; ".join(filter(None, reasons_text)) or "该群组已被屏蔽限制 (restricted)"

                        if is_restricted:
                            with Session(engine) as session:
                                db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link, entity)
                            task["logs"].append(f"账号 {phone} 检测到 {link} 是无效限制群组: {restriction_reason_str}")
                            results.append({
                                "account_id": account_id,
                                "phone": phone,
                                "link": link,
                                "status": "invalid",
                                "error": restriction_reason_str,
                                "group_id": db_group_id,
                                "title": db_group_title or getattr(entity, 'title', '')
                            })
                            task["progress"]["current"] += 1
                            save_last_join_task(task_id)
                            return

                        can_speak = await check_can_speak(client, entity)
                        status_str = "success" if can_speak else "restricted"
                        err_msg = ""
                        if not can_speak:
                            err_msg = "成功加入但无法直接发言（属于频道或被禁言限制）"
                            task["logs"].append(f"账号 {phone} 成功加入 {link}，但检测到无法直接发言。")
                        else:
                            task["logs"].append(f"账号 {phone} 成功加入 {link} 并确认可以直接发言！")

                        with Session(engine) as session:
                            db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link, entity)
                        results.append({
                            "account_id": account_id,
                            "phone": phone,
                            "link": link,
                            "status": status_str,
                            "error": err_msg,
                            "group_id": db_group_id,
                            "title": db_group_title or getattr(entity, 'title', '')
                        })
                        added_this_round += 1

                        if req.move_to_folder:
                            folder_name_clean = ""
                            if req.folder_by_type:
                                try:
                                    company = task.get("company", "rosepay")
                                    folder_name_clean = await determine_group_folder_name(client, entity, link, company)
                                    task["logs"].append(f"根据群组类型自动分类，判定该群归属文件夹: '{folder_name_clean}'")
                                except Exception as de:
                                    task["logs"].append(f"判定群组类型失败，退回默认分类 '中文长': {de}")
                                    folder_name_clean = "中文长"
                            elif req.target_folder_name and req.target_folder_name.strip():
                                folder_name_clean = req.target_folder_name.strip()

                            if folder_name_clean:
                                try:
                                    await add_peer_to_folder(client, entity, folder_name_clean)
                                    task["logs"].append(f"已成功将群组移入文件夹: '{folder_name_clean}'")
                                except Exception as fe:
                                    task["logs"].append(f"移动群组到文件夹 '{folder_name_clean}' 失败: {str(fe)}")

                    except errors.UserAlreadyParticipantError:
                        try:
                            client = await get_client(account_id)
                            entity = await join_group_or_channel_get_entity_only(client, link)

                            is_restricted = getattr(entity, 'restricted', False) if entity else False
                            restriction_reason_str = ""
                            if is_restricted:
                                reasons = getattr(entity, 'restriction_reason', []) or []
                                reasons_text = [getattr(r, 'text', '') for r in reasons]
                                restriction_reason_str = "; ".join(filter(None, reasons_text)) or "该群组已被屏蔽限制 (restricted)"

                            if is_restricted:
                                with Session(engine) as session:
                                    db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link, entity)
                                task["logs"].append(f"账号 {phone} 检测到已加入的 {link} 变为无效限制群组: {restriction_reason_str}")
                                results.append({
                                    "account_id": account_id,
                                    "phone": phone,
                                    "link": link,
                                    "status": "invalid",
                                    "error": restriction_reason_str,
                                    "group_id": db_group_id,
                                    "title": db_group_title or getattr(entity, 'title', '')
                                })
                            else:
                                can_speak = await check_can_speak(client, entity)
                                status_str = "success" if can_speak else "restricted"
                                err_msg = "已在群组中" if can_speak else "已在群组中但无法直接发言"
                                with Session(engine) as session:
                                    db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link, entity)
                                results.append({
                                    "account_id": account_id,
                                    "phone": phone,
                                    "link": link,
                                    "status": status_str,
                                    "error": err_msg,
                                    "group_id": db_group_id,
                                    "title": db_group_title or getattr(entity, 'title', '')
                                })
                                task["logs"].append(f"账号 {phone} 已经在 {link} 中。是否可发言: {can_speak}")

                                # Since we were already a participant, count as success added
                                added_this_round += 1

                                if req.move_to_folder:
                                    folder_name_clean = ""
                                    if req.folder_by_type:
                                        try:
                                            company = task.get("company", "rosepay")
                                            folder_name_clean = await determine_group_folder_name(client, entity, link, company)
                                            task["logs"].append(f"根据群组类型自动分类，判定该群归属文件夹: '{folder_name_clean}'")
                                        except Exception as de:
                                            task["logs"].append(f"判定群组类型失败，退回默认分类 '中文长': {de}")
                                            folder_name_clean = "中文长"
                                    elif req.target_folder_name and req.target_folder_name.strip():
                                        folder_name_clean = req.target_folder_name.strip()

                                    if folder_name_clean:
                                        try:
                                            await add_peer_to_folder(client, entity, folder_name_clean)
                                            task["logs"].append(f"已成功将群组移入文件夹: '{folder_name_clean}'")
                                        except Exception as fe:
                                            task["logs"].append(f"移动群组到文件夹 '{folder_name_clean}' 失败: {str(fe)}")
                        except Exception as ex:
                            if is_banned_or_deactivated_error(ex):
                                await handle_deactivated_or_banned_account(account_id, ex)
                            err_msg = str(ex)
                            err_msg_lower = err_msg.lower()
                            is_invalid = False
                            if "copyright" in err_msg_lower or "unavailable" in err_msg_lower or "forbidden" in err_msg_lower:
                                is_invalid = True
                            if isinstance(ex, (telethon_errors.ChannelPrivateError, telethon_errors.ChatForbiddenError, telethon_errors.ChannelInvalidError)):
                                is_invalid = True

                            with Session(engine) as session:
                                db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link)
                            results.append({
                                "account_id": account_id,
                                "phone": phone,
                                "link": link,
                                "status": "invalid" if is_invalid else "restricted",
                                "error": f"已在群中但获取信息失败: {err_msg}",
                                "group_id": db_group_id,
                                "title": db_group_title
                            })
                    except errors.FloodWaitError as fwe:
                        task["logs"].append(f"账号 {phone} 触发 FloodWait，必须等待 {fwe.seconds} 秒。跳过当前群组。")
                        results.append({
                            "account_id": account_id,
                            "phone": phone,
                            "link": link,
                            "status": "failed",
                            "error": f"触发电报 FloodWait 限制，需等待 {fwe.seconds} 秒"
                        })
                    except Exception as e:
                        if is_banned_or_deactivated_error(e):
                            await handle_deactivated_or_banned_account(account_id, e)
                        err_msg = str(e)
                        err_msg_lower = err_msg.lower()
                        is_invalid = False
                        if "copyright" in err_msg_lower or "unavailable" in err_msg_lower or "forbidden" in err_msg_lower:
                            is_invalid = True
                        if isinstance(e, (telethon_errors.ChannelPrivateError, telethon_errors.ChatForbiddenError, telethon_errors.ChannelInvalidError)):
                            is_invalid = True

                        with Session(engine) as session:
                            db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link)

                        if is_invalid:
                            task["logs"].append(f"账号 {phone} 检测到 {link} 为无效群组: {err_msg}")
                            results.append({
                                "account_id": account_id,
                                "phone": phone,
                                "link": link,
                                "status": "invalid",
                                "error": f"无效群组: {err_msg}",
                                "group_id": db_group_id,
                                "title": db_group_title
                            })
                        else:
                            task["logs"].append(f"账号 {phone} 加入 {link} 失败: {err_msg}")
                            results.append({
                                "account_id": account_id,
                                "phone": phone,
                                "link": link,
                                "status": "failed",
                                "error": err_msg,
                                "group_id": db_group_id,
                                "title": db_group_title
                            })

                try:
                    await asyncio.wait_for(join_link_logic(), timeout=10.0)
                except asyncio.TimeoutError:
                    task["logs"].append(f"⚠️ 警告：账号 {phone} 加入 {link} 超时超过 10 秒，账号可能已被限制/假死！")
                    with Session(engine) as session:
                        db_group_id, db_group_title = find_group_id_by_link_or_entity(session, link)
                    results.append({
                        "account_id": account_id,
                        "phone": phone,
                        "link": link,
                        "status": "timeout",
                        "error": "加群超时已超10秒，账号可能被限制或假死",
                        "group_id": db_group_id,
                        "title": db_group_title
                    })

                task["progress"]["current"] += 1
                save_last_join_task(task_id)

                if idx < len(todo_links) and added_this_round < groups_per_round:
                    delay = base_delay * random.uniform(0.85, 1.15)
                    task["logs"].append(f"账号 {phone} 等待延迟 {delay:.1f} 秒...")
                    slept_links = 0
                    while slept_links < delay and task["status"] == "running":
                        await asyncio.sleep(1)
                        slept_links += 1

            task["logs"].append(f"账号 {phone} 本轮执行完毕，本轮成功加入 {added_this_round} 个群组。")

        # Outer loop to run rounds
        current_round = 1
        while task["status"] == "running":
            # Check if all links processed for all accounts
            all_accounts_done = True
            for acc_id, _ in accounts_info:
                idx = accounts_link_index.get(acc_id, 0)
                todo = accounts_todo_links.get(acc_id, [])
                if idx < len(todo):
                    all_accounts_done = False
                    break

            if all_accounts_done:
                task["logs"].append("所有账号的所有目标链接均已处理完毕！")
                break

            if max_rounds and current_round > max_rounds:
                task["logs"].append(f"已达到设定的执行轮数上限 ({max_rounds} 轮)，任务结束。")
                break

            task["logs"].append(f"--- 启动第 {current_round} 轮加群 ---")

            if mode == "simultaneous":
                await asyncio.gather(*(join_single_account_links_this_round(acc_id, phone) for acc_id, phone in accounts_info))
            else:
                for acc_id, phone in accounts_info:
                    if task["status"] == "stopped":
                        break
                    await join_single_account_links_this_round(acc_id, phone)

            if task["status"] == "stopped":
                break

            # Verify again if we should run next round
            all_accounts_done = True
            for acc_id, _ in accounts_info:
                idx = accounts_link_index.get(acc_id, 0)
                todo = accounts_todo_links.get(acc_id, [])
                if idx < len(todo):
                    all_accounts_done = False
                    break

            if all_accounts_done:
                task["logs"].append("所有链接处理完毕！")
                break

            # Wait between rounds
            if not max_rounds or current_round < max_rounds:
                task["logs"].append(f"第 {current_round} 轮执行完毕。进入轮次休眠间隔，等待 {round_interval_minutes} 分钟开始下一轮...")
                sleep_time_sec = round_interval_minutes * 60
                slept_sec = 0
                while slept_sec < sleep_time_sec and task["status"] == "running":
                    await asyncio.sleep(5)
                    slept_sec += 5

                current_round += 1

        if task["status"] != "stopped":
            task["status"] = "completed"
        task["logs"].append("入群任务执行完毕！")
    except Exception as e:
        task["status"] = "failed"
        task["logs"].append(f"任务执行出错: {str(e)}")
        print(f"Error in join_worker_task: {e}")
        traceback.print_exc()
    finally:
        task["results"] = results
        save_last_join_task(task_id)
        try:
            status_label = {
                "completed": "已完成",
                "failed": "失败",
                "stopped": "已停止",
                "running": "结束处理中",
            }.get(task.get("status"), task.get("status"))
            result_counts: Dict[str, int] = {}
            for item in results:
                status = str(item.get("status") or "unknown")
                result_counts[status] = result_counts.get(status, 0) + 1
            success_count = (
                result_counts.get("joined", 0)
                + result_counts.get("already_joined", 0)
                + result_counts.get("success", 0)
            )
            invalid_groups = []
            for item in results:
                if str(item.get("status") or "") == "invalid":
                    group_id = str(item.get("group_id") or "").strip()
                    if group_id:
                        invalid_groups.append({
                            "id": group_id,
                            "title": item.get("title") or item.get("link") or group_id,
                            "link": item.get("link") or "",
                        })
            dedup_invalid = {}
            for item in invalid_groups:
                dedup_invalid[item["id"]] = item
            invalid_groups = list(dedup_invalid.values())
            account_lines = "\n".join(
                f"• {html.escape(get_account_notify_label(acc_id))}"
                for acc_id in (req.account_ids or [])[:10]
            )
            if len(req.account_ids or []) > 10:
                account_lines += f"\n• ... +{len(req.account_ids or []) - 10}"
            owner_username = task.get("owner_username", "")
            target_mention = get_ops_target_mention(owner_username)
            event = {
                "type": "join",
                "task_id": task_id,
                "owner_username": owner_username,
                "allowed_username": get_user_telegram_contact(owner_username).lstrip("@"),
                "company": task.get("company", ""),
                "status": task.get("status"),
                "account_labels": [get_account_notify_label(acc_id) for acc_id in (req.account_ids or [])],
                "summary": {
                    "target_groups": task.get("precheck", {}).get("target_groups", len(req.links or [])),
                    "dedup_skipped": task.get("precheck", {}).get("dedup_skipped", 0),
                    "todo_total": task.get("precheck", {}).get("todo_total", task.get("progress", {}).get("total", 0)),
                    "account_count": len(req.account_ids or []),
                    "success": success_count,
                    "failed": result_counts.get("failed", 0),
                    "invalid": len(invalid_groups),
                    "timeout": result_counts.get("timeout", 0),
                    "total": len(results),
                },
                "invalid_groups": invalid_groups,
            }
            buttons = [[{"text": "检查日志", "callback_data": "opslog:{event_id}"}]]
            if invalid_groups:
                buttons.append([{"text": f"删除无效群组 ({len(invalid_groups)})", "callback_data": "opsdel_invalid:{event_id}"}])
            send_ops_bot_notification_with_buttons(
                "\n".join([
                    "📦 <b>加群任务完成</b>",
                    f"<b>归属:</b> {html.escape(target_mention)}",
                    html_line("状态", status_label),
                    html_line("账号个数", len(req.account_ids or [])),
                    html_line("目标群组", task.get("precheck", {}).get("target_groups", len(req.links or []))),
                    html_line("排重个数", task.get("precheck", {}).get("dedup_skipped", 0)),
                    html_line("成功/已在群", success_count),
                    html_line("失败", result_counts.get("failed", 0)),
                    html_line("失效群组", len(invalid_groups)),
                    html_line("超时", result_counts.get("timeout", 0)),
                    "",
                    "👇 点击下方按钮查看详细日志。",
                    html_line("时间", ops_event_time()),
                ]),
                event,
                buttons,
            )
        except Exception as exc:
            print(f"[OpsNotify] Failed to send join completion notification: {exc}")
        release_account_task_usage(task_id, req.account_ids, source="join-task-finish")

