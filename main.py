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

# --- Agent Setup ---
TOOL_MAP = {
    "get_user": tools.get_user,
    "update_user_profile": tools.update_user_profile,
    "delete_conversation_by_title": tools.delete_conversation_by_title,
    "delete_all_conversations": tools.delete_all_conversations,
    "sign_out_user": tools.sign_out_user,
}

MASTER_PROMPT_TEMPLATE = """
You are SkyGen, a powerful assistant. You can have normal conversations OR use tools to perform actions.
- For a normal chat question, answer directly.
- When a user asks you to perform an action, you MUST use a tool.

**TOOL USAGE GUIDELINES**:
- For "delete all conversations" or "clear all chats" → use delete_all_conversations
- For "delete conversation about X" → use delete_conversation_by_title with the specific title
- For profile updates → use update_user_profile
- For signing out → use sign_out_user

You have access to the following tools:
{tool_descriptions}

**CRITICAL INSTRUCTION**:
- If you use a tool, your ENTIRE response MUST be a single JSON object with "thought", "tool_name", and "tool_input" keys.
- Example: {{"thought": "The user wants to sign out.", "tool_name": "sign_out_user", "tool_input": {{"user_id": "some-uuid"}}}}
- If you are NOT using a tool, respond naturally as a conversational assistant.

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
        user_id=request.user_id
    )

    messages_for_groq = [{"role": "system", "content": master_prompt}]
    messages_for_groq.extend([msg.dict() for msg in request.messages])

    async def event_generator():
        try:
            initial_response = await groq_client.chat.completions.create(
                messages=messages_for_groq,
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                stream=False
            )
            llm_output = initial_response.choices[0].message.content.strip()

            # Check if the response contains JSON tool calls
            is_tool_call = False
            tool_calls = []
            
            # Try to parse as single JSON
            try:
                tool_call_data = json.loads(llm_output)
                if "tool_name" in tool_call_data and "tool_input" in tool_call_data:
                    is_tool_call = True
                    tool_calls = [tool_call_data]
            except json.JSONDecodeError:
                # Try to parse multiple JSON objects (one per line)
                lines = llm_output.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            tool_call_data = json.loads(line)
                            if "tool_name" in tool_call_data and "tool_input" in tool_call_data:
                                tool_calls.append(tool_call_data)
                                is_tool_call = True
                        except json.JSONDecodeError:
                            continue

            if is_tool_call:
                all_observations = []
                sign_out_requested = False
                
                # Execute all tool calls
                for tool_call_data in tool_calls:
                    action_name = tool_call_data.get("tool_name")
                    action_input = tool_call_data.get("tool_input", {})
                    action_input['user_id'] = request.user_id

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
                
                # Handle sign out if requested
                if sign_out_requested:
                    yield sse_pack({'type': 'agent_action', 'action': 'sign_out'})
                    return
                
                # Generate final response
                if all_observations:
                    final_prompt = f"Original request: '{request.messages[-1].content}'. You executed these actions: {'; '.join(all_observations)}. Briefly and cheerfully confirm what you did."
                    final_response_stream = await groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": final_prompt}],
                        model="llama-3.3-70b-versatile",
                        stream=True
                    )
                    async for chunk in final_response_stream:
                        token = chunk.choices[0].delta.content or ""
                        if token:
                            yield sse_pack({'type': 'final_answer', 'content': token})

            else:
                stream = await groq_client.chat.completions.create(
                    messages=messages_for_groq,
                    model="llama-3.3-70b-versatile",
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
            yield sse_pack({'done': True})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Root Endpoint (for health check) ---
@app.get("/")
def read_root():
    return {"status": "AI Agent Backend is running"}