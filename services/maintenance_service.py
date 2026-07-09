import os
import sys
import json
import time
import asyncio
import logging
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel
from fastapi import HTTPException, BackgroundTasks, Depends

# Import our client and DB layers
from services.shared_state import (
    active_expansion_tasks, active_clients, client_locks,
    register_account_task_usage
)
from services.client_manager import get_client, account_operation_guard

def load_expansion_config() -> tuple[str, int]:
    config_path = Path(__file__).resolve().parent / "config.json"
    default_target = "在印度当地的生活聊天群（交友、生活交流）以及 OTC/USDT/支付相关的专业群中拓展业务"
    default_interval = 15
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            target = data.get("expansion_target", default_target)
            interval = data.get("expansion_interval", default_interval)
            return target, interval
        except Exception:
            pass
    return default_target, default_interval


def save_expansion_config(target: str, interval: int):
    config_path = Path(__file__).resolve().parent / "config.json"
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["expansion_target"] = target
    data["expansion_interval"] = interval
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save expansion config: {e}")


def get_company_expansion_task(company: str) -> dict:
    if company not in active_expansion_tasks:
        init_target, init_interval = load_expansion_config()
        active_expansion_tasks[company] = {
            "status": "idle",  # 'idle', 'running', 'paused', 'failed'
            "target_desc": init_target,
            "current_keyword": "",
            "logs": [],
            "error": None,
            "interval_minutes": init_interval,
            "account_id": None
        }
    return active_expansion_tasks[company]


async def run_business_expansion_loop(
    target_desc: str,
    interval_minutes: int,
    company: str,
    auto_join: bool = False,
    auto_join_min_score: int = 70,
    max_rounds: Optional[int] = None,
    groups_per_round: int = 10,
    round_interval_minutes: int = 5
):
    current_round = 1
    added_this_round = 0
    active_expansion_task = get_company_expansion_task(company)
    expansion_task_id = f"expansion:{company}"
    release_account_task_usage(expansion_task_id, source="expansion-task-reset")
    active_expansion_task["status"] = "running"
    active_expansion_task["target_desc"] = target_desc
    active_expansion_task["interval_minutes"] = interval_minutes
    active_expansion_task["error"] = None

    def log(msg):
        from datetime import datetime
        timestamp = datetime.now().strftime("%m-%d %H:%M:%S")
        active_expansion_task["logs"].append(f"[{timestamp}] {msg}")
        # Keep logs size reasonable (last 500 lines)
        if len(active_expansion_task["logs"]) > 500:
            active_expansion_task["logs"] = active_expansion_task["logs"][-500:]
        print(f"[ExpandAgent] {msg}")

    log(f"业务拓展自主 Agent 已启动。目标: '{target_desc}'，循环间隔: {interval_minutes} 分钟")

    try:
        from group_scraper import (
            generate_keyword_with_gemini,
            generate_keyword_with_deepseek,
            scrape_links_by_keywords,
            fetch_group_messages,
            analyze_group_with_gemini,
            analyze_group_with_deepseek,
            calculate_scraped_group_metrics
        )
        from db import engine, AccountDb, ScrapedGroupDb, GroupDb, Session, select
        from datetime import datetime
        import random

        while active_expansion_task["status"] in ("running", "paused"):
            if active_expansion_task["status"] == "paused":
                await asyncio.sleep(5)
                continue

            gemini_api_key = get_gemini_api_key()
            deepseek_api_key = get_deepseek_api_key()
            if not gemini_api_key and not deepseek_api_key:
                log("错误: 未配置 AI API Key，请先保存您的 API Key 后启动 Agent。")
                active_expansion_task["status"] = "failed"
                active_expansion_task["error"] = "未配置 AI API Key"
                break

            # 1. Gather previously searched keywords from DB to avoid duplication
            with Session(engine) as session:
                stmt = select(ScrapedGroupDb.keyword).where(ScrapedGroupDb.company == company).distinct()
                searched = list(session.exec(stmt).all())
                searched = [s for s in searched if s]

            log("正在请 AI 构思下一步搜寻的关键词...")
            res_kw = None
            if gemini_api_key:
                res_kw = generate_keyword_with_gemini(gemini_api_key, active_expansion_task.get("target_desc", target_desc), searched)
            elif deepseek_api_key:
                res_kw = generate_keyword_with_deepseek(deepseek_api_key, active_expansion_task.get("target_desc", target_desc), searched)

            if not res_kw:
                res_kw = {"keyword": "", "reasoning": "未配置有效的 AI 密钥"}

            kw = res_kw.get("keyword", "").strip()
            reason = res_kw.get("reasoning", "未提供理由").strip()

            if not kw:
                log(f"AI 构思关键词失败或为空。原因: {reason}。将在 2 分钟后重试...")
                await asyncio.sleep(120)
                continue

            active_expansion_task["current_keyword"] = kw
            log(f"[AI 思考结论] 决定搜寻关键词: '{kw}'")
            log(f"[AI 思考逻辑] {reason}")

            # 2. Scrape group links using combined scraper
            log(f"正在抓取关键词 '{kw}' 相关的电报群链接...")
            active_expansion_task["account_id"] = None
            links = scrape_links_by_keywords([kw], max_pages=1)
            log(f"抓取完成。共找到 {len(links)} 个潜在公开群链接。")

            if not links:
                log("此轮未找到合适的新链接，等待下一个周期。")
            else:
                # 3. Find online authorized account under this company
                authorized_account_id = None
                authorized_phone = None
                with Session(engine) as session:
                    accounts = filter_executable_accounts_for_task(session.exec(select(AccountDb).where(AccountDb.company == company)).all())

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
                    log("警告: 当前公司下没有在线已登录的电报账号！无法拉取群消息进行评估，此轮跳过。")
                else:
                    active_expansion_task["account_id"] = authorized_account_id
                    register_account_task_usage(
                        "expansion",
                        expansion_task_id,
                        [authorized_account_id],
                        {"company": company},
                    )
                    log(f"使用账号 [{authorized_phone}] 进行群组消息拉取与 AI 质量评估...")
                    client = await get_client(authorized_account_id)

                    # 4. Iterate and analyze
                    for idx, link in enumerate(links):
                        if active_expansion_task["status"] != "running":
                            break

                        # Extract public username
                        public_match = re.search(r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)?([a-zA-Z0-9_\+]{5,32})', link)
                        if not public_match or "joinchat/" in link or "+" in link:
                            # Skip private links
                            continue

                        username = public_match.group(1)

                        # Check if this group was already analyzed in database
                        with Session(engine) as session:
                            existing = session.get(ScrapedGroupDb, username)
                        if existing and existing.category != "unknown":
                            # Already processed
                            continue

                        log(f"正在拉取群组 @{username} 的详情与消息...")
                        fetch_res = await fetch_group_messages(client, username)

                        if not fetch_res.get("success"):
                            err_msg = fetch_res.get("error", "")
                            log(f"  拉取群组 @{username} 消息失败: {err_msg}")
                            if "FloodWait" in err_msg or "wait of" in err_msg:
                                log(f"⚠️ [限制警告] 检测到当前电报账号已触发限制 (FloodWait): {err_msg}。为防止封号，已自动暂停业务拓展任务，请稍后再试。")
                                active_expansion_task["status"] = "paused"
                                active_expansion_task["error"] = f"触发电报限制: {err_msg}"
                                break
                            await asyncio.sleep(4)
                            continue

                        title = fetch_res["title"]
                        member_count = fetch_res["member_count"]
                        messages = fetch_res["messages"]

                        log(f"  拉取成功。标题: '{title}' | 成员数: {member_count}。提交 AI 进行质量打分...")

                        # Run AI analysis (Prioritize DeepSeek, fallback to Gemini, then local)
                        analysis = None
                        if deepseek_api_key:
                            analysis = analyze_group_with_deepseek(deepseek_api_key, title, fetch_res.get("description", ""), messages, target_keywords=[kw], target_desc=target_desc)
                            if (not analysis or analysis.get("relevance_score") is None) and gemini_api_key:
                                log("  DeepSeek 评估失败，尝试使用 Gemini 进行评估...")
                                analysis = analyze_group_with_gemini(gemini_api_key, title, fetch_res.get("description", ""), messages, target_keywords=[kw], target_desc=target_desc)
                        elif gemini_api_key:
                            analysis = analyze_group_with_gemini(gemini_api_key, title, fetch_res.get("description", ""), messages, target_keywords=[kw], target_desc=target_desc)

                        if not analysis:
                            analysis = {
                                "category": "unknown",
                                "relevance_score": None,
                                "analysis_summary": "未配置或调用 AI 接口失败，使用本地兜底计算",
                                "recommendation": "请在配置中保存有效的 AI 密钥"
                            }

                        category = analysis.get("category", "unknown")
                        relevance = analysis.get("relevance_score") # can be None
                        summary = analysis.get("analysis_summary", "")
                        recom = analysis.get("recommendation", "")

                        # Compute Python metrics and combined quality score
                        metrics = calculate_scraped_group_metrics(member_count, messages, [kw], api_relevance_score=relevance, group_type=fetch_res.get("group_type", "group"), is_dead=fetch_res.get("is_dead", False))
                        score = metrics["quality_score"]

                        log(f"  AI/Python 评估结果 -> 分类: {category} | 粘合度: {metrics['relevance_score']} | 活跃度: {metrics['activity_score']} | 互动率: {metrics['engagement_score']} | 垃圾扣分: {metrics['spam_penalty']} | 综合评分: {score}")

                        # Save in database
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
                                    keyword=kw,
                                    company=company,
                                    group_type=fetch_res.get("group_type", "group"),
                                    is_active=fetch_res.get("is_active", True),
                                    is_dead=fetch_res.get("is_dead", False),
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
                                db_group.keyword = kw
                                db_group.group_type = fetch_res.get("group_type", "group")
                                db_group.is_active = fetch_res.get("is_active", True)
                                db_group.is_dead = fetch_res.get("is_dead", False)
                                db_group.relevance_score = metrics["relevance_score"]
                                db_group.activity_score = metrics["activity_score"]
                                db_group.engagement_score = metrics["engagement_score"]
                                db_group.spam_penalty = metrics["spam_penalty"]
                            session.add(db_group)
                            session.commit()

                        # --- AUTO JOIN & SAFETY WIND CONTROL ---
                        if auto_join and score >= auto_join_min_score and category != "spam":
                            if fetch_res.get("group_type") == "channel":
                                log(f"  [加群控制] 检测到 @{username} 是频道，触发‘频道不自动加入’规则，跳过。")
                            # 1. Round Wind Control Check
                            elif max_rounds is not None and current_round > max_rounds:
                                log(f"  [加群控制] 已达到最大限制轮数 {max_rounds} 轮，不执行对 @{username} 的加群操作。")
                            else:
                                # 2. Local Database Deduplication Check
                                from db import GroupDb
                                is_duplicate = False
                                with Session(engine) as session:
                                    # Check by username, title, or internal group ID
                                    stmt_dup = select(GroupDb).where(GroupDb.company == company)
                                    for g_item in session.exec(stmt_dup).all():
                                        # Compare username
                                        if g_item.username and g_item.username.strip('@').lower() == username.lower():
                                            is_duplicate = True
                                            break
                                        # Compare title
                                        if g_item.title and g_item.title.strip() == title.strip():
                                            is_duplicate = True
                                            break

                                if is_duplicate:
                                    log(f"  [加群控制] 触发排重机制跳过：群组 @{username} ('{title}') 已存在于群组库中，不往下执行。")
                                else:
                                    # 3. Check if we need to sleep due to round limit
                                    if added_this_round >= groups_per_round:
                                        log(f"  [加群控制] 当前第 {current_round} 轮已成功添加 {added_this_round} 个群组，达到单轮上限。进入休眠间隔...")
                                        log(f"  [加群控制] 轮次休眠间隔: {round_interval_minutes} 分钟，暂停加群进程。")
                                        # Sleep safely in chunks to allow quick termination
                                        for _ in range(round_interval_minutes * 60):
                                            if active_expansion_task["status"] != "running":
                                                break
                                            await asyncio.sleep(1)
                                        # Move to next round
                                        current_round += 1
                                        added_this_round = 0
                                        log(f"  [加群控制] 休眠结束，进入第 {current_round} 轮。")

                                    # Double check max_rounds after potential sleep round increments
                                    if max_rounds is None or current_round <= max_rounds:
                                        if active_expansion_task["status"] == "running":
                                            log(f"  [加群控制] 开始自动加入群组 @{username} ...")
                                            try:
                                                # Invoke join_group_or_channel directly (takes client and username/link)
                                                entity = await join_group_or_channel(client, username)
                                                log(f"  [加群控制] 自动加入成功: @{username}")
                                                added_this_round += 1

                                                # Save to GroupDb
                                                from db import GroupDb
                                                with Session(engine) as session:
                                                    db_g = GroupDb(
                                                        id=str(entity.id),
                                                        company=company,
                                                        title=title,
                                                        username=username,
                                                        type="channel" if getattr(entity, 'broadcast', False) else "group",
                                                        enabled=True,
                                                        memberCount=member_count,
                                                        category="自动加群"
                                                    )
                                                    session.merge(db_g)
                                                    session.commit()

                                                # Mark scraped status as joined
                                                with Session(engine) as session:
                                                    db_group = session.get(ScrapedGroupDb, username)
                                                    if db_group:
                                                        db_group.status = "joined"
                                                        session.add(db_group)
                                                        session.commit()
                                            except Exception as je:
                                                log(f"  [加群控制] 自动加入失败: {str(je)}")

                        # Avoid Telegram rate limits
                        await asyncio.sleep(5)

            # Sleep for the interval
            current_interval = active_expansion_task.get("interval_minutes", interval_minutes)
            log(f"此轮自主搜群拓展完成。休眠 {current_interval} 分钟后继续...")
            for _ in range(current_interval * 60):
                if active_expansion_task["status"] != "running":
                    break
                await asyncio.sleep(1)

        log("自主业务拓展任务已终止。")

    except Exception as e:
        import traceback
        err_msg = f"自主业务拓展循环异常: {str(e)}\n{traceback.format_exc()}"
        log(err_msg)
        active_expansion_task["status"] = "failed"
        active_expansion_task["error"] = str(e)
    finally:
        release_account_task_usage(expansion_task_id, source="expansion-task-finish")


async def run_account_cleanup_process(account_id: str):
    import datetime
    import re
    from datetime import timezone

    progress = {
        "status": "running",
        "started_at": time.time(),
        "logs": [],
        "left_groups": 0,
        "grouped_channels": 0,
        "synced_dms": 0,
        "archived_chats": 0
    }
    failed_folders = set()
    cleanup_tasks_progress[account_id] = progress

    def log(msg):
        print(f"[{account_id} Cleanup] {msg}")
        progress["logs"].append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    log("初始化账号整理任务...")

    client = None
    try:
        # 获取 Telethon 客户端，必须在 locks 保护内获取以防写冲突
        if account_id not in client_locks:
            client_locks[account_id] = asyncio.Lock()

        async with client_locks[account_id]:
            # 假定此时账号已经在线，如果没有连上，则临时 connect
            client = active_clients.get(account_id)
            if not client:
                # 从配置加载并获取
                config_path = account_config_path(account_id)
                if not config_path.exists():
                    raise Exception("Account config not found")
                config = load_json(config_path)
                base_dir = config_path.parent.parent
                client = await build_client(config, base_dir)
                await client.connect()
                active_clients[account_id] = client

            if not await client.is_user_authorized():
                raise Exception("账号未授权登录，请先登录")

            if not client.is_connected():
                await client.connect()

            # 获取翻译 Bot 和 AI Bot 的 InputPeer
            ai_bot_username = "RosePayTest_bot"
            translate_bot_username = "RosePay_translation_bot"
            try:
                db_path = get_db_path()
                import sqlite3
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT bot_username, bot_type FROM telegram_bots WHERE is_active = 1")
                    for row in cursor.fetchall():
                        if row["bot_type"] == "ai_bot":
                            ai_bot_username = row["bot_username"]
                        elif row["bot_type"] == "translate_bot":
                            translate_bot_username = row["bot_username"]
            except Exception as e:
                log(f"查询数据库 bots 失败，使用默认值: {e}")

            translate_bot_peer = None
            ai_bot_peer = None
            try:
                if translate_bot_username:
                    translate_bot_peer = await client.get_input_entity(translate_bot_username)
            except Exception as e:
                log(f"获取翻译 Bot '{translate_bot_username}' InputPeer 失败: {e}")

            try:
                if ai_bot_username:
                    ai_bot_peer = await client.get_input_entity(ai_bot_username)
            except Exception as e:
                log(f"获取 AI Bot '{ai_bot_username}' InputPeer 失败: {e}")

            # 开始获取会话列表
            log("正在拉取对话列表...")
            dialogs = await client.get_dialogs()
            log(f"拉取完成。共发现 {len(dialogs)} 个对话窗口")

            now_dt = datetime.datetime.now(timezone.utc)

            # --- 第一阶段：清理不活跃群组 ---
            log("=== 第一阶段：检测并退出不活跃群组 ===")
            groups_to_cleanup = []
            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    is_megagroup = getattr(dialog.entity, 'megagroup', False) if dialog.is_channel else True
                    if not is_megagroup and dialog.is_channel:
                        # 排除纯频道，只清理群组
                        continue

                    last_msg_date = None
                    if dialog.message and dialog.message.date:
                        last_msg_date = dialog.message.date

                    if last_msg_date:
                        diff = now_dt - last_msg_date
                        if diff.days >= 7:
                            groups_to_cleanup.append(dialog)

            log(f"共检测到 {len(groups_to_cleanup)} 个超过 7 天无新发言的不活跃群组。")
            for idx, g in enumerate(groups_to_cleanup):
                try:
                    log(f"({idx+1}/{len(groups_to_cleanup)}) 正在退出群组: {g.name} ...")
                    if g.is_channel:
                        await client(functions.channels.LeaveChannelRequest(channel=g.input_entity))
                    else:
                        await client(functions.messages.DeleteChatUserRequest(chat_id=g.id, user_id='self'))
                    progress["left_groups"] += 1
                    # 退出群组后静默 5 秒
                    await asyncio.sleep(5)
                except errors.FloodWaitError as fwe:
                    log(f"遭遇 429 频限，需要等待 {fwe.seconds} 秒。中断后续退群操作。")
                    auto_private_listener_cooldowns[account_id] = time.time() + fwe.seconds
                    break
                except Exception as e:
                    log(f"退出群组 {g.name} 失败: {e}")
                    await asyncio.sleep(2)

            # 重新拉取一次 Dialog 列表，以排除已经退出的群
            log("重新刷新对话列表以准备分类文件夹...")
            dialogs = await client.get_dialogs()

            # --- 第二阶段：分析字数与中英文，即时分配并写入文件夹 ---
            log("=== 第二阶段：群组字数/语言特征判别、即时归类与文件夹写入 ===")

            # 在第二阶段开始前，先清理所有旧的文件夹分类
            log("正在清理云端旧的分类文件夹...")
            try:
                filters_res = await client(functions.messages.GetDialogFiltersRequest())
                current_filters = filters_res.filters

                old_titles_to_remove = ["中文广告群", "英文广告群", "短广告群", "DM", "中文长", "中文短", "英文长", "英文短"]
                for f in current_filters:
                    if isinstance(f, types.DialogFilter):
                        f_title = getattr(f, "title", "")
                        should_remove = False
                        for ot in old_titles_to_remove:
                            if normalize_title(f_title) == normalize_title(ot):
                                should_remove = True
                                break
                        if should_remove:
                            log(f"正在删除旧文件夹: '{f_title}' (ID: {f.id})")
                            await client(functions.messages.UpdateDialogFilterRequest(id=f.id))
                            await asyncio.sleep(1)
            except Exception as e:
                log(f"清理旧分类文件夹失败: {e}")

            all_classified_peers = set() # 记录已命中规则的所有 Peer 引用，方便后续归档

            # 归类群组
            for idx, dialog in enumerate(dialogs):
                if dialog.is_group or (dialog.is_channel and getattr(dialog.entity, 'megagroup', False)):
                    try:
                        # 拉取最近 10 条消息来判定发言限制和中英文
                        msgs = await client.get_messages(dialog.input_entity, limit=10)
                        await asyncio.sleep(2) # 每次拉取消息静默 2 秒

                        if not msgs:
                            continue

                        # 1. 判定字数限制
                        msg_lengths = [len(m.message) for m in msgs if m.message]
                        is_short_ad = False
                        if msg_lengths:
                            max_len = max(msg_lengths)
                            if max_len < 200:
                                is_short_ad = True

                        # 2. 判定语言 (中英文)，综合考虑群名和活跃发言
                        has_chinese_name = False
                        if dialog.name:
                            has_chinese_name = bool(re.search(r"[\u4e00-\u9fa5]", dialog.name)) or "🇨🇳" in dialog.name

                        text_messages = [m.message for m in msgs if m.message]
                        has_messages = len(text_messages) > 0
                        combined_text = "".join(text_messages)
                        has_chinese_messages = bool(re.search(r"[\u4e00-\u9fa5]", combined_text))

                        is_chinese = False
                        if has_messages:
                            # 活跃发言中必须包含中文，方可判定为中文群（起到了中英文的区别）
                            if has_chinese_messages:
                                is_chinese = True
                        else:
                            # 如果最近没有发言，降级使用群名判定
                            if has_chinese_name:
                                is_chinese = True

                        input_peer = dialog.input_entity
                        all_classified_peers.add(dialog.id)

                        if is_chinese:
                            if is_short_ad:
                                title = "中文短"
                            else:
                                title = "中文长"
                        else:
                            if is_short_ad:
                                title = "英文短"
                            else:
                                title = "英文长"

                        log_info = f"群组: {dialog.name} | 判定类别: {title} | 字数: {'短' if is_short_ad else '长'} | 语言: {'中文' if is_chinese else '英文'}"
                        log(log_info)

                        if title in failed_folders:
                            continue

                        # 即时写入/更新 Telegram 文件夹
                        try:
                            filters_res = await client(functions.messages.GetDialogFiltersRequest())
                            current_filters = filters_res.filters

                            f_obj = None
                            for f in current_filters:
                                if isinstance(f, types.DialogFilter) and normalize_title(f.title) == normalize_title(title):
                                    f_obj = f
                                    break
                            if not f_obj:
                                existing_ids = [f.id for f in current_filters if hasattr(f, 'id')]
                                new_id = max(existing_ids) + 1 if existing_ids else 2
                                f_obj = types.DialogFilter(
                                    id=new_id,
                                    title=title,
                                    include_peers=[],
                                    exclude_peers=[],
                                    pinned_peers=[],
                                    contacts=False,
                                    non_contacts=False,
                                    groups=False,
                                    broadcasts=False,
                                    bots=False,
                                    exclude_muted=False,
                                    exclude_read=False,
                                    exclude_archived=False
                                )
                                current_filters.append(f_obj)
                                log(f"已新建文件夹: '{title}'")

                            existing_peer_ids = []
                            for p in f_obj.include_peers:
                                p_id = getattr(p, 'user_id', None) or getattr(p, 'channel_id', None) or getattr(p, 'chat_id', None)
                                if p_id:
                                    existing_peer_ids.append(p_id)

                            new_p_id = dialog.entity.id
                            peer_obj = await client.get_input_entity(dialog.entity)

                            if new_p_id and new_p_id not in existing_peer_ids:
                                # 重新实例化一个全新的 DialogFilter，清洗所有的 include_peers/pinned_peers/exclude_peers
                                updated_peers = list(f_obj.include_peers) + [peer_obj]
                                clean_include = await clean_and_convert_peers_async(client, updated_peers)
                                clean_pinned = await clean_and_convert_peers_async(client, getattr(f_obj, "pinned_peers", []) or [])
                                clean_exclude = await clean_and_convert_peers_async(client, getattr(f_obj, "exclude_peers", []) or [])

                                title_text = getattr(f_obj, "title", title)
                                if isinstance(title_text, str):
                                    title_obj = types.TextWithEntities(text=title_text, entities=[])
                                else:
                                    title_obj = title_text

                                new_filter = types.DialogFilter(
                                    id=f_obj.id,
                                    title=title_obj,
                                    pinned_peers=clean_pinned,
                                    include_peers=clean_include,
                                    exclude_peers=clean_exclude,
                                    contacts=getattr(f_obj, "contacts", False),
                                    non_contacts=getattr(f_obj, "non_contacts", False),
                                    groups=getattr(f_obj, "groups", False),
                                    broadcasts=getattr(f_obj, "broadcasts", False),
                                    bots=getattr(f_obj, "bots", False)
                                )
                                await client(functions.messages.UpdateDialogFilterRequest(id=f_obj.id, filter=new_filter))
                                log(f"已即时将群组 '{dialog.name}' 移入文件夹 '{title}'。")
                                await asyncio.sleep(1)
                        except Exception as fe:
                            err_msg = str(fe)
                            if "DIALOG_FILTERS_TOO_MUCH" in err_msg:
                                failed_folders.add(title)
                                log(f"账号文件夹数量已达 Telegram 上限，无法创建新文件夹 '{title}'，请手动清理一些不用的文件夹后再试。")
                            else:
                                log(f"即时移动群组 {dialog.name} 到文件夹 {title} 失败: {fe}")

                        progress["grouped_channels"] += 1
                    except errors.FloodWaitError as fwe:
                        log(f"分析群组时遭遇 429 频限，需要等待 {fwe.seconds} 秒。跳过其余群递析。")
                        auto_private_listener_cooldowns[account_id] = time.time() + fwe.seconds
                        break
                    except Exception as e:
                        err_str = str(e)
                        log(f"分析群组 {dialog.name} 异常: {e}")

                        # 判定是否为失效群组，如果是则直接退群（删掉）
                        is_invalid_group = False
                        if any(k in err_str for k in [
                            "CHANNEL_PRIVATE",
                            "CHAT_WRITE_FORBIDDEN",
                            "USER_BANNED_IN_CHANNEL",
                            "CHAT_ADMIN_REQUIRED",
                            "ChannelPrivateError",
                            "ChatWriteForbiddenError"
                        ]):
                            is_invalid_group = True

                        if is_invalid_group:
                            try:
                                log(f"检测到群组 '{dialog.name}' 已失效，正在执行退群物理删除...")
                                if dialog.is_channel:
                                    await client(functions.channels.LeaveChannelRequest(channel=dialog.input_entity))
                                else:
                                    await client(functions.messages.DeleteChatUserRequest(chat_id=dialog.id, user_id='self'))
                                log(f"已成功退出并删除失效群组 '{dialog.name}'。")
                                progress["left_groups"] += 1
                                await asyncio.sleep(3)
                            except Exception as le:
                                log(f"退出失效群组 '{dialog.name}' 失败: {le}")

            # --- 第三阶段：私聊同步 DM 文件夹 (即时同步) ---
            log("=== 第三阶段：同步私聊窗口至 DM 文件夹 ===")
            dm_count = 0
            for dialog in dialogs:
                if dialog.is_user and getattr(dialog.entity, 'bot', False) is False:
                    try:
                        all_classified_peers.add(dialog.id)

                        if "DM" in failed_folders:
                            continue

                        filters_res = await client(functions.messages.GetDialogFiltersRequest())
                        current_filters = filters_res.filters

                        f_obj = None
                        for f in current_filters:
                            if isinstance(f, types.DialogFilter) and normalize_title(f.title) == normalize_title("DM"):
                                f_obj = f
                                break
                        if not f_obj:
                            existing_ids = [f.id for f in current_filters if hasattr(f, 'id')]
                            new_id = max(existing_ids) + 1 if existing_ids else 2
                            f_obj = types.DialogFilter(
                                id=new_id,
                                title="DM",
                                include_peers=[],
                                exclude_peers=[],
                                pinned_peers=[],
                                contacts=False,
                                non_contacts=False,
                                groups=False,
                                broadcasts=False,
                                bots=False,
                                exclude_muted=False,
                                exclude_read=False,
                                exclude_archived=False
                            )
                            current_filters.append(f_obj)
                            log("已新建文件夹: 'DM'")

                        existing_peer_ids = []
                        for p in f_obj.include_peers:
                            p_id = getattr(p, 'user_id', None) or getattr(p, 'channel_id', None) or getattr(p, 'chat_id', None)
                            if p_id:
                                existing_peer_ids.append(p_id)

                        new_p_id = dialog.entity.id
                        peer_obj = await client.get_input_entity(dialog.entity)
                        if new_p_id and new_p_id not in existing_peer_ids:
                            # 重新实例化全新的 DialogFilter 并清洗
                            updated_peers = list(f_obj.include_peers) + [peer_obj]
                            clean_include = await clean_and_convert_peers_async(client, updated_peers)
                            clean_pinned = await clean_and_convert_peers_async(client, getattr(f_obj, "pinned_peers", []) or [])
                            clean_exclude = await clean_and_convert_peers_async(client, getattr(f_obj, "exclude_peers", []) or [])

                            title_text = getattr(f_obj, "title", "DM")
                            if isinstance(title_text, str):
                                title_obj = types.TextWithEntities(text=title_text, entities=[])
                            else:
                                title_obj = title_text

                            new_filter = types.DialogFilter(
                                id=f_obj.id,
                                title=title_obj,
                                pinned_peers=clean_pinned,
                                include_peers=clean_include,
                                exclude_peers=clean_exclude,
                                contacts=getattr(f_obj, "contacts", False),
                                non_contacts=getattr(f_obj, "non_contacts", False),
                                groups=getattr(f_obj, "groups", False),
                                broadcasts=getattr(f_obj, "broadcasts", False),
                                bots=getattr(f_obj, "bots", False)
                            )
                            await client(functions.messages.UpdateDialogFilterRequest(id=f_obj.id, filter=new_filter))
                            log(f"已即时将私聊 '{dialog.name}' 移入文件夹 'DM'。")
                            await asyncio.sleep(0.5)

                        dm_count += 1
                        progress["synced_dms"] = dm_count
                    except Exception as fe:
                        err_msg = str(fe)
                        if "DIALOG_FILTERS_TOO_MUCH" in err_msg:
                            failed_folders.add("DM")
                            log("账号文件夹数量已达 Telegram 上限，无法创建新文件夹 'DM'，请手动清理一些不用的文件夹后再试。")
                        else:
                            log(f"同步私聊 {dialog.name} 失败: {fe}")

            # --- 第五阶段：将所有整理命中会话进行“归档隐藏” ---
            log("=== 第五阶段：批量隐藏归档会话 (Archive) ===")
            peers_to_archive = []

            for dialog in dialogs:
                if dialog.id in all_classified_peers:
                    if dialog.folder_id != 1:
                        peers_to_archive.append(dialog)

            if peers_to_archive:
                log(f"共有 {len(peers_to_archive)} 个会话需要进行归档隐藏...")
                for i in range(0, len(peers_to_archive), 20):
                    batch = peers_to_archive[i:i+20]
                    try:
                        folder_peers = []
                        for item in batch:
                            folder_peers.append(types.InputFolderPeer(peer=item.input_entity, folder_id=1))
                        log(f"正在将本批 {len(batch)} 个会话移动到归档夹...")
                        await client(functions.folders.EditPeerFoldersRequest(folder_peers=folder_peers))
                        progress["archived_chats"] += len(batch)
                        await asyncio.sleep(3)
                    except errors.FloodWaitError as fwe:
                        log(f"归档操作遭遇 429 频限，需要等待 {fwe.seconds} 秒。中断后续归档。")
                        auto_private_listener_cooldowns[account_id] = time.time() + fwe.seconds
                        break
                    except Exception as e:
                        log(f"归档批量操作失败: {e}")
                        await asyncio.sleep(2)
            else:
                log("没有检测到需要移动归档的非归档会话。")

            # --- 第六阶段：确保翻译 Bot 存在于每一个分类文件夹中，并且置顶 ---
            log("=== 第六阶段：将翻译 Bot 同步并置顶到每一个分类文件夹 ===")
            if translate_bot_peer:
                try:
                    filters_res = await client(functions.messages.GetDialogFiltersRequest())
                    current_filters = filters_res.filters

                    # 4个我们要管理的文件夹名称
                    target_folder_titles = ["中文长", "中文短", "英文长", "英文短"]

                    for f_obj in current_filters:
                        if isinstance(f_obj, types.DialogFilter):
                            f_title = getattr(f_obj, "title", "")
                            is_target = False
                            for target_title in target_folder_titles:
                                if normalize_title(f_title) == normalize_title(target_title):
                                    is_target = True
                                    break

                            if is_target:
                                # 清洗现有的 include/pinned/exclude
                                clean_include = await clean_and_convert_peers_async(client, list(f_obj.include_peers) or [])
                                clean_pinned = await clean_and_convert_peers_async(client, getattr(f_obj, "pinned_peers", []) or [])
                                clean_exclude = await clean_and_convert_peers_async(client, getattr(f_obj, "exclude_peers", []) or [])

                                t_user_id = getattr(translate_bot_peer, 'user_id', None)
                                if t_user_id:
                                    # 1. 确保翻译 Bot 存在于 include 中
                                    exists_in_include = False
                                    for p in clean_include:
                                        if getattr(p, 'user_id', None) == t_user_id:
                                            exists_in_include = True
                                            break
                                    if not exists_in_include:
                                        clean_include.append(translate_bot_peer)

                                    # 2. 确保翻译 Bot 在 pinned 中且在第一位
                                    clean_pinned = [p for p in clean_pinned if getattr(p, 'user_id', None) != t_user_id]
                                    clean_pinned.insert(0, translate_bot_peer)

                                    # 构造更新后的 DialogFilter
                                    title_text = getattr(f_obj, "title", f_title)
                                    if isinstance(title_text, str):
                                        title_obj = types.TextWithEntities(text=title_text, entities=[])
                                    else:
                                        title_obj = title_text

                                    new_filter = types.DialogFilter(
                                        id=f_obj.id,
                                        title=title_obj,
                                        pinned_peers=clean_pinned,
                                        include_peers=clean_include,
                                        exclude_peers=clean_exclude,
                                        contacts=getattr(f_obj, "contacts", False),
                                        non_contacts=getattr(f_obj, "non_contacts", False),
                                        groups=getattr(f_obj, "groups", False),
                                        broadcasts=getattr(f_obj, "broadcasts", False),
                                        bots=getattr(f_obj, "bots", False)
                                    )
                                    await client(functions.messages.UpdateDialogFilterRequest(id=f_obj.id, filter=new_filter))
                                    log(f"已将翻译 Bot 置顶并同步到文件夹 '{f_title}'。")
                                    await asyncio.sleep(1)
                except Exception as fe:
                    log(f"同步/置顶翻译 Bot 到分类文件夹失败: {fe}")

            # --- 第七阶段：把 aibot 在主文件夹（默认会话列表）置顶 ---
            if ai_bot_peer:
                try:
                    log(f"正在将 AI Bot '{ai_bot_username}' 置顶在主文件夹...")
                    await client(functions.messages.ToggleDialogPinRequest(
                        peer=ai_bot_peer,
                        pinned=True
                    ))
                    log(f"AI Bot '{ai_bot_username}' 置顶在主文件夹成功。")
                except Exception as e:
                    log(f"置顶 AI Bot 失败 (可能已置顶或已达上限): {e}")

            progress["status"] = "success"
            log("🎉 账号整理整理完毕！完美闭环成功。")

    except Exception as exc:
        progress["status"] = "failed"
        log(f"❌ 账号整理失败中断: {exc}")

