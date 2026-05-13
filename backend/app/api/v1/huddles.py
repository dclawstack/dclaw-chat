import json
import logging
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.repositories.huddle_repo import HuddleRepository
from app.schemas.huddle import (
    HuddleRoomCreate,
    HuddleRoomOut,
    HuddleParticipantOut,
    HuddleJoinRequest,
    HuddleSpeakingRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class HuddlePresenceManager:
    """In-memory WebSocket manager for real-time presence updates.

    Stores live connections only — room/participant state lives in DB.
    """

    def __init__(self):
        # room_id → {user_id: WebSocket}
        self._rooms: Dict[str, Dict[str, WebSocket]] = {}

    def _get_room(self, room_id: str) -> Dict[str, WebSocket]:
        return self._rooms.setdefault(room_id, {})

    def participant_count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, {}))

    async def connect(self, room_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._get_room(room_id)[user_id] = ws
        await self._broadcast(
            room_id,
            {"type": "participant-joined", "user_id": user_id},
            exclude=user_id,
        )

    async def disconnect(self, room_id: str, user_id: str) -> None:
        room = self._rooms.get(room_id, {})
        room.pop(user_id, None)
        if not room:
            self._rooms.pop(room_id, None)
        else:
            await self._broadcast(
                room_id, {"type": "participant-left", "user_id": user_id}
            )

    async def broadcast_presence(self, room_id: str, payload: dict) -> None:
        await self._broadcast(room_id, payload)

    async def _broadcast(
        self, room_id: str, message: dict, exclude: Optional[str] = None
    ) -> None:
        room = self._rooms.get(room_id, {})
        payload = json.dumps(message)
        dead: Set[str] = set()
        for uid, ws in room.items():
            if uid == exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(uid)
        for uid in dead:
            room.pop(uid, None)


_presence = HuddlePresenceManager()


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("", response_model=HuddleRoomOut, status_code=201)
async def create_huddle(
    req: HuddleRoomCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    return await repo.create_room(name=req.name, created_by=user.user_id)


@router.get("", response_model=List[HuddleRoomOut])
async def list_huddles(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    return await repo.list_active()


@router.get("/{room_id}", response_model=HuddleRoomOut)
async def get_huddle(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    room = await repo.get_room(room_id)
    if not room:
        raise HTTPException(404, "Huddle room not found")
    return room


@router.post("/{room_id}/join", response_model=HuddleParticipantOut)
async def join_huddle(
    room_id: str,
    req: HuddleJoinRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    room = await repo.get_room(room_id)
    if not room or room.status != "active":
        raise HTTPException(404, "Huddle room not found or closed")
    participant = await repo.join_room(
        room_id=room_id,
        user_id=user.user_id,
        display_name=req.display_name,
    )
    await _presence.broadcast_presence(
        room_id,
        {
            "type": "participant-joined",
            "user_id": user.user_id,
            "display_name": req.display_name,
        },
    )
    return participant


@router.post("/{room_id}/leave", status_code=204)
async def leave_huddle(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    await repo.leave_room(room_id=room_id, user_id=user.user_id)
    await _presence.broadcast_presence(
        room_id, {"type": "participant-left", "user_id": user.user_id}
    )


@router.post("/{room_id}/speaking", response_model=HuddleParticipantOut)
async def update_speaking(
    room_id: str,
    req: HuddleSpeakingRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    participant = await repo.update_speaking(
        room_id=room_id,
        user_id=user.user_id,
        is_speaking=req.is_speaking,
        is_muted=req.is_muted,
    )
    if not participant:
        raise HTTPException(404, "Not a participant in this huddle")
    await _presence.broadcast_presence(
        room_id,
        {
            "type": "speaking-update",
            "user_id": user.user_id,
            "is_speaking": req.is_speaking,
            "is_muted": req.is_muted,
        },
    )
    return participant


@router.post("/{room_id}/close", response_model=HuddleRoomOut)
async def close_huddle(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    room = await repo.get_room(room_id)
    if not room:
        raise HTTPException(404, "Huddle room not found")
    if room.created_by and room.created_by != user.user_id:
        raise HTTPException(403, "Only the creator can close this huddle")
    room = await repo.close_room(room)
    await _presence.broadcast_presence(room_id, {"type": "huddle-closed"})
    return room


@router.delete("/{room_id}", status_code=204)
async def delete_huddle(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = HuddleRepository(db)
    room = await repo.get_room(room_id)
    if not room:
        raise HTTPException(404, "Huddle room not found")
    if room.created_by and room.created_by != user.user_id:
        raise HTTPException(403, "Only the creator can delete this huddle")
    await repo.delete_room(room)


# ── WebSocket presence endpoint ───────────────────────────────────────────────

@router.websocket("/{room_id}/ws")
async def huddle_presence_ws(
    room_id: str,
    ws: WebSocket,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    """Real-time presence channel for a huddle room.

    Clients receive JSON events:
      participant-joined  { type, user_id, display_name }
      participant-left    { type, user_id }
      speaking-update     { type, user_id, is_speaking, is_muted }
      huddle-closed       { type }

    Clients can send:
      speaking-update     { type, is_speaking, is_muted? }
    """
    repo = HuddleRepository(db)
    room = await repo.get_room(room_id)
    if not room or room.status != "active":
        await ws.close(code=4004, reason="Huddle not found or closed")
        return

    await _presence.connect(room_id, user_id, ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "speaking-update":
                is_speaking = bool(msg.get("is_speaking", False))
                is_muted = msg.get("is_muted")
                await repo.update_speaking(room_id, user_id, is_speaking, is_muted)
                await _presence.broadcast_presence(
                    room_id,
                    {
                        "type": "speaking-update",
                        "user_id": user_id,
                        "is_speaking": is_speaking,
                        "is_muted": is_muted,
                    },
                )
    except WebSocketDisconnect:
        pass
    finally:
        await _presence.disconnect(room_id, user_id)
        await repo.leave_room(room_id, user_id)
