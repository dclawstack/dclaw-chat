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
from app.core.exceptions import NotFoundException, LLMException

logger = logging.getLogger(__name__)

MODEL_PROVIDERS = {
    "gemma-4b": "local",
    "gemma-27b": "local",
    "qwen-32b": "local",
    "kimi-k2.5": "cloud",
    "claude-3.5-sonnet": "cloud",
    "gpt-4o": "cloud",
}


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)
        self.ollama = OllamaService()
        self.openrouter = OpenRouterService()

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
        for mid, name in [
            ("gemma-4b", "Gemma 4B"),
            ("gemma-27b", "Gemma 27B"),
            ("qwen-32b", "Qwen 32B"),
        ]:
            available = any(m.get("name") == OLLAMA_MODELS.get(mid, mid) for m in local_models)
            models.append(
                {
                    "id": mid,
                    "name": name,
                    "provider": "local",
                    "description": f"Local {name} via Ollama",
                    "available": available,
                }
            )
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
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "provider": "cloud",
                    "description": "OpenAI GPT-4o via OpenRouter",
                    "available": True,
                },
            ]
        )
        return models
