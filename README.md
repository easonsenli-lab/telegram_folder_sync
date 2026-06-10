# Telegram folder group sync

第一版只做一件事：读取 Telegram 账号里指定聊天文件夹，例如 `广告`，把里面的群组导出为 `groups.csv` 和 SQLite。

它不会发送消息。

## 准备

## 登录模式

默认使用 Telegram Desktop 的公开客户端模板登录，不需要在 `my.telegram.org/apps` 创建应用：

```json
"auth_mode": "builtin_telegram_desktop"
```

首次运行仍需要输入手机号、验证码，session 会保存在本项目 `sessions` 目录。

如果你能正常创建 Telegram API 应用，也可以切换成 `api_id/api_hash` 模式：

```json
"auth_mode": "api_id_hash"
```

然后到 Telegram 官方开发者页面创建应用，拿到 `api_id` 和 `api_hash`：

```text
https://my.telegram.org/apps
```

## 准备

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item config.example.json config.json
```

另有一个预留的 `telegram_desktop_tdata` 模式，可以读取已经登录的 Telegram Desktop `tdata`。这个模式依赖 `opentele`，在 Python 3.12 上可能需要 C++ Build Tools 才能安装 `tgcrypto`。

如果后续启用 `telegram_desktop_tdata`，请把 Telegram Desktop 的 `tdata` 目录复制或链接到本项目下的相对目录，例如：

```text
tdata
```

所有配置路径都建议写相对路径。相对路径会按配置文件所在目录解析。

## 同步广告文件夹

```powershell
.\.venv\Scripts\python.exe .\sync_folder_groups.py --config .\config.json
```

## 双击执行文件

本目录已经提供两个 Windows 执行文件：

```text
00_检测环境并安装依赖.cmd
01_登录电报.cmd
02_执行广告任务.cmd
03_清除登录Session.cmd
04_网络诊断.cmd
05_QuickQ网络诊断_无需Python.cmd
99_打包前清理.cmd
```

`00_检测环境并安装依赖.cmd` 用于检测本机 Python、虚拟环境、依赖包、配置文件和目录。缺少虚拟环境或依赖时会自动安装。

Python 检测和安装参数集中放在 `env_config.json`。需要更换 Python 版本、安装包下载地址、winget 包名或虚拟环境目录时，优先修改这个配置文件。

打包给别人时不要包含 `.venv` 目录。虚拟环境包含本机绝对路径，不适合跨电脑复制。`01`、`02`、`03`、`04` 只检查环境是否可用，不会自动安装；如果环境缺失或 `.venv` 是从其他电脑复制来的，请先运行 `00_检测环境并安装依赖.cmd`。

`01_登录电报.cmd` 只用于 Telegram 登录和账号检查。运行后会先让你选择账号；每个账号有独立配置、独立 session 和独立群组数据。未登录时会提示输入手机号、验证码和二步验证密码；已登录时会显示当前账号和文件夹列表。

`02_执行广告任务.cmd` 会先让你选择账号，再实时同步该账号所有聊天文件夹中的群组到对应的 `data/账号名/groups.csv` 和 `data/账号名/groups.sqlite3`，然后进入真实广告任务流程，要求你选择文件夹、填写任务次数/间隔，并在最后按回车确认继续；输入 `n` 可取消。

## 多账号

账号配置保存在 `accounts` 目录。第一次运行会自动创建 `accounts/default.json`；也可以在账号选择界面输入 `0` 创建新账号。每个账号会使用独立路径：

```text
accounts/account_1.json
sessions/account_1/telegram_user.session
data/account_1/groups.csv
data/account_1/groups.sqlite3
```

切换账号时，不要在任务运行中切换。先停止 `02`，再重新运行 `02` 选择另一个账号。

`03_清除登录Session.cmd` 用于清除本项目保存的 Telegram 登录 session。清除后再次运行 `01_登录电报.cmd` 可以重新登录其他账号。

`04_网络诊断.cmd` 用于排查登录超时。它不会登录账号，也不会创建 session，只测试 DNS、Telegram 端口、代理端口和 Telethon 连接，并把结果写入 `logs` 目录。

`05_QuickQ网络诊断_无需Python.cmd` 用于在 Python 或 `.venv` 损坏时先排查 QuickQ/系统代理/Telegram 网络。它不依赖 Python，具体诊断逻辑在 `quickq_network_check.ps1`。

`99_打包前清理.cmd` 用于打包前清除本机虚拟环境、session、日志、状态和输出数据。清理后再压缩整个目录给别人。

也可以不改 `config.json`，直接用参数指定文件夹名：

```powershell
.\.venv\Scripts\python.exe .\sync_folder_groups.py --config .\config.json --folder a
.\.venv\Scripts\python.exe .\sync_folder_groups.py --config .\config.json --folder 广告
```

首次运行会要求输入 Telegram 手机号、验证码，可能还会要求 2FA 密码。登录 session 会保存在 `sessions/telegram_user.session`。

## 切换账号

删除本项目 session 后，下次运行会重新要求登录，可以换另一个 Telegram 账号：

```powershell
.\.venv\Scripts\python.exe .\sync_folder_groups.py --config .\config.json --reset-session
```

这只会清除本项目里的本地登录 session，不会删除 Telegram Desktop 的登录，也不会封禁或注销账号。

每次同步和发送前，程序都会检查当前登录账号状态。如果 session 失效、账号被封禁、账号被删除或接口返回受限标记，会输出醒目的提示并停止执行。

## 连接超时和代理

如果其他电脑登录时出现 `TimeoutError`，通常是那台电脑无法连接 Telegram，不是绑定本机，也不是 session 文件导致。请先检查网络、防火墙、代理软件或地区访问限制。

需要走本机代理时，编辑 `config.json`：

```json
"proxy": {
  "enabled": true,
  "type": "http",
  "host": "127.0.0.1",
  "port": 8800,
  "username": "",
  "password": ""
}
```

QuickQ 当前检测到的 Windows 系统代理是 `127.0.0.1:8800`，并且本机测试确认它是 HTTP 代理，不是 SOCKS5。默认配置已经按 QuickQ 设置为 HTTP 代理。修改后重新运行 `01_登录电报.cmd`。

`00_检测环境并安装依赖.cmd` 安装 Python 依赖时也会读取这个代理配置，让 `pip` 通过 QuickQ 下载依赖。

Telethon 代理连接需要 `python-socks[asyncio]`，已经写入 `requirements.txt`。如果旧包仍然超时，请先运行 `00_检测环境并安装依赖.cmd` 更新依赖。

## 输出

- `data/账号名/groups.csv`: 可人工查看和编辑的群组清单
- `data/账号名/groups.sqlite3`: 后续发送器可直接读取的数据库

CSV 字段：

```text
folder,chat_id,access_hash,title,username,type,enabled,last_seen_at,last_sent_at,note
```

如果群从文件夹移出，默认不会删除旧记录，而是把 `enabled` 标为 `false`，方便保留历史和备注。

## 配置广告任务

复制发送配置：

```powershell
Copy-Item ad_sender_config.example.json ad_sender_config.json
```

编辑：

- `message.txt`: 广告文本
- `ad_sender_config.json`
  - `task_interval_minutes`: 默认每轮任务之间的间隔，单位分钟
  - `group_interval_seconds`: 默认每个群之间的发送间隔，单位秒
  - `folder`: 只发送这个文件夹导出的群
  - `max_cycles`: 最大循环次数，`0` 表示一直循环
  - `max_groups_per_cycle`: 每轮最多发送多少个群，`0` 表示不限制

运行后会用中文逐步提示你选择文件夹、任务次数、任务间隔和群组发送间隔。选择文件夹后，会自动发送该文件夹内全部已同步群组，不再逐个选择群组。

先预览，不真正发送。运行后会依次提示：文件夹、任务次数、任务间隔、群组发送间隔、广告文本确认。

```powershell
.\.venv\Scripts\python.exe .\ad_sender.py --config .\ad_sender_config.json
```

确认无误后才真实发送。真实发送前按回车继续，输入 `n` 可取消：

```powershell
.\.venv\Scripts\python.exe .\ad_sender.py --config .\ad_sender_config.json --send
```

如果“任务次数”直接回车，就是一直按提示的任务间隔循环执行。预览模式不会无限循环，真实发送模式会持续运行。

```powershell
.\.venv\Scripts\python.exe .\ad_sender.py --config .\ad_sender_config.json --send
```

日志输出：

```text
logs/ad-send-log.csv
```

请只向你有权限、群规允许或明确同意接收广告的群组发送。遇到 Telegram 返回限流或禁止发言，程序会记录日志并按配置暂停/跳过。
