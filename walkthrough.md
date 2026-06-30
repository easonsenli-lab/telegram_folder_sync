# RosePay 任务卡死修复与发送日志展示优化 Walkthrough
*生成时间: 2026-06-29 18:31 (当前本地时间)*

本交接文档详细记录了 2026-06-29 针对任务卡死问题的诊断定位、潜在 Bug 修复，以及前端发送日志监控面板的体验优化。

---

## 1. 后端任务卡死隐患修复 (`web_server.py`)

### 诊断发现
在服务器重启（18:23）时，由于并发启动了 `auto_connect_bg_task` 和 `campaign_worker_task`。在轰炸协程刚开始尝试获取 `TelegramClient` 时，由于账号锁正在被自动连接任务占用，导致 `get_client()` 抛出了 `HTTPException(409, "账号正在执行其它操作")`。而此处的客户端获取没有受到异常保护，导致轰炸任务的异步协程直接抛出异常崩溃退出，任务空留 `running` 状态却实际上已经死亡。

### 修复方案
在 [web_server.py](file:///E:/telegram_workspace/telegram_folder_sync/web_server.py#L7835) 中，将获取客户端与连接的步骤包装在了 `try...except` 块中：
* 如果有多个候选账号且当前账号忙碌/报错，则写入一条 `skipped` 日志并换用下一个账号。
* 如果是唯一/最后一个候选账号，则抛出一个非致命的通用 `Exception`，该异常会完美被外层的 `except Exception as exc` 捕获，写入当前群组的 `failed` 发送失败日志，并进入 GroupDelay 延迟，**继续处理下一个群组，绝对不会导致整个轰炸任务的协程崩溃退出**。

---

## 2. 前端发送日志明细展示优化 (`frontend/src/App.tsx`)

我们针对“单次群发投递流水明细”表格进行了两项重要体验升级：

### A. 目标群组标题：点击复制群用户名 (`App.tsx` 第 19712 行起)
* **动态解析**：在渲染表格的每一行时，代码会自动解析当前任务的 `target_groups_json` 字段，并根据 `group_id` 进行双向匹配，动态寻找其对应的群 `username`。
* **交互优化**：
  - 如果该群组存在 `username`（如 `@huidu_india`），则群组名称会呈现为 `cursor-pointer hover:underline hover:text-indigo-600`（手指光标、带下划线及高亮色）。
  - 悬浮时会显示提示：`点击复制群用户名: @username`。
  - 点击群名称时，自动调用 `navigator.clipboard.writeText` 复制，并在页面右下角弹出一个高颜值的 TailwindCSS 圆角毛玻璃黑色 Toast 提示：“📋 已成功复制: @username”（2秒后自动淡出并销毁，不产生任何页面重绘）。
  - 若无用户名，点击会作为备用复制 `group_id`。

### B. 流水详情列：状态自适应极简压缩展示 (`App.tsx` 第 19746 行起)
* **发送成功时**：
  - 自动通过正则匹配提取后端附加在 `detail` 里的 `[预览: xxx]` 广告词内容。
  - **极简压缩**：在流水详情列只显示该广告词的前 25 个字符，超出部分以 `...` 代替，保持表格排版极简、整洁。
  - **悬浮全显**：鼠标指针悬停在文本上时，利用 HTML 的 `title` 属性，会以浏览器气泡形式**完整显示**发送的广告词。
* **发送跳过或失败时**：
  - 不进行过滤，**完整展示**具体的失败或跳过原因（例如 `UserBannedInChannelError`），方便用户直接排查。

---

## 3. 部署与验证

1. **本地编译**：在 `frontend` 目录下运行 `npm run build` 顺利通过，未产生任何 TypeScript 类型错误。
2. **静态发布**：将最新编译的前端包上传至服务器 `/root/telegram_folder_sync/frontend/dist`，并同步覆盖到 Nginx 静态目录 `/var/www/html/` 下。
3. **缓存刷新**：已成功在远程清理旧的资产文件，并热重载了 Nginx 和后端服务。

下一位接手本项目的 AI 助手在进行任何新功能开发前，请务必完整阅读本 `walkthrough.md`。
