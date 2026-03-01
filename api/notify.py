# ---- Notification Triggers -----------------------------------------------
# Helpers that create persistent notifications AND push via WebSocket.
#
# Call these from API endpoint handlers when key events occur.

import asyncio
import logging
from typing import Optional

from core.notification_service import get_notification_service

logger = logging.getLogger(__name__)


def _ws_broadcast_fire_and_forget(user_id: str, notification: dict):
    """Best-effort WebSocket push — never blocks or raises."""
    try:
        from api.websockets.notifications_ws import send_notification
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_notification(user_id, notification))
        else:
            asyncio.run(send_notification(user_id, notification))
    except Exception as e:
        logger.debug("WebSocket notification failed (non-fatal): %s", e)


def notify_file_uploaded(
    user_id: str,
    case_id: str,
    filename: str,
    file_count: int = 1,
):
    """Trigger notification when file(s) are uploaded to a case."""
    svc = get_notification_service()
    title = f"{file_count} file(s) uploaded" if file_count > 1 else "File uploaded"
    body = f"{filename} uploaded to case"
    notif = svc.create_notification(
        user_id=user_id,
        notif_type="file_uploaded",
        title=title,
        body=body,
        case_id=case_id,
        metadata={"filename": filename, "count": file_count},
    )
    _ws_broadcast_fire_and_forget(user_id, notif)
    return notif


def notify_analysis_started(
    user_id: str,
    case_id: str,
    prep_id: str,
    modules: Optional[list] = None,
):
    """Trigger notification when analysis begins."""
    svc = get_notification_service()
    body = f"Analysis started for preparation {prep_id}"
    if modules:
        body += f" ({len(modules)} modules)"
    notif = svc.create_notification(
        user_id=user_id,
        notif_type="analysis_complete",  # reuse type; frontend maps to info
        title="Analysis started",
        body=body,
        case_id=case_id,
        metadata={"prep_id": prep_id},
    )
    _ws_broadcast_fire_and_forget(user_id, notif)
    return notif


def notify_phase_changed(
    user_id: str,
    case_id: str,
    old_phase: str,
    new_phase: str,
):
    """Trigger notification when a case phase changes."""
    svc = get_notification_service()
    notif = svc.create_notification(
        user_id=user_id,
        notif_type="phase_changed",
        title="Case phase updated",
        body=f"Phase changed from {old_phase} to {new_phase}",
        case_id=case_id,
        metadata={"old_phase": old_phase, "new_phase": new_phase},
    )
    _ws_broadcast_fire_and_forget(user_id, notif)
    return notif
