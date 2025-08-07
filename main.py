import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal
from groq import AsyncGroq
from dotenv import load_dotenv

# --- Import our tools ---
import tools

# --- App and Client Initialization ---
load_dotenv()
app = FastAPI(title="SkyGen Agent Backend")

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

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
    # Ensure these names match your functions in tools.py exactly
    "get_user_profile": tools.get_user,
    "update_user_profile": tools.update_user_profile,
    "delete_conversation_by_title": tools.delete_conversation_by_title,
    "sign_out_user": tools.sign_out_user,
}

MASTER_PROMPT_TEMPLATE = """
You are SkyGen, a powerful assistant integrated into an application. You can have normal conversations OR use tools to perform actions.
When a user asks you to do something like 'delete my chat' or 'update my profile', you MUST use a tool.
For a normal chat question, you MUST NOT use a tool and should answer as a helpful assistant.

You have access to the following tools:
{tool_descriptions}

Your reasoning format for using a tool:
Question: The user's request.
Thought: Your inner monologue.
Action: The name of the tool to use (must be one of [{tool_names}]).
Action Input: A JSON object of the parameters for the tool. For example: {{"user_id": "some-uuid", "full_name": "John Doe"}}

If you are not using a tool, just respond directly without the Thought/Action/Observation format.

Begin!
"""

# --- New, Improved Agent Endpoint ---
@app.post("/agent-chat")
async def agent_chat_stream(request: AgentChatRequest):
    
    tool_descriptions = ""
    for name, func in TOOL_MAP.items():
        tool_descriptions += f"- Tool: `{name}`\n  - Description: {func.__doc__.strip()}\n"
    
    master_prompt = MASTER_PROMPT_TEMPLATE.format(
        tool_descriptions=tool_descriptions,
        tool_names=", ".join(TOOL_MAP.keys())
    )

    messages_for_groq = [{"role": "system", "content": master_prompt}]
    messages_for_groq.extend([msg.dict() for msg in request.messages])

    async def event_generator():
        stream = await client.chat.completions.create(
            messages=messages_for_groq,
            model="llama3-70b-8192",
            temperature=0.0,
            stream=True
        )

        full_response = ""
        tool_call_detected = False
        
        # This loop streams tokens immediately for a fast UI response
        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                full_response += token
                # Only yield tokens if we haven't decided to call a tool yet
                if not tool_call_detected:
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                
                # Heuristic: Check for "Action:" after a newline to decide if it's a tool call
                if '"Action":' in full_response or "Action:" in full_response:
                    tool_call_detected = True

        # Now, after the stream is complete, we analyze the full response
        if tool_call_detected:
            try:
                # --- Tool-Using Logic ---
                yield f"data: {json.dumps({'type': 'thought', 'content': 'I need to use a tool to complete this request.'})}\n\n"
                
                action_name = full_response.split("Action:")[1].split("Action Input:")[0].strip().replace("`", "")
                action_input_str = full_response.split("Action Input:")[1].strip()
                action_input_json = json.loads(action_input_str)
                
                yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': action_name, 'tool_input': action_input_json})}\n\n"

                if action_name in TOOL_MAP:
                    tool_function = TOOL_MAP[action_name]
                    observation = tool_function(**action_input_json)
                    
                    if observation == "ACTION_SIGN_OUT":
                        yield f"data: {json.dumps({'type': 'agent_action', 'action': 'sign_out'})}\n\n"
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return

                    yield f"data: {json.dumps({'type': 'tool_output', 'content': observation})}\n\n"
                    
                    # Get a final confirmation message
                    final_prompt = f"The user asked: '{request.messages[-1].content}'. You took an action and the result was: '{observation}'. Briefly and cheerfully confirm this to the user."
                    final_response = await client.chat.completions.create(
                        messages=[{"role": "user", "content": final_prompt}],
                        model="llama3-8b-8192"
                    )
                    final_message = final_response.choices[0].message.content
                    yield f"data: {json.dumps({'type': 'final_answer', 'content': final_message})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Agent tried to use a tool that does not exist.'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Error processing tool action: {str(e)}'})}\n\n"
        
        # If no tool was detected, the streaming already happened, so we just signal completion.
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Root Endpoint (for health check) ---
@app.get("/")
def read_root():
    return {"status": "AI Agent Backend is running"}