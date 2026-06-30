import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from telethon.tl import functions, types

# Headers to make Bing think we are a standard browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def scrape_links_by_keywords_for_page(keywords: list[str], page: int) -> list[str]:
    """
    Scrapes Bing, DuckDuckGo (page 0 only), and Yahoo search engines for t.me link results matching keywords
    specifically for a given page index (0-indexed).
    """
    found_links = set()
    cleaned_keywords = [kw.strip() for kw in keywords if kw.strip()]
    if not cleaned_keywords:
        return []

    tme_pattern = re.compile(
        r'(?:t\.me|telegram\.me)/(?:joinchat/|\+)?([a-zA-Z0-9_\+]{5,32})',
        re.IGNORECASE
    )

    for kw in cleaned_keywords:
        query = f"site:t.me {kw}"
        encoded_query = urllib.parse.quote_plus(query)
        first_index = page * 10 + 1
        
        # 1. Search Bing
        url = f"https://www.bing.com/search?q={encoded_query}&first={first_index}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if "t.me/" in href or "telegram.me/" in href:
                        match = tme_pattern.search(href)
                        if match:
                            clean_href = href.split("?")[0].strip()
                            if clean_href.endswith("/"):
                                clean_href = clean_href[:-1]
                            found_links.add(clean_href)
            time.sleep(0.5)
        except Exception as e:
            print(f"[Scraper] Error scraping Bing page {page} for query '{query}': {e}")

        # 2. Search DuckDuckGo (only page 0)
        if page == 0:
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            try:
                ddg_response = requests.get(ddg_url, headers=HEADERS, timeout=10)
                if ddg_response.status_code == 200:
                    ddg_soup = BeautifulSoup(ddg_response.text, "html.parser")
                    for a_tag in ddg_soup.find_all("a", href=True):
                        href = a_tag["href"]
                        if "t.me" in href or "telegram.me" in href:
                            decoded_url = urllib.parse.unquote(href)
                            match = re.search(r'(https?://(?:t\.me|telegram\.me)/(?:joinchat/|\+)?([a-zA-Z0-9_\+]{5,32}))', decoded_url, re.IGNORECASE)
                            if match:
                                clean_href = match.group(1).strip()
                                if clean_href.endswith("/"):
                                    clean_href = clean_href[:-1]
                                clean_href = clean_href.replace("t.me/s/", "t.me/")
                                found_links.add(clean_href)
                time.sleep(0.5)
            except Exception as e:
                print(f"[Scraper] Error scraping DDG page {page} for query '{query}': {e}")

        # 3. Search Yahoo
        yahoo_url = f"https://search.yahoo.com/search?p={encoded_query}&b={first_index}"
        try:
            yahoo_response = requests.get(yahoo_url, headers=HEADERS, timeout=10)
            if yahoo_response.status_code == 200:
                yahoo_soup = BeautifulSoup(yahoo_response.text, "html.parser")
                for a_tag in yahoo_soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if "t.me" in href or "telegram.me" in href:
                        decoded_url = urllib.parse.unquote(href)
                        match = re.search(r'(https?://(?:t\.me|telegram\.me)/(?:joinchat/|\+)?([a-zA-Z0-9_\+]{5,32}))', decoded_url, re.IGNORECASE)
                        if match:
                            clean_href = match.group(1).strip()
                            if clean_href.endswith("/"):
                                clean_href = clean_href[:-1]
                            clean_href = clean_href.replace("t.me/s/", "t.me/")
                            found_links.add(clean_href)
            time.sleep(0.5)
        except Exception as e:
            print(f"[Scraper] Error scraping Yahoo page {page} for query '{query}': {e}")

    return sorted(list(found_links))


def scrape_links_by_keywords(keywords: list[str], max_pages: int = 2) -> list[str]:
    """
    Scrapes Bing, DuckDuckGo, and Yahoo search engines for t.me link results matching keywords.
    Returns a list of unique t.me links.
    """
    found_links = set()
    for page in range(max_pages):
        page_links = scrape_links_by_keywords_for_page(keywords, page)
        found_links.update(page_links)
    return sorted(list(found_links))


async def fetch_group_messages(client, entity_username: str) -> dict:
    """
    Retrieves entity information (title, description, member count)
    and the last 15 messages from a public group without joining it.
    """
    try:
        # Resolve username/entity
        entity = await client.get_entity(entity_username)
        
        # Check if it is a channel or group (we want groups/channels, but primarily groups)
        is_channel = isinstance(entity, types.Channel)
        is_chat = isinstance(entity, types.Chat)
        
        if not (is_channel or is_chat):
            raise ValueError("Entity is not a Chat or Channel.")

        # Determine if it is a channel or group
        is_broadcast_channel = False
        if is_channel and getattr(entity, 'broadcast', False):
            is_broadcast_channel = True
        group_type = "channel" if is_broadcast_channel else "group"

        # Get full channel info (to retrieve description/about and participant count)
        description = ""
        member_count = 0
        
        if is_channel:
            full_entity = await client(functions.channels.GetFullChannelRequest(channel=entity))
            description = getattr(full_entity.full_chat, 'about', '') or ""
            member_count = getattr(full_entity.full_chat, 'participants_count', 0) or 0
        elif is_chat:
            full_entity = await client(functions.messages.GetFullChatRequest(chat_id=entity.id))
            description = getattr(full_entity.full_chat, 'about', '') or ""
            member_count = len(getattr(full_entity.full_chat.participants, 'participants', []))
            
        title = getattr(entity, 'title', '') or ""
        
        # Fetch up to 150 messages from the past 7 days
        import datetime
        import asyncio
        limit_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        messages_data = []
        max_messages_limit = 150
        fetched_count = 0

        try:
            async for msg in client.iter_messages(entity, limit=max_messages_limit):
                if msg.date and msg.date < limit_date:
                    break
                
                messages_data.append({
                    "sender_id": msg.sender_id or 0,
                    "text": msg.text or "",
                    "date": msg.date.isoformat() if msg.date else ""
                })
                fetched_count += 1
                if fetched_count % 50 == 0:
                    await asyncio.sleep(0.5)
        except Exception as msg_err:
            print(f"[Scraper] Failed to fetch messages for {entity_username}: {msg_err}")

        # Check activity based on messages
        is_active = False
        is_dead = True
        try:
            newest_msg = None
            async for m in client.iter_messages(entity, limit=1):
                newest_msg = m
                break
                
            if newest_msg and newest_msg.date:
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                delta = now_utc - newest_msg.date
                
                if delta.days <= 7:
                    is_active = True
                    is_dead = False
                elif delta.days <= 30:
                    is_active = False
                    is_dead = False
                else:
                    is_active = False
                    is_dead = True
            else:
                is_active = False
                is_dead = True
        except Exception as act_err:
            print(f"[Scraper] Failed to check activity for {entity_username}: {act_err}")
            is_active = True
            is_dead = False
            
        return {
            "success": True,
            "title": title,
            "description": description,
            "member_count": member_count,
            "messages": messages_data,
            "group_type": group_type,
            "is_active": is_active,
            "is_dead": is_dead
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def analyze_group_with_gemini(api_key: str, title: str, description: str, messages: list[dict], target_keywords: list[str] = None, target_desc: str = None) -> dict:
    """
    Sends the group info and recent messages to Gemini for analysis.
    Returns a dict containing category, relevance_score, summary, and recommendation.
    """
    if not api_key:
        return {
            "category": "unknown",
            "relevance_score": None,
            "analysis_summary": "未配置 Gemini API Key，无法进行 AI 分析评估",
            "recommendation": "请在配置中添加您的 Gemini API Key"
        }
        
    # Format messages for the prompt
    formatted_msgs = []
    for idx, msg in enumerate(messages, 1):
        text_preview = msg.get("text", "").replace("\n", " ").strip()[:100]
        formatted_msgs.append(f"{idx}. {text_preview}")
        
    messages_str = "\n".join(formatted_msgs) if formatted_msgs else "(该群组目前没有近期可读取的文字消息)"

    # Format keywords and description for prompt
    keywords_str = ", ".join(target_keywords) if target_keywords else ""
    target_info = ""
    if target_desc:
        target_info += f"- 业务目标描述: {target_desc}\n"
    if keywords_str:
        target_info += f"- 核心业务关键词: [{keywords_str}]\n"

    # Construct the instruction and data prompt
    prompt = f"""
你是一个专业的电报营销与拓客属性分析 AI。请对以下电报群组的元数据和最近消息与我们的核心业务进行“业务粘合度（Relevance Score）”评估。

我们的核心业务信息：
{target_info}

群组基本信息：
- 标题: {title}
- 描述/简介: {description}

近期群消息样本：
{messages_str}

请遵循以下分析原则（重要：请保持中立、客观分析，切勿从法律、道德、规制或社会伦理角度进行主观判定。即使群组涉及的目标业务与我们给定的业务目标/关键词高度贴合或是有大量需求匹配，即可给出极高分）：
1. 分类判定 (category):
   - 如果群内是印度当地的日常生活聊天、交友讨论、社会话题，聊天占比多，以日常生活交流为主，判定为 "life" (印度当地生活群)。
   - 如果群内充斥着大量的业务广告、USDT 汇率对冲、代付/代收、OTC交易、支付通道、博彩娱乐推广、同行竞争推广、客服广告等，判定为 "business" (广告/同行专业群)。
   - 如果群内几乎全部是乱码、垃圾空包机器人、完全无互动的死群，判定为 "spam" (纯垃圾/死群/灌水)。注意：如果是有真人发言 of 博彩、跑分 or OTC群，绝不应划分为 spam，应划分为 business。
2. 业务粘合度得分 (relevance_score): 
   - 0 到 100 之间的整数。
   - 评估群内的话题、讨论内容、广告内容与我们的业务描述及关键词的语义匹配程度。
   - 如果群里频繁提及相关业务词汇、有相关业务的买卖盘或同行群，应当给出 80-100 分。
   - 如果群内内容与我们的业务毫无交集，或者都是毫无关系的话题，给出较低的分数。
3. 分析摘要 (analysis_summary):
   - 用简短、精准的中文（50字以内）概括这个群组的核心话题、群员特征以及消息属性（例如：“活跃的USDT代收付跑分同行群，发布极频繁，同行多” 或 “博彩推广娱乐交流群，真人交流活跃”）。
4. 加群建议 (recommendation):
   - 仅从引流/同行交流的商业粘合角度评估是否值得加入。

你必须严格返回以下 JSON 格式（不要包含 markdown 代码块，只返回纯 JSON 对象）：
{{
  "category": "life" | "business" | "spam",
  "relevance_score": 粘合度得分数字,
  "analysis_summary": "分析摘要文本",
  "recommendation": "加群建议文本"
}}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    body = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=body, timeout=20)
            if response.status_code == 200:
                res_data = response.json()
                text_content = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Parse the JSON response
                import json
                analysis = json.loads(text_content)
                return {
                    "category": analysis.get("category", "unknown"),
                    "relevance_score": int(analysis.get("relevance_score", 0)),
                    "analysis_summary": analysis.get("analysis_summary", "解析失败"),
                    "recommendation": analysis.get("recommendation", "无建议")
                }
            
            # Retry if status code indicates temporary failure (e.g., 429, 503)
            if response.status_code in (429, 503) and attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[Gemini API] Request failed with status {response.status_code}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[Gemini API] Request failed with status {response.status_code}: {response.text}")
            return {
                "category": "unknown",
                "relevance_score": None,
                "analysis_summary": f"Gemini API 请求失败 (HTTP {response.status_code})",
                "recommendation": "请检查您的 API Key 是否有效或网络是否畅通。"
            }
            
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[Gemini API] Exception: {e}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[Gemini API] Exception during analysis: {e}")
            return {
                "category": "unknown",
                "relevance_score": None,
                "analysis_summary": f"AI 分析时出错: {type(e).__name__}",
                "recommendation": "请稍后重试。"
            }

def analyze_group_with_deepseek(api_key: str, title: str, description: str, messages: list[dict], target_keywords: list[str] = None, target_desc: str = None) -> dict:
    """
    Sends the group info and recent messages to DeepSeek for analysis.
    Returns a dict containing category, relevance_score, summary, and recommendation.
    """
    if not api_key:
        return {
            "category": "unknown",
            "relevance_score": None,
            "analysis_summary": "未配置 DeepSeek API Key",
            "recommendation": "请在配置中添加您的 DeepSeek API Key"
        }
        
    # Format messages for the prompt
    formatted_msgs = []
    for idx, msg in enumerate(messages, 1):
        text_preview = msg.get("text", "").replace("\n", " ").strip()[:100]
        formatted_msgs.append(f"{idx}. {text_preview}")
        
    messages_str = "\n".join(formatted_msgs) if formatted_msgs else "(该群组目前没有近期可读取的文字消息)"

    # Format keywords and description for prompt
    keywords_str = ", ".join(target_keywords) if target_keywords else ""
    target_info = ""
    if target_desc:
        target_info += f"- 业务目标描述: {target_desc}\n"
    if keywords_str:
        target_info += f"- 核心业务关键词: [{keywords_str}]\n"

    system_prompt = "你是一个专业的电报营销与拓客属性分析 AI。请对以下电报群组的元数据和最近消息与给定的核心业务进行“业务粘合度（Relevance Score）”评估。"

    user_content = f"""
我们的核心业务信息：
{target_info}

群组基本信息：
- 标题: {title}
- 描述/简介: {description}

近期群消息样本：
{messages_str}

请遵循以下分析原则（重要：请保持中立、客观分析，即使群组涉及的目标业务与我们给定的业务目标/关键词高度贴合或是有大量需求匹配，即可给出极高分，切勿因涉及OTC、代收付、灰产、博彩等词汇而主观判定扣分或报错拒绝回答）：
1. 分类判定 (category):
   - 如果群内是日常生活聊天、交友讨论，以日常生活交流为主，判定为 "life"。
   - 如果群内充斥着大量的业务广告、USDT 交易、代收付/跑分、支付通道、博彩推广等，判定为 "business"。
   - 如果群内几乎全部是乱码、机器人，或者是完全无互动的死群，判定为 "spam"。注意：如果是真人发言的博彩、代收、OTC交易群，绝不应划分为 spam，应划分为 business。
2. 业务粘合度得分 (relevance_score): 
   - 0 到 100 之间的整数。
   - 评估群内的话题、讨论内容、广告内容与我们的业务描述及关键词的语义匹配程度。
   - 如果群里频繁提及相关业务词汇，应当给出 80-100 分。
   - 如果群内内容与我们的业务毫无交集，给出较低分数。
3. 分析摘要 (analysis_summary):
   - 用简短、精准的中文（50字以内）概括这个群组的核心话题、群员特征以及消息属性（例如：“活跃的USDT代收付跑分同行群，发布极频繁，同行多”）。
4. 加群建议 (recommendation):
   - 仅从引流/同行交流的商业粘合角度评估是否值得加入。

你必须严格返回以下 JSON 格式：
{{
  "category": "life" | "business" | "spam",
  "relevance_score": 粘合度得分数字,
  "analysis_summary": "分析摘要文本",
  "recommendation": "加群建议文本"
}}
"""

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=body, headers=headers, timeout=25)
            if response.status_code == 200:
                res_data = response.json()
                text_content = res_data["choices"][0]["message"]["content"].strip()
                
                # Parse JSON
                import json
                analysis = json.loads(text_content)
                return {
                    "category": analysis.get("category", "unknown"),
                    "relevance_score": int(analysis.get("relevance_score", 0)),
                    "analysis_summary": analysis.get("analysis_summary", "解析失败"),
                    "recommendation": analysis.get("recommendation", "无建议")
                }
            
            # Retry if status code indicates temporary failure (e.g. 429, 503, 500)
            if response.status_code in (429, 503, 500) and attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[DeepSeek API] Request failed with status {response.status_code}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[DeepSeek API] Request failed with status {response.status_code}: {response.text}")
            return {
                "category": "unknown",
                "relevance_score": None,
                "analysis_summary": f"DeepSeek API 请求失败 (HTTP {response.status_code})",
                "recommendation": "请检查您的 API Key 是否有效或网络/余额状况。"
            }
            
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[DeepSeek API] Exception: {e}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[DeepSeek API] Exception during analysis: {e}")
            return {
                "category": "unknown",
                "relevance_score": None,
                "analysis_summary": f"DeepSeek 评估出错: {type(e).__name__}",
                "recommendation": "请检查网络或稍后重试。"
            }

def generate_keyword_with_gemini(api_key: str, target_desc: str, searched_keywords: list[str]) -> dict:
    """
    Asks Gemini to think about the business target, look at recently searched keywords,
    and generate the next keyword to search, along with a brief explanation/reasoning.
    """
    if not api_key:
        return {
            "keyword": "",
            "reasoning": "未配置 Gemini API Key，无法进行自主拓展"
        }
        
    searched_str = ", ".join(searched_keywords) if searched_keywords else "(目前还没有进行过任何搜索)"
    
    prompt = f"""
你是一个专业的电报营销与自主拓客 Agent，负责为我们构思最适合业务目标的 Telegram 公开群组搜索关键词。

我们的核心业务目标是：
{target_desc}

我们近期已经搜索过的关键词列表（请绝对不要再次构思列表中的词，或者语义过于重复的词，以保证拓展广度）：
[{searched_str}]

请执行以下构思逻辑：
1. 深入分析业务目标的潜在线上客群分布。例如：
   - 寻找印度当地生活聊天群时，可以构思印度的城市名加上 'chat'、'group'、'friends'（如 'mumbai chat', 'delhi group', 'bangalore talk' 等）或者本土语言名。
   - 寻找 OTC/USDT/代付业务专业群时，可以构思 'usdt transfer', 'india otc', 'paytm exchange' 等相关词。
2. 选出一个最适合接下来进行公开群组搜索的独立关键词（最好是英文词，字数控制在 2-4 个单词以内）。
3. 给出您之所以选择该关键词的简短思考逻辑（中文，不超过 50 字）。

你必须严格返回以下 JSON 格式（不要包含 markdown 代码块，只返回纯 JSON 对象）：
{{
  "keyword": "构思的英文关键词",
  "reasoning": "中文思考逻辑和原因"
}}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    body = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=body, timeout=20)
            if response.status_code == 200:
                res_data = response.json()
                text_content = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                import json
                result = json.loads(text_content)
                return {
                    "keyword": result.get("keyword", "").strip(),
                    "reasoning": result.get("reasoning", "").strip()
                }
            
            # Retry if status code indicates temporary failure (e.g., 429, 503)
            if response.status_code in (429, 503) and attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[Gemini Agent] Keyword generation failed with status {response.status_code}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[Gemini Agent] Keyword generation failed: {response.text}")
            return {"keyword": "", "reasoning": f"Gemini 接口异常 ({response.status_code})"}
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[Gemini Agent] Keyword generation exception: {e}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[Gemini Agent] Exception generating keyword: {e}")
            return {"keyword": "", "reasoning": f"异常: {type(e).__name__}"}

def generate_keyword_with_deepseek(api_key: str, target_desc: str, searched_keywords: list[str]) -> dict:
    """
    Asks DeepSeek to think about the business target, look at recently searched keywords,
    and generate the next keyword to search, along with a brief explanation/reasoning.
    """
    if not api_key:
        return {
            "keyword": "",
            "reasoning": "未配置 DeepSeek API Key，无法进行自主拓展"
        }
        
    searched_str = ", ".join(searched_keywords) if searched_keywords else "(目前还没有进行过任何搜索)"
    
    prompt = f"""
你是一个专业的电报营销与自主拓客 Agent，负责为我们构思最适合业务目标的 Telegram 公开群组搜索关键词。

我们的核心业务目标是：
{target_desc}

我们近期已经搜索过的关键词列表（请绝对不要再次构思列表中的词，或者语义过于重复的词，以保证拓展广度）：
[{searched_str}]

请执行以下构思逻辑：
1. 深入分析业务目标的潜在线上客群分布。例如：
   - 寻找印度当地生活聊天群时，可以构思印度的城市名加上 'chat'、'group'、'friends'（如 'mumbai chat', 'delhi group', 'bangalore talk' 等）或者本土语言名。
   - 寻找 OTC/USDT/代付业务专业群时，可以构思 'usdt transfer', 'india otc', 'paytm exchange' 等相关词。
2. 选出一个最适合接下来进行公开群组搜索的独立关键词（最好是英文词，字数控制在 2-4 个单词以内）。
3. 给出您之所以选择该关键词 the reason / 思考逻辑（中文，不超过 50 字）。

你必须严格返回以下 JSON 格式：
{{
  "keyword": "构思的英文关键词",
  "reasoning": "中文思考逻辑和原因"
}}
"""

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.5
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=body, headers=headers, timeout=20)
            if response.status_code == 200:
                res_data = response.json()
                text_content = res_data["choices"][0]["message"]["content"].strip()
                
                import json
                result = json.loads(text_content)
                return {
                    "keyword": result.get("keyword", "").strip(),
                    "reasoning": result.get("reasoning", "").strip()
                }
            
            # Retry if status code indicates temporary failure (e.g., 429, 503)
            if response.status_code in (429, 503) and attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[DeepSeek Agent] Keyword generation failed with status {response.status_code}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[DeepSeek Agent] Keyword generation failed: {response.text}")
            return {"keyword": "", "reasoning": f"DeepSeek 接口异常 ({response.status_code})"}
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"[DeepSeek Agent] Keyword generation exception: {e}. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
                continue
                
            print(f"[DeepSeek Agent] Exception generating keyword: {e}")
            return {"keyword": "", "reasoning": f"异常: {type(e).__name__}"}


def calculate_scraped_group_metrics(member_count: int, messages: list[dict], keywords: list[str], api_relevance_score: int = None, group_type: str = "group", is_dead: bool = False) -> dict:
    import datetime
    
    # 1. Relevance Score (粘合度)
    if api_relevance_score is not None:
        relevance_score = api_relevance_score
    else:
        # Fallback local TF-IDF / Keyword frequency score
        if not messages or not keywords:
            relevance_score = 0
        else:
            matching_msgs = 0
            for m in messages:
                text = m.get('text', '').lower()
                if any(kw.lower() in text for kw in keywords):
                    matching_msgs += 1
            
            match_ratio = matching_msgs / len(messages)
            relevance_score = min(100, int(match_ratio * 250))
            
    # If it is a channel, bypass activity, engagement and spam penalty
    if group_type == "channel":
        return {
            "relevance_score": relevance_score,
            "activity_score": 0,
            "engagement_score": 0,
            "spam_penalty": 0,
            "quality_score": 0 if is_dead else relevance_score
        }

            
    # 2. Activity Score (活跃度)
    if not messages:
        activity_score = 0
        daily_avg = 0.0
    else:
        dates = []
        for m in messages:
            date_str = m.get('date', '')
            if date_str:
                try:
                    dt = datetime.datetime.fromisoformat(date_str)
                    dates.append(dt)
                except Exception:
                    pass
        
        dates.sort()
        
        if len(dates) >= 2:
            timespan_days = (dates[-1] - dates[0]).total_seconds() / 86400.0
        else:
            timespan_days = 7.0
            
        max_messages_limit = 150
        if len(messages) >= max_messages_limit:
            if timespan_days > 0.01:
                daily_avg = len(messages) / timespan_days
            else:
                daily_avg = len(messages) * 10
        else:
            daily_avg = len(messages) / 7.0
            
        activity_score = min(100, int((daily_avg / 100.0) * 100))
        
    # 3. Engagement Score (互动率)
    unique_senders = len(set(m.get('sender_id') for m in messages if m.get('sender_id') != 0))
    
    if unique_senders <= 1:
        engagement_score = 0
    else:
        if member_count <= 0:
            engagement_score = 0
        else:
            target_senders = min(member_count * 0.1, 30.0)
            target_senders = max(2.0, target_senders)
            engagement_score = min(100, int((unique_senders / target_senders) * 100))
            
    # 4. Anti-Spam Deduction (反垃圾扣分)
    dup_penalty = 0
    link_penalty = 0
    flood_penalty = 0
    
    if messages:
        # A. Duplicate text deduction
        text_counts = {}
        for m in messages:
            txt = m.get('text', '').strip()
            if len(txt) >= 5:
                text_counts[txt.lower()] = text_counts.get(txt.lower(), 0) + 1
                
        dup_count = sum(count - 1 for count in text_counts.values() if count > 1)
        dup_ratio = dup_count / len(messages)
        if dup_ratio > 0.2:
            dup_penalty = int(dup_ratio * 50)
            
        # B. Pure links/promotion deduction
        link_count = 0
        for m in messages:
            t = m.get('text', '').lower()
            if "http://" in t or "https://" in t or "t.me/" in t or "@" in t:
                link_count += 1
        link_ratio = link_count / len(messages)
        if link_ratio > 0.3:
            link_penalty = int((link_ratio - 0.3) * 100)
            
        # C. Single user flooding deduction
        sender_counts = {}
        for m in messages:
            sid = m.get('sender_id', 0)
            if sid != 0:
                sender_counts[sid] = sender_counts.get(sid, 0) + 1
        
        if sender_counts:
            max_sender_msgs = max(sender_counts.values())
            sender_ratio = max_sender_msgs / len(messages)
            if sender_ratio > 0.8 and unique_senders > 1:
                flood_penalty = int((sender_ratio - 0.8) * 100)
                
    spam_penalty = min(100, dup_penalty + link_penalty + flood_penalty)
    
    # 5. Combined Quality Score (综合评分)
    if is_dead:
        quality_score = 0
    else:
        quality_score = int(relevance_score * 0.4 + activity_score * 0.3 + engagement_score * 0.3) - spam_penalty
        quality_score = max(0, min(100, quality_score))
    
    return {
        "relevance_score": relevance_score,
        "activity_score": activity_score,
        "engagement_score": engagement_score,
        "spam_penalty": spam_penalty,
        "quality_score": quality_score
    }



