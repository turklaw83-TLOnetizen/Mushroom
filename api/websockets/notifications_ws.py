"""WebSocket endpoint for live notifications."""

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.websockets.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket, token: str = Query(default="")):
    """Live notification stream. Connect with ?token=<jwt>."""
    # Lightweight auth: extract user_id from token
    user_id = _extract_user_id(token)
    if not user_id:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(ws, user_id=user_id)
    try:
        # Send initial connection confirmation
        await ws.send_json({"type": "connected", "user_id": user_id, "timestamp": time.time()})

        while True:
            # Wait for client messages (heartbeat/ack)
            data = await asyncio.wait_for(ws.receive_json(), timeout=60)
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws.send_json({"type": "pong", "timestamp": time.time()})
            elif msg_type == "ack":
                # Client acknowledged a notification
                pass
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as e:
        logger.error("Notification WS error for user %s: %s", user_id, e)
    finally:
        await manager.disconnect(ws)


async def send_notification(user_id: str, notification: dict):
    """Send a notification to a specific user via WebSocket."""
    await manager.send_personal(user_id, {
        "type": "notification",
        "data": notification,
        "timestamp": time.time(),
    })


async def broadcast_notification(notification: dict):
    """Send a notification to all connected users."""
    await manager.broadcast_all({
        "type": "notification",
        "data": notification,
        "timestamp": time.time(),
    })


def _extract_user_id(token: str) -> str:
    """Extract user_id from JWT token. Returns empty string on failure."""
    if not token:
        return "anonymous"  # Allow anonymous in dev
    try:
        import jwt as pyjwt
        import os
        secret = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
        claims = pyjwt.decode(token, secret, algorithms=["HS256"])
        return claims.get("sub", "")
    except Exception:
        # Try decoding without verification (dev mode)
        try:
            import jwt as pyjwt
            claims = pyjwt.decode(token, options={"verify_signature": False})
            return claims.get("sub", "anonymous")
        except Exception:
            return "anonymous"
