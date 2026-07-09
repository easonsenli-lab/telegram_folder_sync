import os
import sys
import json
from pathlib import Path
from collections import Counter

# 静态代理池主机列表与凭证
STATIC_PROXY_HOSTS = [
    "212.68.183.252",
    "212.68.181.201",
    "212.68.181.75",
    "212.68.183.253",
    "212.68.181.43",
    "212.68.183.116",
    "212.68.183.106",
    "212.68.181.34",
    "212.68.181.30",
    "212.68.181.80",
]

PORT = 50101
USERNAME = "easonsenli"
PASSWORD = "Mz8biy6nTn"
PROXY_TYPE = "socks5"

def run_binding():
    print("==================== STARTING PERMANENT PROXY BINDING & CLEANING ====================")
    accounts_dir = Path("accounts")
    if not accounts_dir.exists():
        print("ERROR: accounts directory not found in current directory.")
        return
        
    config_files = list(accounts_dir.glob("*.json"))
    print(f"Found {len(config_files)} account configuration files.")
    
    # 1. 统计当前所有已被 ENABLED 账号使用的代理 IP 的频率
    active_ip_counts = Counter()
    configs_to_update = []
    
    for cfg_file in config_files:
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            proxy = data.get("proxy", {})
            enabled = False
            addr = None
            if isinstance(proxy, dict):
                enabled = proxy.get("enabled", False)
                addr = proxy.get("addr")
                
            if enabled and addr in STATIC_PROXY_HOSTS:
                active_ip_counts[addr] += 1
            else:
                configs_to_update.append((cfg_file, data))
        except Exception as e:
            print(f"Error reading {cfg_file.name}: {e}")
            
    print(f"Current proxy allocation frequencies: {dict(active_ip_counts)}")
    
    # 2. 为未绑定或 DISABLED 的大号进行永久均匀分配
    updated_count = 0
    for cfg_file, data in configs_to_update:
        # 轮询选出当前使用计数最少的代理 IP
        selected_ip = min(STATIC_PROXY_HOSTS, key=lambda ip: active_ip_counts[ip])
        
        # 强行覆盖并开启静态住宅代理
        data["proxy"] = {
            "enabled": True,
            "proxy_type": PROXY_TYPE,
            "addr": selected_ip,
            "port": PORT,
            "username": USERNAME,
            "password": PASSWORD
        }
        
        # 增加使用计数，确保下一个大号分配时保持均匀
        active_ip_counts[selected_ip] += 1
        
        # 写回磁盘
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"SUCCESS: Permanently bound proxy {selected_ip}:{PORT} to {cfg_file.name}")
            updated_count += 1
        except Exception as e:
            print(f"FAILED: Failed to write {cfg_file.name}: {e}")
            
    print(f"\\nPERMANENT BINDING COMPLETE: {updated_count} accounts updated and aligned!")
    print(f"Final proxy allocation frequencies: {dict(active_ip_counts)}")
    print("==================================================================================")

if __name__ == '__main__':
    run_binding()
