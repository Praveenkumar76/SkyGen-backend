import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal, Optional
from groq import AsyncGroq
from dotenv import load_dotenv

# --- Import our tools ---
import tools

# --- App and Client Initialization ---
load_dotenv()
app = FastAPI(title="SkyGen Agent Backend")

# Ensure API keys are loaded
if not os.environ.get("GROQ_API_KEY") or not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
    raise RuntimeError("Required environment variables are not set. Please check your .env file.")

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend's domain
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

# --- Agent Setup ---
TOOL_MAP = {
    "get_user": tools.get_user,
    "update_user_profile": tools.update_user_profile,
    "delete_conversation_by_title": tools.delete_conversation_by_title,
    "sign_out_user": tools.sign_out_user,
}

# IMPROVED: This prompt is more direct, telling the model exactly how to format its response.
# This makes parsing much more reliable than searching for "Action:".
MASTER_PROMPT_TEMPLATE = """
You are SkyGen, a powerful assistant integrated into an application. You can have normal conversations OR use tools to perform actions.

- For a normal chat question (e.g., 'What is React?'), you MUST NOT use a tool. Just answer directly as a helpful assistant.
- When a user asks you to perform an action (e.g., 'delete my chat about groceries', 'change my name to Alex', 'sign me out'), you MUST use a tool.

You have access to the following tools:
{tool_descriptions}

**CRITICAL INSTRUCTION**:
- If you decide to use a tool, your ENTIRE response MUST be a single JSON object.
- The JSON object must have three keys: "thought", "tool_name", and "tool_input".
- Example of a tool-use response:
  {{"thought": "The user wants to delete a conversation. I need to find the title and use the delete tool.", "tool_name": "delete_conversation_by_title", "tool_input": {{"user_id": "some-uuid", "title": "Grocery List"}}}}

- If you are NOT using a tool, respond naturally as a conversational assistant. Do NOT use the JSON format.

Current User ID is: {user_id}
Begin!
"""

# --- Helper to send data as Server-Sent Events (SSE) ---
def sse_pack(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

# --- Main Agent Endpoint ---
@app.post("/agent-chat")
async def agent_chat_stream(request: AgentChatRequest):
    
    tool_descriptions = ""
    for name, func in TOOL_MAP.items():
        tool_descriptions += f"- Tool: `{name}`\n  - Description: {func.__doc__.strip()}\n"
    
    master_prompt = MASTER_PROMPT_TEMPLATE.format(
        tool_descriptions=tool_descriptions,
        tool_names=", ".join(TOOL_MAP.keys()),
        user_id=request.user_id # Pass user_id to the prompt context
    )

    messages_for_groq = [{"role": "system", "content": master_prompt}]
    messages_for_groq.extend([msg.dict() for msg in request.messages])

    async def event_generator():
        try:
            # 1. First call to LLM to decide on a tool or a direct answer
            initial_response = await client.chat.completions.create(
                messages=messages_for_groq,
                model="llama3-70b-8192",
                temperature=0.0,
                stream=False  # We need the full response to check for a tool call
            )
            llm_output = initial_response.choices[0].message.content.strip()

            # 2. Check if the response is a tool call (a valid JSON)
            try:
                tool_call_data = json.loads(llm_output)
                is_tool_call = "tool_name" in tool_call_data and "tool_input" in tool_call_data
            except json.JSONDecodeError:
                is_tool_call = False

            # --- BRANCH 1: Agent decided to use a tool ---
            if is_tool_call:
                action_name = tool_call_data.get("tool_name")
                action_input = tool_call_data.get("tool_input", {})
                
                # Ensure user_id from the request is used, not a hallucinated one
                action_input['user_id'] = request.user_id

                yield sse_pack({'type': 'thought', 'content': tool_call_data.get("thought", "Thinking...")})
                yield sse_pack({'type': 'tool_call', 'tool_name': action_name, 'tool_input': action_input})

                if action_name in TOOL_MAP:
                    tool_function = TOOL_MAP[action_name]
                    # The user_id is now automatically passed to the tool functions
                    observation = tool_function(**action_input)
                    
                    # Handle special sign-out action
                    if observation == "ACTION_SIGN_OUT":
                        yield sse_pack({'type': 'agent_action', 'action': 'sign_out'})
                        return

                    yield sse_pack({'type': 'tool_output', 'content': observation})
                    
                    # Get a final confirmation message from the LLM
                    final_prompt = f"The user's original request was: '{request.messages[-1].content}'. You used the tool '{action_name}' and the result was: '{observation}'. Briefly and cheerfully confirm this action to the user. Do not use any special formatting."
                    final_response_stream = await client.chat.completions.create(
                        messages=[{"role": "user", "content": final_prompt}],
                        model="llama3-8b-8192",
                        stream=True
                    )
                    async for chunk in final_response_stream:
                        token = chunk.choices[0].delta.content or ""
                        if token:
                            yield sse_pack({'type': 'final_answer', 'content': token})
                else:
                    yield sse_pack({'type': 'error', 'content': f"Error: Agent tried to use a tool '{action_name}' that does not exist."})

            # --- BRANCH 2: Agent decided to respond directly ---
            else:
                # Stream the original non-tool response token by token
                # This is a bit inefficient as we're re-requesting, but it's the simplest way to get a stream
                # from a non-streamed initial response. A more advanced solution might use a custom buffer.
                stream = await client.chat.completions.create(
                    messages=messages_for_groq,
                    model="llama3-70b-8192",
                    temperature=0.0,
                    stream=True
                )
                async for chunk in stream:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        yield sse_pack({'type': 'token', 'content': token})

        except Exception as e:
            error_message = f"An unexpected error occurred in the agent: {str(e)}"
            yield sse_pack({'type': 'error', 'content': error_message})
        
        finally:
            # Signal the end of the stream
            yield sse_pack({'done': True})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Root Endpoint (for health check) ---
@app.get("/")
def read_root():
    return {"status": "AI Agent Backend is running"}