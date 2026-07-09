import os
import sys

# 强行将工作目录重定向到脚本所在的绝对目录，彻底避免 SQLite 相对路径 data/rosepay.db 漂移到 /root 目录下
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

from db import engine, GroupDb, Session, select
from services.scraping_service import apply_group_library_scores

print("==================== STARTING GROUP RESTORE & RE-SCORE ====================")

with Session(engine) as session:
    # 查找所有目前被禁用了，但是其实有成员人数（大于0）的正常群组
    stmt = select(GroupDb).where(GroupDb.enabled == False)
    disabled_groups = session.exec(stmt).all()
    
    restored_count = 0
    for group in disabled_groups:
        # 如果不是 0 人，或者有公开用户名（说明不是已销毁的空群）
        if (group.memberCount and group.memberCount > 0) or group.username:
            group.enabled = True
            scores = apply_group_library_scores(group, is_valid=True)
            session.add(group)
            restored_count += 1
            print(f"Restored Group: '{group.title}' (ID: {group.id}) | Members: {group.memberCount} | New Score: {scores['quality_score']}")
            
    session.commit()

print(f"SUCCESS: Total {restored_count} groups restored to Enabled and re-scored!")
print("=========================================================================")
