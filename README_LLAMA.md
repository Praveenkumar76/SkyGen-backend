# SkyGen Local LLaMA 3 Server

This module allows you to run LLaMA 3 (8B) locally on your laptop with 4GB VRAM and expose it via an API.

## Hardware Requirements

- 8 GB RAM (minimum)
- NVIDIA GPU with 4GB+ VRAM (GTX 1650 or better)
- Ryzen 5 5000 series or equivalent CPU

## Setup Instructions

1. Install the required Python packages:

```bash
cd Skygen/backend
pip install -r requirements.txt
```

2. Start the LLaMA 3 API server:

```bash
python start_llama_server.py
```

This will:
- Load the 4-bit quantized LLaMA 3 (8B) model
- Start a FastAPI server on port 8001
- Create a public URL using ngrok

## API Endpoints

- `GET /` - Check if the API is running
- `POST /generate` - Generate text completion (non-streaming)
- `POST /generate-stream` - Generate text completion with streaming

### Example Request for `/generate`

```json
{
  "messages": [
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "max_tokens": 100,
  "temperature": 0.7,
  "top_p": 0.95
}
```

## Testing the API

You can test the API using the provided test script:

```bash
python test_local_llama.py
```

## Frontend Integration

The frontend has been updated to support switching between Ollama and your local LLaMA API.

To use the local LLaMA API instead of Ollama:

1. Open `frontend/src/App.jsx`
2. Change `USE_LOCAL_LLAMA` to `true`
3. Restart your React frontend

## Troubleshooting

1. **Model fails to load**: You might need to adjust the quantization level. Edit `llama_model.py` to use a different model like `TheBloke/Llama-3-8B-Instruct-GGUF` with llama.cpp.

2. **Out of memory errors**: Reduce `max_new_tokens` to a smaller value like 128.

3. **ngrok tunnel not working**: You might need to create a free ngrok account and authenticate using `ngrok authtoken YOUR_TOKEN`.

## Additional Resources

- [TheBloke's 4-bit Quantized Models](https://huggingface.co/TheBloke)
- [GPTQ Quantization](https://github.com/IST-DASLab/gptq)
- [ngrok Documentation](https://ngrok.com/docs)