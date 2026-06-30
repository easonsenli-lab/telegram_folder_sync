import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web_server import get_client
from telethon import functions, types

async def main():
    account_id = "573157010033"
    folder_to_keep = "广告"
    
    print(f"Getting client for account: {account_id}")
    try:
        client = await get_client(account_id)
        is_auth = await client.is_user_authorized()
        if not is_auth:
            print("Account is not authorized!")
            return
            
        print("Fetching existing dialog filters (folders)...")
        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result) or []
        
        # Identify filters with the title '广告'
        matching_filters = []
        for item in raw_filters:
            title = getattr(item, 'title', None)
            if title is None:
                continue
            title_text = title if isinstance(title, str) else getattr(title, 'text', str(title))
            if title_text == folder_to_keep:
                matching_filters.append(item)
                
        print(f"Found {len(matching_filters)} folders with title '{folder_to_keep}'")
        
        if len(matching_filters) > 1:
            print("Deleting duplicate folders, keeping only the first one...")
            # Keep the first one, delete the rest
            keep_filter = matching_filters[0]
            delete_filters = matching_filters[1:]
            
            for item in delete_filters:
                fid = item.id
                print(f"Deleting filter id={fid}...")
                try:
                    # To delete a filter, send UpdateDialogFilterRequest with filter=None
                    await client(functions.messages.UpdateDialogFilterRequest(
                        id=fid,
                        filter=None
                    ))
                    print(f"  Successfully deleted filter id={fid}")
                except Exception as e:
                    print(f"  Failed to delete filter id={fid}: {e}")
                    
            print("Cleanup completed!")
        elif len(matching_filters) == 1:
            print("Only one matching folder exists, no cleanup needed.")
        else:
            print("No matching folders found.")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
