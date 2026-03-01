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


# ---- Invoices ------------------------------------------------------------

class InvoiceResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    case_name: str = ""
    client_name: str = ""
    date_created: str = ""
    due_date: str = ""
    status: str = "draft"
    total_hours: float = 0.0
    subtotal_fees: float = 0.0
    subtotal_expenses: float = 0.0
    total: float = 0.0
    amount_paid: float = 0.0
    notes: str = ""

    model_config = {"extra": "allow"}


class CreateInvoiceRequest(BaseModel):
    time_entry_ids: List[str] = Field(default_factory=list)
    expense_ids: List[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=5000)


class UpdateInvoiceStatusRequest(BaseModel):
    status: str = Field(..., max_length=20)


@router.get("/invoices/{case_id}", response_model=List[InvoiceResponse])
def list_invoices(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List invoices for a case."""
    try:
        from core.billing import load_invoices
        all_invoices = load_invoices()
        return [inv for inv in all_invoices if inv.get("case_id") == case_id]
    except ImportError:
        return []


@router.post("/invoices/{case_id}")
def create_invoice_route(
    case_id: str,
    body: CreateInvoiceRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create an invoice from time entries and expenses."""
    try:
        from core.billing import create_invoice
        cm = get_case_manager()
        meta = cm.get_case_metadata(case_id)
        invoice = create_invoice(
            case_id,
            time_entry_ids=body.time_entry_ids,
            expense_ids=body.expense_ids,
            notes=body.notes,
            case_name=meta.get("name", "") if meta else "",
            client_name=meta.get("client_name", "") if meta else "",
        )
        return {"status": "created", "invoice": invoice}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.patch("/invoices/{invoice_id}/status")
def update_invoice_status_route(
    invoice_id: str,
    body: UpdateInvoiceStatusRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update invoice status (draft, sent, paid, overdue, void)."""
    try:
        from core.billing import update_invoice_status
        if update_invoice_status(invoice_id, body.status):
            return {"status": "updated", "invoice_id": invoice_id}
        raise HTTPException(status_code=404, detail="Invoice not found")
    except ImportError:
        return {"status": "billing_module_not_available"}


# ---- Retainer ------------------------------------------------------------

class RetainerEntryResponse(BaseModel):
    id: str = ""
    type: str = ""
    amount: float = 0.0
    date: str = ""
    note: str = ""
    invoice_id: str = ""

    model_config = {"extra": "allow"}


class AddRetainerDepositRequest(BaseModel):
    amount: float = Field(..., gt=0)
    date: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=2000)


class AddRetainerDrawRequest(BaseModel):
    amount: float = Field(..., gt=0)
    invoice_id: str = Field(default="", max_length=50)
    date: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=2000)


@router.get("/retainer/{case_id}")
def get_retainer(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get retainer balance and history for a case."""
    try:
        from core.billing import load_retainer_history, get_retainer_balance
        return {
            "balance": get_retainer_balance(case_id),
            "history": load_retainer_history(case_id),
        }
    except ImportError:
        return {"balance": 0, "history": []}


@router.post("/retainer/{case_id}/deposit")
def add_retainer_deposit_route(
    case_id: str,
    body: AddRetainerDepositRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Record a retainer deposit."""
    try:
        from core.billing import add_retainer_deposit
        entry_id = add_retainer_deposit(case_id, body.amount, body.date, body.note)
        return {"status": "added", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.post("/retainer/{case_id}/draw")
def add_retainer_draw_route(
    case_id: str,
    body: AddRetainerDrawRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Record a retainer draw (deduction)."""
    try:
        from core.billing import add_retainer_draw
        entry_id = add_retainer_draw(
            case_id, body.amount, body.invoice_id, body.date, body.note
        )
        return {"status": "added", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


# ---- Aging Report --------------------------------------------------------

@router.get("/aging")
def aging_report(
    user: dict = Depends(get_current_user),
):
    """Get invoice aging report (current, 30, 60, 90+ days)."""
    try:
        from core.billing import get_aging_report
        return get_aging_report()
    except ImportError:
        return {"current": [], "30_days": [], "60_days": [], "90_plus": []}
