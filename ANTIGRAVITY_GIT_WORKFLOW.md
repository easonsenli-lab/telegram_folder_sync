# Antigravity Git Workflow For telegram_folder_sync

This repository is now the single source of truth for the `telegram_folder_sync` project.

Local source path:

```text
E:\telegram_workspace\telegram_folder_sync
```

Server runtime path:

```text
/root/telegram_folder_sync
```

The server is a runtime target only. Do not use server files as the development baseline.

## Core Rules

1. Always edit local source first.
2. Never edit production source directly on the server.
3. Never use server code to overwrite local code unless the user explicitly approves a recovery operation.
4. Never commit runtime data, sessions, databases, logs, local configs, or build artifacts.
5. Before deployment, create a server code backup and, when data may be touched, a server data backup.
6. Build frontend locally, then upload the generated `frontend/dist` to the server.
7. Server `frontend/dist/assets` must contain only the latest build output.

## Protected Files And Directories

Do not commit or overwrite these:

```text
data/
accounts/
sessions/
logs/
scratch/
*.db
*.db-*
*.sqlite
*.sqlite3
config.json
ad_sender_config.json
env_config.json
.env
frontend/node_modules/
frontend/dist/
frontend/deploy-package/
```

Only example configs are allowed in Git:

```text
config.example.json
ad_sender_config.example.json
```

## Before Editing

Run:

```bash
git status --short
```

If the worktree is dirty, inspect the changes before touching files:

```bash
git diff --stat
git diff -- <file>
```

Do not discard user changes. Do not run:

```bash
git reset --hard
git checkout -- .
```

unless the user explicitly asks for it.

## After Editing

Run the verification commands:

```bash
cd E:\telegram_workspace\telegram_folder_sync
python -m py_compile web_server.py db.py ad_sender.py private_dm_events.py

cd E:\telegram_workspace\telegram_folder_sync\frontend
npm run build
```

Then check what will be committed:

```bash
cd E:\telegram_workspace\telegram_folder_sync
git status --short
git diff --stat
```

## Commit Policy

Commit only source and documentation changes.

Recommended commit format:

```bash
git add <specific files>
git commit -m "type: short description"
```

Examples:

```text
fix: restore bot permission management page
fix: align auto join folder options with backend
chore: establish protected deployment workflow
docs: document server deployment rules
```

For stable versions, add a tag:

```bash
git tag stable-YYYYMMDD-HHMMSS
```

## Deployment Policy

Deployment direction must be:

```text
local Git source -> local build -> server backup -> server code upload -> service restart -> verification
```

Never deploy from old server source.

Before uploading, create a server code backup:

```bash
mkdir -p /root/telegram_folder_sync_code_backups
cd /root
tar --warning=no-file-changed \
  --exclude='telegram_folder_sync/data' \
  --exclude='telegram_folder_sync/accounts' \
  --exclude='telegram_folder_sync/sessions' \
  --exclude='telegram_folder_sync/*.db' \
  --exclude='telegram_folder_sync/*.db-*' \
  --exclude='telegram_folder_sync/frontend/node_modules' \
  --exclude='telegram_folder_sync/node_modules' \
  -czf /root/telegram_folder_sync_code_backups/telegram_folder_sync_code_before_<reason>_YYYYMMDD_HHMMSS.tar.gz \
  telegram_folder_sync
```

If data may be changed, also backup data first:

```bash
mkdir -p /root/telegram_folder_sync_data_backups
cd /root/telegram_folder_sync
tar --dereference -czf /root/telegram_folder_sync_data_backups/telegram_folder_sync_data_before_<reason>_YYYYMMDD_HHMMSS.tar.gz \
  data accounts sessions config.json *.db *.db-*
```

After upload, verify:

```bash
cd /root/telegram_folder_sync
python3 -m py_compile web_server.py db.py
systemctl restart rosepay.service
systemctl is-active rosepay.service
ss -ltnp | grep -E ':8000|:8001|:8011'
```

Expected:

```text
rosepay.service active
main web service on port 8000
port 8001 belongs to rosepay-monitor.service
```

## Rollback

Rollback must use the timestamped backup created immediately before deployment.

Do not guess which folder is correct. Confirm:

```bash
ls -1dt /root/telegram_folder_sync_code_backups/*
ls -1dt /root/telegram_folder_sync_data_backups/*
```

Then restore only what is needed.

## Final Reminder

The local Git repository is the truth. The server is only where the truth is deployed.

