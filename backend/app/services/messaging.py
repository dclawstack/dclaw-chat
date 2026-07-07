import asyncio
import json
import logging
import os
import uuid
from typing import Dict, Set, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

try:  # redis is optional at runtime (mirrors app.core.cache)
    from redis import asyncio as aioredis
except Exception:  # pragma: no cover - redis not installed
    aioredis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Redis pub/sub channel carrying cross-replica WS events (#23). Every replica
# publishes its broadcasts here and re-delivers events from other replicas to
# its own local sockets. With REDIS_URL unset this layer is a no-op and the
# manager behaves exactly as a single process.
_RELAY_CHANNEL = "dclaw:ws:events"


class ConnectionManager:
    def __init__(self):
        # user_id → WebSocket
        self._connections: Dict[str, WebSocket] = {}
        # channel_id → set of user_ids
        self._subscriptions: Dict[str, Set[str]] = {}
        # channel_id → {user_id: user_name}
        self._typing: Dict[str, Dict[str, str]] = {}
        # Cross-replica relay state. instance_id filters out our own events
        # when they echo back from Redis.
        self._instance_id = uuid.uuid4().hex
        self._redis = None
        self._redis_failed = False
        self._pubsub = None
        self._relay_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Cross-replica relay (#23)
    # ------------------------------------------------------------------

    def _get_redis(self):
        """Lazily build the relay Redis client; None when unconfigured/down."""
        if self._redis is not None:
            return self._redis
        url = os.environ.get("REDIS_URL")
        if self._redis_failed or aioredis is None or not url:
            return None
        try:
            self._redis = aioredis.from_url(url, decode_responses=True)
        except Exception:
            self._redis_failed = True
            return None
        return self._redis

    async def start_relay(self) -> None:
        """Subscribe to the relay channel; no-op without REDIS_URL."""
        if self._relay_task is not None:
            return
        client = self._get_redis()
        if client is None:
            return
        try:
            self._pubsub = client.pubsub(ignore_subscribe_messages=True)
            await self._pubsub.subscribe(_RELAY_CHANNEL)
        except Exception as exc:
            logger.warning(f"WS relay unavailable, staying single-process: {exc!r}")
            self._pubsub = None
            self._redis_failed = True
            return
        self._relay_task = asyncio.create_task(self._relay_loop())
        logger.info(f"WS relay subscribed (instance={self._instance_id})")

    async def stop_relay(self) -> None:
        if self._relay_task is not None:
            self._relay_task.cancel()
            try:
                await self._relay_task
            except (asyncio.CancelledError, Exception):
                pass
            self._relay_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.close()
            except Exception:
                pass
            self._pubsub = None

    async def _relay_loop(self) -> None:
        try:
            async for msg in self._pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    event = json.loads(msg["data"])
                except (ValueError, TypeError, KeyError):
                    continue
                await self._handle_relay_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"WS relay loop stopped: {exc!r}")

    async def _handle_relay_event(self, event: dict) -> None:
        """Deliver an event published by another replica to local sockets."""
        if event.get("origin") == self._instance_id:
            return
        kind = event.get("kind")
        if kind == "broadcast":
            await self._deliver_local(
                event.get("channel_id", ""),
                event.get("payload", {}),
                exclude_user=event.get("exclude_user"),
            )
        elif kind == "send_to":
            await self._deliver_to_user(event.get("user_id", ""), event.get("payload", {}))

    async def _publish(self, event: dict) -> None:
        client = self._get_redis()
        if client is None:
            return
        event["origin"] = self._instance_id
        try:
            await client.publish(_RELAY_CHANNEL, json.dumps(event))
        except Exception as exc:
            # Redis down mid-flight: local delivery already happened, keep going.
            logger.warning(f"WS relay publish failed: {exc!r}")

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

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
        await self._deliver_local(channel_id, payload, exclude_user)
        await self._publish({
            "kind": "broadcast",
            "channel_id": channel_id,
            "payload": payload,
            "exclude_user": exclude_user,
        })

    async def _deliver_local(
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
        await self._deliver_to_user(user_id, payload)
        await self._publish({
            "kind": "send_to",
            "user_id": user_id,
            "payload": payload,
        })

    async def _deliver_to_user(self, user_id: str, payload: dict) -> None:
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
