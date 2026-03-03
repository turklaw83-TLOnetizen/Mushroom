"""Notifications REST router — serves the frontend useNotifications hook."""

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from core.notification_service import get_notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Map notification type -> severity for the frontend
_TYPE_SEVERITY = {
    "analysis_complete": "info",
    "file_uploaded": "info",
    "case_assigned": "info",
    "analysis_failed": "error",
    "deadline_approaching": "warning",
    "phase_changed": "success",
}


def _enrich(notif: dict) -> dict:
    """Map backend notification dict to frontend Notification shape.

    Renames ``body`` -> ``message`` and adds ``severity`` based on type.
    """
    return {
        "id": notif["id"],
        "type": notif["type"],
        "title": notif["title"],
        "message": notif.get("body", ""),
        "severity": _TYPE_SEVERITY.get(notif.get("type", ""), "info"),
        "read": notif.get("read", False),
        "created_at": notif.get("created_at"),
        "case_id": notif.get("case_id"),
        "metadata": notif.get("metadata", {}),
    }


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """Return notifications list and unread count for the authenticated user."""
    svc = get_notification_service()
    user_id = user["id"]
    raw = svc.get_notifications(user_id, unread_only=unread_only, limit=limit, offset=offset)
    return {
        "notifications": [_enrich(n) for n in raw],
        "unread_count": svc.get_unread_count(user_id),
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Mark a single notification as read."""
    svc = get_notification_service()
    if not svc.mark_read(user["id"], notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


@router.post("/mark-all-read")
def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read for the authenticated user."""
    svc = get_notification_service()
    count = svc.mark_all_read(user["id"])
    return {"status": "ok", "count": count}


@router.delete("/{notification_id}")
def delete_notification(notification_id: str, user: dict = Depends(get_current_user)):
    """Delete/dismiss a notification."""
    svc = get_notification_service()
    if not svc.delete_notification(user["id"], notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}
