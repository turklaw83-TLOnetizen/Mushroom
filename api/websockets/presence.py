"""Real-time presence tracking — who is viewing which case."""

import asyncio
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.websockets.connection_manager import manager, verify_ws_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# In-memory presence store: case_id -> {user_id: {name, role, last_heartbeat, status}}
_presence: dict[str, dict[str, dict]] = defaultdict(dict)
_presence_lock = asyncio.Lock()
HEARTBEAT_TIMEOUT = 90  # seconds before marking user as gone
IDLE_TIMEOUT = 120  # seconds before marking user as idle


@router.websocket("/ws/presence/{case_id}")
async def presence_ws(ws: WebSocket, case_id: str, token: str = Query(default="")):
    """Join a case room for presence updates."""
    user = await verify_ws_token(token)
    if not user:
        await ws.accept()
        await ws.close(code=4001, reason="Unauthorized")
        return

    user_id = user["id"]
    user_name = user["name"]
    user_role = user["role"]

    await manager.connect(ws, user_id=user_id, case_id=case_id)

    # Register presence
    async with _presence_lock:
        _presence[case_id][user_id] = {
            "name": user_name,
            "role": user_role,
            "joined_at": time.time(),
            "last_heartbeat": time.time(),
            "status": "active",
        }

    # Broadcast updated viewer list
    await _broadcast_viewers(case_id)

    try:
        while True:
            data = await asyncio.wait_for(ws.receive_json(), timeout=HEARTBEAT_TIMEOUT)
            msg_type = data.get("type", "")

            if msg_type == "heartbeat":
                async with _presence_lock:
                    if user_id in _presence.get(case_id, {}):
                        _presence[case_id][user_id]["last_heartbeat"] = time.time()
                        _presence[case_id][user_id]["status"] = "active"
                await ws.send_json({"type": "pong"})

            elif msg_type == "activity":
                # User did something — reset idle timer
                async with _presence_lock:
                    if user_id in _presence.get(case_id, {}):
                        _presence[case_id][user_id]["last_heartbeat"] = time.time()
                        _presence[case_id][user_id]["status"] = "active"
                await _broadcast_viewers(case_id)

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as e:
        logger.error("Presence WS error: user=%s case=%s err=%s", user_id, case_id, e)
    finally:
        async with _presence_lock:
            _presence.get(case_id, {}).pop(user_id, None)
            if case_id in _presence and not _presence[case_id]:
                del _presence[case_id]
        await manager.disconnect(ws)
        await _broadcast_viewers(case_id)


async def get_case_viewers(case_id: str) -> list[dict]:
    """Get current viewers for a case."""
    now = time.time()
    viewers = []
    async with _presence_lock:
        for uid, info in list(_presence.get(case_id, {}).items()):
            if now - info["last_heartbeat"] > HEARTBEAT_TIMEOUT:
                _presence[case_id].pop(uid, None)
                continue
            status = "idle" if now - info["last_heartbeat"] > IDLE_TIMEOUT else "active"
            viewers.append({
                "user_id": uid,
                "name": info["name"],
                "role": info["role"],
                "status": status,
                "joined_at": info["joined_at"],
            })
    return viewers


async def _broadcast_viewers(case_id: str):
    """Send updated viewer list to all case viewers."""
    viewers = await get_case_viewers(case_id)
    await manager.broadcast_to_case(case_id, {
        "type": "viewers_update",
        "case_id": case_id,
        "viewers": viewers,
        "timestamp": time.time(),
    })


# Legacy export for main.py websocket route registration
websocket_presence = presence_ws
