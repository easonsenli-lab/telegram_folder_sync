import os
import sqlite3

# Enable high-concurrency WAL mode and busy timeout for all SQLite connections globally
if not hasattr(sqlite3, "_patched_for_wal"):
    _orig_connect = sqlite3.connect
    def _patched_connect(database, *args, **kwargs):
        kwargs.setdefault("timeout", 30.0)
        conn = _orig_connect(database, *args, **kwargs)
        if database != ":memory:":
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
            except Exception:
                pass
        return conn
    sqlite3.connect = _patched_connect
    sqlite3._patched_for_wal = True

import csv
import json
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from sqlmodel import Field, SQLModel, create_engine, Session, select



DB_DIR = Path(__file__).resolve().parent / "data"

DB_PATH = DB_DIR / "rosepay.db"

DATABASE_URL = f"sqlite:///{DB_PATH}"



# Connect args needed for SQLite to support multi-threaded access in FastAPI

engine = create_engine(

    DATABASE_URL,

    echo=False,

    connect_args={"check_same_thread": False}

)



def migrate_bot_authorized_users():
    import json
    import os
    import sqlite3
    import datetime

    # 1. 迁移翻译 Bot
    json_path = "/opt/rosepay-translate-bot/data/translate_access.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            allowed_ids = data.get("allowed_user_ids", [])
            owner_ids = data.get("owner_chat_ids", [])

            with sqlite3.connect(str(DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM bot_authorized_users WHERE bot_type = 'translate_bot';")
                if cursor.fetchone()[0] == 0:
                    print(f"Migrating {len(allowed_ids)} users to translate_bot authorized table...")
                    for uid in allowed_ids:
                        cursor.execute(
                            "INSERT OR IGNORE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                            (str(uid), "translate_bot", "", "external", None, 1)
                        )
                    for uid in owner_ids:
                        if uid > 0:
                            cursor.execute(
                                "INSERT OR IGNORE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                                (str(uid), "translate_bot", "", "admin", None, 1)
                            )
                    conn.commit()
        except Exception as exc:
            print(f"Failed to migrate translate_bot access list: {exc}")

    # 2. 迁移 AI Bot
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bot_authorized_users WHERE bot_type = 'ai_bot';")
            if cursor.fetchone()[0] == 0:
                print("Migrating admins table bindings to ai_bot authorized table...")
                cursor.execute("SELECT telegram_chat_id, role, username, telegram_contact FROM admins WHERE telegram_chat_id IS NOT NULL AND telegram_chat_id != '';")
                for chat_id, role, username, contact in cursor.fetchall():
                    r = "admin" if (username == "eason" or role == "admin") else "employee"
                    tg_uname = contact.lstrip("@") if contact else ""
                    cursor.execute(
                        "INSERT OR IGNORE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                        (str(chat_id), "ai_bot", tg_uname, r, None, 1)
                    )
                conn.commit()
    except Exception as exc:
        print(f"Failed to migrate admins bindings to ai_bot table: {exc}")

    # 3. 自动迁移 accounts 中目前已录入的托管账号（如 Frank 郭嘉等），默认全网开通授权
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, account_name, owner_username FROM accounts;")
            accounts_rows = cursor.fetchall()
            approved_time = datetime.datetime.now().isoformat()
            for acc_id, acc_name, owner in accounts_rows:
                if acc_id and len(str(acc_id)) > 3:
                    # 授权 AI Bot
                    cursor.execute(
                        "INSERT OR IGNORE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, approved_at, approved_by, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(acc_id), "ai_bot", acc_name, "external", owner, approved_time, "system_auto", 1)
                    )
                    # 授权 翻译 Bot
                    cursor.execute(
                        "INSERT OR IGNORE INTO bot_authorized_users (telegram_chat_id, bot_type, telegram_username, role, owner_username, approved_at, approved_by, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(acc_id), "translate_bot", acc_name, "external", owner, approved_time, "system_auto", 1)
                    )
            conn.commit()
            print("Successfully auto-authorized all accounts in database.")
    except Exception as exc:
        print(f"Failed to auto-authorize accounts: {exc}")

class BotAuthorizedUserDb(SQLModel, table=True):
    __tablename__ = "bot_authorized_users"
    telegram_chat_id: str = Field(primary_key=True)
    bot_type: str = Field(primary_key=True)  # 'ai_bot' or 'translate_bot'
    telegram_username: Optional[str] = Field(default=None)
    role: str = Field(default="employee")    # 'admin', 'employee', 'external'
    owner_username: Optional[str] = Field(default=None)
    approved_at: Optional[str] = Field(default=None)
    approved_by: Optional[str] = Field(default=None)
    is_active: int = Field(default=1)

class GroupCategoryDb(SQLModel, table=True):
    __tablename__ = "group_categories"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    company: str = Field(default="admin")


class GroupDb(SQLModel, table=True):

    __tablename__ = "groups_library"



    # Using string id matching the original groups.json IDs

    id: str = Field(default=None, primary_key=True)

    company: str = Field(default="admin", primary_key=True)

    title: str

    username: str

    type: str

    enabled: bool

    memberCount: int

    category: str
    price: float = Field(default=0.0)
    quality_score: int = Field(default=0)
    relevance_score: int = Field(default=0)
    activity_score: int = Field(default=0)
    engagement_score: int = Field(default=0)
    created_by: str = Field(default="admin")
    updated_by: str = Field(default="admin")
    bot_rules_summary: Optional[str] = Field(default=None)
    bot_rules_raw_logs: Optional[str] = Field(default=None)



class AdLogDb(SQLModel, table=True):

    __tablename__ = "ad_logs"



    id: Optional[int] = Field(default=None, primary_key=True)

    company: str = Field(default="admin")

    time: str

    folder: str

    chat_id: str

    title: str

    action: str

    status: str

    detail: str



class CampaignTaskDb(SQLModel, table=True):

    __tablename__ = "campaign_tasks"



    id: str = Field(default=None, primary_key=True)

    owner_username: str = Field(default="")

    company: str = Field(default="admin")

    account_id: str

    phone: str

    account_ids_json: str = Field(default="")

    phones_json: str = Field(default="")

    status: str  # 'running', 'stopped', 'completed', 'failed'

    max_cycles: int  # 0 for infinite

    current_cycle: int = 0

    round_interval_minutes: int

    group_interval_seconds: int

    is_safety: bool = False

    message: str

    target_groups_json: str  # JSON array: [{"chat_id": int, "title": str, "username": str}]

    task_config_json: str = Field(default="")

    success_count: int = 0

    fail_count: int = 0

    error_detail: Optional[str] = None

    created_at: str

    updated_at: str
    created_by: str = Field(default="admin")
    updated_by: str = Field(default="admin")



class CampaignLogDb(SQLModel, table=True):
    __tablename__ = "campaign_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    company: str = Field(default="admin", index=True)
    task_id: str = Field(index=True)
    timestamp: str
    cycle: int
    group_title: str
    group_id: str
    group_username: Optional[str] = None
    ad_ref: Optional[str] = None

    account_id: Optional[str] = None

    phone: Optional[str] = None

    status: str  # 'success', 'failed'

    detail: str



class PrivateSendQueueDb(SQLModel, table=True):

    __tablename__ = "private_send_queue"

    id: str = Field(default=None, primary_key=True)

    account_id: str

    peer_id: str

    text: str

    status: str = Field(default="queued")  # queued, sending, sent, failed

    created_by: str = Field(default="")

    created_at: float

    updated_at: float

    sent_at: Optional[float] = None

    sent_message_id: Optional[int] = None

    sent_message_json: Optional[str] = None

    error: Optional[str] = None



class AccountDb(SQLModel, table=True):

    __tablename__ = "accounts"



    id: str = Field(default=None, primary_key=True)  # account_id

    company: str = Field(default="admin")

    account_name: str

    auth_mode: str

    api_id: Optional[int] = None

    api_hash: Optional[str] = None

    tdata_path: Optional[str] = None

    session_name: str

    folder_name: str

    output_csv: str

    output_db: str

    include_types: str = "group,supergroup"

    mark_removed_disabled: bool = True

    connection_timeout_seconds: int = 12

    connection_retries: int = 2



    proxy_enabled: bool = True

    proxy_type: str = "http"

    proxy_host: str = "127.0.0.1"

    proxy_port: int = 8800

    proxy_username: str = ""

    proxy_password: str = ""



    # profile mod

    profile_modified: bool = False

    profile_modified_name: Optional[str] = None

    profile_modified_username: Optional[str] = None



    # campaign options

    campaign_folder: Optional[str] = None

    campaign_message: Optional[str] = None

    campaign_interval_minutes: int = 60

    campaign_group_interval_seconds: int = 5



    # 2FA password cache

    pass2fa: Optional[str] = None

    page_id: Optional[str] = None
    created_by: str = Field(default="admin")
    updated_by: str = Field(default="admin")
    is_available: bool = Field(default=True)
    owner_username: str = Field(default="")
    bot_setup_status: str = Field(default="not_started")
    bot_step_1_input: Optional[str] = None
    bot_step_2_input: Optional[str] = None
    bot_username: Optional[str] = None




    def to_dict(self) -> dict:

        return {

            "company": self.company,

            "account_name": self.account_name,

            "auth_mode": self.auth_mode,

            "api_id": self.api_id,

            "api_hash": self.api_hash,

            "tdata_path": self.tdata_path,

            "session_name": self.session_name,

            "folder_name": self.folder_name,

            "output_csv": self.output_csv,

            "output_db": self.output_db,

            "include_types": [x.strip() for x in self.include_types.split(",") if x.strip()],

            "mark_removed_disabled": self.mark_removed_disabled,

            "connection_timeout_seconds": self.connection_timeout_seconds,

            "connection_retries": self.connection_retries,

            "proxy": {

                "enabled": self.proxy_enabled,

                "type": self.proxy_type,

                "host": self.proxy_host,

                "port": self.proxy_port,

                "username": self.proxy_username,

                "password": self.proxy_password

            },

            "profile_modified": self.profile_modified,

            "profile_modified_name": self.profile_modified_name,

            "profile_modified_username": self.profile_modified_username,

            "campaign_folder": self.campaign_folder,

            "campaign_message": self.campaign_message,

            "campaign_interval_minutes": self.campaign_interval_minutes,

            "campaign_group_interval_seconds": self.campaign_group_interval_seconds,

            "pass2fa": self.pass2fa,

            "page_id": self.page_id,

            "created_by": self.created_by,

            "updated_by": self.updated_by,

            "is_available": self.is_available,

            "owner_username": self.owner_username,

            "bot_setup_status": self.bot_setup_status,

            "bot_step_1_input": self.bot_step_1_input,

            "bot_step_2_input": self.bot_step_2_input,

            "bot_username": self.bot_username


        }



    @classmethod

    def from_dict(cls, account_id: str, d: dict) -> "AccountDb":

        proxy = d.get("proxy") or {}

        include_types = d.get("include_types")

        if isinstance(include_types, list):

            include_types_str = ",".join(include_types)

        else:

            include_types_str = str(include_types or "group,supergroup")



        return cls(

            id=account_id,

            company=d.get("company", "admin"),

            account_name=d.get("account_name", account_id),

            auth_mode=d.get("auth_mode", "builtin_telegram_desktop"),

            api_id=d.get("api_id"),

            api_hash=d.get("api_hash"),

            tdata_path=d.get("tdata_path"),

            session_name=d.get("session_name", f"sessions/{account_id}/telegram_user"),

            folder_name=d.get("folder_name", "广告"),

            output_csv=d.get("output_csv", f"data/{account_id}/groups.csv"),

            output_db=d.get("output_db", f"data/{account_id}/groups.sqlite3"),

            include_types=include_types_str,

            mark_removed_disabled=d.get("mark_removed_disabled", True),

            connection_timeout_seconds=d.get("connection_timeout_seconds", 12),

            connection_retries=d.get("connection_retries", 2),

            proxy_enabled=proxy.get("enabled", True),

            proxy_type=proxy.get("type", "http"),

            proxy_host=proxy.get("host", "127.0.0.1"),

            proxy_port=proxy.get("port", 8800),

            proxy_username=proxy.get("username", ""),

            proxy_password=proxy.get("password", ""),

            profile_modified=d.get("profile_modified", False),

            profile_modified_name=d.get("profile_modified_name"),

            profile_modified_username=d.get("profile_modified_username"),

            campaign_folder=d.get("campaign_folder"),

            campaign_message=d.get("campaign_message"),

            campaign_interval_minutes=d.get("campaign_interval_minutes", 60),

            campaign_group_interval_seconds=d.get("campaign_group_interval_seconds", 5),

            pass2fa=d.get("pass2fa"),

            page_id=d.get("page_id"),

            created_by=d.get("created_by", "admin"),

            updated_by=d.get("updated_by", "admin"),

            is_available=d.get("is_available", True),

            owner_username=d.get("owner_username", ""),

            bot_setup_status=d.get("bot_setup_status", "not_started"),

            bot_step_1_input=d.get("bot_step_1_input"),

            bot_step_2_input=d.get("bot_step_2_input"),

            bot_username=d.get("bot_username")


        )



class CompanyDb(SQLModel, table=True):

    __tablename__ = "companies"



    id: Optional[int] = Field(default=None, primary_key=True)

    name: str = Field(index=True, unique=True)

    created_at: str



class TelegramBotDb(SQLModel, table=True):
    __tablename__ = "telegram_bots"

    id: Optional[int] = Field(default=None, primary_key=True)
    bot_username: str = Field(unique=True, index=True)
    bot_token: str
    bot_type: str  # 'ai_bot', 'translate_bot', 'custom'
    title: Optional[str] = Field(default="")
    description: Optional[str] = Field(default="")
    is_active: int = Field(default=1)
    created_at: str = Field(default="")


class AdminDb(SQLModel, table=True):
    __tablename__ = "admins"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    salt: str
    role: str = "admin"  # admin or user
    company: str = Field(default="admin")
    telegram_contact: str = Field(default="")
    telegram_chat_id: Optional[str] = Field(default=None)
    forum_chat_id: Optional[str] = Field(default=None)
    created_at: str

class RolePermissionDb(SQLModel, table=True):
    __tablename__ = "role_permissions"

    role: str = Field(default=None, primary_key=True)
    allowed_tabs: str = Field(default="")

class LoginLogDb(SQLModel, table=True):

    __tablename__ = "login_logs"



    id: Optional[int] = Field(default=None, primary_key=True)

    company: str = Field(default="admin")

    timestamp: str

    phone: str

    api_link: Optional[str] = None

    original_password: Optional[str] = None

    current_password: Optional[str] = None

    login_type: str

    status: str

    error_detail: Optional[str] = None





class PredefinedAdDb(SQLModel, table=True):

    __tablename__ = "predefined_ads"



    id: Optional[int] = Field(default=None, primary_key=True)

    company: str = Field(default="admin")

    description: str

    content: str
    created_by: str = Field(default="admin")
    updated_by: str = Field(default="admin")
    group_type: str = Field(default="英文短")



class ScrapedGroupDb(SQLModel, table=True):

    __tablename__ = "scraped_groups"



    id: str = Field(default=None, primary_key=True)  # link or username

    title: Optional[str] = None

    link: str

    member_count: Optional[int] = 0

    category: str = "unknown"  # 'life', 'business', 'spam', 'unknown'

    quality_score: int = 0

    analysis_summary: Optional[str] = None

    status: str = "pending"  # 'pending', 'joined', 'ignored'

    keyword: str = ""

    created_at: datetime = Field(default_factory=datetime.utcnow)

    company: str = "admin"

    group_type: str = Field(default="group")  # 'group' or 'channel'

    is_active: bool = Field(default=True)

    is_dead: bool = Field(default=False)

    is_important: bool = Field(default=False)

    relevance_score: int = Field(default=0)

    activity_score: int = Field(default=0)

    engagement_score: int = Field(default=0)

    spam_penalty: int = Field(default=0)







def hash_password(password: str) -> tuple[str, str]:

    """Hashes a password using PBKDF2 with SHA256 and a random salt."""

    salt = secrets.token_hex(16)

    pwd_bytes = password.encode("utf-8")

    salt_bytes = salt.encode("utf-8")

    pwd_hash = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, 100000).hex()

    return pwd_hash, salt



def verify_password(password: str, salt: str, password_hash: str) -> bool:

    """Verifies a password against its PBKDF2 hash and salt."""

    pwd_bytes = password.encode("utf-8")

    salt_bytes = salt.encode("utf-8")

    pwd_hash = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, 100000).hex()

    return pwd_hash == password_hash



def migrate_columns():

    # Check if accounts table has pass2fa column, if not, add it

    import sqlite3

    try:

        with sqlite3.connect(DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(accounts)")

            columns = [info[1] for info in cursor.fetchall()]

            if "pass2fa" not in columns:

                print("Migrating DB: adding column 'pass2fa' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN pass2fa TEXT")

                conn.commit()

            if "page_id" not in columns:

                print("Migrating DB: adding column 'page_id' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN page_id TEXT")

                conn.commit()

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()

            if "is_available" not in columns:

                print("Migrating DB: adding column 'is_available' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN is_available INTEGER DEFAULT 1")

                conn.commit()

            if "owner_username" not in columns:

                print("Migrating DB: adding column 'owner_username' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN owner_username TEXT DEFAULT ''")

                conn.commit()

                cursor.execute("UPDATE accounts SET owner_username = created_by WHERE owner_username IS NULL OR owner_username = ''")

                conn.commit()

            if "bot_setup_status" not in columns:

                print("Migrating DB: adding column 'bot_setup_status' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN bot_setup_status TEXT DEFAULT 'not_started'")

                conn.commit()

            if "bot_step_1_input" not in columns:

                print("Migrating DB: adding column 'bot_step_1_input' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN bot_step_1_input TEXT")

                conn.commit()

            if "bot_step_2_input" not in columns:

                print("Migrating DB: adding column 'bot_step_2_input' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN bot_step_2_input TEXT")

                conn.commit()

            if "bot_username" not in columns:

                print("Migrating DB: adding column 'bot_username' to 'accounts' table...")

                cursor.execute("ALTER TABLE accounts ADD COLUMN bot_username TEXT")

                conn.commit()




            cursor.execute("PRAGMA table_info(admins)")

            columns = [info[1] for info in cursor.fetchall()]

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'admins' table...")

                cursor.execute("ALTER TABLE admins ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()

            if "telegram_contact" not in columns:

                print("Migrating DB: adding column 'telegram_contact' to 'admins' table...")

                cursor.execute("ALTER TABLE admins ADD COLUMN telegram_contact TEXT DEFAULT ''")

                conn.commit()

            if "telegram_chat_id" not in columns:

                print("Migrating DB: adding column 'telegram_chat_id' to 'admins' table...")

                cursor.execute("ALTER TABLE admins ADD COLUMN telegram_chat_id TEXT")

                conn.commit()

            if "forum_chat_id" not in columns:

                print("Migrating DB: adding column 'forum_chat_id' to 'admins' table...")

                cursor.execute("ALTER TABLE admins ADD COLUMN forum_chat_id TEXT")

                conn.commit()



            cursor.execute("PRAGMA table_info(ad_logs)")

            columns = [info[1] for info in cursor.fetchall()]

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'ad_logs' table...")

                cursor.execute("ALTER TABLE ad_logs ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()



            cursor.execute("PRAGMA table_info(campaign_logs)")

            columns = [info[1] for info in cursor.fetchall()]

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'campaign_logs' table...")

                cursor.execute("ALTER TABLE campaign_logs ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()



            cursor.execute("PRAGMA table_info(login_logs)")

            columns = [info[1] for info in cursor.fetchall()]

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'login_logs' table...")

                cursor.execute("ALTER TABLE login_logs ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()



            cursor.execute("PRAGMA table_info(predefined_ads)")

            columns = [info[1] for info in cursor.fetchall()]

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'predefined_ads' table...")

                cursor.execute("ALTER TABLE predefined_ads ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()

            if "group_type" not in columns:

                print("Migrating DB: adding column 'group_type' to 'predefined_ads' table...")

                cursor.execute("ALTER TABLE predefined_ads ADD COLUMN group_type TEXT DEFAULT '英文短'")

                conn.commit()

                # Update existing records to '英文短'
                cursor.execute("UPDATE predefined_ads SET group_type = '英文短' WHERE group_type IS NULL OR group_type = ''")
                conn.commit()



            cursor.execute("PRAGMA table_info(campaign_tasks)")

            columns = [info[1] for info in cursor.fetchall()]

            if "owner_username" not in columns:

                print("Migrating DB: adding column 'owner_username' to 'campaign_tasks' table...")

                cursor.execute("ALTER TABLE campaign_tasks ADD COLUMN owner_username TEXT DEFAULT ''")

                conn.commit()

                cursor.execute("SELECT username FROM admins LIMIT 1")

                row = cursor.fetchone()

                if row:

                    admin_username = row[0]

                    cursor.execute("UPDATE campaign_tasks SET owner_username = ?", (admin_username,))

                    conn.commit()

            if "company" not in columns:

                print("Migrating DB: adding column 'company' to 'campaign_tasks' table...")

                cursor.execute("ALTER TABLE campaign_tasks ADD COLUMN company TEXT DEFAULT 'admin'")

                conn.commit()

            if "account_ids_json" not in columns:

                print("Migrating DB: adding column 'account_ids_json' to 'campaign_tasks' table...")

                cursor.execute("ALTER TABLE campaign_tasks ADD COLUMN account_ids_json TEXT DEFAULT ''")

                conn.commit()

            if "phones_json" not in columns:

                print("Migrating DB: adding column 'phones_json' to 'campaign_tasks' table...")

                cursor.execute("ALTER TABLE campaign_tasks ADD COLUMN phones_json TEXT DEFAULT ''")

                conn.commit()

            if "task_config_json" not in columns:

                print("Migrating DB: adding column 'task_config_json' to 'campaign_tasks' table...")

                cursor.execute("ALTER TABLE campaign_tasks ADD COLUMN task_config_json TEXT DEFAULT ''")

                conn.commit()

            cursor.execute("PRAGMA table_info(campaign_logs)")

            columns = [info[1] for info in cursor.fetchall()]

            if "account_id" not in columns:

                print("Migrating DB: adding column 'account_id' to 'campaign_logs' table...")

                cursor.execute("ALTER TABLE campaign_logs ADD COLUMN account_id TEXT")

                conn.commit()

            if "phone" not in columns:

                print("Migrating DB: adding column 'phone' to 'campaign_logs' table...")

                cursor.execute("ALTER TABLE campaign_logs ADD COLUMN phone TEXT")

                conn.commit()

            if "group_username" not in columns:

                print("Migrating DB: adding column 'group_username' to 'campaign_logs' table...")

                cursor.execute("ALTER TABLE campaign_logs ADD COLUMN group_username TEXT")

                conn.commit()

            if "ad_ref" not in columns:

                print("Migrating DB: adding column 'ad_ref' to 'campaign_logs' table...")

                cursor.execute("ALTER TABLE campaign_logs ADD COLUMN ad_ref TEXT")

                conn.commit()



            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups_library'")

            if cursor.fetchone():

                cursor.execute("PRAGMA table_info(groups_library)")

                columns = [info[1] for info in cursor.fetchall()]

                if "company" not in columns:

                    print("Migrating groups_library table to add composite primary key...")

                    cursor.execute("""

                        CREATE TABLE groups_library_new (

                            id TEXT NOT NULL,

                            company TEXT NOT NULL DEFAULT 'admin',

                            title TEXT NOT NULL,

                            username TEXT NOT NULL,

                            type TEXT NOT NULL,

                            enabled INTEGER NOT NULL,

                            memberCount INTEGER NOT NULL,

                            category TEXT NOT NULL,

                            PRIMARY KEY (id, company)

                        )

                    """)

                    cursor.execute("SELECT id, title, username, type, enabled, memberCount, category FROM groups_library")

                    rows = cursor.fetchall()

                    for row in rows:

                        cursor.execute("""

                            INSERT INTO groups_library_new (id, company, title, username, type, enabled, memberCount, category)

                            VALUES (?, 'admin', ?, ?, ?, ?, ?, ?)

                        """, row)

                    cursor.execute("DROP TABLE groups_library")

                    cursor.execute("ALTER TABLE groups_library_new RENAME TO groups_library")

                    conn.commit()

            # Check price column in groups_library
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups_library'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(groups_library)")
                cols = [info[1] for info in cursor.fetchall()]
                if "price" not in cols:
                    print("Migrating DB: adding column 'price' to 'groups_library' table...")
                    cursor.execute("ALTER TABLE groups_library ADD COLUMN price REAL DEFAULT 0.0")
                    conn.commit()



            # Migrate role permissions table to include templates and scraper tabs for existing records

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'")

            if cursor.fetchone():

                # Admin role

                cursor.execute("SELECT allowed_tabs FROM role_permissions WHERE role='admin'")

                row = cursor.fetchone()

                if row:

                    tabs = row[0]

                    updated = False

                    if "templates" not in tabs:

                        tabs = tabs.replace("campaign,logs", "campaign,templates,logs") if "campaign,logs" in tabs else (tabs + ",templates")

                        updated = True

                    if "scraper" not in tabs:

                        tabs = tabs.replace("templates,logs", "templates,scraper,logs") if "templates,logs" in tabs else (tabs + ",scraper")

                        updated = True

                    if "bot_auth" not in tabs:

                        tabs = tabs + ",bot_auth"

                        updated = True

                    if updated:

                        cursor.execute("UPDATE role_permissions SET allowed_tabs=? WHERE role='admin'", (tabs,))

                        conn.commit()

                # User role

                cursor.execute("SELECT allowed_tabs FROM role_permissions WHERE role='user'")

                row = cursor.fetchone()

                if row:

                    tabs = row[0]

                    updated = False

                    if "templates" not in tabs:

                        tabs = tabs.replace("campaign,logs", "campaign,templates,logs") if "campaign,logs" in tabs else (tabs + ",templates")

                        updated = True

                    if "scraper" not in tabs:

                        tabs = tabs.replace("templates,logs", "templates,scraper,logs") if "templates,logs" in tabs else (tabs + ",scraper")

                        updated = True

                    if updated:

                        cursor.execute("UPDATE role_permissions SET allowed_tabs=? WHERE role='user'", (tabs,))

                        conn.commit()

            # Add created_by & updated_by columns to existing tables if missing
            for table in ["accounts", "groups_library", "campaign_tasks", "predefined_ads"]:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [info[1] for info in cursor.fetchall()]
                if "created_by" not in cols:
                    print(f"Migrating DB: adding column 'created_by' to '{table}' table...")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN created_by TEXT DEFAULT 'admin'")
                    conn.commit()
                if "updated_by" not in cols:
                    print(f"Migrating DB: adding column 'updated_by' to '{table}' table...")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN updated_by TEXT DEFAULT 'admin'")
                    conn.commit()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups_library'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(groups_library)")
                group_cols = [info[1] for info in cursor.fetchall()]
                for score_col in ["quality_score", "relevance_score", "activity_score", "engagement_score"]:
                    if score_col not in group_cols:
                        print(f"Migrating DB: adding column '{score_col}' to 'groups_library' table...")
                        cursor.execute(f"ALTER TABLE groups_library ADD COLUMN {score_col} INTEGER DEFAULT 0")
                        conn.commit()

            # Add group_type, is_active, and is_dead columns to scraped_groups if missing
            cursor.execute("PRAGMA table_info(scraped_groups)")
            scraped_cols = [info[1] for info in cursor.fetchall()]
            if scraped_cols: # Only check if table exists
                if "group_type" not in scraped_cols:
                    print("Migrating DB: adding column 'group_type' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN group_type TEXT DEFAULT 'group'")
                    conn.commit()
                if "is_active" not in scraped_cols:
                    print("Migrating DB: adding column 'is_active' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN is_active INTEGER DEFAULT 1")
                    conn.commit()
                if "is_dead" not in scraped_cols:
                    print("Migrating DB: adding column 'is_dead' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN is_dead INTEGER DEFAULT 0")
                    conn.commit()
                if "relevance_score" not in scraped_cols:
                    print("Migrating DB: adding column 'relevance_score' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN relevance_score INTEGER DEFAULT 0")
                    conn.commit()
                if "activity_score" not in scraped_cols:
                    print("Migrating DB: adding column 'activity_score' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN activity_score INTEGER DEFAULT 0")
                    conn.commit()
                if "engagement_score" not in scraped_cols:
                    print("Migrating DB: adding column 'engagement_score' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN engagement_score INTEGER DEFAULT 0")
                    conn.commit()
                if "spam_penalty" not in scraped_cols:
                    print("Migrating DB: adding column 'spam_penalty' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN spam_penalty INTEGER DEFAULT 0")
                    conn.commit()
                if "is_important" not in scraped_cols:
                    print("Migrating DB: adding column 'is_important' to 'scraped_groups' table...")
                    cursor.execute("ALTER TABLE scraped_groups ADD COLUMN is_important INTEGER DEFAULT 0")
                    conn.commit()

    except Exception as e:

        print(f"DB migration error: {e}")



def init_categories():
    try:
        with Session(engine) as session:
            stmt = select(GroupCategoryDb)
            results = session.exec(stmt).all()
            if not results:
                # Insert default categories
                for name in ["中文广告", "英文广告"]:
                    cat = GroupCategoryDb(name=name, company="admin")
                    session.add(cat)
                session.commit()
                print("Initialized default group categories.")
    except Exception as e:
        print(f"Failed to initialize categories: {e}")


def init_db():

    DB_DIR.mkdir(parents=True, exist_ok=True)

    SQLModel.metadata.create_all(engine)



    # Run migrations

    migrate_columns()

    migrate_data_if_empty()

    migrate_default_company_to_admin()

    init_categories()
    migrate_bot_authorized_users()
    migrate_telegram_bots()

    # 自动清理管理员表里误建的普通账号
    try:
        import sqlite3
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins WHERE username = 'RosePay_frank';")
            conn.commit()
    except Exception as exc:
        print(f"Failed to cleanup RosePay_frank dirty data: {exc}")



def migrate_data_if_empty():

    # 1. Migrate Groups

    json_path = DB_DIR / "groups.json"

    with Session(engine) as session:

        # Check if table is empty

        stmt = select(GroupDb)

        existing_groups = session.exec(stmt).first()

        if not existing_groups and json_path.exists():

            print("Migrating groups from JSON to SQLite database...")

            try:

                with open(json_path, "r", encoding="utf-8") as f:

                    groups_data = json.load(f)

                    for g in groups_data:

                        db_group = GroupDb(

                            id=str(g["id"]),

                            title=g.get("title", ""),

                            username=g.get("username", ""),

                            type=g.get("type", "group"),

                            enabled=g.get("enabled", True),

                            memberCount=g.get("memberCount", 0),

                            category=g.get("category", "中文广告")

                        )

                        session.add(db_group)

                session.commit()

                print("Groups migration completed successfully.")

            except Exception as e:

                print(f"Failed to migrate groups: {e}")

                session.rollback()



        # 2. Migrate Logs

        log_csv_path = Path(__file__).resolve().parent / "logs" / "ad-send-log.csv"

        stmt_log = select(AdLogDb)

        existing_logs = session.exec(stmt_log).first()

        if not existing_logs and log_csv_path.exists():

            print("Migrating campaign logs from CSV to SQLite database...")

            try:

                with open(log_csv_path, "r", encoding="utf-8-sig") as f:

                    reader = csv.reader(f)

                    header = next(reader, None)  # skip header

                    for row in reader:

                        if len(row) >= 6:

                            detail_val = row[6] if len(row) > 6 else ""

                            db_log = AdLogDb(

                                time=row[0],

                                folder=row[1],

                                chat_id=row[2],

                                title=row[3],

                                action=row[4],

                                status=row[5],

                                detail=detail_val

                            )

                            session.add(db_log)

                session.commit()

                print("Logs migration completed successfully.")

            except Exception as e:

                print(f"Failed to migrate logs: {e}")

                session.rollback()



        # 3. Migrate Accounts

        accounts_dir = Path(__file__).resolve().parent / "accounts"

        stmt_acc = select(AccountDb)

        existing_accounts = session.exec(stmt_acc).first()

        if not existing_accounts and accounts_dir.exists():

            print("Migrating accounts from JSON to SQLite database...")

            try:

                for json_file in accounts_dir.glob("*.json"):

                    account_id = json_file.stem

                    with open(json_file, "r", encoding="utf-8") as f:

                        data = json.load(f)

                        db_account = AccountDb.from_dict(account_id, data)

                        session.add(db_account)

                session.commit()

                print("Accounts migration completed successfully.")

            except Exception as e:

                print(f"Failed to migrate accounts: {e}")

                session.rollback()



        # 4. Seed Role Permissions

        stmt_perm = select(RolePermissionDb)

        existing_perms = session.exec(stmt_perm).first()

        if not existing_perms:

            print("Seeding default role permissions into database...")

            try:

                admin_perm = RolePermissionDb(

                    role="admin",

                    allowed_tabs="login,accounts,groups,join,campaign,templates,scraper,logs,settings,users,permissions,bot_auth"

                )

                user_perm = RolePermissionDb(

                    role="user",

                    allowed_tabs="login,accounts,groups,join,campaign,templates,scraper,logs"

                )

                session.add(admin_perm)

                session.add(user_perm)

                session.commit()

                print("Role permissions seeding completed successfully.")

            except Exception as e:

                print(f"Failed to seed role permissions: {e}")

                session.rollback()



        # 5. Seed Default Company
        stmt_comp = select(CompanyDb)
        existing_comp = session.exec(stmt_comp).first()
        if not existing_comp:
            print("Seeding default company...")
            try:
                default_comp = CompanyDb(
                    name="admin",
                    created_at=datetime.now(timezone.utc).isoformat()
                )
                session.add(default_comp)
                session.commit()
                print("Default company seeding completed successfully.")
            except Exception as e:
                print(f"Failed to seed default company: {e}")
                session.rollback()

def migrate_telegram_bots():
    """自动从环境配置文件初始化并迁移默认的两个 Bot 到数据表中"""
    import sqlite3
    import datetime
    import os
    from pathlib import Path

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telegram_bots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_username TEXT NOT NULL UNIQUE,
                    bot_token TEXT NOT NULL,
                    bot_type TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                );
            """)

            # 创建自动回复文本模板表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_auto_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_type TEXT NOT NULL,
                    reply_text TEXT NOT NULL,
                    is_enabled INTEGER DEFAULT 1,
                    created_at TEXT
                );
            """)

            # 初始化一条默认自动回复模板
            cursor.execute("SELECT COUNT(*) FROM bot_auto_replies;")
            reply_count = cursor.fetchone()[0]
            if reply_count == 0:
                now_str = datetime.datetime.now().isoformat()
                default_reply = (
                    "🌹 <b>您好，欢迎咨询 RosePay！</b>\n\n"
                    "⚠️ <b>防骗反诈安全提示</b>：\n"
                    "控制台客服及管理员<b>绝不会主动私聊您</b>，任何主动私聊您的都是骗子，请务必仔细甄别，谨防上当受骗！\n\n"
                    "💬 请在此处说明您的具体业务需求，客服人员看到后会立即进行回复，祝您生活愉快！"
                )
                cursor.execute(
                    "INSERT INTO bot_auto_replies (bot_type, reply_text, is_enabled, created_at) VALUES (?, ?, ?, ?)",
                    ("ai_bot", default_reply, 1, now_str)
                )
                conn.commit()

            cursor.execute("SELECT COUNT(*) FROM telegram_bots;")
            count = cursor.fetchone()[0]
            if count == 0:
                print("[Migrate] Initializing default Telegram Bots into database...")
                ai_token = ""
                if os.name != "nt":
                    bot_env_path = Path("/opt/rosepay-telegram-bot/.env")
                else:
                    bot_env_path = Path(__file__).resolve().parent.parent / "telegram_bot_workspace" / ".env"

                if bot_env_path.exists():
                    try:
                        with bot_env_path.open("r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip().startswith("BOT_TOKEN="):
                                    ai_token = line.split("=", 1)[1].strip()
                                    break
                    except Exception:
                        pass

                if not ai_token:
                    ai_token = os.getenv("BOT_TOKEN", "").strip() or "YOUR_AI_BOT_TOKEN_HERE"

                now_str = datetime.datetime.now().isoformat()

                cursor.execute(
                    "INSERT OR REPLACE INTO telegram_bots (bot_username, bot_token, bot_type, title, description, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("RosePayTest_bot", ai_token, "ai_bot", "AI 控制助手", "控制台接管、私聊中转及绑定的电报账号自动整理通知 Bot", 1, now_str)
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO telegram_bots (bot_username, bot_token, bot_type, title, description, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("RosePay_translation_bot", "YOUR_TRANSLATION_BOT_TOKEN_HERE", "translate_bot", "翻译助手", "绑定的电报账号私聊及群聊对话框的多语种智能实时翻译", 1, now_str)
                )
                conn.commit()
                print("[Migrate] Successfully initialized telegram_bots table.")
    except Exception as exc:
        print(f"[Migrate] Failed to migrate telegram_bots: {exc}")


def migrate_default_company_to_admin():
    from sqlalchemy import text
    with Session(engine) as session:
        try:
            session.execute(text("UPDATE companies SET name = 'admin' WHERE name = '默认公司'"))
            session.execute(text("UPDATE admins SET company = 'admin' WHERE company = '默认公司'"))
            session.execute(text("UPDATE accounts SET company = 'admin' WHERE company = '默认公司'"))
            session.execute(text("UPDATE ad_logs SET company = 'admin' WHERE company = '默认公司'"))
            session.execute(text("UPDATE campaign_logs SET company = 'admin' WHERE company = '默认公司'"))
            session.execute(text("UPDATE login_logs SET company = 'admin' WHERE company = '默认公司'"))
            session.execute(text("UPDATE predefined_ads SET company = 'admin' WHERE company = '默认公司'"))
            session.execute(text("UPDATE groups_library SET company = 'admin' WHERE company = '默认公司'"))
            session.commit()
            print("Successfully migrated '默认公司' to 'admin' in database tables.")
        except Exception as e:
            print(f"Failed to migrate '默认公司' to 'admin' in database tables: {e}")
            session.rollback()

def migrate_groups_library_bot_rules():
    import sqlite3
    print("=== 开始检测 groups_library 数据库字段升级 ===", flush=True)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(groups_library);")
        columns = [row[1] for row in cursor.fetchall()]

        if "bot_rules_summary" not in columns:
            print("正在向 groups_library 动态新增 bot_rules_summary 字段...", flush=True)
            cursor.execute("ALTER TABLE groups_library ADD COLUMN bot_rules_summary TEXT;")
            conn.commit()
            print("✓ bot_rules_summary 字段新增成功。", flush=True)

        if "bot_rules_raw_logs" not in columns:
            print("正在向 groups_library 动态新增 bot_rules_raw_logs 字段...", flush=True)
            cursor.execute("ALTER TABLE groups_library ADD COLUMN bot_rules_raw_logs TEXT;")
            conn.commit()
            print("✓ bot_rules_raw_logs 字段新增成功。", flush=True)

        conn.close()
    except Exception as exc:
        print(f"❌ 自动迁移 groups_library 表结构失败: {exc}", flush=True)

try:
    migrate_groups_library_bot_rules()
except Exception:
    pass
