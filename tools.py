# Assume you have your Supabase client initialized somewhere and can import it
# from your_supabase_connector import supabase 
# For now, we can just define it here to see how it works.
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# --- This part would be in your main app, but we need it for the function ---
# Make sure you have a .env file with these keys
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
        # This is your existing Supabase logic
        response = supabase.table('profiles').select('username').eq('id', user_id).single().execute()

        if response.data:
            # The function must return a simple string (the "Observation")
            return f"Observation: Found user profile. Username is {response.data['username']}."
        else:
            return f"Observation: No profile found for user_id {user_id}."
    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"
    
def delete_conversation_by_title(user_id: str, title: str) -> str:
    """Deletes a user's entire chat conversation based on its exact title."""
    # The original function was named delete_chat_conversation, let's stick to the name used in your main file.
    # The print statement below is also fixed.
    print(f"TOOL CALLED: delete_conversation_by_title for user_id: {user_id}, title: '{title}'")
    try:
        response = supabase.table('conversations').delete().eq('user_id', user_id).eq('title', title).execute()
        if response.count is not None and response.count > 0:
            return f"Observation: Successfully deleted {response.count} conversation(s) titled '{title}'."
        else:
            return f"Observation: No conversation with the exact title '{title}' was found for this user."
    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"
    
def update_user_profile(user_id: str, full_name: str = None, age: int = None, address: str = None, about: str = None) -> str:
    """Updates a user's profile information. Can update full_name, age, address, or about section."""
    print(f"TOOL CALLED: update_user_profile for user_id: {user_id}")
    update_data = {}
    if full_name:
        update_data['full_name'] = full_name
    if age:
        update_data['age'] = age
    if address:
        update_data['address'] = address
    if about:
        update_data['about'] = about
        
    if not update_data:
        return "Observation: No fields were provided to update."

    try:
        response = supabase.table('profiles').update(update_data).eq('id', user_id).execute()
        if response.data:
            return f"Observation: Profile updated successfully with the following data: {json.dumps(update_data)}"
        else:
            # Supabase update can return no data on success, so we check for errors instead
            return "Observation: Profile update command sent. Assuming success."
    except Exception as e:
        return f"Observation: An error occurred during update: {str(e)}"

def sign_out_user(user_id: str) -> str:
    """
    Signs out a user. This action informs the frontend to log the user out.
    The user_id parameter is for logging purposes.
    """
    print(f"TOOL CALLED: sign_out_user for user_id: {user_id}")
    return "ACTION_SIGN_OUT"