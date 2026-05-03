from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    ConversationORM,
    MessageORM,
)
from services.ollama import ollama_chat
from services.openrouter import openrouter_chat

router = APIRouter()

# Map model IDs to providers
MODEL_PROVIDERS = {
    "gemma-4b": "local",
    "gemma-27b": "local",
    "qwen-32b": "local",
    "kimi-k2.5": "cloud",
}


async def get_db():
    from main import async_session
    async with async_session() as session:
        yield session


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    req: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
):
    # Get or create conversation
    result = await db.execute(
        select(ConversationORM).where(ConversationORM.id == req.conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = ConversationORM(
            id=req.conversation_id,
            title=req.messages[0].content[:50] + "..." if req.messages else "New Chat",
            model=req.model,
        )
        db.add(conversation)

    # Store user message
    user_msg = req.messages[-1] if req.messages else Message(role="user", content="")
    db.add(MessageORM(
        id=str(uuid.uuid4()),
        conversation_id=req.conversation_id,
        role=user_msg.role,
        content=user_msg.content,
    ))

    # Route to provider
    provider = MODEL_PROVIDERS.get(req.model, "local")
    try:
        if provider == "local":
            content = await ollama_chat(req.model, req.messages, req.temperature)
        else:
            content = await openrouter_chat(req.model, req.messages, req.temperature)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    # Store assistant message
    assistant_msg = MessageORM(
        id=str(uuid.uuid4()),
        conversation_id=req.conversation_id,
        role="assistant",
        content=content,
        model=req.model,
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatCompletionResponse(
        id=str(uuid.uuid4()),
        message=Message(role="assistant", content=content),
        model=req.model,
        usage={"prompt_tokens": 0, "completion_tokens": 0},  # TODO: real token counting
    )
