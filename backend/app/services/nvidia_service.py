import httpx
import logging
from typing import List
from app.schemas.chat import Message
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

NVIDIA_MODELS = {
    "deepseek-v4": "deepseek-ai/deepseek-v4-pro",
}

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaService:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.base_url = base_url or NVIDIA_BASE_URL

    async def chat(
        self, model: str, messages: List[Message], temperature: float = 0.7
    ) -> str:
        if not self.api_key:
            raise ValueError("NVIDIA API key not configured")

        nv_model = NVIDIA_MODELS.get(model, model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": nv_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "top_p": 0.95,
            "max_tokens": 4096,
        }
        logger.info(f"NVIDIA NIM chat: model={nv_model}, msgs={len(messages)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(f"NVIDIA response: {len(content)} chars")
            return content
