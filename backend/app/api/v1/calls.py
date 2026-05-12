import json
import logging
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.repositories.call_repo import CallRoomRepository
from app.schemas.call import CallRoomCreate, CallRoomOut

router = APIRouter()
logger = logging.getLogger(__name__)


class SignalingManager:
    """In-memory WebSocket manager for WebRTC signaling.

    Tracks live connections only — room metadata lives in the DB.
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
        room = self._get_room(room_id)
        room[user_id] = ws
        await self._broadcast(room_id, {"type": "peer-joined", "user_id": user_id}, exclude=user_id)
        peers = [uid for uid in room if uid != user_id]
        await ws.send_text(json.dumps({"type": "peers", "peers": peers}))

    async def disconnect(self, room_id: str, user_id: str) -> None:
        room = self._rooms.get(room_id, {})
        room.pop(user_id, None)
        if not room:
            self._rooms.pop(room_id, None)
        else:
            await self._broadcast(room_id, {"type": "peer-left", "user_id": user_id})

    async def relay(self, room_id: str, sender_id: str, message: dict) -> None:
        """Forward a signaling message to a specific peer or broadcast."""
        target_id: Optional[str] = message.get("target")
        room = self._rooms.get(room_id, {})
        message["from"] = sender_id
        payload = json.dumps(message)
        if target_id:
            ws = room.get(target_id)
            if ws:
                await ws.send_text(payload)
        else:
            await self._broadcast(room_id, message, exclude=sender_id)

    async def _broadcast(self, room_id: str, message: dict, exclude: Optional[str] = None) -> None:
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


_signaling = SignalingManager()


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("", response_model=CallRoomOut, status_code=201)
async def create_call_room(
    req: CallRoomCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = CallRoomRepository(db)
    room = await repo.create(
        title=req.title,
        host_id=user.user_id,
        channel_id=req.channel_id,
        max_participants=min(req.max_participants, 50),
        recording_enabled=req.recording_enabled,
    )
    return room


@router.get("", response_model=List[CallRoomOut])
async def list_call_rooms(
    channel_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = CallRoomRepository(db)
    return await repo.list_active(channel_id=channel_id)


@router.get("/{room_id}", response_model=CallRoomOut)
async def get_call_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = CallRoomRepository(db)
    room = await repo.get_by_id(room_id)
    if not room:
        raise HTTPException(404, "Call room not found")
    return room


@router.post("/{room_id}/end", response_model=CallRoomOut)
async def end_call_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = CallRoomRepository(db)
    room = await repo.get_by_id(room_id)
    if not room:
        raise HTTPException(404, "Call room not found")
    if room.host_id and room.host_id != user.user_id:
        raise HTTPException(403, "Only the host can end the call")
    room = await repo.update_status(room, "ended")
    # notify all connected peers
    await _signaling._broadcast(room_id, {"type": "call-ended"})
    return room


@router.delete("/{room_id}", status_code=204)
async def delete_call_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = CallRoomRepository(db)
    room = await repo.get_by_id(room_id)
    if not room:
        raise HTTPException(404, "Call room not found")
    if room.host_id and room.host_id != user.user_id:
        raise HTTPException(403, "Only the host can delete the call room")
    await repo.delete(room)


# ── WebSocket signaling endpoint ──────────────────────────────────────────────

@router.websocket("/{room_id}/ws")
async def call_signaling(
    room_id: str,
    ws: WebSocket,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    """WebRTC signaling channel.

    Clients exchange JSON messages:
      offer     { type, sdp, target }       → forwarded to target peer
      answer    { type, sdp, target }       → forwarded to target peer
      ice       { type, candidate, target } → forwarded to target peer
      Any other type is broadcast to all peers in the room.
    """
    repo = CallRoomRepository(db)
    room = await repo.get_by_id(room_id)
    if not room or room.status == "ended":
        await ws.close(code=4004, reason="Room not found or ended")
        return

    if _signaling.participant_count(room_id) >= room.max_participants:
        await ws.close(code=4029, reason="Room is full")
        return

    if room.status == "waiting":
        await repo.update_status(room, "active")

    await _signaling.connect(room_id, user_id, ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") in ("offer", "answer", "ice"):
                await _signaling.relay(room_id, user_id, msg)
            else:
                await _signaling._broadcast(room_id, {**msg, "from": user_id}, exclude=user_id)
    except WebSocketDisconnect:
        pass
    finally:
        await _signaling.disconnect(room_id, user_id)
