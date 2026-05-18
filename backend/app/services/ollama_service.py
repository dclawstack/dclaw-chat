import json
import httpx
import logging
from typing import AsyncGenerator, List
from app.schemas.chat import Message
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Mapping from frontend model IDs to Ollama model names
OLLAMA_MODELS = {
    "gemma-4b": "gemma4:e2b",
    "qwen2.5-7b": "qwen2.5:7b",
    "qwen-32b": "qwen3.5:35b",
    "nemotron-cascade-2": "nemotron-cascade-2:latest",
    "glm-4.7-flash": "glm-4.7-flash:latest",
    "orpheus-3b": "legraphista/Orpheus:3b-ft-q8",
}

# Friendly names for discovered Ollama models
OLLAMA_MODEL_NAMES = {
    "gemma4:e2b": "Gemma 4B",
    "gemma4:latest": "Gemma 4B",
    "qwen2.5:7b": "Qwen 2.5 7B",
    "qwen3.5:35b": "Qwen 3.5 35B",
    "glm-4.7-flash:latest": "GLM 4.7 Flash",
    "nemotron-cascade-2:latest": "Nemotron Cascade 2",
    "legraphista/Orpheus:3b-ft-q8": "Orpheus 3B",
}

# Reverse lookup: Ollama name → frontend ID (covers all known tag variants)
OLLAMA_NAME_TO_ID: dict[str, str] = {v: k for k, v in OLLAMA_MODELS.items()}
OLLAMA_NAME_TO_ID.update({
    "gemma4:latest": "gemma-4b",
    "gemma4:e2b": "gemma-4b",
    "gemma4:2b": "gemma-4b",
})


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

    async def chat_stream(
        self, model: str, messages: List[Message], temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        ollama_model = OLLAMA_MODELS.get(model, model)
        payload = {
            "model": ollama_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        logger.info(f"Ollama stream request: model={ollama_model}, msgs={len(messages)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break

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

    def get_model_display_name(self, ollama_name: str) -> str:
        return OLLAMA_MODEL_NAMES.get(ollama_name, ollama_name)

    def get_model_id(self, ollama_name: str) -> str:
        return OLLAMA_NAME_TO_ID.get(ollama_name, ollama_name.replace(":", "-").replace("/", "-"))
