from __future__ import annotations

from account_manager import choose_account, display_name
from sync_folder_groups import load_config, resolve_path, safe_print


def main() -> None:
    account_path = choose_account("请选择要清除 Session 的账号")
    config = load_config(account_path)
    session_path = resolve_path(account_path.parent, config["session_name"])
    safe_print("")
    safe_print(f"当前账号：{display_name(account_path)}")
    for suffix in ["", ".session", ".session-journal"]:
        target = session_path.parent / f"{session_path.name}{suffix}"
        if target.exists():
            target.unlink()
            safe_print(f"已删除：{target}")
    safe_print("Session 已清除。下次登录该账号会重新验证。")


if __name__ == "__main__":
    main()
