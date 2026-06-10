import json
import httpx
import logging
from typing import AsyncGenerator, List
from app.schemas.chat import Message
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

OPENROUTER_MODELS = {
    "kimi-k2.5": "moonshotai/kimi-k2.5",
    "claude-3.5-sonnet": "anthropic/claude-sonnet-4",
    "claude-3-opus": "anthropic/claude-opus-4",
    "gpt-4o": "openai/gpt-4o",
}


class OpenRouterService:
    def __init__(self, api_key: str = None, base_url: str = None):
        # None = use configured key; an explicit "" means key-less on purpose
        self.api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        self.base_url = base_url or settings.OPENROUTER_URL

    async def chat(
        self, model: str, messages: List[Message], temperature: float = 0.7
    ) -> str:
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        or_model = OPENROUTER_MODELS.get(model, model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://dclawstack.io",
            "X-Title": "DClaw Chat",
        }
        payload = {
            "model": or_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        logger.info(f"OpenRouter chat: model={or_model}, msgs={len(messages)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(f"OpenRouter response: {len(content)} chars")
            return content

    async def chat_stream(
        self, model: str, messages: List[Message], temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        or_model = OPENROUTER_MODELS.get(model, model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://dclawstack.io",
            "X-Title": "DClaw Chat",
        }
        payload = {
            "model": or_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        logger.info(f"OpenRouter stream: model={or_model}, msgs={len(messages)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("choices", [{}])[0].get("delta", {}).get("content", "") or ""
                    if token:
                        yield token
