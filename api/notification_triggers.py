"""Notification triggers — hook into app events to create notifications."""

import logging
from typing import Optional

from core.notification_service import get_notification_service

logger = logging.getLogger(__name__)


def notify_analysis_complete(case_id: str, user_id: str, prep_name: str = ""):
    svc = get_notification_service()
    svc.create_notification(
        user_id=user_id,
        notif_type="analysis_complete",
        title="Analysis Complete",
        body=f"Analysis for '{prep_name}' has finished.",
        case_id=case_id,
    )


def notify_analysis_failed(case_id: str, user_id: str, error: str = ""):
    svc = get_notification_service()
    svc.create_notification(
        user_id=user_id,
        notif_type="analysis_failed",
        title="Analysis Failed",
        body=f"Analysis encountered an error: {error[:200]}",
        case_id=case_id,
    )


def notify_deadline_approaching(case_id: str, user_ids: list[str], deadline_title: str, days_until: int):
    svc = get_notification_service()
    for uid in user_ids:
        svc.create_notification(
            user_id=uid,
            notif_type="deadline_approaching",
            title=f"Deadline in {days_until} day{'s' if days_until != 1 else ''}",
            body=f"'{deadline_title}' is due soon.",
            case_id=case_id,
            metadata={"days_until": days_until},
        )


def notify_file_uploaded(case_id: str, uploader_id: str, team_ids: list[str], filename: str):
    svc = get_notification_service()
    for uid in team_ids:
        if uid == uploader_id:
            continue
        svc.create_notification(
            user_id=uid,
            notif_type="file_uploaded",
            title="New File Uploaded",
            body=f"'{filename}' was uploaded.",
            case_id=case_id,
        )


def notify_case_assigned(case_id: str, assignee_id: str, case_name: str, assigner: str = ""):
    svc = get_notification_service()
    svc.create_notification(
        user_id=assignee_id,
        notif_type="case_assigned",
        title="Case Assigned",
        body=f"You were assigned to '{case_name}'" + (f" by {assigner}" if assigner else ""),
        case_id=case_id,
    )


def notify_phase_changed(case_id: str, team_ids: list[str], case_name: str, new_phase: str):
    svc = get_notification_service()
    for uid in team_ids:
        svc.create_notification(
            user_id=uid,
            notif_type="phase_changed",
            title="Case Phase Updated",
            body=f"'{case_name}' moved to {new_phase}.",
            case_id=case_id,
        )
