from __future__ import annotations

import asyncio
import json
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.sessions import StringSession

from sync_folder_groups import (
    BUILTIN_TELEGRAM_DESKTOP_API_HASH,
    BUILTIN_TELEGRAM_DESKTOP_API_ID,
    choose_telegram_client_options,
    load_config,
    proxy_type_names,
    safe_print,
)


ROOT = Path(__file__).resolve().parent
TELEGRAM_TEST_TARGETS = [
    ("Telegram DC 1", "149.154.175.50", 443),
    ("Telegram DC 2", "149.154.167.50", 443),
    ("Telegram DC 3", "149.154.175.100", 443),
    ("Telegram DC 4", "149.154.167.91", 443),
    ("Telegram DC 5", "91.108.56.130", 443),
]


def ok(text: str) -> None:
    safe_print(f"[通过] {text}")


def fail(text: str) -> None:
    safe_print(f"[失败] {text}")


def warn(text: str) -> None:
    safe_print(f"[提示] {text}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_dns(host: str) -> bool:
    safe_print(f"\n1. DNS 解析测试：{host}")
    try:
        names, aliases, addresses = socket.gethostbyname_ex(host)
    except OSError as exc:
        fail(f"DNS 解析失败：{type(exc).__name__}: {exc}")
        return False
    ok(f"DNS 正常：{names} {aliases} {addresses}")
    return True


def test_tcp(name: str, host: str, port: int, timeout: float = 8.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok(f"{name} {host}:{port} 可连接")
            return True
    except OSError as exc:
        fail(f"{name} {host}:{port} 不可连接：{type(exc).__name__}: {exc}")
        return False


def test_direct_telegram_tcp() -> int:
    safe_print("\n2. Telegram 直连端口测试")
    passed = 0
    for name, host, port in TELEGRAM_TEST_TARGETS:
        if test_tcp(name, host, port):
            passed += 1
    safe_print(f"直连通过数量：{passed}/{len(TELEGRAM_TEST_TARGETS)}")
    return passed


def test_proxy_port(config: dict[str, Any]) -> bool | None:
    proxy = config.get("proxy") or {}
    if not proxy.get("enabled"):
        safe_print("\n3. 代理配置测试")
        warn("config.json 里 proxy.enabled=false，当前没有启用代理。")
        return None

    host = str(proxy.get("host", "")).strip()
    port = int(proxy.get("port", 0) or 0)
    safe_print(f"\n3. 代理配置测试：{host}:{port}")
    if not host or port <= 0:
        fail("代理已启用，但 host/port 配置无效。")
        return False
    warn(f"当前将使用 {proxy.get('type', 'socks5')} 代理：{host}:{port}")
    if str(proxy.get("type", "")).lower() == "auto":
        warn(f"自动探测顺序：{', '.join(proxy_type_names(config))}")
    if host in {"127.0.0.1", "localhost"} and port == 8800:
        warn("这是 QuickQ 常见系统代理端口。运行前请确认 QuickQ 已连接。")
    return test_tcp("本机代理端口", host, port, timeout=5.0)


async def test_telethon_connect(config: dict[str, Any]) -> bool:
    safe_print("\n4. Telethon 连接测试")
    auth_mode = config.get("auth_mode", "builtin_telegram_desktop")
    if auth_mode == "api_id_hash":
        api_id = int(config["api_id"])
        api_hash = config["api_hash"]
    else:
        api_id = BUILTIN_TELEGRAM_DESKTOP_API_ID
        api_hash = BUILTIN_TELEGRAM_DESKTOP_API_HASH

    try:
        options = await choose_telegram_client_options(config, api_id, api_hash)
        client = TelegramClient(StringSession(), api_id, api_hash, **options)
        await asyncio.wait_for(client.connect(), timeout=25)
        connected = client.is_connected()
        await client.disconnect()
    except Exception as exc:
        fail(f"Telethon 连接失败：{type(exc).__name__}: {exc}")
        return False

    if connected:
        ok("Telethon 已成功连接 Telegram。")
        return True
    fail("Telethon 未能建立连接。")
    return False


async def main() -> None:
    safe_print("========================================")
    safe_print("Telegram 网络诊断")
    safe_print("========================================")
    safe_print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print(f"目录：{ROOT}")

    config_path = ROOT / "config.json"
    if not config_path.exists():
        fail("找不到 config.json，请先运行 00_检测环境并安装依赖.cmd。")
        raise SystemExit(1)

    config = load_config(config_path)
    dns_ok = test_dns("telegram.org")
    direct_count = test_direct_telegram_tcp()
    proxy_ok = test_proxy_port(config)
    telethon_ok = await test_telethon_connect(config)

    safe_print("\n诊断结论：")
    if telethon_ok:
        ok("网络可以连接 Telegram。如果登录仍失败，重点检查手机号、验证码或 session。")
    elif proxy_ok is False:
        fail("代理已启用，但代理端口不可连接。请先打开代理软件，或修改 config.json 的代理端口。")
    elif direct_count == 0 and proxy_ok is None:
        fail("直连 Telegram 全部失败，且没有启用代理。请配置代理后重试。")
    elif dns_ok and direct_count > 0:
        warn("底层端口部分可通，但 Telethon 连接失败。可能是防火墙、代理规则或网络质量问题。")
    else:
        fail("当前机器网络不适合直接登录 Telegram，请检查 DNS、代理和防火墙。")

    safe_print("\n如果需要发给我排查，请把本窗口内容或 logs 里的诊断日志截图发来。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        safe_print("\n已取消。")
