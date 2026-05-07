import uuid
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import Message, ChatCompletionRequest, ChatCompletionResponse
from app.schemas.conversation import ConversationCreate
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.services.ollama_service import OllamaService, OLLAMA_MODELS
from app.services.openrouter_service import OpenRouterService
from app.services.nvidia_service import NvidiaService
from app.core.exceptions import NotFoundException, LLMException

logger = logging.getLogger(__name__)

MODEL_PROVIDERS = {
    # Local (Ollama)
    "gemma-4b": "local",
    "qwen-32b": "local",
    "nemotron-cascade-2": "local",
    "glm-4.7-flash": "local",
    "orpheus-3b": "local",
    # Cloud (OpenRouter)
    "kimi-k2.5": "cloud",
    "claude-3.5-sonnet": "cloud",
    "claude-3-opus": "cloud",
    "gpt-4o": "cloud",
    # Cloud (NVIDIA NIMs)
    "deepseek-v4": "nvidia",
}


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)
        self.ollama = OllamaService()
        self.openrouter = OpenRouterService()
        self.nvidia = NvidiaService()

    async def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        # Get or create conversation
        conversation = await self.conv_repo.get_by_id(req.conversation_id)
        if not conversation:
            conversation = await self.conv_repo.create(
                ConversationCreate(
                    title=req.messages[0].content[:50] + "..."
                    if req.messages
                    else "New Chat",
                    model=req.model,
                )
            )
            # Update ID to match request
            conversation.id = req.conversation_id
            await self.db.commit()

        # Store user message
        user_msg = req.messages[-1] if req.messages else Message(role="user", content="")
        await self.msg_repo.create(
            conversation_id=req.conversation_id,
            role=user_msg.role,
            content=user_msg.content,
        )

        # Route to provider
        provider = MODEL_PROVIDERS.get(req.model, "local")
        try:
            if provider == "local":
                content = await self.ollama.chat(req.model, req.messages, req.temperature)
            elif provider == "nvidia":
                content = await self.nvidia.chat(
                    req.model, req.messages, req.temperature
                )
            else:
                content = await self.openrouter.chat(
                    req.model, req.messages, req.temperature
                )
        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise LLMException(f"Failed to generate response: {str(e)}")

        # Store assistant message
        await self.msg_repo.create(
            conversation_id=req.conversation_id,
            role="assistant",
            content=content,
            model=req.model,
        )

        return ChatCompletionResponse(
            id=str(uuid.uuid4()),
            message=Message(role="assistant", content=content),
            model=req.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
        )

    async def list_models(self) -> List[dict]:
        local_models = await self.ollama.list_models()
        models = []

        # Add all installed Ollama models dynamically
        seen_ids = set()
        seen_ollama_names = set()
        for m in local_models:
            ollama_name = m.get("name", "")
            # Skip non-chat models (embeddings, OCR, vision)
            skip_keywords = ["embed", "ocr", "vision"]
            if any(kw in ollama_name.lower() for kw in skip_keywords):
                continue

            # Avoid duplicates from same Ollama model mapped to multiple IDs
            if ollama_name in seen_ollama_names:
                continue
            seen_ollama_names.add(ollama_name)

            model_id = self.ollama.get_model_id(ollama_name)
            if model_id in seen_ids:
                continue
            seen_ids.add(model_id)

            display_name = self.ollama.get_model_display_name(ollama_name)
            size_gb = round(m.get("size", 0) / (1024**3), 1)
            models.append(
                {
                    "id": model_id,
                    "name": display_name,
                    "provider": "local",
                    "description": f"Local {display_name} via Ollama ({size_gb} GB)",
                    "available": True,
                }
            )

        # Add fallback entries for known models not currently installed
        for mid, o_name in OLLAMA_MODELS.items():
            if mid not in seen_ids and o_name not in seen_ollama_names:
                models.append(
                    {
                        "id": mid,
                        "name": self.ollama.get_model_display_name(o_name),
                        "provider": "local",
                        "description": f"Local model via Ollama (not installed)",
                        "available": False,
                    }
                )

        # Cloud models
        models.extend(
            [
                {
                    "id": "kimi-k2.5",
                    "name": "Kimi K2.5",
                    "provider": "cloud",
                    "description": "Moonshot Kimi K2.5 via OpenRouter",
                    "available": True,
                },
                {
                    "id": "claude-3.5-sonnet",
                    "name": "Claude 3.5 Sonnet",
                    "provider": "cloud",
                    "description": "Anthropic Claude 3.5 Sonnet via OpenRouter",
                    "available": True,
                },
                {
                    "id": "claude-3-opus",
                    "name": "Claude 3 Opus",
                    "provider": "cloud",
                    "description": "Anthropic Claude 3 Opus via OpenRouter (Max)",
                    "available": True,
                },
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "provider": "cloud",
                    "description": "OpenAI GPT-4o via OpenRouter",
                    "available": True,
                },
                {
                    "id": "deepseek-v4",
                    "name": "DeepSeek V4",
                    "provider": "cloud",
                    "description": "DeepSeek V4 Pro via NVIDIA NIMs (free tier)",
                    "available": True,
                },
            ]
        )
        return models
