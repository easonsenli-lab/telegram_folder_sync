from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon.errors import (
    ChatAdminRequiredError,
    ChatWriteForbiddenError,
    FloodWaitError,
    UserBannedInChannelError,
)

from sync_folder_groups import (
    build_client,
    check_account_status,
    load_config as load_auth_config,
    resolve_path,
    safe_print,
)
from account_manager import choose_account, display_name
from private_dm_events import register_private_dm_event_listener


@dataclass(frozen=True)
class TargetGroup:
    folder: str
    chat_id: int
    title: str
    username: str
    enabled: bool


@dataclass(frozen=True)
class RuntimeOptions:
    groups: list[TargetGroup]
    max_cycles: int
    task_interval_seconds: int
    group_interval_seconds: int
    message: str
    is_strategy: bool = False


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_sender_config(path: Path) -> dict[str, Any]:
    config = load_json(path)
    required = [
        "message_file",
        "group_interval_seconds",
        "log_file",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise SystemExit(f"发送配置缺少必填项：{', '.join(missing)}")
    return config


def last_plan_path(base_dir: Path, config: dict[str, Any]) -> Path:
    raw = config.get("last_plan_file", "state/last_plan.json")
    return resolve_path(base_dir, raw)


def read_message(path: Path) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    text = path.read_text(encoding="utf-8").strip()
    if "Your advertisement text here" in text:
        raise SystemExit(f"请先编辑占位广告文本：{path}")
    return text


def open_message_editor(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    safe_print(f"正在打开广告文本文件：{path.name}")
    before_mtime = path.stat().st_mtime
    if os.name == "nt":
        process = subprocess.Popen(["notepad.exe", str(path)])
    else:
        editor = os.environ.get("EDITOR", "vi")
        process = subprocess.Popen([editor, str(path)])

    safe_print("请在编辑器中保存广告文本；检测到保存后会自动返回预览。")
    while True:
        time.sleep(0.5)
        current_mtime = path.stat().st_mtime
        current_text = path.read_text(encoding="utf-8").strip()
        if current_mtime != before_mtime and current_text:
            return
        if process.poll() is not None:
            return


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_groups(csv_path: Path, folder: str | None) -> list[TargetGroup]:
    if not csv_path.exists():
        raise SystemExit(f"群组 CSV 不存在：{csv_path}。请先运行 01_登录电报.cmd 同步群组。")

    groups: list[TargetGroup] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if folder and row.get("folder") != folder:
                continue
            enabled = parse_bool(row.get("enabled", "false"))
            if not enabled:
                continue
            groups.append(
                TargetGroup(
                    folder=row.get("folder", ""),
                    chat_id=int(row["chat_id"]),
                    title=row.get("title", ""),
                    username=row.get("username", ""),
                    enabled=enabled,
                )
            )

    return groups


def sync_groups_before_task(base_dir: Path, auth_config_path: Path) -> None:
    script_path = Path(__file__).resolve().parent / "sync_folder_groups.py"
    safe_print("")
    safe_print("正在实时同步 Telegram 文件夹群组信息...")
    command = [
        sys.executable,
        str(script_path),
        "--config",
        str(auth_config_path),
        "--sync-all-folders",
    ]
    result = subprocess.run(command, cwd=base_dir)
    if result.returncode != 0:
        raise SystemExit(f"同步群组失败，退出码：{result.returncode}。请先检查 Telegram 登录和网络。")
    safe_print("群组信息同步完成。")


def account_groups_csv(auth_base_dir: Path, auth_config: dict[str, Any]) -> Path:
    return resolve_path(auth_base_dir, auth_config["output_csv"])


def load_all_groups(csv_path: Path) -> list[TargetGroup]:
    return load_groups(csv_path, None)


def choose_folder(groups: list[TargetGroup]) -> str | None:
    folders = sorted({group.folder for group in groups if group.folder})
    if not folders:
        safe_print("没有读取到文件夹名称，将展示全部群组。")
        return None

    safe_print("")
    safe_print("扫描到以下文件夹：")
    for index, folder in enumerate(folders, start=1):
        count = sum(1 for group in groups if group.folder == folder)
        safe_print(f"{index}. {folder}（{count} 个群组）")

    while True:
        raw = input("请选择要发送广告的文件夹序号（直接回车=全部文件夹）: ").strip()
        if raw == "":
            return None
        try:
            index = int(raw)
            if 1 <= index <= len(folders):
                return folders[index - 1]
            safe_print("序号超出范围。")
        except ValueError:
            safe_print("请输入文件夹序号。")


def ensure_log_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["时间", "文件夹", "群组ID", "群组名称", "动作", "状态", "详情"])


def append_log(path: Path, group: TargetGroup, action: str, status: str, detail: str = "") -> None:
    ensure_log_header(path)
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                group.folder,
                group.chat_id,
                group.title,
                action,
                status,
                detail,
            ]
        )

    # Also write to SQLite database data/rosepay.db
    try:
        import sqlite3
        db_path = Path(__file__).resolve().parent / "data" / "rosepay.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ad_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT,
                    folder TEXT,
                    chat_id TEXT,
                    title TEXT,
                    action TEXT,
                    status TEXT,
                    detail TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO ad_logs (time, folder, chat_id, title, action, status, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    group.folder,
                    str(group.chat_id),
                    group.title,
                    action,
                    status,
                    detail
                )
            )
    except Exception as e:
        print(f"Failed to append log to SQLite: {e}", flush=True)



def prompt_text(prompt: str, default: str | None = None) -> str:
    suffix = f"（默认：{default}）" if default not in (None, "") else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if value == "" and default is not None:
        return default
    return value


def message_summary(message: str, max_chars: int = 80) -> str:
    compact = " ".join(message.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def plan_to_json(options: RuntimeOptions) -> dict[str, Any]:
    return {
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chat_ids": [group.chat_id for group in options.groups],
        "groups": [
            {
                "folder": group.folder,
                "chat_id": group.chat_id,
                "title": group.title,
                "username": group.username,
            }
            for group in options.groups
        ],
        "max_cycles": options.max_cycles,
        "task_interval_seconds": options.task_interval_seconds,
        "group_interval_seconds": options.group_interval_seconds,
        "message_summary": message_summary(options.message),
    }


def save_last_plan(path: Path, options: RuntimeOptions) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan_to_json(options), ensure_ascii=False, indent=2), encoding="utf-8")


def load_last_plan(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        safe_print(f"读取上次任务计划失败，将重新配置：{exc}")
        return None


def show_last_plan(plan: dict[str, Any]) -> None:
    safe_print("")
    safe_print("发现上次任务计划：")
    safe_print(f"- 保存时间：{plan.get('saved_at', '未知')}")
    cycles = int(plan.get("max_cycles", 0) or 0)
    safe_print(f"- 任务执行次数：{'一直运行' if cycles == 0 else str(cycles)}")
    safe_print(f"- 每次任务执行间隔：{int(plan.get('task_interval_seconds', 0) or 0) // 60} 分钟")
    safe_print(f"- 每个群组发送间隔：{int(plan.get('group_interval_seconds', 0) or 0)} 秒")
    safe_print(f"- 广告文本摘要：{plan.get('message_summary', '')}")
    safe_print("- 群组：")
    for index, group in enumerate(plan.get("groups", []), start=1):
        folder = group.get("folder", "")
        title = group.get("title", "")
        chat_id = group.get("chat_id", "")
        safe_print(f"  {index}. [{folder}] {title} | 群组ID：{chat_id}")


def options_from_last_plan(plan: dict[str, Any], all_groups: list[TargetGroup], message: str) -> RuntimeOptions | None:
    chat_ids = [int(chat_id) for chat_id in plan.get("chat_ids", [])]
    if not chat_ids:
        return None

    by_id = {group.chat_id: group for group in all_groups}
    groups: list[TargetGroup] = []
    missing: list[int] = []
    for chat_id in chat_ids:
        group = by_id.get(chat_id)
        if group is None:
            missing.append(chat_id)
        else:
            groups.append(group)

    if missing:
        safe_print(f"注意：上次计划中有 {len(missing)} 个群组当前不可用，已自动跳过。")
    if not groups:
        safe_print("上次计划中的群组当前都不可用，需要重新配置。")
        return None

    return RuntimeOptions(
        groups=groups,
        max_cycles=int(plan.get("max_cycles", 0) or 0),
        task_interval_seconds=int(plan.get("task_interval_seconds", 0) or 0),
        group_interval_seconds=int(plan.get("group_interval_seconds", 0) or 0),
        message=message,
        is_strategy=bool(plan.get("is_strategy", False))
    )


def display_path(base_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def prompt_int(prompt: str, default: int | None = None, allow_blank_forever: bool = False) -> int:
    while True:
        suffix = "（直接回车=一直运行）" if allow_blank_forever else (
            f"（默认：{default}）" if default is not None else ""
        )
        value = input(f"{prompt}{suffix}: ").strip()
        if value == "":
            if allow_blank_forever:
                return 0
            if default is not None:
                return default
        try:
            result = int(value)
            if result < 0:
                safe_print("请输入大于等于 0 的数字。")
                continue
            return result
        except ValueError:
            safe_print("请输入数字。")


def parse_selection(raw: str, count: int) -> list[int]:
    raw = raw.strip()
    if raw == "" or raw.lower() in {"all", "a", "*", "全部"}:
        return list(range(1, count + 1))

    selected: set[int] = set()
    for part in raw.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start, end = int(start_raw), int(end_raw)
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))

    invalid = [item for item in selected if item < 1 or item > count]
    if invalid:
        raise ValueError(f"序号超出范围：{invalid}")
    return sorted(selected)


def task_interval_default_minutes(config: dict[str, Any]) -> int:
    if "task_interval_minutes" in config:
        return int(config.get("task_interval_minutes") or 0)
    return int(config.get("task_interval_seconds", 0) or 0) // 60


def confirm_or_edit_message(message_path: Path) -> str:
    while True:
        message = read_message(message_path)
        safe_print("")
        if message:
            safe_print("当前广告文本预览：")
            safe_print("-" * 40)
            safe_print(message)
            safe_print("-" * 40)
            use_file = prompt_text("是否使用以上广告文本？输入 y 使用，输入 n 重新编辑", "y").lower()
            if use_file in {"y", "yes", "是"}:
                return message
        else:
            safe_print("当前广告文本为空，需要先编辑。")

        open_message_editor(message_path)
        safe_print("已检测到广告文本更新，重新预览。")


def collect_runtime_options(
    groups: list[TargetGroup],
    message_path: Path,
    config: dict[str, Any],
    is_strategy: bool = False
) -> RuntimeOptions:
    chosen_groups = groups
    safe_print("")
    safe_print(f"本次任务将发送该范围内全部群组：{len(chosen_groups)} 个")
    for index, group in enumerate(chosen_groups, start=1):
        username = f" @{group.username}" if group.username else ""
        safe_print(f"{index}. [{group.folder}] {group.title}{username} | 群组ID：{group.chat_id}")

    default_cycles = int(config.get("max_cycles", 0) or 0)
    max_cycles = prompt_int("需要跑多少次任务", default_cycles, allow_blank_forever=True)
    task_interval_minutes = prompt_int("每次任务执行间隔，单位：分钟", task_interval_default_minutes(config))
    group_interval_seconds = prompt_int(
        "每个群组发送间隔，单位：秒",
        int(config.get("group_interval_seconds", 0) or 0),
    )

    message = confirm_or_edit_message(message_path)

    return RuntimeOptions(
        groups=chosen_groups,
        max_cycles=max_cycles,
        task_interval_seconds=task_interval_minutes * 60,
        group_interval_seconds=group_interval_seconds,
        message=message,
        is_strategy=is_strategy
    )


def get_runtime_options(
    base_dir: Path,
    config: dict[str, Any],
    all_groups: list[TargetGroup],
    message_path: Path,
    is_strategy: bool = False
) -> RuntimeOptions:
    plan_path = last_plan_path(base_dir, config)
    last_plan = load_last_plan(plan_path)
    if last_plan:
        show_last_plan(last_plan)
        choice = prompt_text("是否按照上次计划继续执行？输入 y 继续，输入 n 重新配置", "y").lower()
        if choice in {"y", "yes", "是"}:
            message = read_message(message_path)
            if not message:
                message = confirm_or_edit_message(message_path)
            options = options_from_last_plan(last_plan, all_groups, message)
            if options is not None:
                return options

    folder = choose_folder(all_groups)
    groups = [group for group in all_groups if folder is None or group.folder == folder]
    if not groups:
        raise SystemExit(f"没有找到启用状态的群组。当前文件夹：{folder or '全部文件夹'}")

    options = collect_runtime_options(groups, message_path, config, is_strategy=is_strategy)
    save_last_plan(plan_path, options)
    safe_print(f"已保存本次任务计划：{display_path(base_dir, plan_path)}")
    return options


def delay_with_jitter(base_seconds: int, jitter_seconds: int) -> int:
    if base_seconds <= 0:
        return 0
    if jitter_seconds <= 0:
        return base_seconds
    return max(0, base_seconds + random.randint(-jitter_seconds, jitter_seconds))


async def sleep_countdown(seconds: int, label: str) -> None:
    if seconds <= 0:
        return
    safe_print(f"{label}：等待 {seconds} 秒")
    await asyncio.sleep(seconds)


async def call_strategy_send_api(chat_id: int, gtype: str, fallback_message: str, company: str) -> dict:
    import urllib.request
    import urllib.error
    url = "http://127.0.0.1:8000/api/internal/send-strategy-message"
    data = {
        "chat_id": str(chat_id),
        "gtype": gtype,
        "fallback_message": fallback_message,
        "company": company
    }
    req_body = json.dumps(data).encode("utf-8")
    
    def _send():
        req = urllib.request.Request(
            url,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
            
    return await asyncio.to_thread(_send)


async def run_cycle(
    client: Any,
    options: RuntimeOptions,
    config: dict[str, Any],
    log_path: Path,
    send: bool,
    cycle_number: int,
) -> bool:
    max_groups = int(config.get("max_groups_per_cycle", 0) or 0)
    targets = options.groups[:max_groups] if max_groups > 0 else options.groups
    jitter = int(config.get("jitter_seconds", 0) or 0)
    parse_mode = config.get("parse_mode") or None
    link_preview = bool(config.get("link_preview", False))
    stop_on_flood_wait = bool(config.get("stop_on_flood_wait", True))

    safe_print(f"第 {cycle_number} 轮任务：共 {len(targets)} 个群组")

    for index, group in enumerate(targets, start=1):
        label = f"[{index}/{len(targets)}] {group.chat_id} {group.title}"
        if not send:
            safe_print(f"预览策略发送：{label}")
            append_log(log_path, group, "预览", "成功")
        else:
            if options.is_strategy:
                try:
                    safe_print(f"正在策略发送：{label}")
                    # Determine group type
                    gtype = group.folder
                    if gtype not in ("中文长", "中文短", "英文长", "英文短"):
                        try:
                            import sqlite3
                            db_path = Path(__file__).resolve().parent / "data" / "rosepay.db"
                            with sqlite3.connect(str(db_path)) as conn:
                                cursor = conn.cursor()
                                cursor.execute("SELECT category FROM groups_library WHERE id = ? OR username = ?", (str(group.chat_id), group.username or ""))
                                row = cursor.fetchone()
                                if row:
                                    gtype = row[0]
                        except Exception:
                            pass
                    if gtype not in ("中文长", "中文短", "英文长", "英文短"):
                        gtype = "英文短"
                        
                    company = config.get("company", "admin")
                    res = await call_strategy_send_api(group.chat_id, gtype, options.message, company)
                    
                    act_name = res.get("account_name", "未知账号")
                    detail = f"发送话术摘要: {message_summary(res.get('message_sent', ''))}"
                    safe_print(f"[策略成功] {label}，执行账号：{act_name}")
                    append_log(log_path, group, f"发送(策略:{act_name})", "成功", detail)
                except Exception as exc:
                    detail = f"策略发送异常: {str(exc)}"
                    safe_print(f"[策略失败] {label}：{detail}")
                    append_log(log_path, group, "发送(策略)", "错误", detail)
            else:
                try:
                    safe_print(f"正在发送：{label}")
                    await client.send_message(
                        group.chat_id,
                        options.message,
                        parse_mode=parse_mode,
                        link_preview=link_preview,
                    )
                    append_log(log_path, group, "发送", "成功")
                except FloodWaitError as exc:
                    detail = f"Telegram 要求等待 {exc.seconds} 秒"
                    safe_print(f"[限流] {label}：{detail}")
                    append_log(log_path, group, "发送", "限流", detail)
                    if stop_on_flood_wait:
                        return False
                    await sleep_countdown(int(exc.seconds), "Telegram 限流等待")
                except (ChatAdminRequiredError, ChatWriteForbiddenError, UserBannedInChannelError) as exc:
                    detail = type(exc).__name__
                    safe_print(f"[跳过] {label}：无发言权限或账号在群内不可用（{detail}）")
                    append_log(log_path, group, "发送", "无权限", detail)
                except Exception as exc:
                    detail = f"{type(exc).__name__}: {exc}"
                    safe_print(f"[错误] {label}：{detail}")
                    append_log(log_path, group, "发送", "错误", detail)

        if index < len(targets):
            wait_seconds = delay_with_jitter(options.group_interval_seconds, jitter)
            if send:
                await sleep_countdown(wait_seconds, "群组发送间隔")
            else:
                safe_print(f"预览：群组发送间隔 {wait_seconds} 秒")

    return True


def load_account_from_db(db_path: Path, account_id: str) -> dict[str, Any]:
    import sqlite3
    if not db_path.exists():
        raise SystemExit(f"数据库不存在：{db_path}")
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"在数据库中找不到账号：{account_id}")
            
        d = dict(row)
        
        # Construct the config structure exactly matching config.json structure
        config = {
            "account_name": d["account_name"],
            "auth_mode": d["auth_mode"],
            "api_id": d["api_id"],
            "api_hash": d["api_hash"],
            "tdata_path": d["tdata_path"],
            "session_name": d["session_name"],
            "folder_name": d["folder_name"],
            "output_csv": d["output_csv"],
            "output_db": d["output_db"],
            "include_types": [x.strip() for x in (d["include_types"] or "group,supergroup").split(",") if x.strip()],
            "mark_removed_disabled": bool(d["mark_removed_disabled"]),
            "connection_timeout_seconds": int(d["connection_timeout_seconds"] or 12),
            "connection_retries": int(d["connection_retries"] or 2),
            "proxy": {
                "enabled": bool(d["proxy_enabled"]),
                "type": d["proxy_type"],
                "host": d["proxy_host"],
                "port": int(d["proxy_port"] or 8800),
                "username": d["proxy_username"] or "",
                "password": d["proxy_password"] or ""
            },
            # campaign details directly from DB
            "campaign_folder": d["campaign_folder"],
            "campaign_message": d["campaign_message"],
            "campaign_interval_minutes": int(d["campaign_interval_minutes"] or 60),
            "campaign_group_interval_seconds": int(d["campaign_group_interval_seconds"] or 5)
        }
        return config


async def main() -> None:
    parser = argparse.ArgumentParser(description="按本地配置向已同步的 Telegram 群组发送广告文本。")
    parser.add_argument("--config", default="ad_sender_config.json", help="发送配置 JSON 路径")
    parser.add_argument("--account", help="执行任务的账号ID，使用 SQLite 数据库配置")
    parser.add_argument("--folder", help="直接使用这个文件夹；不填则先列出文件夹让用户选择")
    parser.add_argument("--send", action="store_true", help="真实发送；不加此参数只做预览")
    parser.add_argument("--no-confirm", action="store_true", help="跳过真实发送确认提示")
    parser.add_argument("--strategy", action="store_true", help="使用策略轰炸模式")
    args = parser.parse_args()

    db_path = Path(__file__).resolve().parent / "data" / "rosepay.db"
    
    if args.account:
        account_id = args.account
        config = load_account_from_db(db_path, args.account)
        auth_config = config
        auth_config_path = Path(__file__).resolve().parent / "accounts" / f"{args.account}.json"
        auth_base_dir = auth_config_path.parent.parent
        
        message = config.get("campaign_message") or ""
        if not message:
            raise SystemExit("广告内容为空。请在控制面板配置并保存广告内容。")
            
        log_path = Path(__file__).resolve().parent / "logs" / "ad-send-log.csv"
        
        sync_groups_before_task(auth_base_dir, auth_config_path)
        
        groups_csv_path = account_groups_csv(auth_base_dir, auth_config)
        all_groups = load_all_groups(groups_csv_path)
        if not all_groups:
            raise SystemExit("没有找到任何启用状态的群组。请先同步文件夹。")
            
        folder_name = args.folder or config.get("campaign_folder")
        if not folder_name:
            folder_name = choose_folder(all_groups)
            
        filtered_groups = [group for group in all_groups if group.folder == folder_name]
        if not filtered_groups:
            raise SystemExit(f"没有找到启用状态的群组。当前文件夹：{folder_name}")
            
        options = RuntimeOptions(
            groups=filtered_groups,
            max_cycles=0,
            task_interval_seconds=int(config.get("campaign_interval_minutes", 60)) * 60,
            group_interval_seconds=int(config.get("campaign_group_interval_seconds", 5)),
            message=message,
            is_strategy=bool(args.strategy)
        )
        base_dir = Path(__file__).resolve().parent
    else:
        config_path = Path(args.config).resolve()
        base_dir = config_path.parent
        config = load_sender_config(config_path)

        if config.get("auth_config"):
            auth_config_path = resolve_path(base_dir, config["auth_config"])
        else:
            auth_config_path = choose_account("请选择执行任务的账号")
        account_id = auth_config_path.stem
        auth_config = load_auth_config(auth_config_path)
        auth_base_dir = auth_config_path.parent
        
        sync_groups_before_task(auth_base_dir, auth_config_path)
        
        groups_csv_path = account_groups_csv(auth_base_dir, auth_config)
        all_groups = load_all_groups(groups_csv_path)
        if not all_groups:
            raise SystemExit("没有找到任何启用状态的群组。请先同步文件夹。")
        message_path = resolve_path(base_dir, config["message_file"])
        message = read_message(message_path)
        log_path = resolve_path(base_dir, config["log_file"])

        if args.folder is not None:
            filtered_groups = [group for group in all_groups if group.folder == args.folder]
            if not filtered_groups:
                raise SystemExit(f"没有找到启用状态的群组。当前文件夹：{args.folder}")
            options = collect_runtime_options(filtered_groups, message_path, config, is_strategy=bool(args.strategy))
            save_last_plan(last_plan_path(base_dir, config), options)
        else:
            options = get_runtime_options(base_dir, config, all_groups, message_path, is_strategy=bool(args.strategy))

    safe_print("")
    safe_print(f"当前任务账号：{display_name(auth_config_path)}")
    safe_print(f"账号配置：accounts/{auth_config_path.name}")
    safe_print(f"运行模式：{'真实发送' if args.send else '预览，不发送'}")
    safe_print(f"已同步可用群组数量：{len(options.groups)}")
    safe_print(f"广告文本字符数：{len(options.message)}")
    safe_print(f"日志文件：{display_path(base_dir, log_path)}")

    safe_print("")
    safe_print("任务参数确认：")
    safe_print(f"- 已选择群组：{len(options.groups)} 个")
    safe_print(f"- 任务执行次数：{'一直运行' if options.max_cycles == 0 else str(options.max_cycles)}")
    safe_print(f"- 每次任务执行间隔：{options.task_interval_seconds // 60} 分钟")
    safe_print(f"- 每个群组发送间隔：{options.group_interval_seconds} 秒")

    if args.send and not args.no_confirm:
        confirm = prompt_text("确认真实发送？直接回车继续，输入 n 取消", "").lower()
        if confirm in {"n", "no", "否", "取消"}:
            raise SystemExit("已取消真实发送。")

    client = await build_client(auth_config, auth_base_dir)
    jitter = int(config.get("jitter_seconds", 0) or 0)

    async with client:
        await check_account_status(client)
        register_private_dm_event_listener(
            client,
            account_id=str(account_id),
            account_label=display_name(auth_config_path),
            source="ad_sender",
        )
        safe_print("已开启私聊实时监听：广告任务运行时收到私聊会写入本地通知队列。")
        cycle = 1
        while True:
            should_continue = await run_cycle(client, options, config, log_path, args.send, cycle)
            if not should_continue:
                safe_print("任务停止：Telegram 返回限流信号。")
                break
            if options.max_cycles and cycle >= options.max_cycles:
                break
            cycle += 1
            wait_seconds = delay_with_jitter(options.task_interval_seconds, jitter)
            if args.send:
                await sleep_countdown(wait_seconds, "任务执行间隔")
            else:
                safe_print(f"预览：任务执行间隔 {wait_seconds // 60} 分钟（{wait_seconds} 秒）")
                if options.max_cycles == 0:
                    safe_print("预览模式不会无限循环，已在第一轮后停止。")
                    break

    safe_print("完成。")


if __name__ == "__main__":
    asyncio.run(main())
