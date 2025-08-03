import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

# --- App Initialization ---
app = FastAPI(title="SkyGen")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Or specify your frontend URL for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Groq Client Initialization ---
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("Error: GROQ_API_KEY is not set.")
client = AsyncGroq(api_key=api_key)

# --- Pydantic Models ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class TitleRequest(BaseModel):
    firstMessage: str

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "AI Backend is running"}

@app.post("/generate-stream")
async def generate_text_stream(request: ChatRequest):
    messages_for_groq = [msg.dict() for msg in request.messages]
    async def event_generator():
        try:
            stream = await client.chat.completions.create(
                messages=messages_for_groq,
                model="llama3-70b-8192",
                stream=True,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            print(f"Error during Groq stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/generate-title")
async def generate_title(request: TitleRequest):
    try:
        title_prompt = f'Create a very short title (3-5 words) for a conversation that starts with this message: "{request.firstMessage}"'
        chat_completion = await client.chat.completions.create(
            messages=[{"role": "user", "content": title_prompt}],
            model="llama3-8b-8192",
            stream=False,
        )
        generated_title = chat_completion.choices[0].message.content or "New Chat"
        cleaned_title = generated_title.replace('"', '').strip()
        return {"title": cleaned_title}
    except Exception as e:
        print(f"Error generating title: {e}")
        return {"title": "New Chat"}