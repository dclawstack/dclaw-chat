import uuid
import json
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from pydantic import BaseModel, field_validator

from app.core.database import get_db, async_session
from app.core.deps import get_current_user, CurrentUser
from app.models.channel import ChannelORM, ChannelMessageORM
from app.services.messaging import manager
from app.services.ollama_service import OllamaService, OLLAMA_MODELS
from app.services.files import file_service, extract_urls
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
    topic: Optional[str]
    attachments: Optional[list] = None
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator("attachments", mode="before")
    @classmethod
    def parse_attachments(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return v


class UnfurlRequest(BaseModel):
    url: str


class ChannelTopicOut(BaseModel):
    topic: str
    count: int


class CreateChannelRequest(BaseModel):
    name: str
    type: str = "public"


class SendMessageRequest(BaseModel):
    content: str
    thread_parent_id: Optional[str] = None
    attachments: Optional[list] = None


# ── Topic classification ──────────────────────────────────────────────────────

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "frontend": ["react", "css", "html", "ui", "component", "tsx", "jsx", "tailwind", "next", "style", "button", "layout", "page"],
    "backend": ["api", "server", "endpoint", "database", "sql", "orm", "fastapi", "flask", "python", "route", "schema", "query"],
    "devops": ["docker", "kubernetes", "k8s", "ci", "cd", "deploy", "github", "pipeline", "helm", "nginx", "aws", "gcp", "build"],
    "design": ["design", "ux", "figma", "wireframe", "prototype", "color", "font", "typography", "mockup", "spacing", "icon"],
    "bug": ["bug", "fix", "error", "crash", "issue", "broken", "fail", "wrong", "exception", "traceback", "null", "undefined", "not working"],
    "feature": ["feature", "add", "implement", "build", "create", "new", "enhance", "improve", "upgrade", "support"],
    "question": ["?", "how", "why", "what", "where", "when", "who", "anyone", "help", "can someone", "does anyone"],
}

def _classify_topic(content: str) -> str:
    lower = content.lower()
    scores = {
        topic: sum(1 for kw in kws if kw in lower)
        for topic, kws in _TOPIC_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


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
        topic=_classify_topic(req.content),
        attachments=json.dumps(req.attachments) if req.attachments else None,
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


@router.post("/channels/{channel_id}/upload")
async def upload_file(
    channel_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    return await file_service.save_upload(file)


@router.get("/files/{file_id}/{filename}")
async def serve_file(file_id: str, filename: str):
    path = file_service.file_path(file_id, filename)
    if not path:
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.post("/unfurl")
async def unfurl_url(
    req: UnfurlRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return await file_service.unfurl(req.url)


@router.get("/channels/{channel_id}/topics", response_model=List[ChannelTopicOut])
async def get_channel_topics(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChannelMessageORM.topic, sa_func.count(ChannelMessageORM.id).label("count"))
        .where(
            ChannelMessageORM.channel_id == channel_id,
            ChannelMessageORM.topic.isnot(None),
            ChannelMessageORM.thread_parent_id.is_(None),
        )
        .group_by(ChannelMessageORM.topic)
        .order_by(sa_func.count(ChannelMessageORM.id).desc())
    )
    return [{"topic": row.topic, "count": row.count} for row in result.all()]


@router.get("/channels/{channel_id}/topics/{topic}/summary")
async def get_topic_summary(
    channel_id: str,
    topic: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChannelMessageORM)
        .where(
            ChannelMessageORM.channel_id == channel_id,
            ChannelMessageORM.topic == topic,
        )
        .order_by(ChannelMessageORM.created_at.asc())
        .limit(20)
    )
    msgs = list(result.scalars().all())
    if not msgs:
        return {"topic": topic, "message_count": 0, "summary": "No messages found for this topic."}

    transcript = "\n".join(f"{m.user_name}: {m.content[:200]}" for m in msgs)
    prompt_messages = [
        ChatMessage(role="system", content=(
            f"Summarize the following team conversation about '{topic}' in 3-5 concise bullet points. "
            "Focus on decisions made, problems raised, and next steps. "
            "Start each bullet with '•'."
        )),
        ChatMessage(role="user", content=transcript),
    ]
    summary = await _ollama.chat(_default_model, prompt_messages, temperature=0.3)
    return {"topic": topic, "message_count": len(msgs), "summary": summary.strip()}


# ── Helpers ───────────────────────────────────────────────────────────────────

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
        "topic": m.topic,
        "attachments": json.loads(m.attachments) if m.attachments else [],
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
    attachments: Optional[list] = None,
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

        file_context = ""
        for att in (attachments or []):
            if att.get("type") in ("file", "image") and att.get("id") and att.get("name"):
                text = file_service.extract_text(att["id"], att["name"], att.get("mime_type", ""))
                if text:
                    file_context += f"\n\n--- Attached file: {att['name']} ---\n{text}\n---"

        scope = "this thread" if thread_parent_id else "the team channel"
        system_prompt = (
            f"You are DClaw Copilot, an AI assistant embedded in {scope}. "
            "Answer the latest message concisely and helpfully. "
            "Keep replies under 3 sentences unless code or a list is needed.\n\n"
            f"--- Recent history ---\n{context}\n---"
            + file_context
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
                topic=_classify_topic(reply_text),
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


# ── WebSocket ─────────────────────────────────────────────────────────────────

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

                raw_attachments = data.get("attachments") or []
                async with async_session() as db:
                    msg = ChannelMessageORM(
                        id=str(uuid.uuid4()),
                        channel_id=channel_id,
                        user_id=user_id,
                        user_name=user_name,
                        content=content,
                        thread_parent_id=data.get("thread_parent_id"),
                        topic=_classify_topic(content),
                        attachments=json.dumps(raw_attachments) if raw_attachments else None,
                    )
                    db.add(msg)
                    if data.get("thread_parent_id"):
                        parent = await db.get(ChannelMessageORM, data["thread_parent_id"])
                        if parent:
                            parent.reply_count += 1
                    await db.commit()
                    await db.refresh(msg)
                    hist_result = await db.execute(
                        select(ChannelMessageORM)
                        .where(ChannelMessageORM.channel_id == channel_id)
                        .order_by(ChannelMessageORM.created_at.asc())
                        .limit(15)
                    )
                    recent_history = list(hist_result.scalars().all())

                await manager.broadcast(channel_id, _msg_to_dict(msg))

                manager.clear_typing(channel_id, user_id)
                await manager.broadcast(channel_id, {
                    "type": "typing",
                    "channel_id": channel_id,
                    "typing_users": manager.get_typing_names(channel_id),
                })

                asyncio.create_task(_generate_ai_reply(
                    channel_id,
                    recent_history,
                    content,
                    thread_parent_id=data.get("thread_parent_id") or None,
                    attachments=raw_attachments or None,
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
