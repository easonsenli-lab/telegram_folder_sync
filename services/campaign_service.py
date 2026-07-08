# -*- coding: utf-8 -*-
import asyncio
import datetime
import html
import json
import time
import re
import random
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from telethon import functions, types, errors

from services.shared_state import (
    active_campaign_tasks,
    active_campaign_schedules,
    active_processes,
    find_campaign_process,
    register_account_task_usage,
    release_account_task_usage,
    is_account_busy_with_task,
    set_account_status,
    BEIJING_TZ,
    UTC_TZ,
    campaign_task_uses_account,
    get_beijing_time_str,
    background_tasks
)

from services.client_manager import get_client

# Forward-declare or import helpers that are used inside the extracted block
# Let's import other things from web_server if they are needed, or we can resolve them.
# We will check if there are any undefined names after writing.
from sync_folder_groups import normalize_title
from account_manager import account_config_path

# We will define or import notify labels and other UI formatters:
# These will be imported dynamically or we can define placeholders if needed, 
# but let's import them from web_server on demand or statically:
def get_account_notify_label(account_id: str) -> str:
    import web_server
    return web_server.get_account_notify_label(account_id)

def get_ops_target_mention(username: str) -> str:
    import web_server
    return web_server.get_ops_target_mention(username)

def get_user_telegram_contact(username: str) -> str:
    import web_server
    return web_server.get_user_telegram_contact(username)

def send_ops_bot_notification_with_buttons(text: str, event: dict, buttons: List[List[dict]]) -> None:
    import web_server
    return web_server.send_ops_bot_notification_with_buttons(text, event, buttons)

def ops_event_time() -> str:
    import web_server
    return web_server.ops_event_time()

def html_line(label: str, value: Any) -> str:
    import web_server
    return web_server.html_line(label, value)

def send_ops_bot_notification(text: str, dedup_key: str = "", cooldown_seconds: int = 0) -> None:
    import web_server
    return web_server.send_ops_bot_notification(text, dedup_key, cooldown_seconds)

def is_telegram_transport_rate_error(exc: Exception) -> bool:
    import web_server
    return web_server.is_telegram_transport_rate_error(exc)

def mark_private_listener_cooldown(account_id: str, exc: Exception, context: str = "private-listener") -> None:
    import web_server
    return web_server.mark_private_listener_cooldown(account_id, exc, context)

def save_last_join_task(task_id: str):
    import web_server
    return web_server.save_last_join_task(task_id)

def campaign_now_utc() -> datetime.datetime:
    return datetime.datetime.now(UTC_TZ)

def campaign_now_beijing() -> datetime.datetime:
    return datetime.datetime.now(BEIJING_TZ)

def parse_campaign_scheduled_start(value: str | None) -> tuple[datetime.datetime | None, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(normalized)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%dT%H:%M"):
            try:
                parsed = datetime.datetime.strptime(raw, fmt)
                break
            except Exception:
                parsed = None
        if parsed is None:
            raise HTTPException(status_code=400, detail="定时启动时间格式不正确")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING_TZ)
    scheduled_bj = parsed.astimezone(BEIJING_TZ)
    if scheduled_bj <= campaign_now_beijing():
        raise HTTPException(status_code=400, detail="定时启动时间必须晚于当前北京时间")
    return scheduled_bj.astimezone(UTC_TZ), scheduled_bj.strftime("%Y-%m-%d %H:%M:%S")

def campaign_task_config(task_record) -> dict:
    try:
        payload = json.loads(getattr(task_record, "task_config_json", "") or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}

def campaign_task_schedule_utc(task_record) -> datetime.datetime | None:
    payload = campaign_task_config(task_record)
    raw = str(payload.get("scheduled_start_at_utc") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC_TZ)
        return parsed.astimezone(UTC_TZ)
    except Exception:
        return None

def campaign_duration_text(total_seconds: float) -> str:
    seconds = max(0, int(total_seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if not parts:
        parts.append(f"{seconds}秒")
    return "".join(parts)

def parse_campaign_account_ids(task_record) -> List[str]:
    """Return all accounts bound to a campaign task, preserving legacy tasks."""
    raw = getattr(task_record, "account_ids_json", "") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            ids = [str(x).strip() for x in parsed if str(x).strip()]
            if ids:
                return ids
        except Exception:
            pass
    return [str(task_record.account_id)]

def parse_campaign_phones(task_record) -> Dict[str, str]:
    raw = getattr(task_record, "phones_json", "") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            pass
    return {str(task_record.account_id): str(task_record.phone)}

def campaign_task_uses_account(task_record, account_id: str) -> bool:
    return account_id in parse_campaign_account_ids(task_record)

def campaign_account_lines(account_ids: List[str], limit: int = 12) -> str:
    lines = [
        f"• {html.escape(get_account_notify_label(acc_id))}"
        for acc_id in account_ids[:limit]
    ]
    if len(account_ids) > limit:
        lines.append(f"• ... +{len(account_ids) - limit}")
    return "\n".join(lines) or "未选择账号"

def send_campaign_start_notification(task_id: str, scheduled: bool = False):
    from db import engine, CampaignTaskDb, Session
    try:
        with Session(engine) as session:
            task = session.get(CampaignTaskDb, task_id)
            if not task:
                return
            account_ids = parse_campaign_account_ids(task)
            config = campaign_task_config(task)
            target_groups = []
            try:
                target_groups = json.loads(task.target_groups_json or "[]")
            except Exception:
                target_groups = []
            owner_username = task.owner_username or ""
            target_mention = get_ops_target_mention(owner_username)
            max_cycles_label = "持续运行" if int(task.max_cycles or 0) <= 0 else f"{task.max_cycles} 轮"
            safety_label = "多账号安全随机" if bool(config.get("multi_account_safety_enabled")) else "普通轮询"
            strategy_label = "智能广告语匹配" if bool(config.get("strategy_enabled")) else "手动广告池"
            scheduled_label = config.get("scheduled_start_at_beijing") or ""
            intro = "定时广告任务开始执行" if scheduled else "广告任务开始执行"
            lines = [
                f"{html.escape(target_mention)} {html.escape(intro)}",
                html_line("任务ID", task_id[:8]),
                html_line("启动方式", "北京时间定时启动" if scheduled else "立即启动"),
            ]
            if scheduled_label:
                lines.append(html_line("预约时间", f"{scheduled_label} 北京时间"))
            lines.extend([
                html_line("参与账号", len(account_ids)),
                campaign_account_lines(account_ids),
                html_line("目标群组", len(target_groups)),
                html_line("总轮数", max_cycles_label),
                html_line("每轮间隔", f"{task.round_interval_minutes} 分钟"),
                html_line("群间隔", f"{task.group_interval_seconds} 秒"),
                html_line("执行策略", f"{safety_label} / {strategy_label}"),
                html_line("时间", ops_event_time()),
            ])
            event = {
                "type": "campaign_started",
                "task_id": task_id,
                "owner_username": owner_username,
                "allowed_username": get_user_telegram_contact(owner_username).lstrip("@"),
                "company": task.company or "",
                "status": "running",
                "account_labels": [get_account_notify_label(acc_id) for acc_id in account_ids],
            }
            send_ops_bot_notification_with_buttons(
                "\n".join(lines),
                event,
                [[{"text": "查看任务", "callback_data": "opslog:{event_id}"}]],
            )
    except Exception as exc:
        print(f"[OpsNotify] Failed to send campaign start notification: {exc}")

async def launch_campaign_task(task_id: str, scheduled: bool = False):
    from db import engine, CampaignTaskDb, Session
    from datetime import datetime
    with Session(engine) as session:
        task = session.get(CampaignTaskDb, task_id)
        if not task or task.status == "stopped":
            return
        if task.status not in {"scheduled", "running"}:
            return
        account_ids = parse_campaign_account_ids(task)
        for acc_id in account_ids:
            if is_account_busy_with_task(acc_id):
                task.status = "failed"
                task.error_detail = f"定时任务启动时账号 {acc_id} 正在执行其他任务，已取消启动"
                task.updated_at = get_beijing_time_str()
                session.add(task)
                session.commit()
                return
        task.status = "running"
        task.updated_at = get_beijing_time_str()
        session.add(task)
        session.commit()
        register_account_task_usage(
            "campaign",
            task_id,
            account_ids,
            {"company": task.company, "created_by": task.created_by, "scheduled": scheduled},
        )
    send_campaign_start_notification(task_id, scheduled=scheduled)
    worker = asyncio.create_task(campaign_worker_task(task_id))
    active_campaign_tasks[task_id] = worker

async def scheduled_campaign_runner(task_id: str):
    from db import engine, CampaignTaskDb, Session
    try:
        with Session(engine) as session:
            task = session.get(CampaignTaskDb, task_id)
            if not task or task.status != "scheduled":
                return
            scheduled_utc = campaign_task_schedule_utc(task)
            if not scheduled_utc:
                task.status = "failed"
                task.error_detail = "定时启动时间缺失或格式错误"
                task.updated_at = get_beijing_time_str()
                session.add(task)
                session.commit()
                return
        delay = max(0.0, (scheduled_utc - campaign_now_utc()).total_seconds())
        if delay > 0:
            await asyncio.sleep(delay)
        await launch_campaign_task(task_id, scheduled=True)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[CampaignScheduler] Failed to launch scheduled campaign {task_id}: {exc}")
    finally:
        active_campaign_schedules.pop(task_id, None)

async def campaign_worker_task(task_id: str):
    from db import engine, CampaignTaskDb, CampaignLogDb, Session, select
    import json
    import random
    from datetime import datetime

    with Session(engine) as session:
        task_record = session.get(CampaignTaskDb, task_id)
        if not task_record:
            return
        account_id = task_record.account_id
        account_ids = parse_campaign_account_ids(task_record)
        phones_by_id = parse_campaign_phones(task_record)
        message = task_record.message
        target_groups = json.loads(task_record.target_groups_json)
        max_cycles = task_record.max_cycles
        round_interval = task_record.round_interval_minutes
        group_interval = task_record.group_interval_seconds
        is_safety = task_record.is_safety
        phone = task_record.phone
        task_company = task_record.company
        config_payload = {}
        try:
            config_payload = json.loads(getattr(task_record, "task_config_json", "") or "{}")
            if not isinstance(config_payload, dict):
                config_payload = {}
        except Exception:
            config_payload = {}
        multi_account_safety_enabled = bool(config_payload.get("multi_account_safety_enabled", False))
        strategy_enabled = bool(config_payload.get("strategy_enabled", False))
        safe_group_interval = max(5, int(group_interval or 5))
        account_pool_size = max(1, len(account_ids))
        dynamic_cooldown_seconds = max(3, min(90, int(safe_group_interval * max(1, min(account_pool_size - 1, 4)) * random.uniform(0.65, 1.35))))

        # Parse message pool
        msg_pool = []
        try:
            parsed = json.loads(message)
            if isinstance(parsed, list):
                msg_pool = [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass

        if not msg_pool:
            msg_pool = [message]
        register_account_task_usage(
            "campaign",
            task_id,
            account_ids,
            {"company": task_company, "phone": phone},
        )

    try:
        clients: Dict[str, TelegramClient] = {}
        account_cooldowns: Dict[str, float] = {}
        last_selected_account_id = ""
        consecutive_send_count = 0
        round_robin_index = 0
        account_send_counts: Dict[str, int] = {}
        blocked_group_keys: Dict[str, str] = {}
        account_blocked_groups: Dict[str, Set[str]] = {}

        def campaign_group_key(raw_group: Dict[str, Any]) -> str:
            username = str(raw_group.get("username") or "").lstrip("@").strip().lower()
            if username:
                return f"u:{username}"
            chat_id = str(raw_group.get("chat_id") or "").strip()
            if chat_id and chat_id != "0":
                return f"id:{chat_id}"
            return f"title:{str(raw_group.get('title') or '').strip().lower()}"

        def is_campaign_permission_or_invalid_error(exc: Exception) -> bool:
            if isinstance(exc, (errors.ChatAdminRequiredError, errors.ChatWriteForbiddenError, errors.UserBannedInChannelError)):
                return True
            text = str(exc).lower()
            return any(token in text for token in [
                "forbidden",
                "write forbidden",
                "chat_write_forbidden",
                "user_banned",
                "banned in channel",
                "private",
                "deleted",
                "deactivated",
                "restricted",
                "not enough rights",
                "spam",
                "bot warning",
                "machine warning",
                "自动化",
                "机器",
                "警告",
            ])

        async def get_campaign_client(selected_account_id: str) -> TelegramClient:
            client = clients.get(selected_account_id)
            if client and client.is_connected():
                return client
            client = await get_client(selected_account_id)
            if not await client.is_user_authorized():
                raise Exception(f"账号未授权登录，任务无法执行: {phones_by_id.get(selected_account_id, selected_account_id)}")
            clients[selected_account_id] = client
            return client

        async def choose_account_for_send() -> str:
            nonlocal last_selected_account_id, consecutive_send_count, round_robin_index
            if len(account_ids) <= 1:
                selected = account_ids[0]
                consecutive_send_count = consecutive_send_count + 1 if selected == last_selected_account_id else 1
                last_selected_account_id = selected
                return selected

            if not multi_account_safety_enabled:
                selected = account_ids[round_robin_index % len(account_ids)]
                round_robin_index += 1
                consecutive_send_count = consecutive_send_count + 1 if selected == last_selected_account_id else 1
                last_selected_account_id = selected
                return selected

            now_ts = time.time()
            ready_ids = [
                acc_id for acc_id in account_ids
                if account_cooldowns.get(acc_id, 0) <= now_ts
            ]
            if last_selected_account_id and len(ready_ids) > 1:
                ready_ids = [acc_id for acc_id in ready_ids if acc_id != last_selected_account_id]
            if ready_ids:
                weights = []
                for acc_id in ready_ids:
                    sent_count = account_send_counts.get(acc_id, 0)
                    weights.append(1 / (1 + sent_count))
                selected = random.choices(ready_ids, weights=weights, k=1)[0]
                consecutive_send_count = consecutive_send_count + 1 if selected == last_selected_account_id else 1
                last_selected_account_id = selected
                return selected
            # If all accounts are cooling down, do not deadlock the task.
            # Pick the account with the closest release time and least usage.
            selected = min(
                account_ids,
                key=lambda acc_id: (
                    max(0, account_cooldowns.get(acc_id, 0) - now_ts),
                    account_send_counts.get(acc_id, 0),
                    random.random(),
                ),
            )
            wait_seconds = max(0, min(5, int(account_cooldowns.get(selected, 0) - now_ts)))
            if wait_seconds:
                await asyncio.sleep(wait_seconds)
            consecutive_send_count = consecutive_send_count + 1 if selected == last_selected_account_id else 1
            last_selected_account_id = selected
            return selected

        async def build_campaign_candidate_order() -> List[str]:
            if len(account_ids) <= 1 or not multi_account_safety_enabled:
                return [await choose_account_for_send()]

            primary = await choose_account_for_send()
            remaining = [acc_id for acc_id in account_ids if acc_id != primary]
            random.shuffle(remaining)
            remaining.sort(key=lambda acc_id: (account_send_counts.get(acc_id, 0), random.random()))
            return [primary, *remaining]

        async def resolve_campaign_target_for_account(client: TelegramClient, raw_group: Dict[str, Any]) -> Tuple[Any, int, str, bool]:
            group_chat_id = raw_group.get("chat_id") or 0
            group_title = raw_group.get("title") or ""
            username = raw_group.get("username")
            target_entity = None
            joined_now = False

            async def ensure_already_joined(entity: Any):
                from telethon.tl.types import Channel
                if isinstance(entity, Channel):
                    if getattr(entity, "left", False):
                        raise Exception("账号未加入该群组，已跳过未发送")
                    try:
                        await client(functions.channels.GetParticipantRequest(
                            channel=entity,
                            participant="me",
                        ))
                    except Exception as participant_exc:
                        raise Exception(f"无法确认账号已在群内，已跳过未发送: {participant_exc}")

            raw_target = username or group_title
            if raw_target:
                cleaned = str(raw_target).strip()
                if "t.me/" in cleaned:
                    cleaned = cleaned.split("t.me/", 1)[1]
                elif "telegram.me/" in cleaned:
                    cleaned = cleaned.split("telegram.me/", 1)[1]
                cleaned = cleaned.split("?", 1)[0].strip()

                if "joinchat/" in cleaned or cleaned.startswith("+"):
                    invite_hash = cleaned.replace("joinchat/", "").replace("+", "").strip()
                    try:
                        from telethon.tl.functions.messages import CheckChatInviteRequest
                        from telethon.tl.types import ChatInviteAlready
                        invite_info = await client(CheckChatInviteRequest(invite_hash))
                        if isinstance(invite_info, ChatInviteAlready) and invite_info.chat:
                            target_entity = invite_info.chat
                            group_chat_id = target_entity.id
                            group_title = getattr(target_entity, "title", group_title)
                            await ensure_already_joined(target_entity)
                        else:
                            raise Exception("账号未加入该私密群组，已跳过未发送")
                    except Exception as e:
                        raise Exception(f"无法确认账号已加入私密群组: {str(e)}")
                else:
                    pub_username = cleaned.lstrip("@").strip()

                    try:
                        entity = await client.get_entity(pub_username)
                        target_entity = entity
                        group_title = getattr(entity, "title", group_title)
                        group_chat_id = entity.id
                        await ensure_already_joined(entity)
                    except Exception as e:
                        if not group_chat_id:
                            raise Exception(f"解析公开群组失败: {str(e)}")
                        raise Exception(f"无法确认账号已加入公开群组: {str(e)}")

            if not target_entity and group_chat_id:
                try:
                    entity = await client.get_entity(group_chat_id)
                    target_entity = entity
                    await ensure_already_joined(entity)
                except Exception as e:
                    raise Exception(f"无法确认账号已加入目标群组: {str(e)}")

            if not target_entity and not group_chat_id:
                raise Exception("无法解析目标群组用户名或ID")

            return target_entity or group_chat_id, int(group_chat_id or 0), group_title, joined_now

        async def write_campaign_log(
            log_cycle: int,
            log_group_title: str,
            log_group_id: str,
            log_group_username: str | None,
            log_account_id: str | None,
            log_phone: str | None,
            log_status: str,
            log_detail: str,
            ad_ref: str | None = None,
        ):
            with Session(engine) as session:
                new_log = CampaignLogDb(
                    company=task_company,
                    task_id=task_id,
                    timestamp=get_beijing_time_str(),
                    cycle=log_cycle,
                    group_title=log_group_title,
                    group_id=str(log_group_id),
                    group_username=log_group_username,
                    ad_ref=ad_ref,
                    account_id=log_account_id,
                    phone=log_phone,
                    status=log_status,
                    detail=log_detail or "",
                )
                session.add(new_log)
                session.commit()

        def choose_campaign_message_for_group(group: dict, chat_id: Any, title: str, username: str | None) -> tuple[str | None, str, str]:
            current_gtype = ""
            selected = None
            ad_ref = ""
            if strategy_enabled:
                current_gtype = group.get("group_type") or ""
                try:
                    with Session(engine) as temp_session:
                        from db import GroupDb, ScrapedGroupDb
                        db_g = None
                        if chat_id:
                            g_ids = [str(chat_id), f"-{chat_id}", f"-100{chat_id}"]
                            db_g = temp_session.exec(select(GroupDb).where(GroupDb.id.in_(g_ids), GroupDb.company == task_company)).first()
                            if not db_g:
                                db_g = temp_session.exec(select(GroupDb).where(GroupDb.id.in_(g_ids))).first()
                        if not db_g and username:
                            db_g = temp_session.exec(select(GroupDb).where(GroupDb.username == username.lstrip("@").strip(), GroupDb.company == task_company)).first()
                            if not db_g:
                                db_g = temp_session.exec(select(GroupDb).where(GroupDb.username == username.lstrip("@").strip())).first()
                        if db_g:
                            current_gtype = db_g.category

                        db_sg = None
                        if chat_id:
                            g_ids = [str(chat_id), f"-{chat_id}", f"-100{chat_id}"]
                            db_sg = temp_session.exec(select(ScrapedGroupDb).where(ScrapedGroupDb.id.in_(g_ids))).first()
                        if not db_sg and username:
                            db_sg = temp_session.exec(select(ScrapedGroupDb).where(ScrapedGroupDb.username == username.lstrip("@").strip())).first()
                        if not db_sg and title:
                            db_sg = temp_session.exec(select(ScrapedGroupDb).where(ScrapedGroupDb.title == title)).first()
                        if db_sg and db_sg.group_type:
                            current_gtype = db_sg.group_type
                except Exception as gtype_err:
                    print(f"Error resolving group type: {gtype_err}")
                if not current_gtype:
                    current_gtype = "英文短"

                try:
                    with Session(engine) as temp_session:
                        from db import PredefinedAdDb
                        stmt = select(PredefinedAdDb).where(
                            PredefinedAdDb.group_type == current_gtype,
                            PredefinedAdDb.company == task_company
                        )
                        matching_ads = temp_session.exec(stmt).all()
                        if not matching_ads:
                            stmt_admin = select(PredefinedAdDb).where(
                                PredefinedAdDb.group_type == current_gtype,
                                PredefinedAdDb.company == "admin"
                            )
                            matching_ads = temp_session.exec(stmt_admin).all()
                        if matching_ads:
                            ad = random.choice(matching_ads)
                            selected = ad.content
                            ad_ref = f"predefined:{ad.id}"
                except Exception as e:
                    print(f"Error fetching strategy ad: {e}")
            elif msg_pool:
                msg_index = random.randrange(len(msg_pool))
                selected = msg_pool[msg_index]
                ad_ref = f"pool:{msg_index}"
            else:
                selected = "🌹 RosePay 广告投放中"
                ad_ref = "fallback"
            return selected, current_gtype, ad_ref

        async def campaign_drain_private_queues(max_items_per_account: int = 3) -> int:
            drained_total = 0
            for queued_account_id in list(account_ids):
                try:
                    queued_client = clients.get(queued_account_id)
                    if queued_client and queued_client.is_connected():
                        drained_total += await drain_pending_private_sends(
                            queued_account_id,
                            queued_client,
                            max_items=max_items_per_account,
                        )
                except Exception as drain_exc:
                    print(f"[PrivateSendQueue] Campaign drain failed for {queued_account_id}: {drain_exc}")
            return drained_total

        async def campaign_sleep_with_private_queue(total_seconds: float, max_items_per_account: int = 2):
            remaining = max(0.0, float(total_seconds or 0))
            while remaining > 0:
                await campaign_drain_private_queues(max_items_per_account=max_items_per_account)
                step = min(5.0, remaining)
                await asyncio.sleep(step)
                remaining -= step
            await campaign_drain_private_queues(max_items_per_account=max_items_per_account)

        cycle = max(1, int(task_record.current_cycle or 1))
        while True:
            # 1. Update status
            with Session(engine) as session:
                task = session.get(CampaignTaskDb, task_id)
                if not task or task.status == "stopped":
                    break
                task.current_cycle = cycle
                session.add(task)
                session.commit()

            # 2. Iterate through targets in this cycle. Shuffle every round so
            # repeated tasks do not hit groups in the exact same order.
            cycle_groups = list(target_groups)
            random.shuffle(cycle_groups)
            for idx, group in enumerate(cycle_groups):
                await campaign_drain_private_queues(max_items_per_account=2)

                # Check cancellation
                with Session(engine) as session:
                    task = session.get(CampaignTaskDb, task_id)
                    if not task or task.status == "stopped":
                        break

                final_msg = ""
                chat_id = group["chat_id"]
                title = group["title"]
                username = group.get("username")
                selected_msg, current_gtype, selected_ad_ref = choose_campaign_message_for_group(group, chat_id, title, username)

                log_status = "success"
                log_detail = ""
                selected_account_id = ""
                selected_phone = ""
                group_key = campaign_group_key(group)

                if group_key in blocked_group_keys:
                    await write_campaign_log(
                        cycle,
                        title,
                        str(chat_id),
                        username,
                        None,
                        None,
                        "skipped",
                        f"本群上一轮已判定不可发言，本轮跳过。原因：{blocked_group_keys[group_key]}",
                        selected_ad_ref,
                    )
                    continue

                try:
                    candidate_ids = await build_campaign_candidate_order()
                    # Filter out candidate accounts that are blocked from speaking/sending to this specific group
                    candidate_ids = [acc_id for acc_id in candidate_ids if group_key not in account_blocked_groups.get(acc_id, set())]
                    if not candidate_ids:
                        await write_campaign_log(
                            cycle,
                            title,
                            str(chat_id),
                            username,
                            None,
                            None,
                            "skipped",
                            "所有候选账号均已被判定无法在该群发言，直接跳过本群。",
                            selected_ad_ref,
                        )
                        continue

                    skipped_prepare_details: List[str] = []
                    cannot_speak_details: List[str] = []
                    invalid_or_warning_details: List[str] = []
                    last_candidate_error = ""
                    sent_this_group = False

                    for candidate_account_id in candidate_ids:
                        selected_account_id = candidate_account_id
                        selected_phone = phones_by_id.get(selected_account_id, selected_account_id)
                        try:
                            client = await get_campaign_client(selected_account_id)
                            if not client.is_connected():
                                try:
                                    await client.connect()
                                except Exception as conn_err:
                                    if is_banned_or_deactivated_error(conn_err):
                                        await handle_deactivated_or_banned_account(selected_account_id, conn_err)
                                        if selected_account_id in account_ids:
                                            account_ids.remove(selected_account_id)
                                        continue
                                    raise Exception(f"客户端连接已断开，尝试自动重连失败: {conn_err}")
                        except Exception as client_exc:
                            if is_banned_or_deactivated_error(client_exc):
                                await handle_deactivated_or_banned_account(selected_account_id, client_exc)
                                if selected_account_id in account_ids:
                                    account_ids.remove(selected_account_id)
                                continue

                            last_candidate_error = f"{selected_phone} 初始化客户端失败：{client_exc}"
                            if len(candidate_ids) > 1:
                                await write_campaign_log(
                                    cycle,
                                    title,
                                    str(chat_id),
                                    username,
                                    selected_account_id,
                                    selected_phone,
                                    "skipped",
                                    last_candidate_error,
                                    selected_ad_ref,
                                )
                                continue
                            raise Exception(last_candidate_error)

                        try:
                            target_entity, resolved_chat_id, resolved_title, joined_now = await resolve_campaign_target_for_account(client, group)
                            chat_id = resolved_chat_id or chat_id
                            title = resolved_title or title
                        except Exception as account_exc:
                            if is_banned_or_deactivated_error(account_exc):
                                await handle_deactivated_or_banned_account(selected_account_id, account_exc)
                                if selected_account_id in account_ids:
                                    account_ids.remove(selected_account_id)
                                continue
                            last_candidate_error = f"{selected_phone} 检查群组失败：{account_exc}"
                            if is_campaign_permission_or_invalid_error(account_exc):
                                invalid_or_warning_details.append(last_candidate_error)
                                if selected_account_id not in account_blocked_groups:
                                    account_blocked_groups[selected_account_id] = set()
                                account_blocked_groups[selected_account_id].add(group_key)
                            if len(candidate_ids) > 1:
                                await write_campaign_log(
                                    cycle,
                                    title,
                                    str(chat_id),
                                    username,
                                    selected_account_id,
                                    selected_phone,
                                    "skipped",
                                    last_candidate_error,
                                    selected_ad_ref,
                                )
                                continue
                            raise

                        if joined_now:
                            prepare_detail = f"{selected_phone} 未加入该群，已先加入准备，本轮不发送，等待下一轮再判断"
                            skipped_prepare_details.append(prepare_detail)
                            await write_campaign_log(
                                cycle,
                                title,
                                str(chat_id),
                                username,
                                selected_account_id,
                                selected_phone,
                                "skipped",
                                prepare_detail,
                                selected_ad_ref,
                            )
                            if multi_account_safety_enabled:
                                account_cooldowns[selected_account_id] = time.time() + max(10, min(60, safe_group_interval))
                            continue

                        # Bypass active speak permission checking (check_can_speak) to reduce API handshake overhead.
                        # Permissions will be verified reactively during client.send_message.
                        pass

                        if strategy_enabled and not selected_msg:
                            current_gtype = group.get("group_type") or ""
                            try:
                                with Session(engine) as temp_session:
                                    from db import GroupDb, ScrapedGroupDb
                                    db_g = None
                                    if chat_id:
                                        g_ids = [str(chat_id), f"-{chat_id}", f"-100{chat_id}"]
                                        db_g = temp_session.exec(select(GroupDb).where(GroupDb.id.in_(g_ids), GroupDb.company == task_company)).first()
                                        if not db_g:
                                            db_g = temp_session.exec(select(GroupDb).where(GroupDb.id.in_(g_ids))).first()
                                    if not db_g and username:
                                        db_g = temp_session.exec(select(GroupDb).where(GroupDb.username == username.lstrip("@").strip(), GroupDb.company == task_company)).first()
                                        if not db_g:
                                            db_g = temp_session.exec(select(GroupDb).where(GroupDb.username == username.lstrip("@").strip())).first()

                                    if db_g:
                                        current_gtype = db_g.category

                                    db_sg = None
                                    if chat_id:
                                        g_ids = [str(chat_id), f"-{chat_id}", f"-100{chat_id}"]
                                        db_sg = temp_session.exec(select(ScrapedGroupDb).where(ScrapedGroupDb.id.in_(g_ids))).first()
                                    if not db_sg and username:
                                        db_sg = temp_session.exec(select(ScrapedGroupDb).where(ScrapedGroupDb.username == username.lstrip("@").strip())).first()
                                    if not db_sg and title:
                                        db_sg = temp_session.exec(select(ScrapedGroupDb).where(ScrapedGroupDb.title == title)).first()
                                    if db_sg and db_sg.group_type:
                                        current_gtype = db_sg.group_type
                            except Exception as gtype_err:
                                print(f"Error resolving group type: {gtype_err}")
                            if not current_gtype:
                                current_gtype = "英文短"

                            try:
                                with Session(engine) as temp_session:
                                    from db import PredefinedAdDb
                                    stmt = select(PredefinedAdDb).where(
                                        PredefinedAdDb.group_type == current_gtype,
                                        PredefinedAdDb.company == task_company
                                    )
                                    matching_ads = temp_session.exec(stmt).all()
                                    if not matching_ads:
                                        stmt_admin = select(PredefinedAdDb).where(
                                            PredefinedAdDb.group_type == current_gtype,
                                            PredefinedAdDb.company == "admin"
                                        )
                                        matching_ads = temp_session.exec(stmt_admin).all()
                                    if matching_ads:
                                        fallback_ad = random.choice(matching_ads)
                                        selected_msg = fallback_ad.content
                                        selected_ad_ref = f"predefined:{fallback_ad.id}"
                            except Exception as e:
                                print(f"Error fetching strategy ad: {e}")

                        if not selected_msg:
                            if strategy_enabled:
                                strategy_skip_detail = f"智能策略未找到【{current_gtype or '英文短'}】分类广告语，本群本轮跳过。"
                                await write_campaign_log(
                                    cycle,
                                    title,
                                    str(chat_id),
                                    username,
                                    selected_account_id,
                                    selected_phone,
                                    "skipped",
                                    strategy_skip_detail,
                                    selected_ad_ref,
                                )
                                continue
                            if msg_pool:
                                fallback_index = random.randrange(len(msg_pool))
                                selected_msg = msg_pool[fallback_index]
                                selected_ad_ref = f"pool:{fallback_index}"
                            else:
                                selected_msg = "🌹 RosePay 广告投放中"
                                selected_ad_ref = "fallback"

                        final_msg = str(selected_msg or "").strip()
                        if "..." in final_msg or "…" in final_msg:
                            broken_detail = f"{selected_phone} 广告语疑似被截断（包含省略号），已跳过未发送"
                            await write_campaign_log(
                                cycle,
                                title,
                                str(chat_id),
                                username,
                                selected_account_id,
                                selected_phone,
                                "skipped",
                                broken_detail,
                                selected_ad_ref,
                            )
                            continue
                        final_msg_bytes = len(final_msg.encode("utf-8"))
                        if final_msg_bytes > 350:
                            too_long_detail = f"{selected_phone} 广告语超过350 UTF-8字节，已跳过未发送（当前 {final_msg_bytes} 字节）"
                            await write_campaign_log(
                                cycle,
                                title,
                                str(chat_id),
                                username,
                                selected_account_id,
                                selected_phone,
                                "skipped",
                                too_long_detail,
                                selected_ad_ref,
                            )
                            continue

                        target_for_send = target_entity or chat_id

                        try:
                            await client.send_message(target_for_send, final_msg)
                        except (errors.ChatAdminRequiredError, errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as send_perm_exc:
                            no_speak_detail = f"{selected_phone} 发送失败：无发言权限或账号被群限制 ({type(send_perm_exc).__name__})"
                            cannot_speak_details.append(no_speak_detail)
                            
                            # Cache the blocked status for this account/group to avoid subsequent attempts
                            if selected_account_id not in account_blocked_groups:
                                account_blocked_groups[selected_account_id] = set()
                            account_blocked_groups[selected_account_id].add(group_key)
                            
                            await write_campaign_log(
                                cycle,
                                title,
                                str(chat_id),
                                username,
                                selected_account_id,
                                selected_phone,
                                "skipped",
                                no_speak_detail,
                                selected_ad_ref,
                            )
                            continue
                        except Exception as send_exc:
                            if is_banned_or_deactivated_error(send_exc):
                                await handle_deactivated_or_banned_account(selected_account_id, send_exc)
                                if selected_account_id in account_ids:
                                    account_ids.remove(selected_account_id)
                                continue
                            if is_campaign_permission_or_invalid_error(send_exc):
                                warn_detail = f"{selected_phone} 发送失败：群组不可发言/已删除/触发限制警告 ({send_exc})"
                                invalid_or_warning_details.append(warn_detail)
                                
                                # Cache the blocked status for this account/group to avoid subsequent attempts
                                if selected_account_id not in account_blocked_groups:
                                    account_blocked_groups[selected_account_id] = set()
                                account_blocked_groups[selected_account_id].add(group_key)
                                
                                await write_campaign_log(
                                    cycle,
                                    title,
                                    str(chat_id),
                                    username,
                                    selected_account_id,
                                    selected_phone,
                                    "skipped",
                                    warn_detail,
                                    selected_ad_ref,
                                )
                                continue
                            raise
                        account_send_counts[selected_account_id] = account_send_counts.get(selected_account_id, 0) + 1
                        if multi_account_safety_enabled and selected_account_id:
                            dynamic_cooldown_seconds = max(
                                3,
                                min(
                                    90,
                                    int(safe_group_interval * max(1, min(account_pool_size - 1, 4)) * random.uniform(0.65, 1.35)),
                                ),
                            )
                            account_cooldowns[selected_account_id] = time.time() + dynamic_cooldown_seconds
                        log_detail = f"{selected_phone} 消息发送成功"

                        try:
                            await drain_pending_private_sends(selected_account_id, client, max_items=3)
                        except Exception as drain_exc:
                            if is_banned_or_deactivated_error(drain_exc):
                                await handle_deactivated_or_banned_account(selected_account_id, drain_exc)
                                if selected_account_id in account_ids:
                                    account_ids.remove(selected_account_id)
                            else:
                                print(f"[PrivateSendQueue] Drain after campaign send failed for {selected_account_id}: {drain_exc}")

                        with Session(engine) as session:
                            task = session.get(CampaignTaskDb, task_id)
                            if task:
                                task.success_count += 1
                                session.add(task)
                                session.commit()
                        log_status = "success"
                        sent_this_group = True
                        break

                    if not sent_this_group:
                        log_status = "skipped"
                        if cannot_speak_details and len(cannot_speak_details) >= len(candidate_ids):
                            log_detail = "所有候选账号均无该群发言权限，本群后续轮次不再尝试。"
                            blocked_group_keys[group_key] = log_detail
                        elif invalid_or_warning_details and len(invalid_or_warning_details) >= len(candidate_ids):
                            log_detail = "所有候选账号均无法访问/被限制/疑似被机器警告，本群后续轮次不再尝试。"
                            blocked_group_keys[group_key] = log_detail
                        elif len(candidate_ids) == 1 and (cannot_speak_details or invalid_or_warning_details):
                            log_detail = (cannot_speak_details or invalid_or_warning_details)[0] + "；单账号任务后续轮次不再尝试该群。"
                            blocked_group_keys[group_key] = log_detail
                        elif skipped_prepare_details:
                            log_detail = "所有候选账号本轮都未确认可直接发送，已执行入群准备，本群本轮跳过"
                        else:
                            log_detail = last_candidate_error or "没有可用于该群本轮发送的账号，本群本轮跳过"
                except errors.FloodWaitError as exc:
                    log_status = "failed"
                    log_detail = f"触发 Telegram 限流，需要等待 {exc.seconds} 秒"
                    with Session(engine) as session:
                        task = session.get(CampaignTaskDb, task_id)
                        if task:
                            task.fail_count += 1
                            session.add(task)
                            session.commit()
                    # Log failure
                    with Session(engine) as session:
                        new_log = CampaignLogDb(
                            company=task_company,
                            task_id=task_id,
                            timestamp=get_beijing_time_str(),
                            cycle=cycle,
                            group_title=title,
                            group_id=str(chat_id),
                            group_username=username,
                            ad_ref=selected_ad_ref,
                            account_id=selected_account_id,
                            phone=selected_phone,
                            status=log_status,
                            detail=log_detail
                        )
                        session.add(new_log)
                        session.commit()
                    # Cool down only the account that triggered FloodWait.
                    if selected_account_id:
                        account_cooldowns[selected_account_id] = time.time() + int(exc.seconds)
                    await campaign_sleep_with_private_queue(min(int(exc.seconds), max(5, group_interval)), max_items_per_account=2)
                    continue
                except (errors.ChatAdminRequiredError, errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as exc:
                    log_status = "failed"
                    log_detail = f"{selected_phone or '未知账号'} 发送失败：无发言权限 ({type(exc).__name__})"
                    with Session(engine) as session:
                        task = session.get(CampaignTaskDb, task_id)
                        if task:
                            task.fail_count += 1
                            session.add(task)
                            session.commit()
                except Exception as exc:
                    log_status = "failed"
                    log_detail = f"{selected_phone or '未知账号'} 发送失败：{str(exc)}"
                    with Session(engine) as session:
                        task = session.get(CampaignTaskDb, task_id)
                        if task:
                            task.fail_count += 1
                            session.add(task)
                            session.commit()

                # Write sending log to db
                with Session(engine) as session:
                    new_log = CampaignLogDb(
                        company=task_company,
                        task_id=task_id,
                        timestamp=get_beijing_time_str(),
                        cycle=cycle,
                        group_title=title,
                        group_id=str(chat_id),
                        group_username=username,
                        ad_ref=selected_ad_ref,
                        account_id=selected_account_id or None,
                        phone=selected_phone or None,
                        status=log_status,
                        detail=log_detail if log_detail else f"{selected_phone} 消息发送成功"
                    )
                    session.add(new_log)
                    session.commit()

                # Group Delay
                if idx < len(cycle_groups) - 1:
                    delay = group_interval
                    if is_safety:
                        # Safety Blasting: random delay between 5 and group_interval
                        delay = random.randint(5, max(5, group_interval))
                    await campaign_sleep_with_private_queue(delay, max_items_per_account=3)

            # Cycle complete check
            if max_cycles > 0 and cycle >= max_cycles:
                with Session(engine) as session:
                    task = session.get(CampaignTaskDb, task_id)
                    if task and task.status == "running":
                        task.status = "completed"
                        task.updated_at = get_beijing_time_str()
                        session.add(task)
                        session.commit()
                break

            # Round Interval Sleep
            cycle += 1
            # Sleep round_interval minutes
            await campaign_sleep_with_private_queue(round_interval * 60, max_items_per_account=5)

    except asyncio.CancelledError:
        with Session(engine) as session:
            task = session.get(CampaignTaskDb, task_id)
            if task and task.status == "running":
                task.status = "stopped"
                task.error_detail = "任务协程被取消，但未收到停止接口请求；请检查同时间 Telethon/代理 429、服务关闭或事件循环取消日志。"
                task.updated_at = get_beijing_time_str()
                session.add(task)
                session.commit()
                print(f"[Campaign] Worker task {task_id} was cancelled unexpectedly while running.")
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        with Session(engine) as session:
            task = session.get(CampaignTaskDb, task_id)
            if task and task.status == "running":
                task.status = "failed"
                task.error_detail = str(e)
                task.updated_at = get_beijing_time_str()
                session.add(task)
                session.commit()
    finally:
        try:
            with Session(engine) as session:
                task = session.get(CampaignTaskDb, task_id)
                if task:
                    task_account_ids = parse_campaign_account_ids(task)
                    account_lines = "\n".join(
                        f"• {html.escape(get_account_notify_label(acc_id))}"
                        for acc_id in task_account_ids[:10]
                    )
                    if len(task_account_ids) > 10:
                        account_lines += f"\n• ... +{len(task_account_ids) - 10}"
                    status_label = {
                        "completed": "已完成",
                        "failed": "失败",
                        "stopped": "已停止",
                        "running": "结束处理中",
                    }.get(task.status, task.status)
                    logs = session.exec(
                        select(CampaignLogDb).where(CampaignLogDb.task_id == task_id)
                    ).all()
                    cycle_stats: Dict[int, Dict[str, int]] = {}
                    for log in logs:
                        cycle = int(getattr(log, "cycle", 0) or 0)
                        bucket = cycle_stats.setdefault(cycle, {"total": 0, "success": 0, "failed": 0})
                        bucket["total"] += 1
                        if getattr(log, "status", "") == "success":
                            bucket["success"] += 1
                        elif getattr(log, "status", "") == "failed":
                            bucket["failed"] += 1
                    total_rounds = len(cycle_stats) or int(task.current_cycle or 0) or 1
                    total_logs = sum(item["total"] for item in cycle_stats.values()) or len(logs)
                    avg_success_rate = (
                        sum((item["success"] / item["total"]) for item in cycle_stats.values() if item["total"]) / max(1, len(cycle_stats)) * 100
                    ) if cycle_stats else 0
                    avg_failed_rate = (
                        sum((item["failed"] / item["total"]) for item in cycle_stats.values() if item["total"]) / max(1, len(cycle_stats)) * 100
                    ) if cycle_stats else 0
                    owner_username = task.owner_username or ""
                    target_mention = get_ops_target_mention(owner_username)
                    event = {
                        "type": "campaign",
                        "task_id": task_id,
                        "owner_username": owner_username,
                        "allowed_username": get_user_telegram_contact(owner_username).lstrip("@"),
                        "company": task.company or "",
                        "status": task.status,
                        "account_labels": [get_account_notify_label(acc_id) for acc_id in task_account_ids],
                        "summary": {
                            "rounds": total_rounds,
                            "groups": len(json.loads(task.target_groups_json or "[]")),
                            "log_rows": total_logs,
                            "success": task.success_count,
                            "failed": task.fail_count,
                            "avg_success_rate": round(avg_success_rate, 2),
                            "avg_failed_rate": round(avg_failed_rate, 2),
                        },
                    }
                    send_ops_bot_notification_with_buttons(
                        "\n".join([
                            f"{html.escape(target_mention)} 后台执行广告轰炸完毕",
                            html_line("状态", status_label),
                            html_line("轰炸轮数", total_rounds),
                            html_line("目标群数", len(json.loads(task.target_groups_json or "[]"))),
                            html_line("成功", task.success_count),
                            html_line("失败", task.fail_count),
                            html_line("每轮平均成功率", f"{avg_success_rate:.1f}%"),
                            "请点击下方按钮查看详细日志。",
                            html_line("时间", ops_event_time()),
                        ]),
                        event,
                        [[{"text": "检查日志", "callback_data": "opslog:{event_id}"}]],
                    )
        except Exception as exc:
            print(f"[OpsNotify] Failed to send campaign completion notification: {exc}")
        try:
            release_account_task_usage(task_id, account_ids, source="campaign-task-finish")
        except Exception as exc:
            print(f"Failed to release campaign task usage {task_id}: {exc}")
        active_campaign_tasks.pop(task_id, None)


async def check_can_speak(client, entity) -> bool:
    try:
        from telethon.tl import types
        if isinstance(entity, types.User):
            return True
        if isinstance(entity, types.Channel):
            if entity.broadcast:
                try:
                    participant = await client(functions.channels.GetParticipantRequest(
                        channel=entity,
                        participant='me'
                    ))
                    if isinstance(participant.participant, (types.ChannelParticipantAdmin, types.ChannelParticipantCreator)):
                        return True
                except Exception:
                    pass
                return False
        try:
            participant_info = await client(functions.channels.GetParticipantRequest(
                channel=entity,
                participant='me'
            ))
            part = participant_info.participant
            if isinstance(part, (types.ChannelParticipantCreator, types.ChannelParticipantAdmin)):
                return True
            if isinstance(part, types.ChannelParticipantBanned):
                if part.banned_rights.send_messages:
                    return False
        except Exception:
            return False
        try:
            full_chat = await client(functions.channels.GetFullChannelRequest(entity))
            default_rights = full_chat.chats[0].default_banned_rights
            if default_rights and default_rights.send_messages:
                return False
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"Error checking speaking permissions: {e}")
        return False


