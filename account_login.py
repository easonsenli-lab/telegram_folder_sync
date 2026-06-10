from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from account_manager import choose_account, display_name


def main() -> None:
    account_path = choose_account("请选择要登录/检查的账号")
    print("")
    print(f"当前账号：{display_name(account_path)}")
    print(f"配置文件：accounts/{account_path.name}")
    print("")

    script = Path(__file__).resolve().parent / "sync_folder_groups.py"
    command = [
        sys.executable,
        str(script),
        "--config",
        str(account_path),
        "--debug-folders",
    ]
    raise SystemExit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
