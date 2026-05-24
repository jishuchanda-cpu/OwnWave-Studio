import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from app.core.config import settings

class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> str:
        """Call Ollama generation endpoint with retry backoff.
        
        Optimized for CPU-only inference with small models (llama3.2:3b):
        - num_predict caps output length to prevent runaway generation
        - num_ctx reduces context window to lower memory pressure
        - Lower temperature for faster convergence with JSON formatting
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.5,
                "num_predict": 512,   # Cap output tokens for faster CPU inference
                "num_ctx": 2048,      # Smaller context window = less memory pressure
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
            
        if format_json:
            payload["format"] = "json"

        max_retries = 2
        timeout_secs = 600.0  # 10 minutes max per call for CPU-only inference
        for attempt in range(max_retries):
            try:
                print(f"[OllamaService] Calling generate (attempt {attempt+1}/{max_retries}, timeout={timeout_secs}s)...")
                async with httpx.AsyncClient(timeout=timeout_secs) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    elapsed = result.get("total_duration", 0) / 1e9  # nanoseconds to seconds
                    print(f"[OllamaService] Generation complete in {elapsed:.1f}s, tokens: {result.get('eval_count', '?')}")
                    return result.get("response", "")
            except httpx.TimeoutException as e:
                print(f"[OllamaService] Timeout on attempt {attempt+1}: {e}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Ollama generation timed out after {timeout_secs}s. The model may be too slow on CPU. Details: {str(e)}")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Ollama server returned error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Could not connect to Ollama server at {self.base_url}. Details: {str(e)}")
                # Progressive wait: 2s, 4s
                await asyncio.sleep(2.0 * (attempt + 1))

    async def generate_structured(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured output parsed into a dictionary."""
        response_text = await self.generate(prompt, system_prompt=system_prompt, format_json=True)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            # Fallback or clean up common JSON output formatting issues
            print(f"Failed to parse JSON response: {response_text}. Error: {e}")
            # Try searching for markdown json tags or first '{' and last '}'
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(response_text[start:end+1])
                except Exception:
                    pass
            raise RuntimeError("Failed to parse response as valid JSON.")

    async def check_model_availability(self) -> bool:
        """Checks if the configured model is pulled and available in Ollama."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    models = [m["name"] for m in response.json().get("models", [])]
                    # Check both exact match and without version suffix
                    return any(self.model in m or m in self.model for m in models)
        except Exception:
            pass
        return False
