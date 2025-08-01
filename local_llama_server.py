from fastapi import FastAPI, Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import json
import asyncio
import uvicorn
from pyngrok import ngrok
import os

from llama_model import LlamaModel

# --- FastAPI App Initialization ---
app = FastAPI(title="SkyGen LLaMA 3 API")

origins = [
    "https://f09dd74e36e9.ngrok-free.app", # Your public frontend URL
    "http://localhost:5173", # The local URL for your own testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Model Loading ---
model = LlamaModel()
print("LLaMA 3 model initialized and ready for inference.")

# --- Pydantic Models for API Requests ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 256
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95

# --- API Endpoints ---
@app.post("/generate")
async def generate_text(request: ChatRequest):
    """Generate text completion for chat messages."""
    try:
        # Convert Pydantic messages to dictionary format for the model
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Generate response
        response = model.generate(
            messages=messages,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p
        )
        
        return {"text": response}
    
    except Exception as e:
        return {"error": f"Failed to generate response: {str(e)}"}

@app.post("/generate-stream")
async def generate_text_stream(request: ChatRequest):
    """Generate streaming text completion for chat messages."""
    
    async def event_generator():
        try:
            # Convert Pydantic messages to dictionary format for the model
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            # Generate streaming response
            async for token in model.generate_stream(
                messages=messages,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p
            ):
                if token is None:
                    # End of stream
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    break
                else:
                    # Stream token
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/")
def read_root():
    return {"status": "LLaMA 3 API is running"}

# --- Start the server and expose with ngrok ---
# def start_server():
#     # Set up ngrok (free account supports only one tunnel)
#     port = 8001  # Using different port than main.py which uses 8000
    
#     # Start ngrok tunnel
#     public_url = ngrok.connect(port, "http")
#     print(f"Public URL: {public_url}")
    
#     # Start the FastAPI server
#     uvicorn.run("local_llama_server:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_server()