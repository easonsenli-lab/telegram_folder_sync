import asyncio
import sys
import os

# Add directory to sys.path so we can import from web_server
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web_server import get_client, try_create_folder_early, add_peer_to_folder
from telethon import functions, types

async def main():
    account_id = "573157010033"
    folder_name = "测试文件夹"
    
    print(f"Getting client for account: {account_id}")
    try:
        client = await get_client(account_id)
        is_auth = await client.is_user_authorized()
        print(f"Is user authorized: {is_auth}")
        if not is_auth:
            print("Account is not authorized! Cannot proceed.")
            return
            
        print("Fetching existing dialog filters (folders)...")
        result = await client(functions.messages.GetDialogFiltersRequest())
        raw_filters = getattr(result, "filters", result) or []
        print(f"Found {len(raw_filters)} existing filters:")
        for idx, item in enumerate(raw_filters):
            title = getattr(item, 'title', None)
            if hasattr(title, 'text'):
                title = title.text
            print(f"  Filter {idx}: id={getattr(item, 'id', None)}, title={title}, type={type(item).__name__}")
            
        print(f"\nAttempting to create folder '{folder_name}' early...")
        # Let's inspect DialogFilter parameters to make sure we construct it correctly
        # Telegram API UpdateDialogFilterRequest
        # Let's call UpdateDialogFilterRequest with a new filter id
        existing_ids = {item.id for item in raw_filters if hasattr(item, "id")}
        next_id = 2
        while next_id in existing_ids:
            next_id += 1
            
        print(f"Selected next filter id: {next_id}")
        
        # We can construct a DialogFilter and try to update
        # Wait, if we use a seed peer, let's find one
        print("Fetching dialogs to find a group/channel/user to seed...")
        dialogs = await client.get_dialogs(limit=50)
        include_peers = []
        for d in dialogs:
            print(f"  Dialog: title='{d.name}', id={d.id}, type={'Group' if d.is_group else 'Channel' if d.is_channel else 'User'}")
            if d.is_group or d.is_channel:
                try:
                    peer = await client.get_input_entity(d.entity)
                    include_peers = [peer]
                    print(f"    Selected seed peer: {type(peer).__name__} id={getattr(peer, 'channel_id', getattr(peer, 'chat_id', None))}")
                except Exception as ex:
                    print(f"    Failed to get input entity: {ex}")
                break
                
        if not include_peers:
            print("No groups/channels found to seed the folder. Trying to seed with a user or itself...")
            # We can seed with the client's own input entity
            try:
                me = await client.get_me()
                peer = await client.get_input_entity(me)
                include_peers = [peer]
                print(f"    Selected self seed peer: {type(peer).__name__} id={getattr(peer, 'user_id', None)}")
            except Exception as ex:
                print(f"    Failed to get self input entity: {ex}")
                
        if not include_peers:
            print("Error: Could not find any peer to seed the folder!")
            return
            
        print(f"Sending UpdateDialogFilterRequest for folder: {folder_name}...")
        new_filter = types.DialogFilter(
            id=next_id,
            title=types.TextWithEntities(text=folder_name, entities=[]),
            pinned_peers=[],
            include_peers=include_peers,
            exclude_peers=[],
            contacts=False,
            non_contacts=False,
            groups=False,
            broadcasts=False,
            bots=False
        )
        try:
            res = await client(functions.messages.UpdateDialogFilterRequest(
                id=next_id,
                filter=new_filter
            ))
            print(f"Request result: {res}")
        except Exception as e:
            print(f"API Error during UpdateDialogFilterRequest: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
