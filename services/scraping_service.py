import os
import re
import sys
import json
import time
import asyncio
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
from typing import Any
from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import HTTPException, BackgroundTasks, Depends
from sqlmodel import Session, select

from db import engine, AccountDb, GroupDb
from telethon import types, functions, errors

# Import our client and DB layers
from services.shared_state import (
    active_scraper_tasks, active_clients, client_locks,
    register_account_task_usage, filter_executable_accounts_for_task,
    release_account_task_usage
)
from services.client_manager import get_client, account_operation_guard
from typing import Any
from services.maintenance_service import load_expansion_config, get_company_expansion_task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"


def calculate_group_library_scores(member_count: int = 0, group_type: str = "group", has_username: bool = False, is_valid: bool = True) -> dict:
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


def apply_group_library_scores(group: Any, is_valid: bool = True) -> dict:
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


def format_sse(event: str, data: dict) -> str:
    import json
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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

async def get_read_only_probe_client(allowed_account_ids: set, logs: list) -> tuple[Any, str | None]:
    """
    优先遍历并返回被 SpamBot 限制 (restricted / 50分) 但 session 正常连接的账号 client 作为只读探测号。
    如果都没有，再降级选择健康的大号。
    """
    from services.shared_state import active_clients, spambot_cache
    from services.client_manager import get_client
    import random
    
    # 优先第一步：找当前 active_clients 里被限流且在线的探测账号
    restricted_active = []
    for account_id, c in list(active_clients.items()):
        if account_id in allowed_account_ids:
            try:
                if c.is_connected() and await c.is_user_authorized():
                    cached = spambot_cache.get(account_id) or {}
                    if cached.get("status") == "restricted":
                        restricted_active.append((c, account_id))
            except Exception:
                continue
    if restricted_active:
        c, account_id = random.choice(restricted_active)
        logs.append(f"🔌 [探测器选择] 成功命中并锁定在线的受限探测大号: {account_id} (SpamBot restricted，50分账号)")
        return c, account_id

    # 优先第二步：从所有离线账号里连接并寻找是否有被限流的探测账号
    from account_manager import list_accounts
    accounts = list_accounts()
    restricted_offline = []
    for path in accounts:
        account_id = path.stem
        if account_id not in allowed_account_ids:
            continue
        cached = spambot_cache.get(account_id) or {}
        if cached.get("status") == "restricted":
            restricted_offline.append(account_id)
            
    if restricted_offline:
        random.shuffle(restricted_offline)
        for account_id in restricted_offline:
            try:
                c = await get_client(account_id)
                if c.is_connected() and await c.is_user_authorized():
                    logs.append(f"🔌 [探测器选择] 成功连接并拉起离线受限探测大号: {account_id}")
                    return c, account_id
            except Exception:
                continue

    # 降级第三步：普通健康大号 (在已在线大号里挑)
    normal_active = []
    for account_id, c in list(active_clients.items()):
        if account_id in allowed_account_ids:
            try:
                if c.is_connected() and await c.is_user_authorized():
                    normal_active.append((c, account_id))
            except Exception:
                continue
    if normal_active:
        c, account_id = random.choice(normal_active)
        logs.append(f"🔌 [探测器选择] 降级使用在线的普通大号: {account_id}")
        return c, account_id

    # 降级第四步：离线普通大号
    for path in accounts:
        account_id = path.stem
        if account_id not in allowed_account_ids:
            continue
        try:
            c = await get_client(account_id)
            if c.is_connected() and await c.is_user_authorized():
                logs.append(f"🔌 [探测器选择] 降级连接使用普通离线大号: {account_id}")
                return c, account_id
        except Exception:
            continue

    return None, None


async def sync_groups_status(user: dict):
    """
    Iterates through all groups in the database and updates their status
    (title, username, memberCount, enabled) using an active Telegram client.
    """
    from db import engine, GroupDb, AccountDb, Session, select
    from web_server import load_groups
    import asyncio
    import random
    logs = []
    logs.append("开始从 Telegram 更新群组状态与成员数。")

    # 0. 重置 group_categories 表，确保系统内置分类为这四个新分类
    try:
        from sqlmodel import text
        with Session(engine) as session:
            session.exec(text("DELETE FROM group_categories"))
            session.exec(text("INSERT INTO group_categories (name, company) VALUES ('中文长', 'rosepay')"))
            session.exec(text("INSERT INTO group_categories (name, company) VALUES ('中文短', 'rosepay')"))
            session.exec(text("INSERT INTO group_categories (name, company) VALUES ('英文长', 'rosepay')"))
            session.exec(text("INSERT INTO group_categories (name, company) VALUES ('英文短', 'rosepay')"))
            session.commit()
            logs.append("已重置系统群组分类为：'中文长', '中文短', '英文长', '英文短'。")
    except Exception as reset_err:
        print(f"Failed to reset group categories: {reset_err}")
        logs.append(f"重置系统内置分类失败 (将继续同步): {reset_err}")

    # Get all account IDs of this user's company
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user)
        allowed_account_ids = {a.id for a in filter_executable_accounts_for_task(session.exec(stmt).all())}
        account_names = {a.id: (a.account_name or a.id) for a in session.exec(stmt).all()}

    # 1. 优先使用 restricted 50分受限大号作为只读探测 Client
    client, selected_account_id = await get_read_only_probe_client(allowed_account_ids, logs)

    if not client:
        raise HTTPException(
            status_code=400,
            detail="检测到未登录任何电报账号。请先到“账号登录”页面成功登录一个账号后重试。"
        )
    logs.append(f"执行账号：{account_names.get(selected_account_id or '', selected_account_id or '未知账号')}，开始建立群组缓存。")

    # 2. Load all groups for the company from DB
    with Session(engine) as session:
        if user["username"] in ("eason", "admin") or user["company"] == "admin":
            groups = session.exec(select(GroupDb)).all()
        else:
            groups = session.exec(select(GroupDb).where(GroupDb.company == user["company"])).all()

    if not groups:
        return {"status": "success", "message": "群组列表为空，无需同步", "groups": [], "logs": logs}

    # 3. Fetch all dialogs to build a local entity cache (fast lookups)
    entities_map = {}
    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            entities_map[str(entity.id)] = entity
            if getattr(entity, "username", None):
                entities_map[entity.username.lower()] = entity
        logs.append(f"执行账号缓存建立完成：读取到 {len(entities_map)} 个可匹配实体。")
    except Exception as e:
        print(f"Failed to fetch dialogs for cache: {e}")
        logs.append(f"执行账号建立实体缓存失败：{e}，后续将逐个解析。")

    updated_count = 0
    disabled_count = 0
    invalid_groups = []
    total_groups = len(groups)

    # We will update groups one by one
    with Session(engine) as session:
        for index, group in enumerate(groups, start=1):
            entity = None
            is_valid = True
            original_title = group.title
            logs.append(f"[{index}/{total_groups}] 开始检测群组：{group.title or group.id}，执行账号：{account_names.get(selected_account_id or '', selected_account_id or '未知账号')}。")

            # Check if this is a private invite link group
            if group.id and group.id.startswith("invite_"):
                invite_hash = group.id.replace("invite_", "")
                try:
                    invite = await client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
                    if isinstance(invite, types.ChatInviteAlready):
                        entity = invite.chat
                    else:
                        # ChatInvite - valid but not joined yet
                        group.title = invite.title
                        group.memberCount = invite.participants_count
                        group.type = "channel" if invite.broadcast else "group"
                        scores = apply_group_library_scores(group, is_valid=True)
                        session.add(group)
                        updated_count += 1
                        logs.append(f"[{index}/{total_groups}] 私密邀请群有效：{group.title}，成员数 {group.memberCount or 0}，基础评分 {scores['quality_score']}。")
                        continue
                except Exception as invite_err:
                    print(f"Check invite link failed for {group.id}: {invite_err}")
                    logs.append(f"[{index}/{total_groups}] 私密邀请群检测失败：{group.title or group.id}，原因：{invite_err}。")
                    is_valid = False

            # Try to find in cache first
            if is_valid and not entity:
                entity = entities_map.get(group.id)
                if not entity and group.username:
                    entity = entities_map.get(group.username.lower())

            # If not in cache, try to resolve via API
            should_skip_due_to_network = False
            if is_valid and not entity:
                try:
                    if group.username:
                        entity = await client.get_entity(group.username)
                    else:
                        # Try to resolve by ID
                        clean_id = None
                        try:
                            clean_id = int(group.id)
                        except ValueError:
                            pass

                        if clean_id is not None:
                            try:
                                # Try channel/supergroup peer first, then chat peer
                                if group.type in ("channel", "supergroup"):
                                    entity = await client.get_entity(types.PeerChannel(clean_id))
                                else:
                                    entity = await client.get_entity(types.PeerChat(clean_id))
                            except Exception:
                                # Fallback to direct integer if peer types fail
                                try:
                                    entity = await client.get_entity(clean_id)
                                except Exception:
                                    entity = None
                        else:
                            # Fallback to resolving group.id directly
                            try:
                                entity = await client.get_entity(group.id)
                            except Exception:
                                entity = None
                except (errors.UsernameNotOccupiedError, errors.ChannelPrivateError, ValueError) as get_err:
                    print(f"Could not resolve group {group.id} ({group.title}): {get_err}")
                    logs.append(f"[{index}/{total_groups}] 解析群组失败（确定已失效或私密）：{group.title or group.id}，原因：{get_err}。")
                    is_valid = False
                except Exception as net_err:
                    # 关键修复：网络超时、FloodWait、协议抖动等，保留原数据，绝对不删除！
                    print(f"Temporary network/flood issue resolving group {group.id}: {net_err}")
                    logs.append(f"[{index}/{total_groups}] [警告] 临时解析群组失败（保留原数据，跳过本次更新）：{group.title or group.id}，原因：{net_err}。")
                    should_skip_due_to_network = True

            if should_skip_due_to_network:
                # 临时网络故障，直接跳过对当前群组的后续失效判定与删除流程
                continue

            if is_valid and entity:
                # We found the entity! Update properties
                try:
                    group.title = getattr(entity, "title", group.title) or group.title
                    group.username = getattr(entity, "username", group.username) or ""
                    group.type = "channel" if getattr(entity, "broadcast", False) else "group"
                    if getattr(entity, "megagroup", False):
                        group.type = "supergroup"
                    participants_count = getattr(entity, "participants_count", None)
                    if participants_count is not None:
                        group.memberCount = participants_count

                    # === 核心增加：跑消息分析，将广告分类划归为 "中文长", "中文短", "英文长", "英文短" ===
                    try:
                        import re
                        input_peer = await client.get_input_entity(entity)
                        msgs = await client.get_messages(input_peer, limit=20)

                        # 1. 判定字数限制
                        msg_lengths = [len(m.message) for m in msgs if m.message]
                        is_short_ad = False
                        if msg_lengths:
                            max_len = max(msg_lengths)
                            if max_len < 200:
                                is_short_ad = True

                        # 2. 判定语言 (中英文)，综合考虑群名和活跃发言
                        has_chinese_name = False
                        g_title = getattr(entity, "title", "") or ""
                        if g_title:
                            has_chinese_name = bool(re.search(r"[\u4e00-\u9fa5]", g_title)) or "🇨🇳" in g_title

                        text_messages = [m.message for m in msgs if m.message]
                        has_messages = len(text_messages) > 0
                        combined_text = "".join(text_messages)
                        has_chinese_messages = bool(re.search(r"[\u4e00-\u9fa5]", combined_text))

                        is_chinese = False
                        if has_messages:
                            if has_chinese_messages:
                                is_chinese = True
                        else:
                            if has_chinese_name:
                                is_chinese = True

                        # 3. 决定新的 category
                        if is_chinese:
                            if is_short_ad:
                                new_cat = "中文短"
                            else:
                                new_cat = "中文长"
                        else:
                            if is_short_ad:
                                new_cat = "英文短"
                            else:
                                new_cat = "英文长"

                        group.category = new_cat
                        logs.append(f"[{index}/{total_groups}] 群组分类重构：'{group.title}' -> 判定为 '{new_cat}' (字数: {'短' if is_short_ad else '长'}, 语言: {'中文' if is_chinese else '英文'})")
                    except Exception as cat_err:
                        # 优雅退化
                        g_title = getattr(entity, "title", "") or ""
                        has_chinese_name = bool(re.search(r"[\u4e00-\u9fa5]", g_title)) or "🇨🇳" in g_title
                        new_cat = "中文长" if has_chinese_name else "英文长"
                        group.category = new_cat
                        logs.append(f"[{index}/{total_groups}] 拉取消息判定失败，退回名字判定：'{group.title}' -> 判定为 '{new_cat}'，原因：{cat_err}")

                    # 3.5 提取详细群规与发言字数天花板
                    try:
                        from bot_rules_auditor import audit_group_bot_rules
                        rules_summary_json, rules_raw_logs = await audit_group_bot_rules(client, entity.id, group.title, group.username)
                        group.bot_rules_summary = rules_summary_json
                        group.bot_rules_raw_logs = rules_raw_logs
                    except Exception as rule_err:
                        print(f"[Sync Back] 提取群规则出错: {rule_err}")

                    scores = apply_group_library_scores(group, is_valid=True)
                    session.add(group)
                    updated_count += 1
                    logs.append(f"[{index}/{total_groups}] 检测成功并重分类：{original_title} -> {group.title}，用户名 @{group.username or '-'}，类型 {group.type}，成员数 {group.memberCount or 0}，基础评分 {scores['quality_score']}。")
                except Exception as update_err:
                    print(f"Error updating properties for {group.id}: {update_err}")
                    logs.append(f"[{index}/{total_groups}] 更新群组属性失败：{group.title or group.id}，原因：{update_err}。")
                    is_valid = False
            elif not entity and (not group.id or not group.id.startswith("invite_")):
                is_valid = False

            if not is_valid:
                # Entity not found and cannot be resolved -> Directly delete from DB (遇到失效群组直接删掉)
                invalid_groups.append({
                    "id": group.id,
                    "title": group.title,
                    "username": group.username
                })
                session.delete(group)
                disabled_count += 1
                logs.append(f"[{index}/{total_groups}] 检测到群组已失效，已从群组库中物理删除：{group.title or group.id}。")

            if index < total_groups:
                wait_seconds = random.randint(0, 1)
                logs.append(f"[{index}/{total_groups}] 等待 {wait_seconds} 秒后继续检测下一个群组。")
                if wait_seconds:
                    await asyncio.sleep(wait_seconds)

        session.commit()

    logs.append(f"状态同步结束：检测 {total_groups} 个群组，更新 {updated_count} 个，本次禁用 {disabled_count} 个，失效 {len(invalid_groups)} 个。")
    return {
        "status": "success",
        "updated_count": updated_count,
        "disabled_count": disabled_count,
        "invalid_groups": invalid_groups,
        "logs": logs,
        "groups": load_groups(user["company"])
    }


async def analyze_group_category_with_ai(title: str, description: str, recent_msgs: list, user_permissions_str: str) -> dict:
    """
    使用系统配置中的 DeepSeek 或 Gemini API，对群组的语言、长短、活跃度、有效性及风控程度进行智能分类和诊断评估。
    结合了最近 10 条消息的时间跨度和发送间隔作为物理指标。
    """
    import requests
    import json
    import re
    from datetime import datetime, timezone

    # 动态获取系统中的 API 密钥
    deepseek_api_key = get_deepseek_api_key()
    gemini_api_key = get_gemini_api_key()

    # 提取纯文本列表
    messages_text = [m.text for m in recent_msgs if m.text]

    # 计算消息时间差与活跃指标
    time_metrics_str = "【近期消息时间分析】: 暂无消息时间指标"
    avg_interval_mins = 9999.0
    latest_age_hours = 9999.0

    if len(recent_msgs) >= 2:
        first_date = recent_msgs[0].date
        last_date = recent_msgs[-1].date

        total_span_secs = (first_date - last_date).total_seconds()
        avg_interval_mins = (total_span_secs / (len(recent_msgs) - 1)) / 60.0

        now_utc = datetime.now(timezone.utc)
        latest_age_hours = (now_utc - first_date).total_seconds() / 3600.0

        time_metrics_str = f"【近期消息时间分析】:\n"
        time_metrics_str += f"- 最新一条消息发送时间: {first_date.strftime('%Y-%m-%d %H:%M:%S')} UTC (距今约 {latest_age_hours:.2f} 小时)\n"
        time_metrics_str += f"- 最近 {len(recent_msgs)} 条消息时间总跨度: {total_span_secs/3600.0:.2f} 小时\n"
        time_metrics_str += f"- 消息平均发送间隔: {avg_interval_mins:.2f} 分钟/条"
    elif len(recent_msgs) == 1:
        first_date = recent_msgs[0].date
        now_utc = datetime.now(timezone.utc)
        latest_age_hours = (now_utc - first_date).total_seconds() / 3600.0
        time_metrics_str = f"【近期消息时间分析】:\n- 仅有 1 条消息，发送时间: {first_date.strftime('%Y-%m-%d %H:%M:%S')} UTC (距今约 {latest_age_hours:.2f} 小时)"

    # 格式化消息样本
    formatted_msgs = []
    for idx, msg in enumerate(messages_text, 1):
        clean_msg = str(msg).replace("\n", " ").strip()[:100]
        formatted_msgs.append(f"{idx}. {clean_msg}")
    messages_str = "\n".join(formatted_msgs) if formatted_msgs else "(暂无近期文字消息)"

    prompt = f"""
你是一个专业的电报群发拓客与风控分析 AI。请根据以下电报群组的元数据、近期消息、发言权限及物理时间分析，进行全方位智能判定。

群组基本信息：
- 标题: {title}
- 描述/简介: {description}
- 当前账号在群内的发言权限: {user_permissions_str}

消息样本物理时间指标：
{time_metrics_str}

最新 10 条消息样本：
{messages_str}

【判定规则（极为重要，请严格遵守）】
1. 语言与类型判定 (category)：
   - 必须是以下四种分类之一：["中文长", "中文短", "英文长", "英文短"]。
   - 语言标准：如果群内大部分消息是中文，则为中文；如果是英文、印地语、或者其他拼音文字，则为英文。
   - 长短标准：
     - 若群员主要发布排版工整、大段文字、多段业务详情/通道介绍的复杂文案（字数多，超过 150 字符），判定为 "长"。
     - 若群员多发布零散交流、极简短语、单句需求（如 "need yes bank", "来卡", "15s"），判定为 "短"。
     - 如果群内几乎没有消息或以简短消息为主，优先归为 "短"。
2. 活跃度判定 (is_active)：
   - 必须参考“消息样本物理时间指标”：
     - 如果最新消息距今小于 24 小时，且最近 10 条消息的平均发送间隔在数小时内，判定为 true（活跃群）。
     - 如果最新消息距今超过 48 小时，或者 10 条消息的时间跨度跨越了数天甚至数周，判定为 false（死群/不活跃）。
3. 有效性判定 (is_valid)：
   - 若是活跃的跑分群、卡商群、OTC承兑群、博彩推广群，即为 true（对我们营销有价值）；若全是无价值乱码、死群、完全无互动的死号灌水，为 false。
4. 易封禁风控判定 (is_highly_moderated)：
   - 若群内有防垃圾 Bot（如 GHClone2Bot, RemoveHyperlinkBot, fangzhangBot）频繁发出警告、删除提示，或者当前账号在群内“已被禁言”，为 true；否则为 false。
5. 理由 (reason)：
   - 用一句简短的中文（35字以内）说明判定依据（必须包含时间间隔及分类原因，如：“英文短群，最新消息1小时前，平均15分钟一条，极活跃”）。

你必须严格且仅返回以下 JSON 格式（不要包含 markdown ``` 代码块包装，直接返回 JSON 对象）：
{{
  "category": "中文长" | "中文短" | "英文长" | "英文短",
  "is_active": true | false,
  "is_valid": true | false,
  "is_highly_moderated": true | false,
  "reason": "判定依据简述"
}}
"""

    # 1. 优先使用 DeepSeek
    if deepseek_api_key:
        try:
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {deepseek_api_key}"
            }
            body = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {
                    "type": "json_object"
                }
            }
            response = requests.post(url, json=body, headers=headers, timeout=15)
            if response.status_code == 200:
                res_json = response.json()
                text = res_json["choices"][0]["message"]["content"].strip()
                return json.loads(text)
        except Exception as e:
            print(f"[AI Sync] DeepSeek analysis failed: {e}")

    # 2. 兜底使用 Gemini
    if gemini_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            response = requests.post(url, json=body, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return json.loads(text)
        except Exception as e:
            print(f"[AI Sync] Gemini analysis failed: {e}")

    # 3. 如果 API Key 均不可用，进行本地高精度正则兜底
    # 统计汉字和英文字符比例
    content_sample = (title + " " + " ".join(messages_text)).strip()
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content_sample))
    english_words = len(re.findall(r'[a-zA-Z]+', content_sample))

    lang = "中文" if chinese_chars * 2 > english_words else "英文"

    # 判定长短：是否有消息大于 120 字符
    has_long = any(len(str(m)) > 120 for m in messages_text)
    length = "长" if has_long else "短"

    is_active = len(messages_text) >= 3
    is_valid = len(messages_text) > 0

    return {
        "category": f"{lang}{length}",
        "is_active": is_active,
        "is_valid": is_valid,
        "is_highly_moderated": False,
        "reason": "本地正则兜底 analysis"
    }


async def stream_groups_sync(user: dict):
    """Foreground group sync with realtime SSE logs for the UI execution modal."""

    async def event_generator():
        from db import engine, GroupDb, AccountDb, Session, select
        from sync_folder_groups import collect_records
        import asyncio
        import random

        sync_data = {
            "status": "success",
            "synced_count": 0,
            "added_count": 0,
            "skipped_count": 0,
            "errors": [],
        }
        status_data = {
            "status": "success",
            "updated_count": 0,
            "disabled_count": 0,
            "invalid_groups": [],
        }

        def log(message: str) -> str:
            return format_sse("log", {"message": message})

        try:
            yield log("已跳过账号聊天文件夹同步，直接对系统后台维护的群组执行检测与 AI 分类诊断。")
            yield log("开始从 Telegram 更新群组状态、成员数与基础评分。")

            with Session(engine) as session:
                stmt = query_allowed_accounts(session, user)
                allowed_accounts = filter_executable_accounts_for_task(session.exec(stmt).all())
                allowed_account_ids = {a.id for a in allowed_accounts}
                account_names = {a.id: (a.account_name or a.id) for a in allowed_accounts}

            client = None
            selected_account_id = None
            for account_id, c in list(active_clients.items()):
                if account_id in allowed_account_ids and c.is_connected() and await c.is_user_authorized():
                    client = c
                    selected_account_id = account_id
                    break

            if not client:
                from account_manager import list_accounts
                accounts = list_accounts()
                for path in accounts:
                    account_id = path.stem
                    if account_id not in allowed_account_ids:
                        continue
                    try:
                        c = await get_client(account_id)
                        if c.is_connected() and await c.is_user_authorized():
                            client = c
                            selected_account_id = account_id
                            break
                    except Exception:
                        continue

            if not client:
                yield format_sse("sync_error", {"message": "检测到未登录任何电报账号。请先到“账号登录”页面成功登录一个账号后重试。"})
                return

            selected_account_label = account_names.get(selected_account_id or "", selected_account_id or "未知账号")
            yield log(f"执行账号：{selected_account_label}，开始建立群组缓存。")

            with Session(engine) as session:
                if user["username"] in ("eason", "admin") or user["company"] == "admin":
                    groups = session.exec(select(GroupDb)).all()
                else:
                    groups = session.exec(select(GroupDb).where(GroupDb.company == user["company"])).all()

            if not groups:
                status_data["groups"] = []
                yield log("群组列表为空，无需同步。")
                yield format_sse("done", {"syncData": sync_data, "statusData": status_data, "groups": []})
                return

            entities_map = {}
            try:
                async for dialog in client.iter_dialogs():
                    entity = dialog.entity
                    entities_map[str(entity.id)] = entity
                    if getattr(entity, "username", None):
                        entities_map[entity.username.lower()] = entity
                yield log(f"执行账号缓存建立完成：读取到 {len(entities_map)} 个可匹配实体。")
            except Exception as e:
                yield log(f"执行账号建立实体缓存失败：{e}，后续将逐个解析。")

            total_groups = len(groups)
            with Session(engine) as session:
                for index, group in enumerate(groups, start=1):
                    entity = None
                    is_valid = True
                    original_title = group.title
                    yield log(f"[{index}/{total_groups}] 开始检测群组：{group.title or group.id}，执行账号：{selected_account_label}。")

                    if group.id and group.id.startswith("invite_"):
                        invite_hash = group.id.replace("invite_", "")
                        try:
                            invite = await client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
                            if isinstance(invite, types.ChatInviteAlready):
                                entity = invite.chat
                            else:
                                group.title = invite.title
                                group.memberCount = invite.participants_count
                                group.type = "channel" if invite.broadcast else "group"
                                scores = apply_group_library_scores(group, is_valid=True)
                                session.add(group)
                                status_data["updated_count"] += 1
                                yield log(f"[{index}/{total_groups}] 私密邀请群有效：{group.title}，成员数 {group.memberCount or 0}，基础评分 {scores['quality_score']}。")
                                if index < total_groups:
                                    wait_seconds = random.randint(0, 1)
                                    yield log(f"[{index}/{total_groups}] 等待 {wait_seconds} 秒后继续检测下一个群组。")
                                    if wait_seconds:
                                        await asyncio.sleep(wait_seconds)
                                continue
                        except Exception as invite_err:
                            yield log(f"[{index}/{total_groups}] 私密邀请群检测失败：{group.title or group.id}，原因：{invite_err}。")
                            is_valid = False

                    if is_valid and not entity:
                        entity = entities_map.get(group.id)
                        if not entity and group.username:
                            entity = entities_map.get(group.username.lower())

                    if is_valid and not entity:
                        try:
                            if group.username:
                                entity = await client.get_entity(group.username)
                            else:
                                clean_id = None
                                try:
                                    clean_id = int(group.id)
                                except ValueError:
                                    pass

                                if clean_id is not None:
                                    try:
                                        if group.type in ("channel", "supergroup"):
                                            entity = await client.get_entity(types.PeerChannel(clean_id))
                                        else:
                                            entity = await client.get_entity(types.PeerChat(clean_id))
                                    except Exception:
                                        try:
                                            entity = await client.get_entity(clean_id)
                                        except Exception:
                                            entity = None
                                else:
                                    try:
                                        entity = await client.get_entity(group.id)
                                    except Exception:
                                        entity = None
                        except Exception as get_err:
                            yield log(f"[{index}/{total_groups}] 解析群组失败：{group.title or group.id}，原因：{get_err}。")
                            is_valid = False

                    if is_valid and entity:
                        try:
                            group.title = getattr(entity, "title", group.title) or group.title
                            group.username = getattr(entity, "username", group.username) or ""
                            group.type = "channel" if getattr(entity, "broadcast", False) else "group"
                            if getattr(entity, "megagroup", False):
                                group.type = "supergroup"
                            participants_count = getattr(entity, "participants_count", None)
                            if participants_count is not None:
                                group.memberCount = participants_count
                            # 0. 过滤并忽略个人账号 (User)，防止爬取个人私聊
                            from telethon.tl.types import User
                            if isinstance(entity, User):
                                yield log(f"[{index}/{total_groups}] 忽略个人账号：{original_title} (ID: {group.id} 为个人私聊，非群组/频道)。")
                                group.enabled = False
                                apply_group_library_scores(group, is_valid=False)
                                session.add(group)
                                session.commit()
                                continue

                            # 1. 尝试获取最近 10 条消息作为 AI 分析样本
                            recent_msgs = []
                            try:
                                recent_msgs = await client.get_messages(entity, limit=10)
                            except Exception as msg_err:
                                print(f"[AI Sync] 获取群消息失败: {msg_err}")

                            # 2. 获取当前账号在该群的发言权限状态
                            perms_str = "正常"
                            try:
                                perms = await client.get_permissions(entity, 'me')
                                if perms.has_left:
                                    perms_str = "账号已不在该群内 (未加入/被踢出)"
                                elif not perms.can_send_messages:
                                    perms_str = "账号已被该群禁言"
                            except Exception as perm_err:
                                if "UserNotParticipant" in type(perm_err).__name__:
                                    perms_str = "账号未加入该群 (非成员)"
                                else:
                                    perms_str = f"获取权限异常: {perm_err}"

                            # 3. 调用 AI 智能进行分类诊断与风控评估
                            yield log(f"[{index}/{total_groups}] 正在请 AI 智能评估群组「{original_title}」的历史消息与风控...")
                            ai_res = await analyze_group_category_with_ai(group.title, getattr(entity, "about", "") or "", recent_msgs, perms_str)

                            # 4. 应用 AI 评估结论更新群组属性
                            if ai_res:
                                old_cat = group.category
                                group.category = ai_res.get("category", group.category)

                                # 根据 AI 的有效性判定决定是否启用
                                is_group_valid = bool(ai_res.get("is_valid", True))
                                group.enabled = is_group_valid

                                # 写入 AI 的判定日志到弹窗流中
                                yield log(f"[{index}/{total_groups}] AI 评估 ➔ 类型: {group.category} | 活跃: {ai_res.get('is_active')} | 有效: {group.enabled} | 依据: {ai_res.get('reason')}")
                                if ai_res.get("is_highly_moderated"):
                                    yield log(f"  ⚠️ 警告：该群被检测为高风控群组，可能存在严密风控 Bot 或处于禁言状态！")
                            else:
                                yield log(f"[{index}/{total_groups}] AI 评估失败，使用本地兜底算法。")

                            scores = apply_group_library_scores(group, is_valid=group.enabled)
                            session.add(group)
                            status_data["updated_count"] += 1
                            yield log(f"[{index}/{total_groups}] 检测成功：{original_title} -> {group.title}，用户名 @{group.username or '-'}，类型 {group.type}，成员数 {group.memberCount or 0}，最终分类 【{group.category}】，基础评分 {scores['quality_score']}。")
                        except Exception as update_err:
                            yield log(f"[{index}/{total_groups}] 更新群组属性失败：{group.title or group.id}，原因：{update_err}。")
                            is_valid = False
                    elif not entity and (not group.id or not group.id.startswith("invite_")):
                        is_valid = False

                    if not is_valid:
                        status_data["invalid_groups"].append({
                            "id": group.id,
                            "title": group.title,
                            "username": group.username
                        })
                        if group.enabled:
                            group.enabled = False
                            status_data["disabled_count"] += 1
                        apply_group_library_scores(group, is_valid=False)
                        session.add(group)
                        yield log(f"[{index}/{total_groups}] 检测失败并标记禁用：{group.title or group.id}，评分 0 / 疑似失效。")

                    session.commit()

                    if index < total_groups:
                        wait_seconds = random.randint(0, 1)
                        yield log(f"[{index}/{total_groups}] 等待 {wait_seconds} 秒后继续检测下一个群组。")
                        if wait_seconds:
                            await asyncio.sleep(wait_seconds)

            status_data["groups"] = load_groups(user["company"])
            yield log(f"状态同步结束：检测 {total_groups} 个群组，更新 {status_data['updated_count']} 个，本次禁用 {status_data['disabled_count']} 个，失效 {len(status_data['invalid_groups'])} 个。")
            yield format_sse("done", {
                "syncData": sync_data,
                "statusData": status_data,
                "groups": status_data["groups"],
            })
        except Exception as e:
            yield format_sse("sync_error", {"message": f"同步执行异常：{type(e).__name__}: {e}"})

    return event_generator()


async def classify_group_category_for_import(client, entity, fallback_title: str, fallback_category: Optional[str] = None) -> str:
    from web_server import classify_group_category_from_text
    valid_categories = {"中文长", "中文短", "英文长", "英文短"}
    if fallback_category in valid_categories:
        default_category = fallback_category
    else:
        default_category = classify_group_category_from_text(fallback_title or "", [])
    if not entity:
        return default_category
    try:
        input_peer = await client.get_input_entity(entity)
        msgs = await client.get_messages(input_peer, limit=20)
        return classify_group_category_from_text(
            getattr(entity, "title", fallback_title) or fallback_title or "",
            [getattr(m, "message", "") or "" for m in msgs],
        )
    except Exception:
        return default_category


async def resolve_group(req, user):
    from web_server import (
        normalize_group_identifier,
        map_telegram_error,
        find_group_by_username_or_id,
        classify_group_category_from_text
    )
    # Get all account IDs of this user's company
    from db import engine, AccountDb, Session, select
    with Session(engine) as session:
        stmt = query_allowed_accounts(session, user)
        allowed_account_ids = {a.id for a in filter_executable_accounts_for_task(session.exec(stmt).all())}

    # 1. 收集当前所有可用的在线客户端
    available_clients = []
    for account_id, c in list(active_clients.items()):
        try:
            if account_id in allowed_account_ids and c.is_connected() and await c.is_user_authorized():
                available_clients.append((account_id, c))
        except Exception:
            continue

    if not available_clients:
        from account_manager import list_accounts
        accounts = list_accounts()
        for path in accounts:
            account_id = path.stem
            if account_id not in allowed_account_ids:
                continue
            try:
                c = await get_client(account_id)
                if c.is_connected() and await c.is_user_authorized():
                    available_clients.append((account_id, c))
            except Exception:
                continue

    if not available_clients:
        raise HTTPException(
            status_code=400,
            detail="检测到未登录任何电报账号。请先到“账号登录”页面成功登录一个账号后重试。"
        )

    link = req.link.strip()
    if not link:
        raise HTTPException(status_code=400, detail="群组链接不能为空")

    import re
    invite_hash = None
    private_match = re.search(r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)?([a-zA-Z0-9_\\-]{5,32})', re.sub(r"^https?:/*", "", link, flags=re.IGNORECASE))
    if private_match and ("joinchat/" in link or "+" in link):
        invite_hash = private_match.group(1)

    res_data = None
    last_exception = None
    resolved_ok = False
    active_query_client = None

    # 2. 依次轮询大号进行 8 秒的超时容灾解析
    for account_id, client in available_clients:
        try:
            if invite_hash:
                invite = await asyncio.wait_for(
                    client(functions.messages.CheckChatInviteRequest(hash=invite_hash)),
                    timeout=8.0
                )
                if isinstance(invite, types.ChatInviteAlready):
                    chat = invite.chat
                    chat_type = "channel" if getattr(chat, "broadcast", False) else "group"
                    member_count = getattr(chat, "participants_count", 0) or 0
                    res_data = {
                        "id": str(chat.id),
                        "title": chat.title,
                        "username": getattr(chat, "username", "") or "",
                        "type": chat_type,
                        "memberCount": member_count,
                        "enabled": True,
                        "category": classify_group_category_from_text(chat.title, []),
                        "price": req.price or 0.0
                    }
                else: # ChatInvite
                    chat_type = "channel" if invite.broadcast else "group"
                    res_data = {
                        "id": f"invite_{invite_hash}",
                        "title": invite.title,
                        "username": "",
                        "type": chat_type,
                        "memberCount": invite.participants_count,
                        "enabled": True,
                        "category": classify_group_category_from_text(invite.title, []),
                        "price": req.price or 0.0
                    }
            else:
                # Public username, link, or ID
                identifier = normalize_group_identifier(link)
                if isinstance(identifier, str) and (identifier.isdigit() or (identifier.startswith("-") and identifier[1:].isdigit())):
                    identifier = int(identifier)

                entity = await asyncio.wait_for(
                    client.get_entity(identifier),
                    timeout=8.0
                )
                if isinstance(entity, types.User):
                    raise HTTPException(status_code=400, detail="该链接指向的是个人账户，群组库只允许添加群组或频道。")

                chat_type = "channel" if getattr(entity, "broadcast", False) else "group"

                # Get participant count
                member_count = 0
                try:
                    if isinstance(entity, types.Chat):
                        full_chat = await asyncio.wait_for(
                            client(functions.messages.GetFullChatRequest(chat_id=entity.id)),
                            timeout=6.0
                        )
                    else:
                        full_chat = await asyncio.wait_for(
                            client(functions.channels.GetFullChannelRequest(channel=entity)),
                            timeout=6.0
                        )

                    if hasattr(full_chat, "full_chat") and hasattr(full_chat.full_chat, "participants_count"):
                        member_count = full_chat.full_chat.participants_count
                    elif hasattr(full_chat, "chats") and len(full_chat.chats) > 0:
                        member_count = getattr(full_chat.chats[0], "participants_count", 0) or 0
                except Exception:
                    member_count = getattr(entity, "participants_count", 0) or 0

                res_data = {
                    "id": str(entity.id),
                    "title": getattr(entity, "title", ""),
                    "username": getattr(entity, "username", "") or "",
                    "type": chat_type,
                    "memberCount": member_count,
                    "enabled": True,
                    "category": await classify_group_category_for_import(client, entity, getattr(entity, "title", ""), req.category),
                    "price": req.price or 0.0
                }
            
            resolved_ok = True
            active_query_client = client
            print(f"[解析群组] 使用账号 {account_id} 成功定位并解析群组。")
            break
        except Exception as e:
            last_exception = e
            print(f"[解析群组] 使用账号 {account_id} 解析失败或超时: {e}，尝试下一个账号...")
            continue

    if not resolved_ok:
        detail_msg = "目标链接在电报端响应卡死或失效，已记录并跳过。"
        if last_exception:
            if isinstance(last_exception, asyncio.TimeoutError):
                detail_msg = "校验超时 (15s) - 目标链接在电报端响应卡死，已记录并跳过。"
            else:
                detail_msg = map_telegram_error(last_exception, "无法解析该群组/频道标识符")
        raise HTTPException(status_code=400, detail=detail_msg)


    # 3. Add to database if not already there
    from db import engine, GroupDb, Session, select
    with Session(engine) as session:
        db_group = find_group_by_username_or_id(
            session,
            res_data.get("id"),
            res_data.get("username"),
            user["company"],
        )
        if db_group:
            raise HTTPException(status_code=400, detail=f"群组/频道 '{res_data['title']}' 已在列表中，无需重复添加")

        new_db_group = GroupDb(
            id=str(res_data["id"]),
            company=user["company"],
            title=res_data.get("title", ""),
            username=res_data.get("username", ""),
            type=res_data.get("type", "group"),
            enabled=res_data.get("enabled", True),
            memberCount=res_data.get("memberCount", 0),
            category=res_data.get("category", "中文广告"),
            price=res_data.get("price", 0.0),
            created_by=user["username"],
            updated_by=user["username"]
        )
        # 4. 立即对该群组执行同步规则审计与评分计算，使其导入后立即可用
        if active_query_client:
            try:
                from bot_rules_auditor import audit_group_bot_rules
                rules_summary_json, rules_raw_logs = await audit_group_bot_rules(
                    active_query_client, 
                    str(res_data["id"]), 
                    res_data.get("title", ""), 
                    res_data.get("username", "")
                )
                new_db_group.bot_rules_summary = rules_summary_json
                new_db_group.bot_rules_raw_logs = rules_raw_logs
                
                # 并立即应用群规则计算并更新其质量与活跃评分
                apply_group_library_scores(new_db_group, is_valid=True)
            except Exception as audit_err:
                print(f"[导入自动审计] 自动审计新导入群组失败: {audit_err}")

        session.add(new_db_group)
        session.commit()
    return res_data


def get_company_scraper_task(company: str) -> dict:
    if company not in active_scraper_tasks:
        init_keywords, init_min_members, init_max_pages, init_continuous, init_interval_minutes = load_scraper_config()
        active_scraper_tasks[company] = {
            "status": "idle",  # 'idle', 'running', 'completed', 'failed', 'stopped'
            "progress": {"current": 0, "total": 0},
            "logs": [],
            "error": None,
            "keywords": init_keywords,
            "min_members": init_min_members,
            "max_pages": init_max_pages,
            "continuous": init_continuous,
            "interval_minutes": init_interval_minutes,
            "account_id": None
        }
    return active_scraper_tasks[company]


def load_scraper_config() -> tuple[List[str], int, int, bool, int]:
    default_keywords = []
    default_min_members = 1000
    default_max_pages = 5
    default_continuous = False
    default_interval_minutes = 30
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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


def get_gemini_api_key() -> str:
    config_path = CONFIG_PATH
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("gemini_api_key", "")
        except Exception:
            pass
    return ""


def save_gemini_api_key(key: str):
    config_path = CONFIG_PATH
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["gemini_api_key"] = key
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save gemini_api_key: {e}")


def get_deepseek_api_key() -> str:
    config_path = CONFIG_PATH
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("deepseek_api_key", "")
        except Exception:
            pass
    return ""


def save_deepseek_api_key(key: str):
    config_path = CONFIG_PATH
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["deepseek_api_key"] = key
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save deepseek_api_key: {e}")


async def run_group_scraping_task(
    keywords: List[str],
    min_members: int,
    max_pages: int,
    company: str,
    continuous: bool = False,
    interval_minutes: int = 30,
    auto_join: bool = False,
    auto_join_min_score: int = 70,
    max_rounds: Optional[int] = None,
    groups_per_round: int = 10,
    round_interval_minutes: int = 5,
    owner_username: Optional[str] = None
):
    current_round = 1
    from datetime import datetime
    active_scraper_task = get_company_scraper_task(company)
    scraper_task_id = f"scraper:{company}"
    release_account_task_usage(scraper_task_id, source="scraper-task-reset")
    active_scraper_task["status"] = "running"
    active_scraper_task["progress"] = {"current": 0, "total": 0}
    active_scraper_task["logs"] = []
    active_scraper_task["error"] = None

    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        active_scraper_task["logs"].append(f"[{timestamp}] {msg}")
        print(f"[ScrapeTask] {msg}")

    try:
        gemini_api_key = get_gemini_api_key()
        deepseek_api_key = get_deepseek_api_key()
        if not gemini_api_key and not deepseek_api_key:
            log("错误: 未配置 AI API Key，请先在配置中保存您的 API Key（支持 Gemini 或 DeepSeek）。")
            active_scraper_task["status"] = "failed"
            active_scraper_task["error"] = "未配置 AI API Key"
            return

        while active_scraper_task["status"] == "running":
            log(f"开始搜群任务 [第 {current_round} 轮]。目标保存群组数: {groups_per_round} 个 | 最少成员数: {min_members}")

            added_this_round = 0
            history_skip_count = 0
            member_skip_count = 0
            fetch_fail_count = 0

            # Step 1: Find a healthy, authorized Telegram account under this company
            from db import engine, AccountDb, Session, select, ScrapedGroupDb, GroupDb, GroupCategoryDb

            authorized_account_id = None
            authorized_phone = None
            active_scraper_task["account_id"] = None

            with Session(engine) as session:
                if owner_username:
                    from sqlmodel import or_
                    stmt_acc = select(AccountDb).where(
                        or_(AccountDb.owner_username == owner_username, AccountDb.created_by == owner_username)
                    )
                else:
                    stmt_acc = select(AccountDb).where(AccountDb.company == company)
                accounts = filter_executable_accounts_for_task(session.exec(stmt_acc).all())

            for acc in accounts:
                try:
                    cl = await get_client(acc.id)
                    if await cl.is_user_authorized():
                        authorized_account_id = acc.id
                        authorized_phone = acc.account_name
                        break
                except Exception:
                    pass

            if not authorized_account_id:
                log("错误: 当前公司下没有可用的、已授权在线的电报账号，无法进行群消息获取。请至少登录一个账号！")
                active_scraper_task["status"] = "failed"
                active_scraper_task["error"] = "没有可在线 of 电报账号进行解析"
                return

            active_scraper_task["account_id"] = authorized_account_id
            register_account_task_usage(
                "scraper",
                scraper_task_id,
                [authorized_account_id],
                {"company": company, "owner_username": owner_username},
            )
            log(f"使用账号 [{authorized_phone}] 进行群组消息抓取 and 解析...")
            client = await get_client(authorized_account_id)

            current_page = 0
            max_safety_pages = 30
            exhausted = False

            while added_this_round < groups_per_round and current_page < max_safety_pages:
                if active_scraper_task["status"] != "running":
                    break

                log(f"正在搜寻第 {current_page + 1} 页的潜在公开群组链接 (当前本轮已保存: {added_this_round}/{groups_per_round}) ...")
                from group_scraper import scrape_links_by_keywords_for_page, fetch_group_messages, analyze_group_with_gemini, analyze_group_with_deepseek, calculate_scraped_group_metrics

                links = scrape_links_by_keywords_for_page(keywords, current_page)

                if not links:
                    log(f"第 {current_page + 1} 页未找到任何潜在链接，搜索引擎结果已耗尽。")
                    exhausted = True
                    break

                log(f"第 {current_page + 1} 页搜寻结束，共找到 {len(links)} 个潜在链接。开始进行提取与分析...")

                active_scraper_task["progress"]["total"] = len(links)

                for idx, link in enumerate(links):
                    if active_scraper_task["status"] != "running":
                        break
                    if added_this_round >= groups_per_round:
                        break

                    active_scraper_task["progress"]["current"] = idx + 1

                    # Extract username
                    public_match = re.search(r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)?([a-zA-Z0-9_\+]{5,32})', link)
                    if not public_match:
                        continue

                    username = public_match.group(1)

                    # Deduplication check
                    with Session(engine) as session:
                        existing = session.get(ScrapedGroupDb, username)
                    if existing:
                        log(f"  [排重] 跳过历史已存在重复群组: @{username}")
                        history_skip_count += 1
                        continue

                    # Check if this is a joinchat/private hash
                    if "joinchat/" in link or "+" in link:
                        log(f"  [过滤] 跳过私有加群链接: {link}")
                        continue

                    log(f"  正在免加群提取群组信息: @{username} ...")
                    res = await fetch_group_messages(client, username)
                    if not res.get("success"):
                        err_msg = res.get("error", "")
                        log(f"  获取群 @{username} 失败: {err_msg}")
                        if "FloodWait" in err_msg or "wait of" in err_msg:
                            log(f"⚠️ [限制警告] 检测到当前电报账号已触发限制 (FloodWait): {err_msg}。为防止封号，已自动暂停搜群任务，请稍后再试。")
                            active_scraper_task["status"] = "paused"
                            active_scraper_task["error"] = f"触发电报限制: {err_msg}"
                            break
                        fetch_fail_count += 1
                        await asyncio.sleep(4)
                        continue

                    title = res["title"]
                    member_count = res["member_count"]
                    messages = res["messages"]

                    log(f"  获取成功! 标题: '{title}' | 成员数: {member_count}。")

                    if member_count < min_members:
                        log(f"  群成员数 ({member_count}) 低于最低成员数限制 ({min_members})。跳过。")
                        member_skip_count += 1
                        await asyncio.sleep(4)
                        continue

                    # Perform AI analysis
                    analysis = None
                    if deepseek_api_key:
                        log("  正在交由 DeepSeek 进行智能属性与业务粘合度评估...")
                        analysis = analyze_group_with_deepseek(deepseek_api_key, title, res.get("description", ""), messages, target_keywords=keywords)
                        if (not analysis or analysis.get("relevance_score") is None) and gemini_api_key:
                            log("  DeepSeek 评估失败或受限，尝试使用 Gemini 进行评估...")
                            analysis = analyze_group_with_gemini(gemini_api_key, title, res.get("description", ""), messages, target_keywords=keywords)
                    elif gemini_api_key:
                        log("  正在交由 Gemini 进行智能属性与业务粘合度评估...")
                        analysis = analyze_group_with_gemini(gemini_api_key, title, res.get("description", ""), messages, target_keywords=keywords)

                    if not analysis:
                        analysis = {
                            "category": "unknown",
                            "relevance_score": None,
                            "analysis_summary": "未配置或调用 AI 接口失败，使用本地兜底计算",
                            "recommendation": "请在配置中保存有效的 AI 密钥"
                        }

                    category = analysis.get("category", "unknown")
                    relevance = analysis.get("relevance_score")
                    summary = analysis.get("analysis_summary", "")
                    recom = analysis.get("recommendation", "")

                    # Compute Python metrics and combined quality score
                    metrics = calculate_scraped_group_metrics(member_count, messages, keywords, api_relevance_score=relevance, group_type=res.get("group_type", "group"), is_dead=res.get("is_dead", False))
                    score = metrics["quality_score"]

                    log(f"  AI/Python 评估结果 -> 分类: {category} | 综合评分: {score}")

                    # Save/Update in DB
                    with Session(engine) as session:
                        db_group = session.get(ScrapedGroupDb, username)
                        if not db_group:
                            db_group = ScrapedGroupDb(
                                id=username,
                                title=title,
                                link=f"https://t.me/{username}",
                                member_count=member_count,
                                category=category,
                                quality_score=score,
                                analysis_summary=f"{summary} | 建议: {recom}",
                                keyword=keywords[0] if keywords else "",
                                company=company,
                                group_type=res.get("group_type", "group"),
                                is_active=res.get("is_active", True),
                                is_dead=res.get("is_dead", False),
                                relevance_score=metrics["relevance_score"],
                                activity_score=metrics["activity_score"],
                                engagement_score=metrics["engagement_score"],
                                spam_penalty=metrics["spam_penalty"]
                            )
                        else:
                            db_group.title = title
                            db_group.member_count = member_count
                            db_group.category = category
                            db_group.quality_score = score
                            db_group.analysis_summary = f"{summary} | 建议: {recom}"
                            db_group.keyword = keywords[0] if keywords else ""
                            db_group.group_type = res.get("group_type", "group")
                            db_group.is_active = res.get("is_active", True)
                            db_group.is_dead = res.get("is_dead", False)
                            db_group.relevance_score = metrics["relevance_score"]
                            db_group.activity_score = metrics["activity_score"]
                            db_group.engagement_score = metrics["engagement_score"]
                            db_group.spam_penalty = metrics["spam_penalty"]
                            db_group.created_at = datetime.utcnow()
                        session.add(db_group)
                        session.commit()

                    # Save GroupDb record (Auto save)
                    if auto_join and score >= auto_join_min_score and category != "spam":
                        log(f"  [自动保存] 评分 {score} 符合门槛 {auto_join_min_score}，自动保存至群组库...")
                        category_mapping = {
                            "life": "生活聊天",
                            "business": "广告同行",
                            "spam": "垃圾/灌水",
                            "unknown": "待测/私有"
                        }
                        group_category = category_mapping.get(category, "待测/私有")

                        is_duplicate = False
                        with Session(engine) as session:
                            stmt_dup = select(GroupDb).where(GroupDb.company == company)
                            for g_item in session.exec(stmt_dup).all():
                                if g_item.username and g_item.username.strip('@').lower() == username.lower():
                                    is_duplicate = True
                                    break
                                if g_item.title and g_item.title.strip() == title.strip():
                                    is_duplicate = True
                                    break

                        if is_duplicate:
                            log(f"  [自动保存] 触发排重：群组 @{username} 已存在于主群组库中，跳过。")
                        else:
                            try:
                                with Session(engine) as session:
                                    existing_cat = session.exec(
                                        select(GroupCategoryDb)
                                        .where(GroupCategoryDb.company == company)
                                        .where(GroupCategoryDb.name == group_category)
                                    ).first()
                                    if not existing_cat:
                                        new_cat = GroupCategoryDb(name=group_category, company=company)
                                        session.add(new_cat)
                                        session.commit()

                                group_id_str = username
                                group_type_str = res.get("group_type", "group")
                                try:
                                    entity = await client.get_entity(username)
                                    if entity:
                                        group_id_str = str(entity.id)
                                        group_type_str = "channel" if getattr(entity, 'broadcast', False) else "group"
                                except Exception as ee:
                                    log(f"  [自动保存] 获取实体ID失败: {ee}")

                                if group_type_str == "channel":
                                    log(f"  [自动保存] 检测到 @{username} 是频道，触发‘频道不自动保存’规则，跳过。")
                                else:
                                    with Session(engine) as session:
                                        db_g = GroupDb(
                                            id=group_id_str,
                                            company=company,
                                            title=title,
                                            username=username,
                                            type=group_type_str,
                                            enabled=True,
                                            memberCount=member_count,
                                            category=group_category
                                        )
                                        session.merge(db_g)
                                        session.commit()
                                    log(f"  [自动保存] 自动保存群组成功: @{username} (分类: {group_category})")
                                    added_this_round += 1

                                    with Session(engine) as session:
                                        db_group = session.get(ScrapedGroupDb, username)
                                        if db_group:
                                            db_group.status = "joined"
                                            session.add(db_group)
                                            session.commit()
                            except Exception as se:
                                log(f"  [自动保存] 自动保存失败: {str(se)}")
                    else:
                        if not auto_join:
                            added_this_round += 1

                    await asyncio.sleep(5)

                current_page += 1

            # Summary report at the end of each round
            log("阶段性搜寻分析汇报：")
            log(f"- 本轮已搜寻并处理的新增/更新群组: {added_this_round}/{groups_per_round} 个")
            log(f"- 跳过历史已存在重复群组: {history_skip_count} 个")
            log(f"- 跳过成员数不达标群组: {member_skip_count} 个")
            log(f"- 跳过消息提取失败群组: {fetch_fail_count} 个")

            if exhausted:
                log("由于所有搜索页面均已被穷尽，本轮搜寻提前结束。")

            if max_rounds is not None and current_round >= max_rounds:
                log(f"已达到最大限制轮数 {max_rounds} 轮，任务正常结束。")
                break

            if not continuous:
                break

            log(f"本轮任务完成。休眠 {interval_minutes} 分钟后继续搜寻新群组...")
            current_round += 1
            for _ in range(interval_minutes * 60):
                if active_scraper_task["status"] != "running":
                    break
                await asyncio.sleep(1)

        if active_scraper_task["status"] != "stopped":
            log("搜群与分析任务全部完成！")
            active_scraper_task["status"] = "completed"

    except Exception as e:
        import traceback
        err_msg = f"任务运行异常: {str(e)}\n{traceback.format_exc()}"
        log(err_msg)
        active_scraper_task["status"] = "failed"
        active_scraper_task["error"] = str(e)
    finally:
        release_account_task_usage(scraper_task_id, source="scraper-task-finish")

