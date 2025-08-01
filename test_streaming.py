import requests
import json

# --- Configuration ---
STREAMING_URL = "http://localhost:8000/generate-stream"
TEST_PROMPT = "Why is the sky blue? Explain in detail."

# --- Pydantic-like Models for Test Data ---
class ChatMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content

    def to_dict(self):
        return {"role": self.role, "content": self.content}

class ChatRequest:
    def __init__(self, messages):
        self.messages = messages

    def to_dict(self):
        return {"messages": [msg.to_dict() for msg in self.messages]}

# --- Main Test Function ---
def test_streaming_endpoint():
    """
    Tests the /generate-text-stream endpoint with SSE.
    """
    print(f"--- Starting SSE streaming test for {STREAMING_URL} ---")
    
    # 1. Prepare the request data
    chat_messages = [ChatMessage(role="user", content=TEST_PROMPT)]
    chat_request = ChatRequest(messages=chat_messages)
    
    # 2. Send the streaming request
    try:
        with requests.post(STREAMING_URL, json=chat_request.to_dict(), stream=True) as response:
            # 3. Check for a successful response
            if response.status_code == 200:
                print("Successfully connected to the streaming endpoint.")
                print("Streaming response:\n")
                
                full_response = ""
                # 4. Iterate over the streamed chunks
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data: '):
                            data = decoded_line[6:]  # Remove 'data: ' prefix
                            if data.strip():
                                try:
                                    parsed = json.loads(data)
                                    if 'token' in parsed:
                                        token = parsed['token']
                                        print(token, end="", flush=True)
                                        full_response += token
                                    elif 'done' in parsed and parsed['done']:
                                        print("\n\n--- Streaming finished ---")
                                        break
                                    elif 'error' in parsed:
                                        print(f"\nError: {parsed['error']}")
                                        break
                                except json.JSONDecodeError as e:
                                    print(f"\nError decoding JSON: {e}")
                
                print(f"\nFull response received ({len(full_response)} characters)")
                
            else:
                print(f"Error: Received status code {response.status_code}")
                print(f"Response body: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to the server: {e}")

if __name__ == "__main__":
    test_streaming_endpoint()