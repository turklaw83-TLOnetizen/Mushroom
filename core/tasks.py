"""
tasks.py -- Task Assignment System
Assign follow-up tasks to staff from within analysis results or case view.
Storage: data/cases/{case_id}/tasks.json
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TASK_STATUSES = ["pending", "in_progress", "completed", "cancelled"]
TASK_PRIORITIES = ["low", "medium", "high", "urgent"]
TASK_CATEGORIES = [
    "Investigation", "Document Review", "Research", "Filing",
    "Client Communication", "Witness Prep", "Court Appearance",
    "Discovery", "Deposition", "Administrative", "Other",
]


def _tasks_path(data_dir: str, case_id: str) -> Path:
    return Path(data_dir) / "cases" / case_id / "tasks.json"


def _load_tasks_raw(data_dir: str, case_id: str) -> List[Dict]:
    path = _tasks_path(data_dir, case_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_tasks_raw(data_dir: str, case_id: str, tasks: List[Dict]):
    path = _tasks_path(data_dir, case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False, default=str)


def add_task(
    data_dir: str,
    case_id: str,
    title: str,
    description: str = "",
    assigned_to: str = "",
    assigned_by: str = "",
    priority: str = "medium",
    due_date: str = "",
    category: str = "Other",
) -> str:
    """Create a task linked to a case. Returns task ID."""
    tasks = _load_tasks_raw(data_dir, case_id)
    task_id = uuid.uuid4().hex[:8]
    task = {
        "id": task_id,
        "case_id": case_id,
        "title": title.strip(),
        "description": description.strip(),
        "assigned_to": assigned_to,
        "assigned_by": assigned_by,
        "priority": priority,
        "status": "pending",
        "due_date": due_date,
        "category": category,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": "",
        "notes": "",
    }
    tasks.insert(0, task)
    _save_tasks_raw(data_dir, case_id, tasks)
    return task_id


def load_tasks(
    data_dir: str,
    case_id: str,
    status_filter: Optional[str] = None,
    assigned_to: Optional[str] = None,
    priority_filter: Optional[str] = None,
) -> List[Dict]:
    """Load tasks for a case with optional filters."""
    tasks = _load_tasks_raw(data_dir, case_id)
    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]
    if assigned_to:
        tasks = [t for t in tasks if t.get("assigned_to") == assigned_to]
    if priority_filter:
        tasks = [t for t in tasks if t.get("priority") == priority_filter]
    return tasks


def update_task(data_dir: str, case_id: str, task_id: str, updates: Dict) -> bool:
    """Update fields on a task. Returns True if found."""
    tasks = _load_tasks_raw(data_dir, case_id)
    for t in tasks:
        if t.get("id") == task_id:
            for k, v in updates.items():
                if k != "id":
                    t[k] = v
            t["updated_at"] = datetime.now().isoformat()
            if updates.get("status") == "completed" and not t.get("completed_at"):
                t["completed_at"] = datetime.now().isoformat()
            _save_tasks_raw(data_dir, case_id, tasks)
            return True
    return False


def delete_task(data_dir: str, case_id: str, task_id: str) -> bool:
    """Delete a task. Returns True if found."""
    tasks = _load_tasks_raw(data_dir, case_id)
    filtered = [t for t in tasks if t.get("id") != task_id]
    if len(filtered) < len(tasks):
        _save_tasks_raw(data_dir, case_id, filtered)
        return True
    return False


def get_tasks_for_user(data_dir: str, user_id: str) -> List[Dict]:
    """Get all tasks assigned to a user across all cases."""
    cases_dir = Path(data_dir) / "cases"
    if not cases_dir.exists():
        return []
    all_tasks = []
    for case_dir in cases_dir.iterdir():
        if case_dir.is_dir():
            tasks = _load_tasks_raw(data_dir, case_dir.name)
            user_tasks = [t for t in tasks if t.get("assigned_to") == user_id]
            all_tasks.extend(user_tasks)
    # Sort by due date, then priority
    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    all_tasks.sort(key=lambda t: (
        t.get("due_date") or "9999-99-99",
        priority_order.get(t.get("priority", "medium"), 2),
    ))
    return all_tasks


def get_overdue_tasks(data_dir: str, case_id: Optional[str] = None) -> List[Dict]:
    """Get overdue tasks (past due_date, not completed)."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if case_id:
        tasks = _load_tasks_raw(data_dir, case_id)
    else:
        tasks = []
        cases_dir = Path(data_dir) / "cases"
        if cases_dir.exists():
            for case_dir in cases_dir.iterdir():
                if case_dir.is_dir():
                    tasks.extend(_load_tasks_raw(data_dir, case_dir.name))
    
    overdue = [
        t for t in tasks
        if t.get("due_date") and t["due_date"] < today
        and t.get("status") not in ("completed", "cancelled")
    ]
    return overdue


def get_task_stats(data_dir: str, case_id: str) -> Dict:
    """Get task statistics for a case."""
    tasks = _load_tasks_raw(data_dir, case_id)
    return {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t.get("status") == "pending"),
        "in_progress": sum(1 for t in tasks if t.get("status") == "in_progress"),
        "completed": sum(1 for t in tasks if t.get("status") == "completed"),
        "cancelled": sum(1 for t in tasks if t.get("status") == "cancelled"),
        "overdue": sum(
            1 for t in tasks
            if t.get("due_date") and t["due_date"] < datetime.now().strftime("%Y-%m-%d")
            and t.get("status") not in ("completed", "cancelled")
        ),
    }
