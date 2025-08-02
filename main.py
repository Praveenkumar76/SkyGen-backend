import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal
import json
from groq import AsyncGroq  # Import the Groq library
from dotenv import load_dotenv
load_dotenv()
# --- FastAPI App Initialization ---
app = FastAPI(title="SkyGen")

# --- Middleware for CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize Groq Client ---
# The API key will be set as an environment variable on the server
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("Error: GROQ_API_KEY is not set in the environment variables.")

client = AsyncGroq(api_key=api_key)

# --- Pydantic Models ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

# --- API Endpoints ---
@app.post("/generate-stream")
async def generate_text_stream(request: ChatRequest):
    # Convert incoming messages to the format Groq expects
    messages_for_groq = [msg.dict() for msg in request.messages]

    async def event_generator():
        try:
            # Create a streaming chat completion request to Groq
            stream = await client.chat.completions.create(
                messages=messages_for_groq,
                model = "llama3-70b-8192",  # Use a model available on Groq
                stream=True,
            )
            # Yield each token as it arrives
            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield f"data: {json.dumps({'token': token})}\n\n"
            
            # Send a 'done' signal at the end
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            print(f"Error during Groq stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/")
def read_root():
    return {"status": "AI Backend is running"}