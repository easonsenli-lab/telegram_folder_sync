import sys
import json
import sqlite3
from pathlib import Path

db_path = Path("data/rosepay.db")
if not db_path.exists():
    print(f"Database {db_path} does not exist!")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = ["admins", "accounts", "groups_library", "campaign_tasks", "campaign_logs", "ad_logs", "predefined_ads", "login_logs"]

target_company = "rosepay"

def safe_print(text):
    print(text.encode("gbk", errors="backslashreplace").decode("gbk"))

for table in tables:
    try:
        # Check if the table exists
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            safe_print(f"Table '{table}' does not exist, skipping.")
            continue
            
        # Check if 'company' column exists in this table
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [info[1] for info in cursor.fetchall()]
        if "company" not in columns:
            safe_print(f"Column 'company' not found in table '{table}', skipping.")
            continue

        # Print current counts per company in this table
        cursor.execute(f"SELECT company, COUNT(*) FROM {table} GROUP BY company")
        safe_print(f"\nBefore update for '{table}':")
        for row in cursor.fetchall():
            comp_str = str(row[0]) if row[0] is not None else "None"
            safe_print(f"  Company: {comp_str}, Count: {row[1]}")
            
        # Update records where company is '默认公司', 'ĬϹ˾', '', or NULL
        cursor.execute(f"""
            UPDATE {table} 
            SET company = ? 
            WHERE company = '默认公司' 
               OR company = 'ĬϹ˾' 
               OR company = '' 
               OR company IS NULL
        """, (target_company,))
        updated = cursor.rowcount
        conn.commit()
        safe_print(f"Updated {updated} rows in '{table}' to company '{target_company}'")
        
    except Exception as e:
        safe_print(f"Error migrating table '{table}': {e}")

# Also update the user "test"'s company to "rosepay" so they can see the rosepay company data
try:
    cursor.execute("UPDATE admins SET company = 'rosepay' WHERE username = 'test'")
    conn.commit()
    safe_print("Updated test user's company to 'rosepay'")
except Exception as e:
    safe_print(f"Error updating test user's company: {e}")

conn.close()

# Now migrate data/join_tasks/*.json
join_tasks_dir = Path("data/join_tasks")
if join_tasks_dir.exists():
    migrated_json_count = 0
    for f in join_tasks_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                task = json.load(file)
            company = task.get("company", "")
            if company in ["默认公司", "ĬϹ˾", "", None]:
                task["company"] = target_company
                with open(f, "w", encoding="utf-8") as file:
                    json.dump(task, file, ensure_ascii=False, indent=2)
                migrated_json_count += 1
        except Exception as e:
            safe_print(f"Error migrating join task file {f.name}: {e}")
    safe_print(f"\nMigrated {migrated_json_count} join task JSON files to company '{target_company}'")
