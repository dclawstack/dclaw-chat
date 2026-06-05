import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id → WebSocket
        self._connections: Dict[str, WebSocket] = {}
        # channel_id → set of user_ids
        self._subscriptions: Dict[str, Set[str]] = {}
        # channel_id → {user_id: user_name}
        self._typing: Dict[str, Dict[str, str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self._connections[user_id] = websocket
        logger.info(f"WS connected: {user_id} (total={len(self._connections)})")

    def disconnect(self, user_id: str) -> None:
        self._connections.pop(user_id, None)
        for subs in self._subscriptions.values():
            subs.discard(user_id)
        for typing_map in self._typing.values():
            typing_map.pop(user_id, None)
        logger.info(f"WS disconnected: {user_id}")

    def subscribe(self, channel_id: str, user_id: str) -> None:
        self._subscriptions.setdefault(channel_id, set()).add(user_id)

    def unsubscribe(self, channel_id: str, user_id: str) -> None:
        self._subscriptions.get(channel_id, set()).discard(user_id)

    async def broadcast(
        self, channel_id: str, payload: dict, exclude_user: Optional[str] = None
    ) -> None:
        subscribers = self._subscriptions.get(channel_id, set()).copy()
        dead: list[str] = []
        for uid in subscribers:
            if uid == exclude_user:
                continue
            ws = self._connections.get(uid)
            if ws is None:
                continue
            try:
                await ws.send_json(payload)
            except WebSocketDisconnect:
                # Genuine client disconnect — drop them.
                dead.append(uid)
            except Exception as exc:
                # Transient/unknown send failure: only treat as dead if the
                # socket is no longer connected, otherwise just log it.
                logger.warning(f"WS broadcast send failed for {uid}: {exc!r}")
                if getattr(ws, "application_state", None) != WebSocketState.CONNECTED:
                    dead.append(uid)
        # Clean up dead connections only after iterating the copied subscriber
        # set, so we never mutate the live subscription/typing maps mid-loop.
        for uid in dead:
            self.disconnect(uid)

    async def send_to(self, user_id: str, payload: dict) -> None:
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(user_id)

    def set_typing(self, channel_id: str, user_id: str, user_name: str) -> None:
        self._typing.setdefault(channel_id, {})[user_id] = user_name

    def clear_typing(self, channel_id: str, user_id: str) -> None:
        self._typing.get(channel_id, {}).pop(user_id, None)

    def get_typing_names(self, channel_id: str) -> list[str]:
        return list(self._typing.get(channel_id, {}).values())

    @property
    def online_count(self) -> int:
        return len(self._connections)


# Module-level singleton shared across all WS connections
manager = ConnectionManager()
