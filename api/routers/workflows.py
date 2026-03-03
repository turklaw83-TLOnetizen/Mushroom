# ---- Workflow Router -----------------------------------------------------
# Manage workflow templates and automation triggers.
# Wraps core/workflow.py

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows", tags=["Workflows"])


# ---- Schemas -------------------------------------------------------------

class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    trigger_event: str = ""
    steps: list = []


class WorkflowTrigger(BaseModel):
    case_id: str
    workflow_id: str
    params: dict = {}


# ---- Endpoints -----------------------------------------------------------

@router.get("")
def list_workflows(user: dict = Depends(get_current_user)):
    """List all workflow templates."""
    try:
        from core.workflow import list_workflows as _list
        items = _list()
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception("Failed to list workflows")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
def create_workflow(
    body: WorkflowCreate,
    user: dict = Depends(require_role("admin")),
):
    """Create a workflow template."""
    try:
        from core.workflow import create_workflow as _create
        wf = _create(body.model_dump())
        return {"status": "created", "workflow": wf}
    except Exception as e:
        logger.exception("Failed to create workflow")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a workflow template."""
    try:
        from core.workflow import get_workflow
        wf = get_workflow(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return wf
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get workflow")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trigger")
def trigger_workflow(
    body: WorkflowTrigger,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Trigger a workflow for a specific case."""
    try:
        from core.workflow import execute_workflow
        result = execute_workflow(body.workflow_id, body.case_id, body.params)
        return {"status": "triggered", "result": result}
    except Exception as e:
        logger.exception("Failed to trigger workflow")
        raise HTTPException(status_code=500, detail="Internal server error")
