import httpx
import logging
from typing import List
from app.schemas.chat import Message
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

OLLAMA_MODELS = {
    "gemma-4b": "gemma:4b",
    "gemma-27b": "gemma:27b",
    "qwen-32b": "qwen:32b",
}


class OllamaService:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.OLLAMA_URL

    async def chat(
        self, model: str, messages: List[Message], temperature: float = 0.7
    ) -> str:
        ollama_model = OLLAMA_MODELS.get(model, model)
        payload = {
            "model": ollama_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        logger.info(f"Ollama chat request: model={ollama_model}, msgs={len(messages)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            logger.info(f"Ollama response: {len(content)} chars")
            return content

    async def list_models(self) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            logger.warning(f"Ollama list models failed: {e}")
            return []
