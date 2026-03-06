# ---- Billing Router ------------------------------------------------------
# Time entries, expenses, and invoice management per case.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
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
    try:
        from core.billing import load_time_entries
        return load_time_entries(case_id)
    except ImportError:
        return []


@router.post("/time/{case_id}")
def add_time_entry(
    case_id: str,
    body: CreateTimeEntryRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Add a time entry."""
    try:
        from core.billing import add_time_entry as core_add
        entry_id = core_add(
            case_id,
            duration_hours=body.hours,
            description=body.description,
            rate=body.rate,
            billable=body.billable,
            date_str=body.date,
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
    """Update a time entry (delete + recreate)."""
    try:
        from core.billing import delete_time_entry, add_time_entry as core_add
        delete_time_entry(case_id, entry_id)
        new_id = core_add(
            case_id,
            duration_hours=body.hours,
            description=body.description,
            rate=body.rate,
            billable=body.billable,
            date_str=body.date,
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
    try:
        from core.billing import delete_time_entry
        delete_time_entry(case_id, entry_id)
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
    try:
        from core.billing import load_expenses
        return load_expenses(case_id)
    except ImportError:
        return []


@router.post("/expenses/{case_id}")
def add_expense(
    case_id: str,
    body: CreateExpenseRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Add an expense."""
    try:
        from core.billing import add_expense as core_add
        entry_id = core_add(
            case_id,
            amount=body.amount,
            description=body.description,
            category=body.category,
            date_str=body.date,
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
    try:
        from core.billing import delete_expense, add_expense as core_add
        delete_expense(case_id, expense_id)
        new_id = core_add(
            case_id,
            amount=body.amount,
            description=body.description,
            category=body.category,
            date_str=body.date,
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
    try:
        from core.billing import delete_expense
        delete_expense(case_id, expense_id)
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
    try:
        from core.billing import get_case_billing_summary
        return get_case_billing_summary(case_id)
    except ImportError:
        return {"total_hours": 0, "total_expenses": 0, "total_billable": 0}


# ---- AR Overview ---------------------------------------------------------

@router.get("/ar-overview")
def ar_overview(
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Firm-wide accounts receivable overview across all clients."""
    try:
        from core.billing import get_ar_overview
        return get_ar_overview()
    except ImportError:
        return {"total_plans": 0, "active_plans": 0, "total_receivable": 0,
                "total_collected": 0, "total_overdue": 0, "overdue_count": 0, "plans": []}


# ---- Revenue Overview ----------------------------------------------------

@router.get("/revenue-overview")
def revenue_overview(
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Firm-wide revenue tracker — all plans including completed."""
    try:
        from core.billing import get_revenue_overview
        return get_revenue_overview()
    except ImportError:
        return {"total_plans": 0, "total_revenue": 0, "completed_revenue": 0,
                "active_revenue": 0, "total_outstanding": 0, "plans": []}


# ==========================================================================
#  INVOICES
# ==========================================================================

class CreateInvoiceRequest(BaseModel):
    time_entry_ids: list[str] = []
    expense_ids: list[str] = []
    notes: str = ""
    case_name: str = ""
    client_name: str = ""


class UpdateInvoiceStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(draft|sent|paid|overdue|void)$")


class RecordPaymentRequest(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method: str = ""
    date: str = ""


@router.post("/invoices/{case_id}")
def create_invoice_route(
    case_id: str,
    body: CreateInvoiceRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create an invoice from selected time entries and expenses."""
    try:
        from core.billing import create_invoice
        invoice = create_invoice(
            case_id,
            time_entry_ids=body.time_entry_ids,
            expense_ids=body.expense_ids,
            notes=body.notes,
            case_name=body.case_name,
            client_name=body.client_name,
        )
        return invoice
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.get("/invoices")
def list_invoices(
    user: dict = Depends(get_current_user),
):
    """List all invoices (firm-wide)."""
    try:
        from core.billing import load_invoices
        return load_invoices()
    except ImportError:
        return []


@router.get("/invoices/{invoice_id}")
def get_invoice_route(
    invoice_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single invoice by ID."""
    try:
        from core.billing import get_invoice
        inv = get_invoice(invoice_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return inv
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.put("/invoices/{invoice_id}/status")
def update_invoice_status_route(
    invoice_id: str,
    body: UpdateInvoiceStatusRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update invoice status (draft, sent, paid, overdue, void)."""
    try:
        from core.billing import update_invoice_status
        ok = update_invoice_status(invoice_id, body.status)
        if not ok:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"status": "updated", "invoice_id": invoice_id, "new_status": body.status}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.post("/invoices/{invoice_id}/void")
def void_invoice_route(
    invoice_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Void an invoice and un-bill its time entries and expenses."""
    try:
        from core.billing import void_invoice
        ok = void_invoice(invoice_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"status": "voided", "invoice_id": invoice_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: str,
    user: dict = Depends(get_current_user),
):
    """Generate and download an invoice PDF."""
    try:
        from core.billing import generate_invoice_pdf
        from fastapi.responses import StreamingResponse
        pdf = generate_invoice_pdf(invoice_id)
        if pdf:
            return StreamingResponse(
                pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=invoice-{invoice_id}.pdf"
                },
            )
        raise HTTPException(status_code=404, detail="Invoice not found")
    except ImportError:
        raise HTTPException(status_code=501, detail="Billing module not available")


@router.post("/invoices/{invoice_id}/payments")
def record_payment_route(
    invoice_id: str,
    body: RecordPaymentRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Record a payment against an invoice."""
    try:
        from core.billing import record_payment
        ok = record_payment(
            invoice_id,
            amount=body.amount,
            method=body.payment_method,
            date_str=body.date,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"status": "payment_recorded", "invoice_id": invoice_id, "amount": body.amount}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.get("/invoices/{invoice_id}/payments")
def get_payment_history_route(
    invoice_id: str,
    user: dict = Depends(get_current_user),
):
    """Get payment history for an invoice."""
    try:
        from core.billing import get_payment_history
        return get_payment_history(invoice_id)
    except ImportError:
        return []


@router.get("/invoices/{invoice_id}/balance")
def get_invoice_balance_route(
    invoice_id: str,
    user: dict = Depends(get_current_user),
):
    """Get remaining balance on an invoice."""
    try:
        from core.billing import get_invoice_balance
        balance = get_invoice_balance(invoice_id)
        return {"invoice_id": invoice_id, "balance": balance}
    except ImportError:
        return {"invoice_id": invoice_id, "balance": 0.0}


# ==========================================================================
#  RETAINER
# ==========================================================================

class RetainerDepositRequest(BaseModel):
    amount: float = Field(..., gt=0)
    date: str = ""
    notes: str = ""


class RetainerDrawRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = ""
    date: str = ""


@router.get("/retainer/{case_id}")
def get_retainer(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get retainer history and current balance for a case."""
    try:
        from core.billing import load_retainer_history, get_retainer_balance
        history = load_retainer_history(case_id)
        balance = get_retainer_balance(case_id)
        return {"history": history, "balance": balance}
    except ImportError:
        return {"history": [], "balance": 0.0}


@router.post("/retainer/{case_id}/deposit")
def add_retainer_deposit_route(
    case_id: str,
    body: RetainerDepositRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Record a retainer deposit."""
    try:
        from core.billing import add_retainer_deposit
        entry_id = add_retainer_deposit(
            case_id,
            amount=body.amount,
            date_str=body.date,
            note=body.notes,
        )
        return {"status": "deposit_recorded", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


@router.post("/retainer/{case_id}/draw")
def add_retainer_draw_route(
    case_id: str,
    body: RetainerDrawRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Record a retainer draw (deduction for billed work)."""
    try:
        from core.billing import add_retainer_draw
        entry_id = add_retainer_draw(
            case_id,
            amount=body.amount,
            note=body.description,
            date_str=body.date,
        )
        return {"status": "draw_recorded", "id": entry_id}
    except ImportError:
        return {"status": "billing_module_not_available"}


# ==========================================================================
#  UNBILLED
# ==========================================================================

@router.get("/unbilled/{case_id}")
def get_unbilled(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get unbilled time entries and expenses for a case."""
    try:
        from core.billing import get_unbilled_time, get_unbilled_expenses
        return {
            "unbilled_time": get_unbilled_time(case_id),
            "unbilled_expenses": get_unbilled_expenses(case_id),
        }
    except ImportError:
        return {"unbilled_time": [], "unbilled_expenses": []}


# ==========================================================================
#  AGING REPORT
# ==========================================================================

@router.get("/aging")
def get_aging_report_route(
    user: dict = Depends(require_role("admin")),
):
    """Get invoice aging report grouped by 30/60/90+ day buckets. Admin only."""
    try:
        from core.billing import get_aging_report
        return get_aging_report()
    except ImportError:
        return {"current": [], "30_days": [], "60_days": [], "90_plus": []}


# ==========================================================================
#  BILLING SETTINGS
# ==========================================================================

class BillingSettingsRequest(BaseModel):
    default_rate: float = 0.0
    payment_terms_days: int = 30
    firm_name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    tax_rate: float = 0.0

    model_config = {"extra": "allow"}


@router.get("/settings")
def get_billing_settings(
    user: dict = Depends(require_role("admin")),
):
    """Get firm billing settings. Admin only."""
    try:
        from core.billing import load_billing_settings
        return load_billing_settings()
    except ImportError:
        return {"default_rate": 0.0, "payment_terms_days": 30, "firm_name": "",
                "address": "", "phone": "", "email": "", "tax_rate": 0.0}


@router.put("/settings")
def update_billing_settings(
    body: BillingSettingsRequest,
    user: dict = Depends(require_role("admin")),
):
    """Update firm billing settings. Admin only."""
    try:
        from core.billing import save_billing_settings
        save_billing_settings(body.model_dump())
        return {"status": "settings_saved"}
    except ImportError:
        return {"status": "billing_module_not_available"}


# ==========================================================================
#  FIRM STATS
# ==========================================================================

@router.get("/stats")
def get_firm_billing_stats_route(
    user: dict = Depends(require_role("admin")),
):
    """Firm-wide billing statistics. Admin only."""
    try:
        from core.billing import get_firm_billing_stats
        from api.deps import get_case_manager
        cm = get_case_manager()
        return get_firm_billing_stats(cm)
    except ImportError:
        return {
            "total_billable_hours": 0.0,
            "unbilled_hours": 0.0,
            "unbilled_amount": 0.0,
            "unbilled_expenses": 0.0,
            "outstanding_invoices": 0,
            "outstanding_total": 0.0,
            "total_collected": 0.0,
            "monthly_revenue": 0.0,
            "overdue_count": 0,
            "overdue_total": 0.0,
            "total_invoices": 0,
            "draft_count": 0,
        }
