import os
import subprocess
import sys
import time

def check_dependencies():
    """Check if required packages are installed."""
    try:
        import torch
        import transformers
        import pyngrok
        
        # Check CUDA
        if torch.cuda.is_available():
            print(f"✅ CUDA is available. Using device: {torch.cuda.get_device_name(0)}")
            print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        else:
            print("⚠️ CUDA is not available. Using CPU only - this will be very slow!")
            
        return True
        
    except ImportError as e:
        print(f"❌ Error: Missing required package: {e.name}")
        print("   Please install the requirements first:")
        print("   pip install -r requirements.txt")
        return False

def start_server():
    """Start the LLaMA server."""
    print("🚀 Starting LLaMA 3 Server...")
    print("⏳ Loading model - this may take a few minutes on first run...")
    
    try:
        # Import for direct execution
        from local_llama_server import app
        import uvicorn
        from pyngrok import ngrok
        import os
        
        # Set up ngrok - handling authentication
        port = 8001
        
        # Try to connect with ngrok
        # try:
        #     # Check if ngrok auth token exists
        #     ngrok_token = os.environ.get("NGROK_AUTH_TOKEN")
        #     if ngrok_token:
        #         print("Using NGROK_AUTH_TOKEN from environment variables")
        #         ngrok.set_auth_token(ngrok_token)
            
        #     # Connect and create tunnel
        #     public_url = ngrok.connect(port, "http")
        #     print(f"\n🌐 Public URL: {public_url}")
        #     print("   Share this URL to allow others to access your model")
        #     print("   Note: Free ngrok URLs expire after a while")
        # except Exception as ngrok_error:
        #     print(f"\n⚠️ Ngrok connection failed: {ngrok_error}")
        #     print("   Starting in local-only mode.")
        #     print("   To use ngrok, get a free auth token from https://ngrok.com")
        #     print("   Then run: ngrok authtoken YOUR_TOKEN")
        
        # Print local URL
        print(f"\n🏠 Local URL: http://localhost:{port}")
        
        # Start server
        print("\n📡 Starting FastAPI server...")
        uvicorn.run(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False
        
    return True

if __name__ == "__main__":
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
        
    # Start the server
    start_server()