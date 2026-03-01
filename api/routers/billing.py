# ---- Billing Router ------------------------------------------------------
# Time entries, expenses, and invoice management per case.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager
from api.schemas import PaginatedResponse, paginate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])


class TimeEntryResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    date: str = ""
    hours: float = 0.0
    description: str = ""
    attorney: str = ""
    rate: float = 0.0
    billable: bool = True

    model_config = {"extra": "allow"}


class CreateTimeEntryRequest(BaseModel):
    date: str = Field(..., max_length=20)
    hours: float = Field(..., ge=0, le=24)
    description: str = Field(..., min_length=1, max_length=2000)
    rate: float = Field(default=0.0, ge=0)
    billable: bool = True


class ExpenseResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    date: str = ""
    amount: float = 0.0
    description: str = ""
    category: str = ""

    model_config = {"extra": "allow"}


class CreateExpenseRequest(BaseModel):
    date: str = Field(..., max_length=20)
    amount: float = Field(..., ge=0)
    description: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(default="", max_length=100)


# ---- Time Entries --------------------------------------------------------

@router.get("/time/{case_id}", response_model=List[TimeEntryResponse])
def list_time_entries(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List time entries for a case."""
    cm = get_case_manager()
    try:
        from core.billing import load_time_entries
        return load_time_entries(cm.storage, case_id)
    except ImportError:
        return []


@router.post("/time/{case_id}")
def add_time_entry(
    case_id: str,
    body: CreateTimeEntryRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Add a time entry."""
    cm = get_case_manager()
    try:
        from core.billing import add_time_entry as core_add
        entry_id = core_add(
            cm.storage, case_id,
            date=body.date,
            hours=body.hours,
            description=body.description,
            attorney=user.get("name", user.get("id", "")),
            rate=body.rate,
            billable=body.billable,
        )
        return {"status": "added", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.put("/time/{case_id}/{entry_id}")
def update_time_entry(
    case_id: str,
    entry_id: str,
    body: CreateTimeEntryRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Update a time entry (delete + recreate with same ID)."""
    cm = get_case_manager()
    try:
        from core.billing import delete_time_entry, add_time_entry as core_add
        delete_time_entry(cm.storage, case_id, entry_id)
        new_id = core_add(
            cm.storage, case_id,
            date=body.date, hours=body.hours, description=body.description,
            attorney=user.get("name", user.get("id", "")),
            rate=body.rate, billable=body.billable, entry_id=entry_id,
        )
        return {"status": "updated", "id": new_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.delete("/time/{case_id}/{entry_id}")
def delete_time_entry_route(
    case_id: str,
    entry_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a time entry."""
    cm = get_case_manager()
    try:
        from core.billing import delete_time_entry
        delete_time_entry(cm.storage, case_id, entry_id)
        return {"status": "deleted", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


# ---- Expenses ------------------------------------------------------------

@router.get("/expenses/{case_id}", response_model=List[ExpenseResponse])
def list_expenses(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List expenses for a case."""
    cm = get_case_manager()
    try:
        from core.billing import load_expenses
        return load_expenses(cm.storage, case_id)
    except ImportError:
        return []


@router.post("/expenses/{case_id}")
def add_expense(
    case_id: str,
    body: CreateExpenseRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Add an expense."""
    cm = get_case_manager()
    try:
        from core.billing import add_expense as core_add
        entry_id = core_add(
            cm.storage, case_id,
            date=body.date,
            amount=body.amount,
            description=body.description,
            category=body.category,
        )
        return {"status": "added", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.put("/expenses/{case_id}/{expense_id}")
def update_expense(
    case_id: str,
    expense_id: str,
    body: CreateExpenseRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Update an expense."""
    cm = get_case_manager()
    try:
        from core.billing import delete_expense, add_expense as core_add
        delete_expense(cm.storage, case_id, expense_id)
        new_id = core_add(
            cm.storage, case_id,
            date=body.date, amount=body.amount,
            description=body.description, category=body.category,
            expense_id=expense_id,
        )
        return {"status": "updated", "id": new_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.delete("/expenses/{case_id}/{expense_id}")
def delete_expense_route(
    case_id: str,
    expense_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete an expense."""
    cm = get_case_manager()
    try:
        from core.billing import delete_expense
        delete_expense(cm.storage, case_id, expense_id)
        return {"status": "deleted", "id": expense_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


# ---- Summary -------------------------------------------------------------

@router.get("/summary/{case_id}")
def billing_summary(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get billing summary for a case."""
    cm = get_case_manager()
    try:
        from core.billing import get_case_billing_summary
        return get_case_billing_summary(cm.storage, case_id)
    except ImportError:
        return {"total_hours": 0, "total_expenses": 0, "total_billable": 0}
