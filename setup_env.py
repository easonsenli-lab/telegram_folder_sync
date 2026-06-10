from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from account_manager import ensure_default_account


ROOT = Path(__file__).resolve().parent


def safe_print(text: str = "") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), flush=True)


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    safe_print(f"执行：{' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def load_project_config() -> dict:
    path = ROOT / "config.json"
    if not path.exists():
        path = ROOT / "config.example.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def proxy_url_from_config() -> str:
    try:
        proxy = (load_project_config().get("proxy") or {})
    except Exception:
        return ""

    if not proxy.get("enabled"):
        return ""
    proxy_type = str(proxy.get("type", "")).lower()
    if proxy_type == "auto":
        proxy_type = "http"
    if proxy_type not in {"http", "socks5", "socks4"}:
        return ""
    host = str(proxy.get("host", "")).strip()
    port = int(proxy.get("port", 0) or 0)
    username = str(proxy.get("username", "")).strip()
    password = str(proxy.get("password", "")).strip()
    if not host or port <= 0:
        return ""
    auth = f"{username}:{password}@" if username or password else ""
    return f"{proxy_type}://{auth}{host}:{port}"


def ensure_file_from_example(target: str, example: str) -> None:
    target_path = ROOT / target
    example_path = ROOT / example
    if target_path.exists():
        safe_print(f"已存在：{target}")
        return
    if not example_path.exists():
        raise SystemExit(f"缺少模板文件：{example}")
    target_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    safe_print(f"已创建：{target}")


def ensure_dirs() -> None:
    for name in ["accounts", "data", "logs", "sessions", "state"]:
        path = ROOT / name
        path.mkdir(exist_ok=True)
        safe_print(f"目录就绪：{name}")


def ensure_message_file() -> None:
    path = ROOT / "message.txt"
    if path.exists():
        safe_print("广告文本文件就绪：message.txt")
        return
    path.write_text("请在这里填写你的广告文本。\n", encoding="utf-8")
    safe_print("已创建广告文本文件：message.txt")


def ensure_dependencies() -> None:
    python = sys.executable
    safe_print(f"当前 Python：{python}")
    safe_print(f"Python 版本：{sys.version.split()[0]}")
    pip_check = subprocess.run([python, "-m", "pip", "--version"], cwd=ROOT)
    if pip_check.returncode != 0:
        safe_print("当前虚拟环境缺少 pip，正在修复。")
        run([python, "-m", "ensurepip", "--upgrade"])

    env = os.environ.copy()
    pip_args = [python, "-m", "pip", "--timeout", "60", "--retries", "3"]
    proxy_url = proxy_url_from_config()
    if proxy_url:
        env["HTTP_PROXY"] = proxy_url
        env["HTTPS_PROXY"] = proxy_url
        safe_print(f"pip 将使用代理：{proxy_url}")
        pip_args.extend(["--proxy", proxy_url])
    else:
        safe_print("pip 未配置代理。")
    run([*pip_args, "install", "--upgrade", "pip"], env=env)
    run([*pip_args, "install", "-r", str(ROOT / "requirements.txt")], env=env)


def validate_json(path: str) -> None:
    full_path = ROOT / path
    with full_path.open("r", encoding="utf-8") as f:
        json.load(f)
    safe_print(f"JSON 配置有效：{path}")


def compile_scripts() -> None:
    run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(ROOT / "sync_folder_groups.py"),
            str(ROOT / "ad_sender.py"),
            str(ROOT / "network_check.py"),
            str(ROOT / "account_manager.py"),
            str(ROOT / "account_login.py"),
            str(ROOT / "clear_session.py"),
        ]
    )
    safe_print("Python 脚本语法检查通过。")


def main() -> None:
    safe_print("========================================")
    safe_print("本机环境检测 / 自动安装依赖")
    safe_print("========================================")
    ensure_dirs()
    ensure_file_from_example("config.json", "config.example.json")
    ensure_file_from_example("ad_sender_config.json", "ad_sender_config.example.json")
    ensure_default_account()
    ensure_message_file()
    ensure_dependencies()
    validate_json("config.json")
    validate_json("ad_sender_config.json")
    compile_scripts()
    safe_print("")
    safe_print("环境检查完成，可以继续运行：")
    safe_print("01_登录电报.cmd")
    safe_print("02_执行广告任务.cmd")


if __name__ == "__main__":
    main()
