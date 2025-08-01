import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List, Dict, Any

class LlamaModel:
    def __init__(self, model_id="meta-llama/Meta-Llama-3-8B-Instruct"):
        print(f"Loading LLaMA 3 model: {model_id}... This may take a moment.")
        
        # Check for CUDA availability
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
        # For CPU usage, we'll use a smaller model since Llama 3 is very large
        if self.device == "cpu":
            print("CPU detected - switching to a smaller model for better performance")
            model_id = "facebook/opt-350m"
            
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
            
            # Load model with appropriate settings
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                device_map="auto",  # Automatically determine best device mapping
                trust_remote_code=True,
                load_in_4bit=self.device == "cuda",  # Only use 4-bit if on GPU
            )
        except Exception as e:
            print(f"Error loading {model_id}: {e}")
            print("Falling back to tiny model (distilgpt2)...")
            model_id = "distilgpt2"
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModelForCausalLM.from_pretrained(model_id)
        
        print("LLaMA 3 model loaded successfully!")

    def generate(self, messages: List[Dict[str, str]], max_new_tokens=256, temperature=0.7, top_p=0.95):
        """Generate text based on chat messages."""
        # Format messages into a prompt
        prompt = ""
        for msg in messages:
            prompt += f"{msg['role']}: {msg['content']}\n"
        prompt += "assistant:"
        
        # Tokenize input
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        # Generate response
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True
            )
            
        # Decode and return response
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract just the assistant's response
        if "assistant:" in response:
            response = response.split("assistant:")[-1].strip()
            
        return response
    
    async def generate_stream(self, messages: List[Dict[str, str]], max_new_tokens=256, temperature=0.7, top_p=0.95):
        """Generate text in a streaming fashion."""
        # Format messages into a prompt
        prompt = ""
        for msg in messages:
            prompt += f"{msg['role']}: {msg['content']}\n"
        prompt += "assistant:"
        
        # Tokenize input
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        # Stream generation
        streamer = self.tokenizer.decode(inputs.input_ids[0])
        generated_text = ""
        
        # Generate with streaming
        with torch.no_grad():
            for output in self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                streamer=None,  # We handle streaming manually
                return_dict_in_generate=True,
                output_scores=True
            ).sequences:
                token = self.tokenizer.decode([output[-1]], skip_special_tokens=True)
                if token:
                    generated_text += token
                    # Only yield the new token, not the entire text so far
                    yield token
        
        # Return a done signal at the end
        yield None