import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web_server import get_client
from telethon import functions, types
from db import engine, AccountDb, Session, select

async def cleanup_account(account_id: str, phone: str):
    print(f"[{phone}] Connecting and fetching filters...")
    try:
        client = await get_client(account_id)
        is_auth = await client.is_user_authorized()
        if not is_auth:
            print(f"[{phone}] Account not authorized. Skipping.")
            return
            
        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result) or []
        
        custom_filters = [
            item for item in raw_filters 
            if hasattr(item, "id") and item.id is not None
        ]
        
        print(f"[{phone}] Found {len(custom_filters)} custom folders to delete.")
        
        for item in custom_filters:
            fid = item.id
            title = getattr(item, 'title', None)
            title_text = title if isinstance(title, str) else getattr(title, 'text', str(title))
            print(f"[{phone}] Deleting folder '{title_text}' (id={fid})...")
            try:
                await client(functions.messages.UpdateDialogFilterRequest(
                    id=fid,
                    filter=None
                ))
                print(f"[{phone}]   Successfully deleted id={fid}")
            except Exception as e:
                print(f"[{phone}]   Failed to delete id={fid}: {e}")
                
    except Exception as e:
        print(f"[{phone}] Error: {e}")

async def main():
    print("Fetching all accounts from database...")
    accounts = []
    with Session(engine) as session:
        stmt = select(AccountDb)
        db_accounts = session.exec(stmt).all()
        for acc in db_accounts:
            accounts.append((acc.id, acc.account_name))
                
    print(f"Found {len(accounts)} accounts in database.")
    
    for account_id, phone in accounts:
        await cleanup_account(account_id, phone)
        print("-" * 50)
        
    print("All accounts cleaned up!")

if __name__ == "__main__":
    asyncio.run(main())
