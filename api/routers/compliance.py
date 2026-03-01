# ---- Compliance Router ---------------------------------------------------
# Ethical compliance: trust ledger, conflicts, SOL tracking.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/compliance", tags=["Compliance"])


class TrustEntry(BaseModel):
    id: str = ""
    case_id: str = ""
    date: str = ""
    amount: float = 0.0
    type: str = ""  # deposit / withdrawal
    description: str = ""

    model_config = {"extra": "allow"}


class CreateTrustEntryRequest(BaseModel):
    date: str = Field(..., max_length=20)
    amount: float = Field(...)
    type: str = Field(default="deposit", max_length=20)
    description: str = Field(default="", max_length=2000)


@router.get("/dashboard")
def compliance_dashboard(
    user: dict = Depends(get_current_user),
):
    """Get compliance dashboard (alerts, SOL, conflicts summary)."""
    try:
        from core.ethical_compliance import get_compliance_dashboard
        cm = get_case_manager()
        return get_compliance_dashboard(cm.storage)
    except ImportError:
        return {"conflicts": [], "sol_alerts": [], "trust_alerts": []}


@router.get("/conflicts/{case_id}")
def scan_conflicts(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Scan for conflicts of interest."""
    try:
        from core.ethical_compliance import scan_conflicts_smart
        cm = get_case_manager()
        return scan_conflicts_smart(cm.storage, case_id)
    except ImportError:
        return {"conflicts": [], "status": "module_not_available"}


@router.get("/trust/{case_id}", response_model=List[TrustEntry])
def get_trust_ledger(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get trust account ledger for a case."""
    try:
        from core.ethical_compliance import load_trust_ledger
        cm = get_case_manager()
        return load_trust_ledger(cm.storage, case_id)
    except ImportError:
        return []


@router.post("/trust/{case_id}")
def add_trust_entry(
    case_id: str,
    body: CreateTrustEntryRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a trust account entry."""
    try:
        from core.ethical_compliance import add_trust_entry as core_add
        cm = get_case_manager()
        entry_id = core_add(cm.storage, case_id, **body.model_dump())
        return {"status": "added", "id": entry_id}
    except ImportError:
        return {"status": "compliance_module_not_available"}


@router.get("/sol/{case_id}")
def get_sol_tracking(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get statute of limitations tracking for a case."""
    try:
        from core.ethical_compliance import load_sol_tracking
        cm = get_case_manager()
        return load_sol_tracking(cm.storage, case_id)
    except ImportError:
        return []


@router.get("/sol/alerts")
def get_sol_alerts(
    user: dict = Depends(get_current_user),
):
    """Get SOL alerts across all cases."""
    try:
        from core.ethical_compliance import get_sol_alerts
        cm = get_case_manager()
        return get_sol_alerts(cm.storage)
    except ImportError:
        return []
