import mcp
import httpx
import json
import re
import asyncio
import os
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, EmailStr, constr
from typing import Literal, Dict, Any, List

# --- Pydantic models for Zod-like validation ---
# This replicates the schema from your Create-User tool
class UserParams(BaseModel):
    uid: str
    name: str
    email: EmailStr
    ph: constr(pattern=r"^[0-9]{10}$")

# --- Server Initialization ---
server = FastMCP(
    name='SkyGen\'s MCP',
    version='1.0.0',
)

# --- Path for our local JSON database ---
DATA_FILE = "./data/data.json"

# --- Helper function for reading/writing JSON data ---
# CHANGED: 'async def' to 'def' because it uses sync file I/O (open, json.load)
def get_users_from_db() -> List[Dict[str, Any]]:
    """Loads the user list from the JSON file."""
    # Ensure directory and file exist
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            return data
    except (json.JSONDecodeError, IOError):
        return []

# CHANGED: 'async def' to 'def' because it uses sync file I/O (open, json.dump)
def save_users_to_db(users: List[Dict[str, Any]]) -> None:
    """Saves the user list to the JSON file."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(users, f, indent=2)

# --- Tool 1: Generate Onboarding Email ---
# This is correct as 'async def' because it does no blocking I/O
@server.tool(title="Generate Email", open_world_hint=False)
async def Generate_Onboarding_Email(
    name: str,
    role: Literal["developer", "designer", "manager", "founder", "student"],
    tone: Literal["casual", "formal", "witty", "inspirational"] = "casual"
) -> str:
    """Generates a personalized onboarding email for a user."""
    
    if tone == "witty":
        journey_phrase = "less boring and more thrilling"
    elif tone == "inspirational":
        journey_phrase = "an adventure worth remembering"
    elif tone == "formal":
        journey_phrase = "professional and efficient"
    else:
        journey_phrase = "smooth and enjoyable"

    email_template = f"""
Hi {name},

Welcome aboard! As a {role}, you're going to love what we’ve built.

Let’s make this journey {journey_phrase}.

Cheers,
The SkyGen's MCP 🚀
    """.strip()

    return email_template

# --- Tool 2: Get LeetCode Data ---
# This is correct as 'async def' because it uses 'await httpx'
@server.tool(title="Get LeetCode Data", destructive_hint=False, open_world_hint=True)
async def GetLeetcodeData(username: str) -> str:
    """This tool gets your leetcode total problems solved data."""
    
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
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://leetcode.com/graphql',
                json={'query': query, 'variables': variables},
                headers=headers
            )
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()
            return json.dumps(data, indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error fetching Leetcode data: HTTP Error {e.response.status_code}"
    except Exception as e:
        return f"Error fetching Leetcode data: {e}"

# --- Tool 3: Get Google Scholar Data ---
# This is correct as 'async def' because it uses 'await httpx'
@server.tool(title="Get Google Scholar Data", destructive_hint=False, open_world_hint=True)
async def GoogleScholar_Data(profile: str) -> str:
    """This tool fetches public Google Scholar profile data given a profile ID or URL"""
    
    scholar_id_regex = r"user=([a-zA-Z0-9_-]+)"
    profile_id = profile
    
    match = re.search(scholar_id_regex, profile)
    if match:
        profile_id = match.group(1)
        
    url = f"https://scholar.google.com/citations?user={profile_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
            
            # Basic scraping with regex (as in the original)
            name_match = re.search(r'<div id="gsc_prf_in">([^<]+)</div>', html)
            aff_match = re.search(r'<div class="gsc_prf_il">([^<]+)</div>', html)
            citations_all = re.findall(r'<td class="gsc_rsb_std">(\d+)</td>', html)
            
            data = {
                "name": name_match.group(1) if name_match else None,
                "affiliation": aff_match.group(1) if aff_match else None,
                "total_citations": citations_all[0] if len(citations_all) > 0 else None,
                "h_index": citations_all[2] if len(citations_all) > 2 else None,
                "i10_index": citations_all[4] if len(citations_all) > 4 else None,
                "profile_url": url
            }
            return json.dumps(data, indent=2)
            
    except Exception as e:
        return f"Error fetching Google Scholar data: {e}"

# --- Tool 4: Create User ---
# CHANGED: 'async def' to 'def' and removed 'await'
@server.tool(title="Create User", destructive_hint=False, open_world_hint=True)
def Create_User(params: UserParams) -> str:
    """This tool will create a user and stores locally"""
    try:
        users = get_users_from_db() # Removed 'await'
        # Pydantic's .model_dump() converts the model to a dict
        users.append(params.model_dump()) 
        save_users_to_db(users) # Removed 'await'
        return f"User {params.uid} got created successfully!"
    except Exception as e:
        return f"User can't be created! We got error at our side: {e}"

# --- Tool 5: Delete User ---
# CHANGED: 'async def' to 'def' and removed 'await'
@server.tool(title="Delete User", read_only_hint=False, destructive_hint=True)
def Delete_User(user: str) -> str:
    """Tool to delete users in the local storage by uid or name."""
    try:
        users = get_users_from_db() # Removed 'await'
        original_count = len(users)
        
        # Filter out the user
        users_to_keep = [
            u for u in users if u.get('uid') != user and u.get('name') != user
        ]
        
        if len(users_to_keep) == original_count:
            return f"User '{user}' not found. No user was deleted."

        save_users_to_db(users_to_keep) # Removed 'await'
        return f"The user '{user}' was deleted successfully."
    except Exception as e:
        return f"Error deleting user: {e}"

# --- Resource 1: Get Local Users ---
# CHANGED: 'async def' to 'def' and removed 'await'
@server.resource(
    "local://users",
    description="Retrieve all local users from data.json",
    title="Local Users",
    mime_type="application/json"
)
def Get_LocalUsers(uri: str) -> str:
    """Provides the local user database as a JSON string."""
    users = get_users_from_db() # Removed 'await'
    return json.dumps(users, indent=2)

# --- Main function to run the server ---
def main():
    """Runs the MCP server with StdioTransport."""
    server.run(transport='stdio')

if __name__ == "__main__":
    main()