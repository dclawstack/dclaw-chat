import httpx
from typing import List
from models import Message

OLLAMA_BASE_URL = "http://localhost:11434"

# Map our model IDs to Ollama model names
OLLAMA_MODELS = {
    "gemma-4b": "gemma:4b",
    "gemma-27b": "gemma:27b",
    "qwen-32b": "qwen:32b",
}


async def ollama_chat(model: str, messages: List[Message], temperature: float = 0.7) -> str:
    """Proxy chat request to local Ollama instance."""
    ollama_model = OLLAMA_MODELS.get(model, model)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": ollama_model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")


async def list_ollama_models() -> List[dict]:
    """List models available in local Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
    except Exception:
        return []
