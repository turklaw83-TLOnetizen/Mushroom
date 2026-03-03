"""WebSocket endpoint for live notifications."""

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.websockets.connection_manager import manager, verify_ws_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket, token: str = Query(default="")):
    """Live notification stream. Connect with ?token=<jwt>."""
    user = await verify_ws_token(token)
    if not user:
        await ws.accept()
        await ws.close(code=4001, reason="Unauthorized")
        return

    user_id = user["id"]

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


# Legacy export for main.py websocket route registration
websocket_notifications = notifications_ws
