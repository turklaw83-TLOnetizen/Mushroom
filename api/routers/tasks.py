# ---- Tasks Router --------------------------------------------------------
# CRUD for case tasks (deadlines, assignments, checklists).
# Wraps core/tasks.py

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/tasks", tags=["Tasks"])


# ---- Schemas -------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    assigned_to: str = ""
    due_date: str = ""
    priority: str = "medium"
    category: str = ""


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None


# ---- Endpoints -----------------------------------------------------------

@router.get("")
def list_tasks(
    case_id: str,
    status: str = "",
    assigned_to: str = "",
    user: dict = Depends(get_current_user),
):
    """List all tasks for a case, optionally filtered."""
    try:
        from core.tasks import get_tasks
        tasks = get_tasks(case_id, status_filter=status, assigned_filter=assigned_to)
        return {"items": tasks, "total": len(tasks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_task(
    case_id: str,
    body: TaskCreate,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Create a new task."""
    try:
        from core.tasks import create_task as _create
        task = _create(case_id, body.model_dump())
        return {"status": "created", "task": task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}")
def get_task(
    case_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific task."""
    try:
        from core.tasks import get_task
        task = get_task(case_id, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{task_id}")
def update_task(
    case_id: str,
    task_id: str,
    body: TaskUpdate,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Update a task."""
    try:
        from core.tasks import update_task as _update
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        task = _update(case_id, task_id, updates)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
def delete_task(
    case_id: str,
    task_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a task."""
    try:
        from core.tasks import delete_task as _delete
        if not _delete(case_id, task_id):
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/complete")
def complete_task(
    case_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Mark a task as complete."""
    try:
        from core.tasks import update_task as _update
        task = _update(case_id, task_id, {"status": "completed"})
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
