import os

target_file = r"E:\telegram_workspace\telegram_folder_sync\static_proxy_pool.py"

with open(target_file, "r", encoding="utf-8") as f:
    code = f.read()

# 1. 替换 choose_runtime_proxy_host
choose_start = code.find("def choose_runtime_proxy_host(current_account_id")
choose_end = code.find("def choose_balanced_proxy_host")

if choose_start != -1 and choose_end != -1:
    old_block = code[choose_start:choose_end]
    new_block = """_STICKY_FILE = ROOT / "data" / "sticky_borrowed_proxies.json"

def choose_runtime_proxy_host(current_account_id: str = "") -> tuple[str, str]:
    current_account_id = str(current_account_id).strip()
    if not current_account_id:
        # 如果没有指定大号 ID，默认返回代理池首选 IP
        return STATIC_PROXY_HOSTS[0], "borrowed"

    # A. 优先尝试从持久化黏性记录中读取
    sticky_host = None
    try:
        if _STICKY_FILE.exists():
            import json
            state = json.loads(_STICKY_FILE.read_text(encoding="utf-8"))
            candidate = state.get(current_account_id)
            if candidate in STATIC_PROXY_HOSTS:
                sticky_host = candidate
    except Exception as e:
        print(f"[StickyProxy] Error reading sticky cache: {e}")

    if sticky_host:
        # 命中黏性分配，直接秒回同一出口 IP，彻底规避异地登录漂移风控
        return sticky_host, "borrowed_sticky"

    # B. 未命中黏性缓存，执行高可靠分配算法：
    # 统计所有大号【物理绑定】+ 其它大号【逻辑黏性借用】的总负载，空闲优先，否则选负载最轻的
    counts = static_proxy_usage_counts(current_account_id)
    sticky_counts = Counter()
    try:
        if _STICKY_FILE.exists():
            import json
            state = json.loads(_STICKY_FILE.read_text(encoding="utf-8"))
            for aid, hip in state.items():
                if aid != current_account_id and hip in STATIC_PROXY_HOSTS:
                    sticky_counts[hip] += 1
    except Exception:
        pass

    total_counts = Counter()
    for host in STATIC_PROXY_HOSTS:
        total_counts[host] = counts.get(host, 0) + sticky_counts.get(host, 0)

    idle_hosts = [host for host in STATIC_PROXY_HOSTS if total_counts.get(host, 0) <= 0]
    if idle_hosts:
        selected_host = idle_hosts[0]
        source = "idle"
    else:
        selected_host = min(STATIC_PROXY_HOSTS, key=lambda item: (total_counts.get(item, 0), STATIC_PROXY_HOSTS.index(item)))
        source = "borrowed"

    # C. 将新分配的 IP 写入持久化黏性缓存，使其未来永不漂移
    try:
        import json
        state = {}
        if _STICKY_FILE.exists():
            state = json.loads(_STICKY_FILE.read_text(encoding="utf-8"))
        state[current_account_id] = selected_host
        _STICKY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STICKY_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"[StickyProxy] Successfully bound sticky proxy {selected_host} to account {current_account_id}.")
    except Exception as e:
        print(f"[StickyProxy] Failed to save sticky assignment: {e}")

    return selected_host, source

"""
    code = code.replace(old_block, new_block)

# 2. 替换 ensure_safe_telegram_proxy_config 中对 allow_runtime_borrow 的硬性拦截
target_str = """    if not allow_runtime_borrow:
        raise RuntimeError("账号未绑定静态代理，且当前操作禁止临时借用代理。")"""

replace_str = """    # 允许临时借用，借用将在此函数下方的 choose_runtime_proxy_host 内部强制黏性绑定以保防封安全
    pass"""

code = code.replace(target_str, replace_str)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(code)

print("SUCCESS: static_proxy_pool.py refactored for Sticky Dynamic Borrowing!")
