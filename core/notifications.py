# ---- Notification Center --------------------------------------------------
# Aggregates notifications from overdue tasks, approaching deadlines,
# low retainer balances, and OCR errors.

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def get_notifications(
    case_mgr,
    data_dir: str = "",
    user_id: str = "",
    case_ids: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Aggregate notifications from multiple sources.

    Returns list of notification dicts sorted by severity, newest first:
        [{type, title, detail, case_id, case_name, severity, timestamp}, ...]
    """
    _dir = data_dir or _DATA_DIR
    notifications = []

    _target_cases = case_ids
    if _target_cases is None:
        try:
            _target_cases = [c["id"] for c in case_mgr.list_cases(include_archived=False)]
        except Exception:
            _target_cases = []

    # ---- Overdue Tasks ----
    try:
        from core.tasks import get_overdue_tasks
        overdue = get_overdue_tasks(_dir)
        for t in overdue:
            if _target_cases and t.get("case_id") not in _target_cases:
                continue
            if user_id and t.get("assigned_to") and t.get("assigned_to") != user_id:
                continue
            notifications.append({
                "type": "overdue_task",
                "title": f"Overdue: {t.get('title', 'Task')}",
                "detail": f"Due {t.get('due_date', '?')} — {t.get('priority', 'medium')} priority",
                "case_id": t.get("case_id", ""),
                "case_name": "",
                "severity": "high",
                "timestamp": t.get("due_date", ""),
            })
    except Exception as exc:
        logger.debug("Overdue tasks notification error: %s", exc)

    # ---- Approaching Deadlines (≤3 days) ----
    try:
        reminders = case_mgr.get_active_reminders()
        for d in reminders:
            days = d.get("days_remaining", 999)
            if days < 0:
                notifications.append({
                    "type": "overdue_deadline",
                    "title": f"OVERDUE: {d.get('label', 'Deadline')}",
                    "detail": f"{abs(days)} days overdue — {d.get('case_name', '')}",
                    "case_id": d.get("case_id", ""),
                    "case_name": d.get("case_name", ""),
                    "severity": "critical",
                    "timestamp": d.get("date", ""),
                })
            elif days <= 3:
                _sev = "critical" if days == 0 else "high" if days == 1 else "medium"
                _label = "TODAY" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
                notifications.append({
                    "type": "approaching_deadline",
                    "title": f"Deadline {_label}: {d.get('label', '')}",
                    "detail": d.get("case_name", ""),
                    "case_id": d.get("case_id", ""),
                    "case_name": d.get("case_name", ""),
                    "severity": _sev,
                    "timestamp": d.get("date", ""),
                })
    except Exception as exc:
        logger.debug("Deadline notification error: %s", exc)

    # ---- Low Retainer Balance ----
    try:
        from core.billing import get_retainer_balance, load_retainer_history
        for cid in _target_cases[:30]:
            history = load_retainer_history(cid)
            if not history:
                continue
            balance = get_retainer_balance(cid)
            if balance <= 0:
                notifications.append({
                    "type": "retainer_exhausted",
                    "title": "Retainer exhausted",
                    "detail": f"Balance: $0 — {case_mgr.get_case_name(cid)}",
                    "case_id": cid,
                    "case_name": case_mgr.get_case_name(cid),
                    "severity": "high",
                    "timestamp": "",
                })
            elif balance < 500:
                notifications.append({
                    "type": "retainer_low",
                    "title": f"Low retainer: ${balance:,.2f}",
                    "detail": case_mgr.get_case_name(cid),
                    "case_id": cid,
                    "case_name": case_mgr.get_case_name(cid),
                    "severity": "medium",
                    "timestamp": "",
                })
    except Exception as exc:
        logger.debug("Retainer notification error: %s", exc)

    # Fill in case names
    for n in notifications:
        if n.get("case_id") and not n.get("case_name"):
            try:
                n["case_name"] = case_mgr.get_case_name(n["case_id"])
            except Exception:
                pass

    # Sort: severity first, then reverse timestamp
    notifications.sort(
        key=lambda n: (
            SEVERITY_ORDER.get(n.get("severity", "low"), 3),
            n.get("timestamp", "") or "",
        ),
    )

    return notifications
