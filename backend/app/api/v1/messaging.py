import uuid
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db, async_session
from app.core.deps import get_current_user, CurrentUser
from app.models.channel import ChannelORM, ChannelMessageORM
from app.services.messaging import manager
from app.services.ollama_service import OllamaService, OLLAMA_MODELS
from app.schemas.chat import Message as ChatMessage

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ChannelOut(BaseModel):
    id: str
    name: str
    type: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ChannelMessageOut(BaseModel):
    id: str
    channel_id: str
    user_id: str
    user_name: str
    content: str
    thread_parent_id: Optional[str]
    reply_count: int
    created_at: datetime
    model_config = {"from_attributes": True}


class CreateChannelRequest(BaseModel):
    name: str
    type: str = "public"


class SendMessageRequest(BaseModel):
    content: str
    thread_parent_id: Optional[str] = None


# ── REST endpoints ────────────────────────────────────────────────────────────

DEFAULT_CHANNELS = ["general", "engineering", "random"]


@router.get("/channels", response_model=List[ChannelOut])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(select(ChannelORM).order_by(ChannelORM.created_at))
    channels = list(result.scalars().all())
    if not channels:
        channels = [ChannelORM(id=str(uuid.uuid4()), name=n) for n in DEFAULT_CHANNELS]
        for ch in channels:
            db.add(ch)
        await db.commit()
        for ch in channels:
            await db.refresh(ch)
    return channels


@router.post("/channels", response_model=ChannelOut, status_code=201)
async def create_channel(
    req: CreateChannelRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    channel = ChannelORM(id=str(uuid.uuid4()), name=req.name, type=req.type)
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.get("/channels/{channel_id}/messages", response_model=List[ChannelMessageOut])
async def list_messages(
    channel_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChannelMessageORM)
        .where(
            ChannelMessageORM.channel_id == channel_id,
            ChannelMessageORM.thread_parent_id.is_(None),
        )
        .order_by(ChannelMessageORM.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post("/channels/{channel_id}/messages", response_model=ChannelMessageOut, status_code=201)
async def send_message(
    channel_id: str,
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    msg = ChannelMessageORM(
        id=str(uuid.uuid4()),
        channel_id=channel_id,
        user_id=user.user_id,
        user_name=user.email.split("@")[0],
        content=req.content,
        thread_parent_id=req.thread_parent_id,
    )
    db.add(msg)
    if req.thread_parent_id:
        parent = await db.get(ChannelMessageORM, req.thread_parent_id)
        if parent:
            parent.reply_count += 1
    await db.commit()
    await db.refresh(msg)
    await manager.broadcast(channel_id, _msg_to_dict(msg))
    return msg


@router.get(
    "/channels/{channel_id}/messages/{message_id}/thread",
    response_model=List[ChannelMessageOut],
)
async def get_thread(
    channel_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChannelMessageORM)
        .where(ChannelMessageORM.thread_parent_id == message_id)
        .order_by(ChannelMessageORM.created_at.asc())
    )
    return list(result.scalars().all())


# ── WebSocket ─────────────────────────────────────────────────────────────────

def _msg_to_dict(m: ChannelMessageORM) -> dict:
    return {
        "type": "message",
        "id": m.id,
        "channel_id": m.channel_id,
        "user_id": m.user_id,
        "user_name": m.user_name,
        "content": m.content,
        "thread_parent_id": m.thread_parent_id,
        "reply_count": m.reply_count,
        "created_at": m.created_at.isoformat(),
    }


AI_USER_ID = "dclaw-copilot"
AI_USER_NAME = "DClaw Copilot"
_ollama = OllamaService()
_default_model = next(iter(OLLAMA_MODELS.keys()), "gemma-4b")


async def _generate_ai_reply(
    channel_id: str,
    history: list[ChannelMessageORM],
    trigger_content: str,
    thread_parent_id: Optional[str] = None,
) -> None:
    """Call Ollama, persist + broadcast the AI reply (in thread if thread_parent_id given)."""
    try:
        manager.set_typing(channel_id, AI_USER_ID, AI_USER_NAME)
        await manager.broadcast(channel_id, {
            "type": "typing",
            "channel_id": channel_id,
            "typing_users": manager.get_typing_names(channel_id),
        })

        context = "\n".join(
            f"{m.user_name}: {m.content[:300]}"
            for m in history[-10:]
            if m.user_id != AI_USER_ID
        )
        scope = "this thread" if thread_parent_id else "the team channel"
        system_prompt = (
            f"You are DClaw Copilot, an AI assistant embedded in {scope}. "
            "Answer the latest message concisely and helpfully. "
            "Keep replies under 3 sentences unless code or a list is needed.\n\n"
            f"--- Recent history ---\n{context}\n---"
        )
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=trigger_content),
        ]
        reply_text = await _ollama.chat(_default_model, messages, temperature=0.7)

        async with async_session() as db:
            ai_msg = ChannelMessageORM(
                id=str(uuid.uuid4()),
                channel_id=channel_id,
                user_id=AI_USER_ID,
                user_name=AI_USER_NAME,
                content=reply_text.strip(),
                thread_parent_id=thread_parent_id,
            )
            db.add(ai_msg)
            if thread_parent_id:
                parent = await db.get(ChannelMessageORM, thread_parent_id)
                if parent:
                    parent.reply_count += 1
            await db.commit()
            await db.refresh(ai_msg)

        manager.clear_typing(channel_id, AI_USER_ID)
        await manager.broadcast(channel_id, _msg_to_dict(ai_msg))
        await manager.broadcast(channel_id, {
            "type": "typing",
            "channel_id": channel_id,
            "typing_users": manager.get_typing_names(channel_id),
        })
    except Exception as e:
        logger.error(f"AI reply failed for channel {channel_id}: {e}")
        manager.clear_typing(channel_id, AI_USER_ID)


@router.websocket("/ws/{channel_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    channel_id: str,
    user_id: str = "dev-user",
    user_name: str = "You",
):
    await manager.connect(websocket, user_id)
    manager.subscribe(channel_id, user_id)

    # Send message history on join
    async with async_session() as db:
        result = await db.execute(
            select(ChannelMessageORM)
            .where(
                ChannelMessageORM.channel_id == channel_id,
                ChannelMessageORM.thread_parent_id.is_(None),
            )
            .order_by(ChannelMessageORM.created_at.asc())
            .limit(50)
        )
        history_rows = list(result.scalars().all())

    await websocket.send_json({
        "type": "history",
        "channel_id": channel_id,
        "messages": [_msg_to_dict(m) for m in history_rows],
    })

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("type")

            if event == "message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                async with async_session() as db:
                    msg = ChannelMessageORM(
                        id=str(uuid.uuid4()),
                        channel_id=channel_id,
                        user_id=user_id,
                        user_name=user_name,
                        content=content,
                        thread_parent_id=data.get("thread_parent_id"),
                    )
                    db.add(msg)
                    if data.get("thread_parent_id"):
                        parent = await db.get(ChannelMessageORM, data["thread_parent_id"])
                        if parent:
                            parent.reply_count += 1
                    await db.commit()
                    await db.refresh(msg)
                    # Capture history for AI context while session is open
                    hist_result = await db.execute(
                        select(ChannelMessageORM)
                        .where(ChannelMessageORM.channel_id == channel_id)
                        .order_by(ChannelMessageORM.created_at.asc())
                        .limit(15)
                    )
                    recent_history = list(hist_result.scalars().all())

                # Broadcast user message to all subscribers (sender included via subscription)
                await manager.broadcast(channel_id, _msg_to_dict(msg))

                # Clear typing
                manager.clear_typing(channel_id, user_id)
                await manager.broadcast(channel_id, {
                    "type": "typing",
                    "channel_id": channel_id,
                    "typing_users": manager.get_typing_names(channel_id),
                })

                # AI reply runs in background so it doesn't block the WS loop
                asyncio.create_task(_generate_ai_reply(
                    channel_id,
                    recent_history,
                    content,
                    thread_parent_id=data.get("thread_parent_id") or None,
                ))

            elif event == "typing_start":
                manager.set_typing(channel_id, user_id, user_name)
                await manager.broadcast(
                    channel_id,
                    {"type": "typing", "channel_id": channel_id, "typing_users": manager.get_typing_names(channel_id)},
                    exclude_user=user_id,
                )

            elif event == "typing_stop":
                manager.clear_typing(channel_id, user_id)
                await manager.broadcast(
                    channel_id,
                    {"type": "typing", "channel_id": channel_id, "typing_users": manager.get_typing_names(channel_id)},
                    exclude_user=user_id,
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast(channel_id, {
            "type": "typing",
            "channel_id": channel_id,
            "typing_users": manager.get_typing_names(channel_id),
        })
