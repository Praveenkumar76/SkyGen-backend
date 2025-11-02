# SkyGen Backend

FastAPI backend server for SkyGen AI chat application with Groq integration and Supabase database.

## Features

- FastAPI server with CORS support
- Groq API integration for AI chat (Llama 3.3 70B)
- Supabase database integration
- Streaming responses with Server-Sent Events (SSE)
- Tool-based agent system for user management

- python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

## Prerequisites

- Python 3.10+
- Groq API key ([Get one here](https://console.groq.com))
- Supabase project ([Create one here](https://supabase.com))

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the backend directory:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
GROQ_API_KEY=your_groq_api_key_here
SKYGEN_URL=https://your-project.supabase.co
SKYGEN_SERVICE_KEY=your_supabase_service_role_key_here
```

### 3. Run the Backend Server

#### Option 1: Using PowerShell Script (Recommended)

```powershell
.\start_backend.ps1
```

#### Option 2: Using uvicorn directly

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start at: **http://localhost:8000**

## API Endpoints

### Health Check
```
GET /
```
Returns server status.

### Agent Chat
```
POST /agent-chat
```
Streaming chat endpoint with AI agent capabilities.

**Request Body:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "user_id": "user-uuid-here"
}
```

**Response:** Server-Sent Events (SSE) stream with token updates.

## Available Tools

The agent has access to these tools:

1. **get_user** - Fetch user profile information
2. **update_user_profile** - Update user details (name, age, address, about)
3. **delete_conversation_by_title** - Delete specific chat conversation
4. **delete_all_conversations** - Clear all user conversations
5. **sign_out_user** - Sign out current user

## Project Structure

```
backend/
├── main.py              # FastAPI app and agent endpoint
├── tools.py             # Agent tool functions
├── server.py            # MCP server (alternative)
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (create this)
├── .env.example         # Environment template
└── start_backend.ps1    # Startup script for Windows
```

## Troubleshooting

### Import Errors
If you see dependency conflicts, try:
```bash
pip install --upgrade fastapi uvicorn groq python-dotenv supabase
```

### Environment Variables Not Loading
Make sure your `.env` file is in the `backend` directory and has proper formatting (no quotes around values).

### Port Already in Use
Change the port in `start_backend.ps1` or use:
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### CORS Errors
The backend is configured to allow all origins (`*`). If you still get CORS errors, check that the frontend is making requests to the correct URL.

## Development

To run in development mode with auto-reload:
```bash
uvicorn main:app --reload
```

## Production Deployment

For production, use:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or deploy to platforms like:
- Railway
- Render
- Fly.io
- AWS/GCP/Azure

## License

Part of the SkyGen project.
