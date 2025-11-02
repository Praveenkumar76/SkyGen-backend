# In tools.py
import httpx  # Make sure 'httpx' is imported at the top of tools.py
import os
import json
from supabase import create_client, Client
from groq import AsyncGroq
from firecrawl import FirecrawlApp # <-- Add this import

# --- MCP Client Imports (NEW) ---
import mcp
import asyncio
import sys
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters, ClientSession

# --- Initialize Clients for SkyGen ---
# This setup assumes your environment variables are loaded in your main app.
SKYGEN_URL = os.environ.get("SKYGEN_URL")
SKYGEN_KEY = os.environ.get("SKYGEN_SERVICE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
FIRECRAWL_API_KEY = os.environ.get("WEB_SCRAPE") # <-- Add this

# Initialize clients lazily to avoid import-time errors
skygen_supabase = None
groq_client = None

def _ensure_clients():
    """Ensure clients are initialized"""
    global skygen_supabase, groq_client
    
    if not all([SKYGEN_URL, SKYGEN_KEY, GROQ_API_KEY]):
        raise ValueError("A required environment variable for SkyGen was not loaded. Check your server configuration.")
    if not FIRECRAWL_API_KEY:
        raise ValueError("FIRECRAWL_API_KEY is not set. Check your .env file.")
    if skygen_supabase is None:
        skygen_supabase = create_client(SKYGEN_URL, SKYGEN_KEY)
    if groq_client is None:
        groq_client = AsyncGroq(api_key=GROQ_API_KEY)


# ==============================================================================
# === All tool functions MUST start with "async def"                         ===
# ==============================================================================

async def get_user(user_id: str) -> str:
    """
    Fetches the profile information for a given user ID from the database.
    Use this to find a user's name, email, or other details.
    """
    _ensure_clients()
    print(f"TOOL CALLED: get_user_profile for user_id: {user_id}")
    try:
        response = skygen_supabase.table('profiles').select('username, full_name').eq('id', user_id).single().execute()
        if response.data:
            return f"Observation: Found user profile. Details: {json.dumps(response.data)}."
        else:
            return f"Observation: No profile found for user_id {user_id}."
    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"

async def update_user_profile(user_id: str, full_name: str = None, fullname: str = None, age: int = None, address: str = None, about: str = None, key: str = None, value: str = None) -> str:
    """Updates a user's profile information. Can update one or more of the following: full_name, age, address, or the 'about' section."""
    _ensure_clients()
    print(f"TOOL CALLED: update_user_profile for user_id: {user_id}")
    update_data = {}
    
    # Handle key-value format (new LLM format)
    if key and value:
        if key == 'full_name' or key == 'fullname':
            update_data['full_name'] = value
        elif key == 'age':
            update_data['age'] = int(value) if value.isdigit() else None
        elif key == 'address':
            update_data['address'] = value
        elif key == 'about':
            update_data['about'] = value
    else:
        # Handle direct parameter format (legacy)
        name_value = full_name or fullname
        if name_value is not None: update_data['full_name'] = name_value
        if age is not None: update_data['age'] = age
        if address is not None: update_data['address'] = address
        if about is not None: update_data['about'] = about
        
    if not update_data:
        return "Observation: No fields were provided to update."

    try:
        response = skygen_supabase.table('profiles').update(update_data).eq('id', user_id).execute()
        if response.data:
            updated_fields = list(update_data.keys())
            return f"Observation: Profile updated successfully. The following fields were changed: {', '.join(updated_fields)}."
        else:
            return "Observation: Profile update command sent, but no data was returned. This may indicate the user does not exist or the update failed silently."
    except Exception as e:
        return f"Observation: An error occurred during update: {str(e)}"

async def delete_conversation_by_title(user_id: str, title: str) -> str:
    """Deletes a user's entire chat conversation based on its exact title."""
    _ensure_clients()
    print(f"TOOL CALLED: delete_conversation_by_title for user_id: {user_id}, title: '{title}'")
    try:
        # First try exact match
        exact_res = skygen_supabase.table('conversations').select('id, title').eq('user_id', user_id).eq('title', title).execute()
        
        if exact_res.data:
            conversation_ids_to_delete = [conv['id'] for conv in exact_res.data]
            response = skygen_supabase.table('conversations').delete().in_('id', conversation_ids_to_delete).execute()
            count = len(response.data)
            return f"Observation: Successfully deleted {count} conversation(s) with exact title '{title}'."
        
        # If no exact match, try partial match
        partial_res = skygen_supabase.table('conversations').select('id, title').eq('user_id', user_id).ilike('title', f'%{title}%').execute()
        
        if not partial_res.data:
            return f"Observation: No conversation with title containing '{title}' was found for this user."

        conversation_ids_to_delete = [conv['id'] for conv in partial_res.data]
        response = skygen_supabase.table('conversations').delete().in_('id', conversation_ids_to_delete).execute()
        
        count = len(response.data)
        if count > 0:
            return f"Observation: Successfully deleted {count} conversation(s) matching the title '{title}'."
        else:
            return f"Observation: Could not delete conversation matching '{title}', though an initial match was found."

    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"

async def delete_all_conversations(user_id: str) -> str:
    """Deletes all conversations for a user."""
    _ensure_clients()
    print(f"TOOL CALLED: delete_all_conversations for user_id: {user_id}")
    try:
        # First get all conversation IDs for the user
        find_res = skygen_supabase.table('conversations').select('id').eq('user_id', user_id).execute()
        
        if not find_res.data:
            return f"Observation: No conversations found for this user."

        conversation_ids_to_delete = [conv['id'] for conv in find_res.data]
        response = skygen_supabase.table('conversations').delete().in_('id', conversation_ids_to_delete).execute()
        
        count = len(response.data)
        if count > 0:
            return f"Observation: Successfully deleted all {count} conversation(s) for this user."
        else:
            return f"Observation: Could not delete conversations, though {len(conversation_ids_to_delete)} were found."

    except Exception as e:
        return f"Observation: An error occurred: {str(e)}"

async def sign_out_user(user_id: str) -> str:
    """
    Signs out the current user. This action informs the frontend to log the user out.
    The user_id parameter is for logging and to conform to the tool structure.
    """
    _ensure_clients()
    print(f"TOOL CALLED: sign_out_user for user_id: {user_id}")
    return "ACTION_SIGN_OUT"

# ... (other imports)

async def get_leetcode_stats(username: str, user_id: str = None) -> str:
    """
    Fetches a user's LeetCode problem-solving stats (Total, Easy, Medium, Hard) by username.
    """
    print(f"[tools.py] Received request for LeetCode user: {username}")
    
    # The query is moved here directly
    query = """
    query userProblemsSolved($username: String!) {
        allQuestionsCount {
            difficulty
            count
        }
        matchedUser(username: $username) {
            problemsSolvedBeatsStats {
                difficulty
                percentage
            }
            submitStatsGlobal {
                acSubmissionNum {
                    difficulty
                    count
                }
            }
        }
    }
    """
    variables = {"username": username}
    
    # The fixed headers are here
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://leetcode.com/{username}/'
    }

    try:
        # We use httpx directly inside the tool
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://leetcode.com/graphql',
                json={'query': query, 'variables': variables},
                headers=headers
            )
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()
        
        # --- Start of parsing logic from server.py ---
        if "errors" in data:
            return f"Observation: LeetCode API error: {data['errors'][0]['message']}"
        if not data.get('data', {}).get('matchedUser'):
             return f"Observation: No LeetCode user found with username: '{username}'"

        solved_stats = data.get('data', {}).get('matchedUser', {}).get('submitStatsGlobal', {}).get('acSubmissionNum', [])
        
        # Format a clean answer
        total = next((item['count'] for item in solved_stats if item['difficulty'] == 'All'), 0)
        easy = next((item['count'] for item in solved_stats if item['difficulty'] == 'Easy'), 0)
        medium = next((item['count'] for item in solved_stats if item['difficulty'] == 'Medium'), 0)
        hard = next((item['count'] for item in solved_stats if item['difficulty'] == 'Hard'), 0)

        return f"Observation: LeetCode stats for {username}: Total: {total} (Easy: {easy}, Medium: {medium}, Hard: {hard})"

    except httpx.HTTPStatusError as e:
        return f"Observation: Failed to get LeetCode data: HTTP Error {e.response.status_code}"
    except Exception as e:
        print(f"[tools.py] An error occurred: {e}")
        return f"Observation: Failed to get LeetCode data: {e}"
    
async def search_the_web(user_id: str, query: str) -> str:
    """
    Searches the web for a query and scrapes the top results.
    Use this to answer questions about current events, real-time information, or topics not in your training data.
    """
    _ensure_clients() # Ensures other keys are loaded if needed, good practice
    print(f"TOOL CALLED: search_the_web with query: {query}")

    try:
        app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        
        # We ask FireCrawl to search AND scrape the top 3 results
        search_results = app.search(
            query=query,
            page_options={
                "fetch_page_content": True, # This tells it to scrape
                "limit": 3                  # Get top 3 pages
            }
        )
        
        # We will format the scraped content for the LLM
        scraped_content = []
        for result in search_results:
            scraped_content.append(f"Source URL: {result.get('url')}\nContent: {result.get('markdown')[:2000]}") # Get first 2000 chars

        if not scraped_content:
            return "Observation: No results found for that query."
            
        # Join all sources into one big string
        return f"Observation: Here is the information from the web:\n\n{'---'.join(scraped_content)}"

    except Exception as e:
        print(f"Error in FireCrawl tool: {e}")
        return f"Observation: An error occurred while searching the web: {str(e)}"