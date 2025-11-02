import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal, Optional
from groq import AsyncGroq
from dotenv import load_dotenv, find_dotenv

# --- App and Client Initialization ---
load_dotenv(find_dotenv())

# --- Import our tools ---
import tools

app = FastAPI(title="SkyGen Agent Backend")

# Ensure API keys are loaded using the new, clear variable names
if not all([
    os.environ.get("GROQ_API_KEY"),
    os.environ.get("SKYGEN_URL"),
    os.environ.get("SKYGEN_SERVICE_KEY")
]):
    raise RuntimeError("Required environment variables are not set. Please check your .env file for GROQ_API_KEY, SKYGEN_URL, and SKYGEN_SERVICE_KEY.")

groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class AgentChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class AgentChatRequest(BaseModel):
    messages: List[AgentChatMessage]
    user_id: str
    conversation_id: Optional[str] = None

# --- Agent Setup ---
TOOL_MAP = {
    "get_user": tools.get_user,
    "update_user_profile": tools.update_user_profile,
    "delete_conversation_by_title": tools.delete_conversation_by_title,
    "delete_all_conversations": tools.delete_all_conversations,
    "sign_out_user": tools.sign_out_user,
    "get_leetcode_stats": tools.get_leetcode_stats,  # <--- ADD THIS LINE
    "search_the_web": tools.search_the_web,  # <--- ADD THIS LINE
}

MASTER_PROMPT_TEMPLATE = """
You are SkyGen, a powerful and friendly conversational assistant.

Your primary goal is to analyze the user's intent and respond in *only one* of two ways:
1.  **Conversational Text:** A natural, friendly text response.
2.  **Tool-Use JSON:** A JSON object (or multiple, one per line) to execute tools.

---

### ## 1. Conversational Intent (Text Response)

You MUST respond with natural text when:
* The user provides a greeting ('hi', 'hello', 'how are you').
* The user is making simple small talk.
* The user asks a question you can answer from your internal knowledge (e.g., "What is 2+2?").

**Guidelines for Text Responses:**
* Respond naturally.
* **DO NOT** output any JSON.

---

### ## 2. Tool Intent (JSON Response)

You MUST respond with JSON when the user's request requires you to:
* **Fetch real-time data** (e.g., "what's the latest news?", "suggest some articles", "find youtube videos").
* **Perform an action** (e.g., "update my profile," "delete my chats," "sign me out").
* **Access user data** (e.g., "what's my username?", "get my leetcode stats").

**CRITICAL RULES FOR TOOL USE:**

1. Your *entire* response must be **only** JSON.

2. If a user asks for *any* external content (articles, videos, links, real-time info), you MUST use the `search_the_web` tool.

3. **DO NOT, under any circumstances, invent or "hallucinate" URLs or links.** Your *only* source of links is the `search_the_web` tool.

**JSON Examples:**

```json
{{"thought": "The user wants to sign out.", "tool_name": "sign_out_user", "tool_input": {{}} }}
```

```json
{{"thought": "The user wants articles on the grandfather paradox.", "tool_name": "search_the_web", "tool_input": {{"query": "grandfather paradox articles and videos"}} }}
```

---

### ## 3. Final Answer Formatting

This section guides your final response after you have received Observation: data from a tool.

For Actions (delete, update): Simply confirm the action.

Example: "Done! I've updated your profile."

For Search Results (search_the_web): You MUST synthesize the tool's output. Present the information in a clear, modern, and helpful way.

**REQUIRED FORMATS FOR LINKS:**

For Articles/Websites:

Present as a numbered list.

The title MUST be a clickable Markdown link.

Example:

1. **[Title of the Article](https://example.com/article)**
   A brief, helpful description of what the article is about.

For YouTube Videos (Your "Modern" Suggestion):

Present them clearly, including the channel if possible.

The title MUST be a clickable Markdown link.

Example:

**Video:** [What Is the Grandfather Paradox?](https://youtube.com/watch?v=...)

**Channel:** PBS Space Time

**Description:** This video provides a great visual explanation of the paradox...

---

### ## Your Tools

You have access to the following tools. Use them only when necessary. {tool_descriptions}

### Context

Current User ID is: {user_id}

Begin!
"""

# --- Helper to send data as Server-Sent Events (SSE) ---
def sse_pack(data: 
             dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

# --- Main Agent Endpoint ---
@app.post("/agent-chat")
async def agent_chat_stream(request: AgentChatRequest):
    
    tool_descriptions = ""
    for name, func in TOOL_MAP.items():
        tool_descriptions += f"- Tool: `{name}`\n  - Description: {func.__doc__.strip()}\n"
    
    master_prompt = MASTER_PROMPT_TEMPLATE.format(
        tool_descriptions=tool_descriptions,
        user_id=request.user_id
    )

    messages_for_groq = [{"role": "system", "content": master_prompt}]
    messages_for_groq.extend([msg.dict() for msg in request.messages])

    async def event_generator():
        print("\n--- [DEBUG] Event Generator Started ---")
        try:
            # 1. Start a single streaming call
            print(f"[DEBUG] 1. Creating Groq stream with {len(messages_for_groq)} messages...")
            stream = await groq_client.chat.completions.create(
                messages=messages_for_groq,
                model="openai/gpt-oss-120b", # CHANGED: Using a standard, reliable model name
                temperature=0.0,
                stream=True
            )
            print("[DEBUG] 2. Groq stream created. Looping...")

            is_tool_call = False
            first_token_seen = False
            full_response = ""
            
            async for chunk in stream:
                print("[DEBUG] 3. Received a chunk.")
                
                # Safer check for content
                if not (chunk.choices and chunk.choices[0].delta):
                    print("[DEBUG]    ...chunk has no choices/delta. Skipping.")
                    continue
                
                token = chunk.choices[0].delta.content or ""
                
                if not token:
                    print("[DEBUG]    ...chunk has empty token. Skipping.")
                    continue # Skip empty content chunks

                print(f"[DEBUG] 4. Token: '{token}'")

                # 2. Peek at the first token to decide the route
                if not first_token_seen:
                    first_token_seen = True
                    print("[DEBUG] 5. First token seen.")
                    if token.strip().startswith('{'):
                        is_tool_call = True
                        print("[DEBUG] 6. --> Route: TOOL CALL")
                        yield sse_pack({'type': 'thought', 'content': "Thinking..."})
                    else:
                        print("[DEBUG] 6. --> Route: CHAT REPLY")
                
                if is_tool_call:
                    # 3. If in tool mode, buffer the full JSON
                    print("[DEBUG] 7. Buffering tool JSON.")
                    full_response += token
                else:
                    # 4. If in chat mode, stream tokens directly
                    print("[DEBUG] 7. Streaming chat token.")
                    yield sse_pack({'type': 'token', 'content': token})

            print("[DEBUG] 8. Stream loop finished.")
            
            # --- The Stream is Done ---
            
            if is_tool_call:
                print(f"[DEBUG] 9. Executing tool call logic. Full JSON:\n{full_response}")
                # 5. Now that the stream is finished, execute the tool call
                tool_calls = []
                try:
                    # Try to parse as single JSON
                    tool_call_data = json.loads(full_response.strip())
                    if "tool_name" in tool_call_data and "tool_input" in tool_call_data:
                         tool_calls = [tool_call_data]
                except json.JSONDecodeError:
                    # Try to parse multiple JSON objects (one per line)
                    lines = full_response.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:
                            try:
                                tool_call_data = json.loads(line)
                                if "tool_name" in tool_call_data and "tool_input" in tool_call_data:
                                    tool_calls.append(tool_call_data)
                            except json.JSONDecodeError:
                                continue # Ignore invalid lines
                
                if not tool_calls:
                     print("[DEBUG] ERROR: LLM generated invalid tool call JSON.")
                     yield sse_pack({'type': 'error', 'content': "LLM generated invalid tool call JSON."})
                     return # End the generator

                # --- (This is your original, correct tool execution logic) ---
                all_observations = []
                sign_out_requested = False
                
                for tool_call_data in tool_calls:
                    action_name = tool_call_data.get("tool_name")
                    action_input = tool_call_data.get("tool_input", {})
                    action_input['user_id'] = request.user_id

                    print(f"[DEBUG] 10. Calling tool: {action_name}")
                    yield sse_pack({'type': 'thought', 'content': tool_call_data.get("thought", "Thinking...")})
                    yield sse_pack({'type': 'tool_call', 'tool_name': action_name, 'tool_input': action_input})

                    if action_name in TOOL_MAP:
                        tool_function = TOOL_MAP[action_name]
                        observation = await tool_function(**action_input)
                        all_observations.append(f"{action_name}: {observation}")
                        
                        if observation == "ACTION_SIGN_OUT":
                            sign_out_requested = True
                        
                        yield sse_pack({'type': 'tool_output', 'content': observation})
                    else:
                        error_msg = f"Error: Tool '{action_name}' does not exist."
                        all_observations.append(error_msg)
                        yield sse_pack({'type': 'error', 'content': error_msg})
                
                if sign_out_requested:
                    yield sse_pack({'type': 'agent_action', 'action': 'sign_out'})
                    return
                
                if all_observations:
                    print("[DEBUG] 11. Generating final tool response.")
                    final_prompt = f"""
You are a helpful assistant. The user's original request was:
"{request.messages[-1].content}"

You just executed tools and got these results:
"{'; '.join(all_observations)}"

Now, provide a final, natural language response to the user.
- If the tools were for an *action* (like delete, update), simply confirm the action.
- If the tools were for a *search* (like search_the_web), synthesize the information from the results and answer the user's question directly.

**REQUIRED FORMATS FOR LINKS:**

For Articles/Websites:

Present as a numbered list.

The title MUST be a clickable Markdown link.

Example:

1. **[Title of the Article](https://example.com/article)**
   A brief, helpful description of what the article is about.

For YouTube Videos (Your "Modern" Suggestion):

Present them clearly, including the channel if possible.

The title MUST be a clickable Markdown link.

Example:

**Video:** [What Is the Grandfather Paradox?](https://youtube.com/watch?v=...)

**Channel:** PBS Space Time

**Description:** This video provides a great visual explanation of the paradox...

Begin your final response now.
"""
                    final_response_stream = await groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": final_prompt}],
                        model="openai/gpt-oss-120b", # CHANGED: Using standard model
                        stream=True
                    )
                    async for chunk in final_response_stream:
                        token = chunk.choices[0].delta.content or ""
                        if token:
                            yield sse_pack({'type': 'final_answer', 'content': token})
            
            # 6. If it was a chat reply (is_tool_call = False), we're done.
            print("[DEBUG] 9. Chat reply finished.")

        except Exception as e:
            # 7. This will catch any error
            print(f"\n--- [DEBUG] AN ERROR OCCURRED ---")
            print(f"[DEBUG] Exception: {str(e)}")
            import traceback
            traceback.print_exc() # This will print the full error to your terminal
            print("---------------------------------")
            error_message = f"An unexpected error occurred in the agent: {str(e)}"
            yield sse_pack({'type': 'error', 'content': error_message})
        
        finally:
            # 8. Send the "done" signal
            print("[DEBUG] 10. Sending 'done' packet.")
            yield sse_pack({'done': True})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Root Endpoint (for health check) ---
@app.get("/")
def read_root():
    return {"status": "AI Agent Backend is running"}