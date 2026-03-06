"""
activity.py -- Recent Activity Aggregator
Collects recent events from comms log, payment records, and file activity.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data")


def get_recent_activity(limit: int = 15) -> List[Dict]:
    """Aggregate recent activity across the system.
    Returns unified list sorted by timestamp (newest first).
    Each item: {type, title, detail, case_id, timestamp}
    """
    items: List[Dict] = []
    cutoff = (datetime.now() - timedelta(days=14)).isoformat()

    # 1. Recent communications sent
    _collect_comms(items, cutoff)

    # 2. Recent payments recorded
    _collect_payments(items, cutoff)

    # 3. Recent analysis completions
    _collect_analysis(items, cutoff)

    # Sort by timestamp descending, take top N
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items[:limit]


def _collect_comms(items: List[Dict], cutoff: str):
    """Collect recent sent communications."""
    log_path = os.path.join(_DATA_DIR, "comms", "log.json")
    if not os.path.exists(log_path):
        return
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log = json.load(f)
        for entry in log:
            ts = entry.get("sent_at", "")
            if ts and ts >= cutoff:
                items.append({
                    "type": "comm",
                    "title": "Communication sent",
                    "detail": entry.get("subject", "No subject"),
                    "case_id": entry.get("case_id", ""),
                    "client_id": entry.get("client_id", ""),
                    "timestamp": ts,
                })
    except (json.JSONDecodeError, IOError):
        pass


def _collect_payments(items: List[Dict], cutoff: str):
    """Collect recent payment recordings from payment plans."""
    plans_dir = os.path.join(_DATA_DIR, "crm", "payment_plans")
    if not os.path.isdir(plans_dir):
        return
    try:
        for client_dir in os.listdir(plans_dir):
            plans_file = os.path.join(plans_dir, client_dir, "plans.json")
            if not os.path.exists(plans_file):
                continue
            with open(plans_file, "r", encoding="utf-8") as f:
                plans = json.load(f)
            for plan in plans:
                client_name = plan.get("client_name", "")
                for sp in plan.get("scheduled_payments", []):
                    paid_date = sp.get("paid_date", "")
                    if paid_date and paid_date >= cutoff[:10]:
                        amount = sp.get("paid_amount") or sp.get("amount", 0)
                        items.append({
                            "type": "payment",
                            "title": "Payment received",
                            "detail": f"${amount:.2f} from {client_name}" if client_name else f"${amount:.2f}",
                            "case_id": "",
                            "client_id": client_dir,
                            "timestamp": paid_date + "T00:00:00",
                        })
    except (json.JSONDecodeError, IOError, OSError):
        pass


def _collect_analysis(items: List[Dict], cutoff: str):
    """Collect recent analysis completions."""
    cases_dir = os.path.join(_DATA_DIR, "cases")
    if not os.path.isdir(cases_dir):
        return
    try:
        for case_id in os.listdir(cases_dir):
            progress_file = os.path.join(cases_dir, case_id, "progress.json")
            if not os.path.exists(progress_file):
                continue
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
            if progress.get("status") == "completed":
                ts = progress.get("completed_at", progress.get("updated_at", ""))
                if ts and ts >= cutoff:
                    items.append({
                        "type": "analysis",
                        "title": "Analysis completed",
                        "detail": f"Case {case_id[:8]}",
                        "case_id": case_id,
                        "timestamp": ts,
                    })
    except (json.JSONDecodeError, IOError, OSError):
        pass
