from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon.errors import (
    AuthKeyError,
    AuthKeyUnregisteredError,
    PhoneNumberBannedError,
    UserDeactivatedBanError,
    UserDeactivatedError,
)
from telethon import TelegramClient, functions, types, utils
from telethon.sessions import StringSession

BUILTIN_TELEGRAM_DESKTOP_API_ID = 2040
BUILTIN_TELEGRAM_DESKTOP_API_HASH = "b18441a1ff607e10a989891a5462e627"


def safe_print(text: str = "") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), flush=True)


def alert_block(title: str, lines: list[str]) -> str:
    width = max([len(title), *(len(line) for line in lines), 36])
    border = "!" * (width + 8)
    body = [border, f"!!! {title.center(width)} !!!"]
    body.extend(f"!!! {line.ljust(width)} !!!" for line in lines)
    body.append(border)
    return "\n".join(body)


@dataclass(frozen=True)
class GroupRecord:
    folder: str
    chat_id: int
    access_hash: int | None
    title: str
    username: str
    type: str
    enabled: bool
    last_seen_at: str
    last_sent_at: str = ""
    note: str = ""


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    required = ["auth_mode", "session_name", "folder_name", "output_csv", "output_db"]
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit(f"配置缺少必填项：{', '.join(missing)}")

    auth_mode = config.get("auth_mode", "api_id_hash")
    if auth_mode not in {"api_id_hash", "builtin_telegram_desktop", "telegram_desktop_tdata"}:
        raise SystemExit(
            "auth_mode 无效。请使用 api_id_hash、builtin_telegram_desktop 或 telegram_desktop_tdata。"
        )

    if auth_mode == "api_id_hash" and config.get("api_hash") == "replace_with_your_api_hash":
        raise SystemExit("请先编辑 config.json，填写 api_id 和 api_hash。")

    if auth_mode == "telegram_desktop_tdata" and not config.get("tdata_path"):
        raise SystemExit("telegram_desktop_tdata 登录模式需要设置 tdata_path。")

    return config


def resolve_path(base_dir: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else base_dir / path


def proxy_type_names(config: dict[str, Any]) -> list[str]:
    proxy_config = config.get("proxy") or {}
    if not proxy_config.get("enabled"):
        return []

    proxy_type = str(proxy_config.get("type", "socks5")).lower()
    if proxy_type == "auto":
        return ["http", "socks5", "socks4"]
    return [proxy_type]


def build_proxy(config: dict[str, Any], proxy_type: str | None = None) -> Any | None:
    proxy_config = config.get("proxy") or {}
    if not proxy_config.get("enabled"):
        return None

    try:
        import socks
    except ImportError as exc:
        raise SystemExit("代理已启用，但缺少代理依赖。请先运行 00_检测环境并安装依赖.cmd。") from exc

    proxy_type = (proxy_type or str(proxy_config.get("type", "socks5"))).lower()
    type_map = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http": socks.HTTP,
    }
    if proxy_type not in type_map:
        raise SystemExit("proxy.type 无效。请使用 auto、socks5、socks4 或 http。")

    host = str(proxy_config.get("host", "")).strip()
    port = int(proxy_config.get("port", 0))
    if not host or port <= 0:
        raise SystemExit("代理已启用，但 proxy.host 或 proxy.port 无效。")

    username = str(proxy_config.get("username", "")).strip() or None
    password = str(proxy_config.get("password", "")).strip() or None
    return (type_map[proxy_type], host, port, True, username, password)


def proxy_label(config: dict[str, Any], proxy_type: str | None = None) -> str:
    proxy_config = config.get("proxy") or {}
    if not proxy_config.get("enabled"):
        return "直连"
    host = str(proxy_config.get("host", "")).strip()
    port = int(proxy_config.get("port", 0) or 0)
    return f"{proxy_type or proxy_config.get('type', 'socks5')}://{host}:{port}"


def telegram_client_options(config: dict[str, Any], proxy_type: str | None = None) -> dict[str, Any]:
    timeout = int(config.get("connection_timeout_seconds", 30) or 30)
    retries = int(config.get("connection_retries", 5) or 5)
    return {
        "timeout": max(timeout, 5),
        "connection_retries": max(retries, 1),
        "retry_delay": 3,
        "proxy": build_proxy(config, proxy_type),
    }


async def choose_telegram_client_options(config: dict[str, Any], api_id: int, api_hash: str) -> dict[str, Any]:
    types_to_try = proxy_type_names(config)
    if not types_to_try or len(types_to_try) == 1:
        if types_to_try:
            safe_print(f"当前代理：{proxy_label(config, types_to_try[0])}")
        return telegram_client_options(config, types_to_try[0] if types_to_try else None)

    errors: list[str] = []
    for proxy_type in types_to_try:
        options = telegram_client_options(config, proxy_type)
        label = proxy_label(config, proxy_type)
        safe_print(f"正在测试代理：{label}")
        client = TelegramClient(StringSession(), api_id, api_hash, **options)
        try:
            await client.connect()
            if client.is_connected():
                await client.disconnect()
                safe_print(f"代理可用：{label}")
                return options
            errors.append(f"{label}: 未能建立连接")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
        finally:
            if client.is_connected():
                await client.disconnect()

    safe_print(
        alert_block(
            "TELEGRAM 代理全部失败",
            [
                "已经尝试 http、socks5、socks4，但都无法连接 Telegram。",
                "请确认 QuickQ 已连接，且 127.0.0.1:8800 端口可用。",
                *errors[:4],
            ],
        )
    )
    raise SystemExit(2)


def normalize_title(value: Any) -> str:
    if hasattr(value, "text"):
        return str(value.text)
    return str(value)


def format_user(user: Any) -> str:
    username = f"@{user.username}" if getattr(user, "username", None) else "（无用户名）"
    name = " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part)
    phone = getattr(user, "phone", None) or "（手机号隐藏）"
    return f"{name} {username} id={user.id} phone={phone}".strip()


async def check_account_status(client: TelegramClient) -> Any:
    try:
        me = await client.get_me()
    except (TimeoutError, ConnectionError, OSError) as exc:
        safe_print(
            alert_block(
                "TELEGRAM 连接超时",
                [
                    f"连接失败：{type(exc).__name__}",
                    "这通常不是绑定本机，也不是账号被封。",
                    "请检查当前机器网络、防火墙、代理或地区访问限制。",
                    "如需代理，请编辑 config.json 里的 proxy 配置后重试。",
                ],
            )
        )
        raise SystemExit(2) from exc
    except (PhoneNumberBannedError, UserDeactivatedBanError, UserDeactivatedError) as exc:
        safe_print(
            alert_block(
                "TELEGRAM 账号不可用",
                [
                    f"状态检查失败：{type(exc).__name__}",
                    "当前 session/账号不能继续使用。",
                    "请清除本地 session 后重新登录其他可用账号。",
                ],
            )
        )
        raise SystemExit(2) from exc
    except (AuthKeyUnregisteredError, AuthKeyError) as exc:
        safe_print(
            alert_block(
                "TELEGRAM 登录已失效",
                [
                    f"Session 检查失败：{type(exc).__name__}",
                    "请执行 --reset-session 后重新登录。",
                ],
            )
        )
        raise SystemExit(2) from exc

    if me is None:
        safe_print(
            alert_block(
                "TELEGRAM 登录已失效",
                [
                    "Telegram 没有返回当前用户信息。",
                    "请执行 --reset-session 后重新登录。",
                ],
            )
        )
        raise SystemExit(2)

    warnings: list[str] = []
    if bool(getattr(me, "deleted", False)):
        warnings.append("当前 Telegram 用户被标记为已删除。")
    if bool(getattr(me, "restricted", False)):
        warnings.append("当前 Telegram 用户被标记为受限。")

    restriction_reason = getattr(me, "restriction_reason", None)
    if restriction_reason:
        warnings.append(f"受限原因：{restriction_reason}")

    if warnings:
        safe_print(
            alert_block(
                "TELEGRAM 账号状态警告",
                [
                    *warnings,
                    "请先检查账号状态，再运行发送任务。",
                ],
            )
        )
        raise SystemExit(2)

    safe_print(f"当前登录账号：{format_user(me)}")
    return me


def folder_debug_line(item: Any) -> str:
    title = normalize_title(getattr(item, "title", ""))
    include_count = len(getattr(item, "include_peers", []) or [])
    pinned_count = len(getattr(item, "pinned_peers", []) or [])
    exclude_count = len(getattr(item, "exclude_peers", []) or [])
    flags = []
    for name in ["contacts", "non_contacts", "groups", "broadcasts", "bots", "exclude_muted", "exclude_read", "exclude_archived"]:
        if bool(getattr(item, name, False)):
            flags.append(name)
    return (
        f"- id={getattr(item, 'id', '?')} title={title!r} "
        f"include={include_count} pinned={pinned_count} exclude={exclude_count} "
        f"flags={','.join(flags) or '-'}"
    )


def entity_type(entity: Any) -> str:
    if isinstance(entity, types.Channel):
        if entity.megagroup:
            return "supergroup"
        if entity.broadcast:
            return "channel"
        return "channel"
    if isinstance(entity, types.Chat):
        return "group"
    if isinstance(entity, types.User):
        return "user"
    return type(entity).__name__


def entity_title(entity: Any) -> str:
    if isinstance(entity, types.User):
        return " ".join(part for part in [entity.first_name, entity.last_name] if part)
    return getattr(entity, "title", "") or ""


def entity_username(entity: Any) -> str:
    return getattr(entity, "username", "") or ""


def entity_access_hash(entity: Any) -> int | None:
    return getattr(entity, "access_hash", None)


async def peer_to_entity(client: TelegramClient, peer: Any) -> Any | None:
    try:
        return await client.get_entity(peer)
    except Exception as exc:
        safe_print(f"[警告] 无法解析群组/会话 {peer!r}：{exc}")
        return None


async def filter_peer_ids(client: TelegramClient, peers: list[Any]) -> set[int]:
    ids: set[int] = set()
    for peer in peers:
        entity = await peer_to_entity(client, peer)
        if entity is not None:
            ids.add(utils.get_peer_id(entity))
    return ids


async def collect_records(client: TelegramClient, folder: Any, include_types: set[str]) -> list[GroupRecord]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    folder_title = normalize_title(folder.title)
    records: dict[int, GroupRecord] = {}

    explicit_peers = list(getattr(folder, "include_peers", []) or []) + list(getattr(folder, "pinned_peers", []) or [])
    exclude_ids = await filter_peer_ids(client, list(getattr(folder, "exclude_peers", []) or []))

    for peer in explicit_peers:
        entity = await peer_to_entity(client, peer)
        if entity is None:
            continue

        chat_type = entity_type(entity)
        if chat_type not in include_types:
            continue

        chat_id = utils.get_peer_id(entity)
        records[chat_id] = GroupRecord(
            folder=folder_title,
            chat_id=chat_id,
            access_hash=entity_access_hash(entity),
            title=entity_title(entity),
            username=entity_username(entity),
            type=chat_type,
            enabled=True,
            last_seen_at=now,
        )

    has_dynamic_group_rule = bool(getattr(folder, "groups", False))
    has_dynamic_channel_rule = bool(getattr(folder, "broadcasts", False))

    if has_dynamic_group_rule or has_dynamic_channel_rule:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            chat_type = entity_type(entity)
            if chat_type not in include_types:
                continue

            chat_id = utils.get_peer_id(entity)
            if chat_id in exclude_ids:
                continue

            if has_dynamic_group_rule and chat_type in {"group", "supergroup"}:
                records[chat_id] = GroupRecord(
                    folder=folder_title,
                    chat_id=chat_id,
                    access_hash=entity_access_hash(entity),
                    title=entity_title(entity),
                    username=entity_username(entity),
                    type=chat_type,
                    enabled=True,
                    last_seen_at=now,
                )
            elif has_dynamic_channel_rule and chat_type == "channel":
                records[chat_id] = GroupRecord(
                    folder=folder_title,
                    chat_id=chat_id,
                    access_hash=entity_access_hash(entity),
                    title=entity_title(entity),
                    username=entity_username(entity),
                    type=chat_type,
                    enabled=True,
                    last_seen_at=now,
                )

    return sorted(records.values(), key=lambda item: item.title.lower())


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                folder TEXT NOT NULL,
                access_hash INTEGER,
                title TEXT NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_seen_at TEXT NOT NULL,
                last_sent_at TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()


def upsert_records(db_path: Path, folder_name: str, records: list[GroupRecord], mark_removed_disabled: bool) -> None:
    init_db(db_path)
    seen_ids = {record.chat_id for record in records}

    with sqlite3.connect(db_path) as conn:
        existing_notes = {
            row[0]: (row[1], row[2])
            for row in conn.execute("SELECT chat_id, last_sent_at, note FROM groups")
        }

        for record in records:
            last_sent_at, note = existing_notes.get(record.chat_id, ("", ""))
            conn.execute(
                """
                INSERT INTO groups (
                    chat_id, folder, access_hash, title, username, type,
                    enabled, last_seen_at, last_sent_at, note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    folder = excluded.folder,
                    access_hash = excluded.access_hash,
                    title = excluded.title,
                    username = excluded.username,
                    type = excluded.type,
                    enabled = 1,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    record.chat_id,
                    record.folder,
                    record.access_hash,
                    record.title,
                    record.username,
                    record.type,
                    1,
                    record.last_seen_at,
                    last_sent_at,
                    note,
                ),
            )

        if mark_removed_disabled:
            placeholders = ",".join("?" for _ in seen_ids)
            if seen_ids:
                conn.execute(
                    f"UPDATE groups SET enabled = 0 WHERE folder = ? AND chat_id NOT IN ({placeholders})",
                    [folder_name, *seen_ids],
                )
            else:
                conn.execute("UPDATE groups SET enabled = 0 WHERE folder = ?", [folder_name])

        conn.commit()


def export_csv(db_path: Path, csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "folder",
        "chat_id",
        "access_hash",
        "title",
        "username",
        "type",
        "enabled",
        "last_seen_at",
        "last_sent_at",
        "note",
    ]

    with sqlite3.connect(db_path) as conn, csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        conn.row_factory = sqlite3.Row
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in conn.execute(
            """
            SELECT folder, chat_id, access_hash, title, username, type, enabled,
                   last_seen_at, last_sent_at, note
            FROM groups
            ORDER BY enabled DESC, folder, lower(title)
            """
        ):
            data = dict(row)
            data["enabled"] = "true" if data["enabled"] else "false"
            writer.writerow(data)


async def build_client(config: dict[str, Any], base_dir: Path) -> TelegramClient:
    auth_mode = config.get("auth_mode", "api_id_hash")
    session_path = resolve_path(base_dir, config["session_name"])
    session_path.parent.mkdir(parents=True, exist_ok=True)

    if auth_mode == "api_id_hash":
        options = await choose_telegram_client_options(config, int(config["api_id"]), config["api_hash"])
        return TelegramClient(str(session_path), int(config["api_id"]), config["api_hash"], **options)

    if auth_mode == "builtin_telegram_desktop":
        options = await choose_telegram_client_options(
            config,
            BUILTIN_TELEGRAM_DESKTOP_API_ID,
            BUILTIN_TELEGRAM_DESKTOP_API_HASH,
        )
        return TelegramClient(
            str(session_path),
            BUILTIN_TELEGRAM_DESKTOP_API_ID,
            BUILTIN_TELEGRAM_DESKTOP_API_HASH,
            device_model="Desktop",
            system_version="Windows 10",
            app_version="3.4.3 x64",
            lang_code="en",
            system_lang_code="en-US",
            **options,
        )

    try:
        from opentele.api import API, UseCurrentSession
        from opentele.td import TDesktop
        from opentele.tl import TelegramClient as OpenTeleTelegramClient
    except ImportError as exc:
        raise SystemExit(
            "telegram_desktop_tdata 模式需要安装 opentele。"
            "在 Python 3.12 上可能还需要 Microsoft C++ Build Tools 编译 tgcrypto。"
            "如果想避开 my.telegram.org，请使用 auth_mode=builtin_telegram_desktop。"
        ) from exc

    tdata_path = resolve_path(base_dir, config["tdata_path"])
    if not tdata_path.exists():
        raise SystemExit(f"找不到 tdata_path：{tdata_path}")

    tdesk = TDesktop(str(tdata_path))
    if not tdesk.isLoaded():
        raise SystemExit(f"无法读取 Telegram Desktop tdata：{tdata_path}")

    api = API.TelegramDesktop.Generate(system="windows", unique_id=str(session_path))
    return await OpenTeleTelegramClient.FromTDesktop(
        tdesk,
        session=str(session_path),
        flag=UseCurrentSession,
        api=api,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="同步 Telegram 文件夹中的群组，并导出群组 ID。")
    parser.add_argument("--config", default="config.json", help="config.json 路径")
    parser.add_argument("--folder", help="要同步的 Telegram 文件夹名；会覆盖 config.json 中的 folder_name")
    parser.add_argument("--sync-all-folders", action="store_true", help="同步当前账号所有聊天文件夹中的群组")
    parser.add_argument("--list-folders", action="store_true", help="只列出当前账号可见的 Telegram 文件夹")
    parser.add_argument("--debug-folders", action="store_true", help="打印当前账号和文件夹详情")
    parser.add_argument("--reset-session", action="store_true", help="删除当前配置对应的本地 session 后退出")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    base_dir = config_path.parent
    config = load_config(config_path)
    folder_name = args.folder if args.folder is not None else config["folder_name"]

    if args.reset_session:
        session_path = resolve_path(base_dir, config["session_name"])
        for suffix in ["", ".session", ".session-journal"]:
            target = Path(f"{session_path}{suffix}")
            if target.exists():
                target.unlink()
                safe_print(f"已删除：{target}")
        safe_print("Session 已清除。下次运行会重新登录。")
        return

    client = await build_client(config, base_dir)

    async with client:
        await check_account_status(client)

        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result)
        filters = [
            item
            for item in raw_filters
            if isinstance(item, (types.DialogFilter, types.DialogFilterChatlist))
        ]

        if args.list_folders:
            for item in filters:
                safe_print(f"- {normalize_title(item.title)}")
            return

        if args.debug_folders:
            safe_print("文件夹列表：")
            for item in filters:
                safe_print(folder_debug_line(item))
            return

        include_types = set(config.get("include_types", ["group", "supergroup"]))
        if args.sync_all_folders:
            sync_items = filters
        else:
            folder = next((item for item in filters if normalize_title(item.title) == folder_name), None)
            if folder is None:
                available = ", ".join(normalize_title(item.title) for item in filters) or "(none)"
                raise SystemExit(f"找不到文件夹：{folder_name}。当前可用文件夹：{available}")
            sync_items = [folder]

        records: list[GroupRecord] = []
        for item in sync_items:
            item_title = normalize_title(item.title)
            safe_print(f"正在同步文件夹：{item_title}")
            item_records = await collect_records(client, item, include_types)
            records.extend(item_records)

    db_path = resolve_path(base_dir, config["output_db"])
    csv_path = resolve_path(base_dir, config["output_csv"])
    init_db(db_path)
    for synced_folder_name in sorted({record.folder for record in records}):
        folder_records = [record for record in records if record.folder == synced_folder_name]
        upsert_records(db_path, synced_folder_name, folder_records, bool(config.get("mark_removed_disabled", True)))
    export_csv(db_path, csv_path)

    if args.sync_all_folders:
        safe_print(f"已同步文件夹数量：{len(sync_items)}")
    else:
        safe_print(f"已同步文件夹：{folder_name}")
    safe_print(f"找到群组数量：{len(records)}")
    safe_print(f"CSV 输出：{csv_path}")
    safe_print(f"SQLite 输出：{db_path}")
    for record in records[:20]:
        username = f" @{record.username}" if record.username else ""
        safe_print(f"- {record.chat_id} [{record.type}] {record.title}{username}")
    if len(records) > 20:
        safe_print(f"... and {len(records) - 20} more")


if __name__ == "__main__":
    asyncio.run(main())
