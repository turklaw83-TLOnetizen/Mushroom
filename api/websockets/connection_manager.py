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
        # Explicitly close the WebSocket to release resources
        try:
            await ws.close()
        except Exception:
            pass  # already closed or broken pipe
        logger.info("WS disconnect: user=%s case=%s", user_id, case_id)

    async def sweep_idle(self, max_idle_seconds: int = 3600):
        """Close connections idle for longer than max_idle_seconds."""
        now = time.time()
        stale: list[WebSocket] = []
        async with self._lock:
            for ws, meta in list(self._metadata.items()):
                if now - meta.get("connected_at", now) > max_idle_seconds:
                    stale.append(ws)
        for ws in stale:
            logger.info("Sweeping idle WebSocket (age > %ds)", max_idle_seconds)
            await self.disconnect(ws)

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


# ---- Shared WebSocket Authentication ------------------------------------

async def verify_ws_token(token: str) -> Optional[dict]:
    """
    Verify a WebSocket token using the same auth chain as HTTP endpoints.

    Returns a user dict {id, role, name} or None if verification fails.
    Tries Clerk JWKS first, then falls back to legacy HS256 JWT.
    Never accepts unverified tokens.
    """
    if not token:
        return None

    try:
        from api.auth import _verify_clerk_session, _verify_jwt, _get_clerk_secret_key

        # Try Clerk first (RS256 via JWKS)
        if _get_clerk_secret_key():
            claims = await _verify_clerk_session(token)
            if claims:
                return {
                    "id": claims.get("sub", ""),
                    "role": claims.get("role", claims.get("public_metadata", {}).get("role", "attorney")),
                    "name": claims.get("name", "Unknown"),
                }

        # Fallback: legacy HS256 JWT with signature verification
        claims = _verify_jwt(token)
        if claims:
            return {
                "id": claims.get("sub", ""),
                "role": claims.get("role", "attorney"),
                "name": claims.get("name", "Unknown"),
            }
    except Exception as e:
        logger.debug("WebSocket token verification failed: %s", e)

    return None
