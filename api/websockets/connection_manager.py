"""WebSocket Connection Manager — tracks connections by user and case."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with user/case tracking."""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self._user_connections: dict[str, set[WebSocket]] = defaultdict(set)
        # case_id -> set of (user_id, WebSocket)
        self._case_connections: dict[str, set[tuple[str, WebSocket]]] = defaultdict(set)
        # WebSocket -> metadata
        self._metadata: dict[WebSocket, dict] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, ws: WebSocket, user_id: str, case_id: Optional[str] = None, **meta
    ):
        await ws.accept()
        async with self._lock:
            self._user_connections[user_id].add(ws)
            if case_id:
                self._case_connections[case_id].add((user_id, ws))
            self._metadata[ws] = {
                "user_id": user_id,
                "case_id": case_id,
                "connected_at": time.time(),
                **meta,
            }
        logger.info("WS connect: user=%s case=%s total=%d", user_id, case_id, self.total_connections)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            meta = self._metadata.pop(ws, {})
            user_id = meta.get("user_id", "")
            case_id = meta.get("case_id")
            if user_id and ws in self._user_connections.get(user_id, set()):
                self._user_connections[user_id].discard(ws)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]
            if case_id:
                self._case_connections[case_id].discard((user_id, ws))
                if not self._case_connections[case_id]:
                    del self._case_connections[case_id]
        logger.info("WS disconnect: user=%s case=%s", user_id, case_id)

    async def send_personal(self, user_id: str, message: dict):
        conns = list(self._user_connections.get(user_id, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(ws)

    async def broadcast_to_case(self, case_id: str, message: dict, exclude_user: Optional[str] = None):
        conns = list(self._case_connections.get(case_id, []))
        for uid, ws in conns:
            if uid == exclude_user:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(ws)

    async def broadcast_all(self, message: dict):
        for user_id in list(self._user_connections):
            await self.send_personal(user_id, message)

    def get_case_users(self, case_id: str) -> list[str]:
        return list({uid for uid, _ in self._case_connections.get(case_id, [])})

    @property
    def total_connections(self) -> int:
        return len(self._metadata)

    @property
    def active_users(self) -> int:
        return len(self._user_connections)


# Global singleton
manager = ConnectionManager()
