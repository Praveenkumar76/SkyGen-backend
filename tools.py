import os
import json # <-- CRITICAL FIX: Import the json library
from supabase import create_client, Client
from dotenv import load_dotenv

# --- This part would be in your main app, but we need it for the function ---
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def get_user(user_id: str) -> str:
    """
    Fetches the profile information for a given user ID from the database.
    Use this to find a user's name, email, or other details.
    """
    print(f"TOOL CALLED: get_user_profile for user_id: {user_id}")
    try:
        response = supabase.table('profiles').select('username, full_name').eq('id', user_id).single().execute()

        if response.data:
            return f"Observation: Found user profile. Details: {json.dumps(response.data)}."
        else:
            return f"Observation: No profile found for user_id {user_id}."
    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"
    
def delete_conversation_by_title(user_id: str, title: str) -> str:
    """Deletes a user's entire chat conversation based on its exact title."""
    print(f"TOOL CALLED: delete_conversation_by_title for user_id: {user_id}, title: '{title}'")
    try:
        # First, find the conversation to confirm it exists and belongs to the user
        find_res = supabase.table('conversations').select('id').eq('user_id', user_id).ilike('title', f'%{title}%').execute()
        
        if not find_res.data:
            return f"Observation: No conversation with a title containing '{title}' was found for this user."

        # If found, proceed with deletion
        conversation_ids_to_delete = [conv['id'] for conv in find_res.data]
        response = supabase.table('conversations').delete().in_('id', conversation_ids_to_delete).execute()
        
        count = len(response.data)
        if count > 0:
            return f"Observation: Successfully deleted {count} conversation(s) matching the title '{title}'."
        else:
            return f"Observation: No conversation with the exact title '{title}' was found for this user, despite an initial match."

    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"
    
def update_user_profile(user_id: str, full_name: str = None, age: int = None, address: str = None, about: str = None) -> str:
    """Updates a user's profile information. Can update one or more of the following: full_name, age, address, or the 'about' section."""
    print(f"TOOL CALLED: update_user_profile for user_id: {user_id}")
    update_data = {}
    if full_name is not None: update_data['full_name'] = full_name
    if age is not None: update_data['age'] = age
    if address is not None: update_data['address'] = address
    if about is not None: update_data['about'] = about
        
    if not update_data:
        return "Observation: No fields were provided to update."

    try:
        response = supabase.table('profiles').update(update_data).eq('id', user_id).execute()
        # Supabase update returns data in response.data
        if response.data:
            updated_fields = list(update_data.keys())
            return f"Observation: Profile updated successfully. The following fields were changed: {', '.join(updated_fields)}."
        else:
            return "Observation: Profile update command sent, but no data was returned. This may indicate the user does not exist or the update failed silently."
    except Exception as e:
        return f"Observation: An error occurred during update: {str(e)}"

def sign_out_user(user_id: str) -> str:
    """
    Signs out the current user. This action informs the frontend to log the user out.
    The user_id parameter is for logging and to conform to the tool structure.
    """
    print(f"TOOL CALLED: sign_out_user for user_id: {user_id}")
    return "ACTION_SIGN_OUT"