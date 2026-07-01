from __future__ import annotations

import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "rosepay.db"

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

STATIC_PROXY_TYPE = os.environ.get("ROSEPAY_STATIC_PROXY_TYPE", "socks5").strip() or "socks5"
STATIC_PROXY_PORT = int(os.environ.get("ROSEPAY_STATIC_PROXY_PORT", "50101") or "50101")
STATIC_PROXY_USERNAME = os.environ.get("ROSEPAY_STATIC_PROXY_USERNAME", "easonsenli").strip()
STATIC_PROXY_PASSWORD = os.environ.get("ROSEPAY_STATIC_PROXY_PASSWORD", "Mz8biy6nTn")


def is_static_proxy_host(host: str | None) -> bool:
    return str(host or "").strip() in STATIC_PROXY_HOSTS


def is_local_or_direct_proxy(proxy: dict[str, Any]) -> bool:
    host = str(proxy.get("host") or "").strip().lower()
    enabled = bool(proxy.get("enabled"))
    if not enabled:
        return True
    return host in {"", "127.0.0.1", "localhost", "::1"}


def is_safe_static_proxy(proxy: dict[str, Any]) -> bool:
    if not proxy or not bool(proxy.get("enabled")):
        return False
    host = str(proxy.get("host") or "").strip()
    try:
        port = int(proxy.get("port") or 0)
    except Exception:
        port = 0
    return is_static_proxy_host(host) and port > 0


def normalize_static_proxy(host: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "type": STATIC_PROXY_TYPE,
        "host": host,
        "port": STATIC_PROXY_PORT,
        "username": STATIC_PROXY_USERNAME,
        "password": STATIC_PROXY_PASSWORD,
    }


def infer_account_id(config: dict[str, Any], account_id: str | None = None) -> str:
    if account_id:
        return str(account_id)
    for key in ("id", "account_id"):
        value = config.get(key)
        if value:
            return str(value)
    session_name = str(config.get("session_name") or "")
    parts = Path(session_name.replace("\\", "/")).parts
    if "sessions" in parts:
        idx = parts.index("sessions")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def static_proxy_usage_counts(current_account_id: str = "", db_path: Path = DB_PATH) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not db_path.exists():
        return counts
    try:
        with sqlite3.connect(str(db_path), timeout=3.0) as conn:
            conn.row_factory = sqlite3.Row
            cols = [row[1] for row in conn.execute("pragma table_info(accounts)")]
            if "proxy_host" not in cols:
                return counts
            id_col = "id" if "id" in cols else None
            query = "select proxy_host"
            if id_col:
                query += ", id"
            query += " from accounts where coalesce(proxy_host, '') != ''"
            for row in conn.execute(query):
                row_account_id = str(row["id"]) if id_col else ""
                if current_account_id and row_account_id == current_account_id:
                    continue
                host = str(row["proxy_host"] or "").strip()
                if is_static_proxy_host(host):
                    counts[host] += 1
    except Exception:
        return counts
    return counts


def choose_runtime_proxy_host(current_account_id: str = "") -> tuple[str, str]:
    counts = static_proxy_usage_counts(current_account_id)
    for host in STATIC_PROXY_HOSTS:
        if counts.get(host, 0) <= 0:
            return host, "idle"
    host = min(STATIC_PROXY_HOSTS, key=lambda item: (counts.get(item, 0), STATIC_PROXY_HOSTS.index(item)))
    return host, "borrowed"


def runtime_proxy_candidates(preferred_host: str | None = None, current_account_id: str = "") -> list[dict[str, Any]]:
    counts = static_proxy_usage_counts(current_account_id)
    ordered_hosts: list[str] = []
    preferred_host = str(preferred_host or "").strip()
    if is_static_proxy_host(preferred_host):
        ordered_hosts.append(preferred_host)

    for host in STATIC_PROXY_HOSTS:
        if host not in ordered_hosts and counts.get(host, 0) <= 0:
            ordered_hosts.append(host)

    remaining = [
        host
        for host in STATIC_PROXY_HOSTS
        if host not in ordered_hosts
    ]
    remaining.sort(key=lambda item: (counts.get(item, 0), STATIC_PROXY_HOSTS.index(item)))
    ordered_hosts.extend(remaining)
    return [normalize_static_proxy(host) for host in ordered_hosts]


def ensure_safe_telegram_proxy_config(
    config: dict[str, Any],
    *,
    account_id: str | None = None,
    allow_runtime_borrow: bool = True,
) -> dict[str, Any]:
    account_id = infer_account_id(config, account_id)
    proxy = dict(config.get("proxy") or {})
    if is_safe_static_proxy(proxy):
        config["proxy"] = {
            **normalize_static_proxy(str(proxy.get("host")).strip()),
            **proxy,
            "enabled": True,
        }
        config["_runtime_proxy_source"] = "configured"
        config["_runtime_proxy_candidates"] = runtime_proxy_candidates(proxy.get("host"), account_id)
        return config

    if not allow_runtime_borrow:
        raise RuntimeError("账号未绑定静态代理，且当前操作禁止临时借用代理。")

    host, source = choose_runtime_proxy_host(account_id)
    config["proxy"] = normalize_static_proxy(host)
    config["_runtime_proxy_source"] = source
    config["_runtime_proxy_borrowed"] = source == "borrowed"
    config["_runtime_proxy_candidates"] = runtime_proxy_candidates(host, account_id)
    return config


def safe_proxy_summary(config: dict[str, Any]) -> str:
    proxy = config.get("proxy") or {}
    host = str(proxy.get("host") or "").strip()
    port = str(proxy.get("port") or "").strip()
    source = str(config.get("_runtime_proxy_source") or "configured")
    label = "临时借用" if source == "borrowed" else ("空闲分配" if source == "idle" else "已绑定")
    return f"{label} {host}:{port}"
