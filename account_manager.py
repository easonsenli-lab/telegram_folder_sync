from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
ACCOUNTS_DIR = ROOT / "accounts"


def safe_print(text: str = "") -> None:
    print(text, flush=True)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def account_id_from_name(name: str) -> str:
    raw = name.strip()
    if not raw:
        raw = "account"
    value = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", raw).strip("_")
    return value or "account"


def account_config_path(account_id: str) -> Path:
    return ACCOUNTS_DIR / f"{account_id}.json"


def account_paths(account_id: str) -> tuple[str, str, str]:
    return (
        f"../sessions/{account_id}/telegram_user",
        f"../data/{account_id}/groups.csv",
        f"../data/{account_id}/groups.sqlite3",
    )


def build_account_config(account_id: str, display_name: str, template: dict[str, Any]) -> dict[str, Any]:
    session_name, output_csv, output_db = account_paths(account_id)
    config = dict(template)
    config["account_name"] = display_name
    config["session_name"] = session_name
    config["output_csv"] = output_csv
    config["output_db"] = output_db
    return config


def ensure_accounts_dir() -> None:
    ACCOUNTS_DIR.mkdir(exist_ok=True)


def ensure_default_account() -> None:
    ensure_accounts_dir()
    if list(ACCOUNTS_DIR.glob("*.json")):
        return

    source = ROOT / "config.json"
    if not source.exists():
        source = ROOT / "config.example.json"
    template = load_json(source)
    config = build_account_config("default", "default", template)
    save_json(account_config_path("default"), config)


def normalize_account_config(path: Path) -> None:
    config = load_json(path)
    account_id = path.stem
    session_name, output_csv, output_db = account_paths(account_id)
    changed = False
    expected = {
        "session_name": session_name,
        "output_csv": output_csv,
        "output_db": output_db,
    }
    for key, value in expected.items():
        current = str(config.get(key, ""))
        if current.startswith("sessions/") or current.startswith("data/") or not current:
            config[key] = value
            changed = True
    if not config.get("account_name"):
        config["account_name"] = account_id
        changed = True
    if changed:
        save_json(path, config)


def list_accounts() -> list[Path]:
    ensure_default_account()
    accounts = sorted(ACCOUNTS_DIR.glob("*.json"), key=lambda path: path.stem.lower())
    for path in accounts:
        normalize_account_config(path)
    return accounts


def display_name(path: Path) -> str:
    try:
        config = load_json(path)
        return str(config.get("account_name") or path.stem)
    except Exception:
        return path.stem


def create_account() -> Path:
    ensure_accounts_dir()
    while True:
        name = input("请输入新账号名称（例如 account_1 / 印度号1）: ").strip()
        if not name:
            safe_print("账号名称不能为空。")
            continue
        account_id = account_id_from_name(name)
        path = account_config_path(account_id)
        if path.exists():
            safe_print(f"账号配置已存在：{path.name}")
            continue
        template = load_json(ROOT / "config.example.json")
        save_json(path, build_account_config(account_id, name, template))
        safe_print(f"已创建账号配置：accounts/{path.name}")
        safe_print(f"Session：sessions/{account_id}/telegram_user")
        safe_print(f"群组数据：data/{account_id}/groups.csv")
        return path


def choose_account(prompt: str = "请选择账号") -> Path:
    accounts = list_accounts()
    safe_print("")
    safe_print("账号列表：")
    for index, path in enumerate(accounts, start=1):
        safe_print(f"{index}. {display_name(path)}（accounts/{path.name}）")
    safe_print("0. 创建新账号")

    while True:
        raw = input(f"{prompt}（输入序号，默认 1）: ").strip()
        if raw == "":
            return accounts[0]
        try:
            index = int(raw)
        except ValueError:
            safe_print("请输入账号序号。")
            continue
        if index == 0:
            return create_account()
        if 1 <= index <= len(accounts):
            return accounts[index - 1]
        safe_print("账号序号超出范围。")
