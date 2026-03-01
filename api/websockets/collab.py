"""Collaborative editing — field-level locking and conflict detection."""

import asyncio
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.websockets.connection_manager import manager, verify_ws_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# Field locks: (case_id, field_name) -> {user_id, locked_at, version}
_field_locks: dict[tuple[str, str], dict] = {}
# Field versions: (case_id, field_name) -> version counter
_field_versions: dict[tuple[str, str], int] = defaultdict(int)
LOCK_TIMEOUT = 300  # 5 minutes


@router.websocket("/ws/collab/{case_id}")
async def collab_ws(ws: WebSocket, case_id: str, token: str = Query(default="")):
    """Collaborative editing WebSocket for a case."""
    user = await verify_ws_token(token)
    if not user:
        await ws.accept()
        await ws.close(code=4001, reason="Unauthorized")
        return

    user_id = user["id"]
    user_name = user["name"]

    await manager.connect(ws, user_id=user_id, case_id=case_id)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "lock_field":
                field = data.get("field", "")
                success = _try_lock(case_id, field, user_id)
                await ws.send_json({"type": "lock_result", "field": field, "success": success})
                if success:
                    await manager.broadcast_to_case(case_id, {
                        "type": "field_locked",
                        "field": field,
                        "locked_by": user_id,
                        "locked_by_name": user_name,
                        "timestamp": time.time(),
                    }, exclude_user=user_id)

            elif msg_type == "unlock_field":
                field = data.get("field", "")
                _unlock(case_id, field, user_id)
                await manager.broadcast_to_case(case_id, {
                    "type": "field_unlocked",
                    "field": field,
                    "timestamp": time.time(),
                }, exclude_user=user_id)

            elif msg_type == "field_update":
                field = data.get("field", "")
                value = data.get("value", "")
                key = (case_id, field)
                _field_versions[key] += 1
                version = _field_versions[key]
                # Release lock after update
                _unlock(case_id, field, user_id)
                await manager.broadcast_to_case(case_id, {
                    "type": "field_updated",
                    "field": field,
                    "value": value,
                    "updated_by": user_id,
                    "updated_by_name": user_name,
                    "version": version,
                    "timestamp": time.time(),
                }, exclude_user=user_id)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        # Release all locks held by this user for this case
        _release_user_locks(case_id, user_id)
        await manager.disconnect(ws)


def _try_lock(case_id: str, field: str, user_id: str) -> bool:
    key = (case_id, field)
    now = time.time()
    existing = _field_locks.get(key)
    if existing:
        if existing["user_id"] == user_id:
            existing["locked_at"] = now
            return True
        if now - existing["locked_at"] > LOCK_TIMEOUT:
            pass  # Expired, allow override
        else:
            return False
    _field_locks[key] = {"user_id": user_id, "locked_at": now}
    return True


def _unlock(case_id: str, field: str, user_id: str):
    key = (case_id, field)
    lock = _field_locks.get(key)
    if lock and lock["user_id"] == user_id:
        del _field_locks[key]


def _release_user_locks(case_id: str, user_id: str):
    to_remove = [k for k, v in _field_locks.items() if k[0] == case_id and v["user_id"] == user_id]
    for k in to_remove:
        del _field_locks[k]


# Legacy export for main.py websocket route registration
websocket_collab = collab_ws
