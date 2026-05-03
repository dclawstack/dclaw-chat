import os
import httpx
from typing import List
from models import Message

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Map our model IDs to OpenRouter model names
OPENROUTER_MODELS = {
    "kimi-k2.5": "moonshot-ai/kimi-k2.5",
}


async def openrouter_chat(model: str, messages: List[Message], temperature: float = 0.7) -> str:
    """Proxy chat request to OpenRouter (cloud fallback)."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    openrouter_model = OPENROUTER_MODELS.get(model, model)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://dclawstack.io",
                "X-Title": "DClaw Chat",
            },
            json={
                "model": openrouter_model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
