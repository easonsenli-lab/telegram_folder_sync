# -*- coding: utf-8 -*-
import os
import asyncio
import urllib.request
import urllib.error
import json
import re
from datetime import datetime

async def call_deepseek_api_rules(api_key: str, api_base: str, group_title: str, context: str) -> str:
    url = f"{api_base.rstrip('/')}/chat/completions"
    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个 Telegram 群组发言限制规则提取专家。你的任务是根据提供的【群置顶公告】、【Bot/管理员警告记录】以及【普通用户历史正常发言长度统计】，"
                    "提取出该群对普通成员发言的硬性限制规则。\n"
                    "你必须严格返回一个 JSON 格式的字典，不得包含任何 Markdown 格式包裹（不要加 ```json 标签）、不要包含任何解释或闲聊文字。JSON 包含以下字段：\n"
                    "1. \"max_length\": 整数。如果检测到字数限制，提取其具体限制数值。如果 Bot 警告或置顶里有字数限制但没有说明具体数字，"
                    "请结合【普通用户历史正常发言长度统计】中给出的最大成功发言长度（如 195 字），合理向上取整并推断出限制数字（如 200）。如果没有字数限制，返回 0。\n"
                    "2. \"has_sensitive_words\": 布尔值。是否限制敏感词、人机敏感词或包含特定违禁词。\n"
                    "3. \"banned_links\": 布尔值。是否禁发链接/URL、二维码等。\n"
                    "4. \"banned_media\": 布尔值。是否禁发图片、视频、语音、文件等媒体（不包括文字中的链接）。\n"
                    "5. \"other_rules\": 字符串数组。如有其他限制规则，在此简短列出，否则留空。\n\n"
                    "输出样例：\n"
                    "{\n"
                    "  \"max_length\": 200,\n"
                    "  \"has_sensitive_words\": true,\n"
                    "  \"banned_links\": true,\n"
                    "  \"banned_media\": false,\n"
                    "  \"other_rules\": [\"禁止频繁刷屏\"]\n"
                    "}"
                )
            },
            {
                "role": "user",
                "content": f"群组: {group_title}\n\n{context}"
            }
        ],
        "temperature": 0.1
    }
    req_body = json.dumps(data).encode("utf-8")
    
    def _do_post():
        req = urllib.request.Request(
            url,
            data=req_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
            
    try:
        res = await asyncio.to_thread(_do_post)
        content = res["choices"][0]["message"]["content"].strip()
        # 剔除 markdown 块包裹
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return content.strip()
    except Exception as e:
        print(f"[DeepSeek API] 请求规则审计接口异常: {e}")
        return "{}"

async def audit_group_bot_rules(client, chat_id: int, group_title: str, username: str) -> tuple[str, str]:
    """Scrapes group messages, filters bot warnings/pins, estimates char limits, and summaries rules via local regex parser and optional DeepSeek API."""
    print(f"\n[Bot审计] 正在为群组 '{group_title}' ({username or chat_id}) 扫描发言规则...", flush=True)
    
    # 默认无规则的结构化 JSON
    default_json = {
        "max_length": 0,
        "has_sensitive_words": False,
        "banned_links": False,
        "banned_media": False,
        "other_rules": []
    }
    
    try:
        # 1. 预先定义内部抓取函数，实现大号轮询降级
        admin_ids = set()
        messages = []
        pin_text = ""
        bot_warnings = []
        human_message_bytes = []

        async def try_fetch_messages(target_client):
            from telethon import types
            resolved_entity = None
            
            # 1. 优先使用公开用户名 username 获取，这在 Telegram 中是最稳健、最不容易出错的方法
            if username:
                try:
                    resolved_entity = await target_client.get_entity(str(username).strip())
                except Exception as ent_err:
                    print(f"[Bot审计] 尝试使用用户名 '{username}' 获取实体失败: {ent_err}")
            
            # 2. 如果用户名没拿到，通过 ID 进行多重 Peer 类型重试获取
            if not resolved_entity:
                clean_id_str = str(chat_id).strip()
                # 提取纯数字部分
                raw_id_str = clean_id_str
                if raw_id_str.startswith("-100"):
                    raw_id_str = raw_id_str[4:]
                elif raw_id_str.startswith("-"):
                    raw_id_str = raw_id_str[1:]
                
                try:
                    val_id = int(raw_id_str)
                except ValueError:
                    val_id = None
                
                if val_id is not None:
                    # 依次尝试：PeerChannel -> PeerChat -> 负数整数 -> 原始整数
                    for peer in [
                        types.PeerChannel(val_id),
                        types.PeerChat(val_id),
                        -val_id,
                        int(clean_id_str)
                    ]:
                        try:
                            resolved_entity = await target_client.get_entity(peer)
                            if resolved_entity:
                                print(f"[Bot审计] 通过 Peer/ID 转换模式 ({type(peer).__name__}) 成功定位实体。")
                                break
                        except Exception:
                            continue
            
            # 3. 兜底：如果上面均失败，使用原始 chat_id 直接获取
            if not resolved_entity:
                try:
                    # 尝试转成整数，或者直接传
                    try:
                        resolved_entity = await target_client.get_entity(int(str(chat_id).strip()))
                    except ValueError:
                        resolved_entity = await target_client.get_entity(chat_id)
                except Exception as final_err:
                    raise Exception(f"无法定位群组实体: {final_err}")

            t_admin_ids = set()
            try:
                from telethon.tl.types import ChannelParticipantsAdmins
                participants = await target_client.get_participants(resolved_entity, filter=ChannelParticipantsAdmins())
                for p in participants:
                    t_admin_ids.add(p.id)
            except Exception:
                pass
            
            t_messages = await target_client.get_messages(resolved_entity, limit=90)
            t_pin = ""
            for m in t_messages:
                if m and getattr(m, "pinned", False) and m.text:
                    t_pin = m.text
                    break
            return t_admin_ids, t_messages, t_pin

        # 第一步：尝试首选 client (探测号)，设置 5 秒超时防卡死
        try:
            admin_ids, messages, pin_text = await asyncio.wait_for(try_fetch_messages(client), timeout=5.0)
            print(f"[Bot审计] 首选探测大号成功拉取群组 '{group_title}' 的消息。")
        except Exception as client_err:
            print(f"[Bot审计] 探测号拉取群组 '{group_title}' 消息失败 (可能不在群内): {client_err}，尝试降级轮询其他在线大号...")
            # 第二步：轮询其它在线的客户端
            from services.shared_state import active_clients
            fetched_ok = False
            # 限制最多轮询 2 个备用大号，且每个限制 5.0 秒超时，控制总体流程在 15 秒绝对安全线内
            fallback_attempts = 0
            for alt_id, alt_client in list(active_clients.items()):
                if alt_client != client:
                    if fallback_attempts >= 2:
                        break
                    try:
                        if alt_client.is_connected() and await alt_client.is_user_authorized():
                            fallback_attempts += 1
                            admin_ids, messages, pin_text = await asyncio.wait_for(
                                try_fetch_messages(alt_client), 
                                timeout=5.0
                            )
                            print(f"[Bot审计] 降级大号成功！已使用在线大号 {alt_id} 拉取到群组消息。")
                            fetched_ok = True
                            break
                    except Exception as alt_err:
                        print(f"[Bot审计] 降级大号 {alt_id} 尝试拉取消息失败或超时: {alt_err}")
                        continue
            if not fetched_ok:
                raise Exception(f"所有在线账号均不在此群组内，无法拉取消息：{client_err}")
        
        for msg in messages:
            if not msg:
                continue
            
            # 提取群置顶内容
            if getattr(msg, "pinned", False) and msg.text:
                pin_text = msg.text
                
            is_bot = False
            is_admin = False
            sender = None
            try:
                if msg.sender_id in admin_ids:
                    is_admin = True
                sender = msg.sender  # 直接读取内存中已缓存的发件人
                if sender:
                    if getattr(sender, "bot", False):
                        is_bot = True
                    elif getattr(sender, "username", None) and str(sender.username).lower().endswith("bot"):
                        is_bot = True
            except Exception:
                pass
                
            msg_text = msg.text or ""
            
            # 【引用过滤】
            if msg_text:
                msg_text = re.sub(r"^Reply to .*?:?\n", "", msg_text, flags=re.IGNORECASE)
                msg_text = re.sub(r"^Forwarded from .*?:?\n", "", msg_text, flags=re.IGNORECASE)
                
            msg_text = msg_text.strip()
            
            if not msg_text:
                continue
                
            # 【双重过滤】：如果是 Bot、管理员、或者是带违禁字眼的属于警告消息
            lower_text = msg_text.lower()
            is_warning = is_bot or is_admin or any(w in lower_text for w in ["deleted", "removed", "warn", "warning", "rules", "禁止", "警告", "违规", "删除", "屏蔽", "人机", "验证", "spam", "captcha"])
            
            if is_warning:
                sender_role = "管理员" if is_admin else "Bot"
                sender_name = getattr(sender, "username", None) or getattr(sender, "first_name", None) or "System"
                bot_warnings.append(f"[{msg.date.strftime('%m-%d %H:%M') if msg.date else ''}] {sender_name}({sender_role}): {msg_text[:200]}")
            else:
                # 普通散客用户历史发言长度统计 (使用 UTF-8 字节数保存)
                # 仅保留最近 20 条非 admin 非 bot 发言作为统计样本
                if len(human_message_bytes) < 20:
                    utf8_bytes = len(msg_text.encode('utf-8'))
                    human_message_bytes.append(utf8_bytes)
                
        # 计算普通人类最长正常发言长度 (UTF-8 字节)
        max_human_bytes = max(human_message_bytes) if human_message_bytes else 0
                    
        context_lines = []
        if pin_text:
            context_lines.append(f"【群置顶公告】:\n{pin_text}")
        if bot_warnings:
            context_lines.append("【Bot/管理员发言限制警告记录】:\n" + "\n".join(bot_warnings[:20]))
            
        context_lines.append(f"【普通用户历史正常发言长度统计】:\n- 扫描到的非 Bot 用户最长成功发言字节数为: {max_human_bytes} 字节。")
            
        context_str = "\n\n".join(context_lines).strip()

        # ==================== 本地规则静态提取引擎 (Local Static Parser) ====================
        local_rules = default_json.copy()
        local_rules["max_length"] = max_human_bytes # 以散客发言最大 UTF-8 字节兜底
        
        # 合并分析的全部文本
        full_audit_context = (pin_text + "\n" + "\n".join(bot_warnings)).lower()
        
        # 1. 提取字数硬限制正则
        # 寻找诸如 "limit 200", "max 150", "不超过 300 字节", "不超过 200 字", "不超过200字", "字数限制: 200" 等特征
        limit_matches = re.findall(r"(?:limit|max|不超过|超过|字数限制|限制)\s*(?:字符|字|bytes)?\s*[:：]?\s*(\d+)", full_audit_context)
        for m in limit_matches:
            val = int(m)
            if 10 <= val <= 2000: # 过滤不合理的值
                # 如果明确指出是字数限制，且可能为中文字符，粗略将其转换为字节保护 (乘以 3 字节)
                if "字" in full_audit_context or "字符" in full_audit_context:
                    local_rules["max_length"] = val * 3
                else:
                    local_rules["max_length"] = val
                break
                
        # 2. 禁链接正则匹配
        if any(w in full_audit_context for w in ["no link", "no url", "banned link", "禁止链接", "禁链接", "不要发链接", "不允许链接", "禁止发送链接", "禁止url", "banned url"]):
            local_rules["banned_links"] = True
            
        # 3. 禁媒体正则匹配
        if any(w in full_audit_context for w in ["no media", "no photo", "no video", "no voice", "禁止媒体", "禁媒体", "禁止图片", "禁图片", "禁止视频", "banned photo", "banned media"]):
            local_rules["banned_media"] = True
            
        # 4. 敏感词匹配
        if any(w in full_audit_context for w in ["sensitive", "forbidden word", "违禁词", "敏感词", "违规词", "警告"]):
            local_rules["has_sensitive_words"] = True
            
        # ===================================================================================

        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            try:
                from pathlib import Path
                config_path = Path(__file__).resolve().parent / "config.json"
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                        api_key = config_data.get("deepseek_api_key", "").strip()
            except Exception:
                pass
                
        api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1").strip()
        
        summary_json_str = json.dumps(local_rules, ensure_ascii=False)
        if context_str and api_key:
            print(f"[Bot审计] 抓取到置顶/警告背景日志，正在向 DeepSeek 请求智能审计归纳...", flush=True)
            ai_res = await call_deepseek_api_rules(api_key, api_base, group_title, context_str)
            
            # 校验是否为合法 JSON
            try:
                parsed = json.loads(ai_res)
                # 校验核心键，确保不缺字段
                for k in ["max_length", "has_sensitive_words", "banned_links", "banned_media", "other_rules"]:
                    if k not in parsed:
                        parsed[k] = local_rules[k]
                        
                # 智能审计的 max_length 如果是 0，或者偏小，进行安全保护
                if int(parsed.get("max_length", 0)) == 0 and max_human_bytes > 0:
                    parsed["max_length"] = max_human_bytes
                    
                summary_json_str = json.dumps(parsed, ensure_ascii=False)
                print(f"[Bot审计] DeepSeek 规则提取成功 JSON: {summary_json_str}", flush=True)
            except Exception as json_err:
                print(f"[Bot审计] DeepSeek 返回非标准 JSON，降级为本地规则提取结构。AI原始返回: {ai_res}", flush=True)
        else:
            print(f"[Bot审计] 未检测到 API 密钥或公告背景，采用本地正则逻辑提取 JSON结果: {summary_json_str}", flush=True)
            
        return summary_json_str, context_str[:3500]
    except Exception as e:
        print(f"[Bot审计] 发生异常: {e}", flush=True)
        return json.dumps(default_json, ensure_ascii=False), f"Error: {e}"


async def solve_group_join_requirements(client, entity) -> bool:
    """
    智能检测并破解加群后的人机验证与前置门槛限制（如：自动点击 inline 验证按钮、自动加绑定频道）
    本逻辑为纯单次触发，不挂载任何事件订阅，任务执行完会话立刻归于静默。
    """
    import asyncio
    import re
    import random
    from telethon.tl.functions.channels import JoinChannelRequest

    try:
        # 获取我的 ID 和 username
        me = await client.get_me()
        my_id = me.id
        my_username = (me.username or "").lower()

        # 1. 刚加群，先微睡 2 秒，等待群里验证 Bot 响应并将消息推出来
        await asyncio.sleep(2.0)

        # 2. 主动拉取本群最近 15 条消息
        messages = await client.get_messages(entity, limit=15)
        if not messages:
            return False

        for msg in messages:
            if not msg:
                continue

            # 判断消息发送者是否为 Bot
            is_bot = False
            sender = msg.sender
            if sender:
                if getattr(sender, "bot", False):
                    is_bot = True
                else:
                    username = getattr(sender, "username", None)
                    if username and str(username).lower().endswith("bot"):
                        is_bot = True

            if not is_bot:
                continue

            msg_text = msg.text or ""
            is_for_me = False

            # 判断是否是针对我们的验证码（@我，包含我的ID，包含我的首名，或者有加群常见指令）
            if str(my_id) in msg_text or my_username in msg_text.lower():
                is_for_me = True
            elif me.first_name and me.first_name.lower() in msg_text.lower():
                is_for_me = True
            elif any(kw in msg_text.lower() for kw in ["human", "robot", "captcha", "verify", "click", "验证", "机器人", "加群", "防垃圾"]):
                is_for_me = True

            if not is_for_me:
                continue

            # === 破解情况 A: 含有 inline 验证按钮 ===
            if msg.buttons:
                for row in msg.buttons:
                    for button in row:
                        btn_text = (button.text or "").lower()
                        # 查找是否有验证、人机、已阅读、已加入、确认等通过关键字
                        if any(kw in btn_text for kw in ["verify", "human", "click", "验证", "阅读", "通过", "确认", "joined", "已加入", "人机", "解除", "解除禁言"]):
                            # 模拟人类，延迟 1.5 - 3.5 秒点击
                            delay = random.uniform(1.5, 3.5)
                            print(f"[验证破解] 检测到本账号进群验证按钮: '{button.text}'，模拟人类延迟 {delay:.2f} 秒后点击...")
                            await asyncio.sleep(delay)
                            await button.click()
                            print(f"[验证破解] 成功点击验证按钮: '{button.text}'")
                            return True

            # === 破解情况 B: 强制要求关注关联频道 ===
            # 正则提取形如 @username 或 t.me/username 的内容
            channels = re.findall(r"@([a-zA-Z0-9_]{5,})", msg_text)
            links = re.findall(r"t\.me/([a-zA-Z0-9_]{5,})", msg_text)
            all_targets = list(set(channels + links))

            joined_any = False
            for target in all_targets:
                # 排除验证 Bot 自身和常见的官方前缀，防止误入
                if target.lower() in ["shieldybot", "missrose_bot", "rosepaychannel", "rosepay"]:
                    continue
                try:
                    target_entity = await client.get_entity(target)
                    await client(JoinChannelRequest(channel=target_entity))
                    print(f"[验证破解] 检测到前置发言限制，自动关注了频道: @{target}")
                    joined_any = True
                except Exception as join_err:
                    print(f"[验证破解] 自动关注频道 @{target} 失败: {join_err}")

            if joined_any:
                # 关注关联频道后，再次微睡并拉取，检查是否有 "I have joined" / "已加入" 等二级确认按钮，如果有则点击
                await asyncio.sleep(2.0)
                msg_refresh = await client.get_messages(entity, ids=msg.id)
                if msg_refresh and msg_refresh.buttons:
                    for row in msg_refresh.buttons:
                        for button in row:
                            btn_text = (button.text or "").lower()
                            if any(kw in btn_text for kw in ["joined", "verify", "确认", "已加入", "通过"]):
                                delay = random.uniform(1.5, 3.0)
                                await asyncio.sleep(delay)
                                await button.click()
                                print(f"[验证破解] 关注频道后，成功点击二级确认按钮: '{button.text}'")
                return True

    except Exception as e:
        print(f"[验证破解] 破解入群发言门槛时发生异常: {e}")

    return False
