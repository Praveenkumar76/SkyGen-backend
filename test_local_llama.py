import requests
import json
import time

def test_local_llama():
    """Test the local LLaMA API with a simple prompt."""
    url = "http://localhost:8001/generate"
    
    data = {
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    print("Sending request to local LLaMA API...")
    start_time = time.time()
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        # Print response
        result = response.json()
        print(f"\nResponse received in {time.time() - start_time:.2f} seconds:")
        print(result["text"])
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        print("\nMake sure the local_llama_server.py is running!")

if __name__ == "__main__":
    test_local_llama()