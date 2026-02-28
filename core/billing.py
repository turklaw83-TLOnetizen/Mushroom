"""
AllRise Beta -- Billing & Time Tracking Module
=============================================
Time tracking, expense management, and invoice generation
for law firm billing workflows.

Features:
  1. Time Entry CRUD (billable/non-billable, activity types)
  2. Expense CRUD (categories, reimbursable flag)
  3. Invoice Generation (from unbilled time + expenses)
  4. Firm-wide billing statistics & aggregation
"""

import os
import io
import json
import uuid
import logging
from typing import List, Dict, Optional
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data")

# ===================================================================
#  CONSTANTS
# ===================================================================

ACTIVITY_TYPES = [
    "Research",
    "Drafting",
    "Court Appearance",
    "Client Meeting",
    "Phone/Email",
    "Travel",
    "Deposition",
    "Negotiation",
    "Document Review",
    "Administrative",
    "Other",
]

EXPENSE_CATEGORIES = [
    "Filing Fee",
    "Court Reporter",
    "Expert Witness",
    "Travel",
    "Copying/Printing",
    "Postage/Delivery",
    "Process Server",
    "Transcription",
    "Investigation",
    "Medical Records",
    "Other",
]

INVOICE_STATUSES = ["draft", "sent", "paid", "overdue", "void"]

DEFAULT_BILLING_SETTINGS = {
    "default_rate": 350.00,
    "payment_terms_days": 30,
    "firm_name": "",
    "firm_address": "",
    "firm_phone": "",
    "firm_email": "",
    "tax_rate": 0.0,
    "invoice_notes": "Payment is due within 30 days of invoice date.",
    "next_invoice_seq": 1,
}


# ===================================================================
#  1.  BILLING SETTINGS
# ===================================================================

def _settings_path() -> str:
    return os.path.join(_DATA_DIR, "billing_settings.json")


def load_billing_settings() -> Dict:
    """Load firm billing settings (rates, terms, firm info)."""
    path = _settings_path()
    settings = dict(DEFAULT_BILLING_SETTINGS)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
            settings.update(saved)
    return settings


def save_billing_settings(settings: Dict) -> None:
    """Save billing settings."""
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def _next_invoice_number() -> str:
    """Generate next invoice number in TLO-B#### format."""
    settings = load_billing_settings()
    seq = settings.get("next_invoice_seq", 1)
    inv_num = f"TLO-B{seq:04d}"
    settings["next_invoice_seq"] = seq + 1
    save_billing_settings(settings)
    return inv_num


# ===================================================================
#  2.  TIME ENTRIES
# ===================================================================

def _time_entries_path(case_id: str) -> str:
    return os.path.join(_DATA_DIR, "cases", case_id, "time_entries.json")


def load_time_entries(case_id: str) -> List[Dict]:
    """Load time entries for a case (newest first)."""
    path = _time_entries_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
            return sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
    return []


def _save_time_entries(case_id: str, entries: List[Dict]) -> None:
    path = _time_entries_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def add_time_entry(
    case_id: str,
    duration_hours: float,
    description: str,
    activity_type: str = "Other",
    billable: bool = True,
    rate: float = 0.0,
    date_str: str = "",
) -> str:
    """Add a time entry. Returns entry ID."""
    settings = load_billing_settings()
    if rate <= 0:
        rate = settings.get("default_rate", 350.00)

    entries = load_time_entries(case_id)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "case_id": case_id,
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "duration_hours": round(abs(duration_hours), 2),
        "description": description,
        "activity_type": activity_type,
        "billable": billable,
        "rate": rate,
        "billed_invoice_id": "",
        "created_at": datetime.now().isoformat(),
    }
    entries.append(entry)
    _save_time_entries(case_id, entries)
    return entry["id"]


def update_time_entry(case_id: str, entry_id: str, updates: Dict) -> bool:
    """Update fields on a time entry. Returns True if found."""
    entries = load_time_entries(case_id)
    for entry in entries:
        if entry.get("id") == entry_id:
            entry.update(updates)
            _save_time_entries(case_id, entries)
            return True
    return False


def delete_time_entry(case_id: str, entry_id: str) -> bool:
    """Remove a time entry. Returns True if found."""
    entries = load_time_entries(case_id)
    filtered = [e for e in entries if e.get("id") != entry_id]
    if len(filtered) < len(entries):
        _save_time_entries(case_id, filtered)
        return True
    return False


# ===================================================================
#  3.  EXPENSES
# ===================================================================

def _expenses_path(case_id: str) -> str:
    return os.path.join(_DATA_DIR, "cases", case_id, "expenses.json")


def load_expenses(case_id: str) -> List[Dict]:
    """Load expenses for a case (newest first)."""
    path = _expenses_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            expenses = json.load(f)
            return sorted(expenses, key=lambda e: e.get("date", ""), reverse=True)
    return []


def _save_expenses(case_id: str, expenses: List[Dict]) -> None:
    path = _expenses_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(expenses, f, indent=2)


def add_expense(
    case_id: str,
    amount: float,
    category: str = "Other",
    description: str = "",
    reimbursable: bool = True,
    receipt_note: str = "",
    date_str: str = "",
) -> str:
    """Add an expense. Returns expense ID."""
    expenses = load_expenses(case_id)
    expense = {
        "id": uuid.uuid4().hex[:8],
        "case_id": case_id,
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "amount": round(abs(amount), 2),
        "category": category,
        "description": description,
        "reimbursable": reimbursable,
        "receipt_note": receipt_note,
        "billed_invoice_id": "",
        "created_at": datetime.now().isoformat(),
    }
    expenses.append(expense)
    _save_expenses(case_id, expenses)
    return expense["id"]


def update_expense(case_id: str, expense_id: str, updates: Dict) -> bool:
    """Update fields on an expense. Returns True if found."""
    expenses = load_expenses(case_id)
    for exp in expenses:
        if exp.get("id") == expense_id:
            exp.update(updates)
            _save_expenses(case_id, expenses)
            return True
    return False


def delete_expense(case_id: str, expense_id: str) -> bool:
    """Remove an expense. Returns True if found."""
    expenses = load_expenses(case_id)
    filtered = [e for e in expenses if e.get("id") != expense_id]
    if len(filtered) < len(expenses):
        _save_expenses(case_id, filtered)
        return True
    return False


# ===================================================================
#  4.  INVOICES
# ===================================================================

def _invoices_path() -> str:
    """Invoices are stored firm-wide (not per-case)."""
    return os.path.join(_DATA_DIR, "invoices.json")


def load_invoices() -> List[Dict]:
    """Load all invoices (newest first)."""
    path = _invoices_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            invoices = json.load(f)
            return sorted(invoices, key=lambda i: i.get("date_created", ""), reverse=True)
    return []


def _save_invoices(invoices: List[Dict]) -> None:
    path = _invoices_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(invoices, f, indent=2)


def create_invoice(
    case_id: str,
    time_entry_ids: List[str],
    expense_ids: List[str],
    notes: str = "",
    case_name: str = "",
    client_name: str = "",
) -> Dict:
    """
    Create an invoice from selected time entries and expenses.
    Marks included items as billed. Returns the new invoice dict.
    """
    settings = load_billing_settings()
    inv_id = _next_invoice_number()

    # Calculate totals from time entries
    time_entries = load_time_entries(case_id)
    selected_time = [t for t in time_entries if t.get("id") in time_entry_ids]
    subtotal_fees = sum(
        t.get("duration_hours", 0) * t.get("rate", 0) for t in selected_time
    )
    total_hours = sum(t.get("duration_hours", 0) for t in selected_time)

    # Calculate totals from expenses
    expenses = load_expenses(case_id)
    selected_expenses = [e for e in expenses if e.get("id") in expense_ids]
    subtotal_expenses = sum(e.get("amount", 0) for e in selected_expenses)

    # Tax
    tax_rate = settings.get("tax_rate", 0.0)
    tax_amount = subtotal_fees * (tax_rate / 100) if tax_rate else 0.0
    total = subtotal_fees + subtotal_expenses + tax_amount

    # Payment terms
    terms_days = settings.get("payment_terms_days", 30)
    due_date = (datetime.now() + timedelta(days=terms_days)).strftime("%Y-%m-%d")

    invoice = {
        "id": inv_id,
        "case_id": case_id,
        "case_name": case_name,
        "client_name": client_name,
        "date_created": datetime.now().strftime("%Y-%m-%d"),
        "due_date": due_date,
        "status": "draft",
        "time_entry_ids": time_entry_ids,
        "expense_ids": expense_ids,
        "total_hours": round(total_hours, 2),
        "subtotal_fees": round(subtotal_fees, 2),
        "subtotal_expenses": round(subtotal_expenses, 2),
        "tax_rate": tax_rate,
        "tax_amount": round(tax_amount, 2),
        "total": round(total, 2),
        "amount_paid": 0.0,
        "payments": [],
        "notes": notes or settings.get("invoice_notes", ""),
        "firm_name": settings.get("firm_name", ""),
        "firm_address": settings.get("firm_address", ""),
        "created_at": datetime.now().isoformat(),
    }

    # Mark time entries as billed
    for t in time_entries:
        if t.get("id") in time_entry_ids:
            t["billed_invoice_id"] = inv_id
    _save_time_entries(case_id, time_entries)

    # Mark expenses as billed
    for e in expenses:
        if e.get("id") in expense_ids:
            e["billed_invoice_id"] = inv_id
    _save_expenses(case_id, expenses)

    # Save invoice
    invoices = load_invoices()
    invoices.append(invoice)
    _save_invoices(invoices)

    return invoice


def update_invoice_status(invoice_id: str, new_status: str) -> bool:
    """Update invoice status (draft, sent, paid, overdue, void). Returns True if found."""
    invoices = load_invoices()
    for inv in invoices:
        if inv.get("id") == invoice_id:
            inv["status"] = new_status
            if new_status == "paid":
                inv["amount_paid"] = inv.get("total", 0)
                inv["payments"].append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "amount": inv.get("total", 0) - inv.get("amount_paid", 0),
                })
            _save_invoices(invoices)
            return True
    return False


def void_invoice(invoice_id: str) -> bool:
    """
    Void an invoice and un-bill its time entries and expenses.
    Returns True if found.
    """
    invoices = load_invoices()
    target = None
    for inv in invoices:
        if inv.get("id") == invoice_id:
            target = inv
            break
    if not target:
        return False

    case_id = target.get("case_id", "")

    # Un-bill time entries
    if case_id:
        time_entries = load_time_entries(case_id)
        for t in time_entries:
            if t.get("billed_invoice_id") == invoice_id:
                t["billed_invoice_id"] = ""
        _save_time_entries(case_id, time_entries)

        # Un-bill expenses
        expenses = load_expenses(case_id)
        for e in expenses:
            if e.get("billed_invoice_id") == invoice_id:
                e["billed_invoice_id"] = ""
        _save_expenses(case_id, expenses)

    target["status"] = "void"
    _save_invoices(invoices)
    return True


def get_invoice(invoice_id: str) -> Optional[Dict]:
    """Get a single invoice by ID."""
    for inv in load_invoices():
        if inv.get("id") == invoice_id:
            return inv
    return None


# ===================================================================
#  5.  AGGREGATION & REPORTING
# ===================================================================

def get_unbilled_time(case_id: str) -> List[Dict]:
    """Get time entries not yet billed for a case."""
    return [
        t for t in load_time_entries(case_id)
        if not t.get("billed_invoice_id") and t.get("billable", True)
    ]


def get_unbilled_expenses(case_id: str) -> List[Dict]:
    """Get expenses not yet billed for a case."""
    return [
        e for e in load_expenses(case_id)
        if not e.get("billed_invoice_id")
    ]


def get_case_billing_summary(case_id: str) -> Dict:
    """
    Get billing summary for a single case.
    Returns totals for time, expenses, billed, and unbilled amounts.
    """
    time_entries = load_time_entries(case_id)
    expenses = load_expenses(case_id)

    total_hours = sum(t.get("duration_hours", 0) for t in time_entries)
    billable_hours = sum(
        t.get("duration_hours", 0) for t in time_entries if t.get("billable", True)
    )
    billable_amount = sum(
        t.get("duration_hours", 0) * t.get("rate", 0)
        for t in time_entries
        if t.get("billable", True)
    )
    billed_amount = sum(
        t.get("duration_hours", 0) * t.get("rate", 0)
        for t in time_entries
        if t.get("billed_invoice_id")
    )
    unbilled_amount = billable_amount - billed_amount

    total_expenses = sum(e.get("amount", 0) for e in expenses)
    billed_expenses = sum(
        e.get("amount", 0) for e in expenses if e.get("billed_invoice_id")
    )
    unbilled_expenses = total_expenses - billed_expenses

    return {
        "total_hours": round(total_hours, 2),
        "billable_hours": round(billable_hours, 2),
        "billable_amount": round(billable_amount, 2),
        "billed_amount": round(billed_amount, 2),
        "unbilled_amount": round(unbilled_amount, 2),
        "total_expenses": round(total_expenses, 2),
        "billed_expenses": round(billed_expenses, 2),
        "unbilled_expenses": round(unbilled_expenses, 2),
        "time_entry_count": len(time_entries),
        "expense_count": len(expenses),
    }


def get_firm_billing_stats(case_mgr) -> Dict:
    """
    Firm-wide billing statistics across all cases.
    Returns aggregate metrics for dashboard display.
    """
    all_cases = case_mgr.list_cases(include_archived=False)
    invoices = load_invoices()

    total_unbilled_hours = 0.0
    total_unbilled_amount = 0.0
    total_unbilled_expenses = 0.0
    total_billable_hours = 0.0

    for case in all_cases:
        cid = case.get("id", "")
        summary = get_case_billing_summary(cid)
        total_unbilled_hours += summary.get("unbilled_amount", 0) / max(
            load_billing_settings().get("default_rate", 350), 1
        )
        total_unbilled_amount += summary.get("unbilled_amount", 0)
        total_unbilled_expenses += summary.get("unbilled_expenses", 0)
        total_billable_hours += summary.get("billable_hours", 0)

    # Invoice stats
    active_invoices = [i for i in invoices if i.get("status") not in ("void", "paid")]
    outstanding_total = sum(
        i.get("total", 0) - i.get("amount_paid", 0) for i in active_invoices
    )
    paid_invoices = [i for i in invoices if i.get("status") == "paid"]
    total_collected = sum(i.get("amount_paid", 0) for i in paid_invoices)

    # This month's revenue
    this_month = datetime.now().strftime("%Y-%m")
    monthly_paid = [
        i for i in paid_invoices
        if i.get("date_created", "").startswith(this_month)
    ]
    monthly_revenue = sum(i.get("amount_paid", 0) for i in monthly_paid)

    # Overdue invoices
    today_str = datetime.now().strftime("%Y-%m-%d")
    overdue = [
        i for i in invoices
        if i.get("status") == "sent" and i.get("due_date", "9999") < today_str
    ]

    return {
        "total_billable_hours": round(total_billable_hours, 2),
        "unbilled_hours": round(total_unbilled_hours, 2),
        "unbilled_amount": round(total_unbilled_amount, 2),
        "unbilled_expenses": round(total_unbilled_expenses, 2),
        "outstanding_invoices": len(active_invoices),
        "outstanding_total": round(outstanding_total, 2),
        "total_collected": round(total_collected, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "overdue_count": len(overdue),
        "overdue_total": round(
            sum(i.get("total", 0) - i.get("amount_paid", 0) for i in overdue), 2
        ),
        "total_invoices": len(invoices),
        "draft_count": sum(1 for i in invoices if i.get("status") == "draft"),
    }


# ===================================================================
#  6.  INVOICE PDF EXPORT
# ===================================================================

def generate_invoice_pdf(invoice_id: str) -> Optional[io.BytesIO]:
    """
    Render a professional invoice PDF using fpdf2.
    Returns BytesIO or None if invoice not found.
    """
    from fpdf import FPDF

    inv = get_invoice(invoice_id)
    if not inv:
        return None

    settings = load_billing_settings()

    class InvoicePDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 18)
            self.cell(0, 10, settings.get("firm_name", "Law Firm"), ln=True)
            addr = settings.get("firm_address", "")
            if addr:
                self.set_font("Helvetica", "", 9)
                for line in addr.split("\n"):
                    self.cell(0, 4, line.strip(), ln=True)
            phone = settings.get("firm_phone", "")
            email = settings.get("firm_email", "")
            if phone or email:
                self.set_font("Helvetica", "", 9)
                self.cell(0, 4, " | ".join(filter(None, [phone, email])), ln=True)
            self.ln(4)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128)
            self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    pdf = InvoicePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # -- Invoice title bar --
    pdf.set_fill_color(30, 58, 95)
    pdf.set_text_color(255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"  INVOICE  {inv.get('id', '')}", fill=True, ln=True)
    pdf.set_text_color(0)
    pdf.ln(3)

    # -- Meta columns --
    pdf.set_font("Helvetica", "", 10)
    col_w = pdf.w / 2 - pdf.l_margin
    y_top = pdf.get_y()

    # Left: bill-to
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_w, 6, "BILL TO:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(col_w, 5, inv.get("client_name", "---"), ln=True)
    pdf.cell(col_w, 5, f"Case: {inv.get('case_name', inv.get('case_id', ''))}", ln=True)
    y_left = pdf.get_y()

    # Right: dates
    pdf.set_y(y_top)
    pdf.set_x(pdf.w / 2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_w, 6, "DETAILS:", ln=True)
    pdf.set_x(pdf.w / 2)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(col_w, 5, f"Date: {inv.get('date_created', '')}", ln=True)
    pdf.set_x(pdf.w / 2)
    pdf.cell(col_w, 5, f"Due: {inv.get('due_date', '')}", ln=True)
    pdf.set_x(pdf.w / 2)
    status_label = inv.get("status", "draft").upper()
    pdf.cell(col_w, 5, f"Status: {status_label}", ln=True)
    y_right = pdf.get_y()
    pdf.set_y(max(y_left, y_right) + 4)

    # -- Line items table --
    # Time entries
    case_id = inv.get("case_id", "")
    time_ids = set(inv.get("time_entry_ids", []))
    exp_ids = set(inv.get("expense_ids", []))
    time_entries = [t for t in load_time_entries(case_id) if t.get("id") in time_ids]
    expenses = [e for e in load_expenses(case_id) if e.get("id") in exp_ids]

    # Table header
    pdf.set_fill_color(230, 235, 240)
    pdf.set_font("Helvetica", "B", 9)
    widths = [70, 30, 25, 25, 25]
    headers = ["Description", "Date", "Hours", "Rate", "Amount"]
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 7, h, border=1, fill=True, align="C" if i > 0 else "L")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    # Time entry rows
    for t in time_entries:
        desc = t.get("description", "")[:55]
        date = t.get("date", "")
        hrs = t.get("duration_hours", 0)
        rate = t.get("rate", 0)
        amt = hrs * rate
        pdf.cell(widths[0], 6, desc, border=1)
        pdf.cell(widths[1], 6, date, border=1, align="C")
        pdf.cell(widths[2], 6, f"{hrs:.2f}", border=1, align="R")
        pdf.cell(widths[3], 6, f"${rate:,.0f}", border=1, align="R")
        pdf.cell(widths[4], 6, f"${amt:,.2f}", border=1, align="R")
        pdf.ln()

    # Expense rows
    if expenses:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(sum(widths), 7, "Expenses", border=1, fill=True, ln=True)
        pdf.set_font("Helvetica", "", 9)
        for e in expenses:
            desc = f"{e.get('category', '')} --- {e.get('description', '')}"[:55]
            date = e.get("date", "")
            amt = e.get("amount", 0)
            pdf.cell(widths[0], 6, desc, border=1)
            pdf.cell(widths[1], 6, date, border=1, align="C")
            pdf.cell(widths[2], 6, "", border=1)
            pdf.cell(widths[3], 6, "", border=1)
            pdf.cell(widths[4], 6, f"${amt:,.2f}", border=1, align="R")
            pdf.ln()

    pdf.ln(2)

    # -- Totals --
    tot_x = pdf.w - pdf.r_margin - 80
    pdf.set_font("Helvetica", "", 10)
    for label, val in [
        ("Subtotal --- Fees", inv.get("subtotal_fees", 0)),
        ("Subtotal --- Expenses", inv.get("subtotal_expenses", 0)),
    ]:
        pdf.set_x(tot_x)
        pdf.cell(45, 6, label, border=0)
        pdf.cell(35, 6, f"${val:,.2f}", border=0, align="R", ln=True)

    if inv.get("tax_rate"):
        pdf.set_x(tot_x)
        pdf.cell(45, 6, f"Tax ({inv['tax_rate']}%)", border=0)
        pdf.cell(35, 6, f"${inv.get('tax_amount', 0):,.2f}", border=0, align="R", ln=True)

    pdf.set_x(tot_x)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(45, 8, "TOTAL DUE", border="T")
    pdf.cell(35, 8, f"${inv.get('total', 0):,.2f}", border="T", align="R", ln=True)

    # -- Notes --
    notes = inv.get("notes", "")
    if notes:
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(80)
        pdf.multi_cell(0, 5, f"Notes: {notes}")
        pdf.set_text_color(0)

    # -- Payment terms --
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    terms = settings.get("payment_terms_days", 30)
    pdf.cell(0, 5, f"Payment is due within {terms} days of invoice date. Thank you for your business.", ln=True)

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf


# ===================================================================
#  7.  INVOICE EMAIL
# ===================================================================

def email_invoice(invoice_id: str, recipient_email: str) -> Dict:
    """
    Email an invoice PDF as attachment via SMTP.
    Returns {"ok": True/False, "message": str}.
    SMTP settings come from billing_settings: smtp_host, smtp_port,
    smtp_user, smtp_password, from_email.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders

    settings = load_billing_settings()
    smtp_host = settings.get("smtp_host", "")
    smtp_port = int(settings.get("smtp_port", 587))
    smtp_user = settings.get("smtp_user", "")
    smtp_pass = settings.get("smtp_password", "")
    from_addr = settings.get("from_email", smtp_user)

    if not smtp_host or not smtp_user:
        return {"ok": False, "message": "SMTP not configured. Set host/user in Billing Settings > Email."}

    inv = get_invoice(invoice_id)
    if not inv:
        return {"ok": False, "message": f"Invoice {invoice_id} not found."}

    pdf_buf = generate_invoice_pdf(invoice_id)
    if not pdf_buf:
        return {"ok": False, "message": "Failed to generate PDF."}

    firm = settings.get("firm_name", "Law Firm")
    subject = f"Invoice {inv['id']} -- {firm}"
    body = (
        f"Dear {inv.get('client_name', 'Client')},\n\n"
        f"Please find attached invoice {inv['id']} for ${inv.get('total', 0):,.2f}.\n"
        f"Payment is due by {inv.get('due_date', 'N/A')}.\n\n"
        f"Thank you,\n{firm}"
    )

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "pdf")
    part.set_payload(pdf_buf.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={inv['id']}.pdf")
    msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        # Auto-mark as sent
        if inv.get("status") == "draft":
            update_invoice_status(invoice_id, "sent")
        return {"ok": True, "message": f"Invoice emailed to {recipient_email}."}
    except Exception as exc:
        return {"ok": False, "message": f"Email failed: {exc}"}


# ---- Retainer Management ---------------------------------------------------

_RETAINER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "data", "cases")


def _retainer_path(case_id: str) -> str:
    return os.path.join(_RETAINER_DIR, case_id, "retainer.json")


def _load_retainer(case_id: str) -> list:
    path = _retainer_path(case_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_retainer(case_id: str, entries: list):
    path = _retainer_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False, default=str)


def add_retainer_deposit(
    case_id: str,
    amount: float,
    date_str: str = "",
    note: str = "",
) -> str:
    """Record a retainer deposit. Returns entry ID."""
    entries = _load_retainer(case_id)
    entry_id = uuid.uuid4().hex[:8]
    entries.append({
        "id": entry_id,
        "type": "deposit",
        "amount": round(amount, 2),
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "note": note.strip(),
        "created_at": datetime.now().isoformat(),
    })
    _save_retainer(case_id, entries)
    return entry_id


def add_retainer_draw(
    case_id: str,
    amount: float,
    invoice_id: str = "",
    date_str: str = "",
    note: str = "",
) -> str:
    """Record a retainer draw (deduction for billed work). Returns entry ID."""
    entries = _load_retainer(case_id)
    entry_id = uuid.uuid4().hex[:8]
    entries.append({
        "id": entry_id,
        "type": "draw",
        "amount": round(amount, 2),
        "invoice_id": invoice_id,
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "note": note.strip(),
        "created_at": datetime.now().isoformat(),
    })
    _save_retainer(case_id, entries)
    return entry_id


def load_retainer_history(case_id: str) -> list:
    """Load full retainer transaction history."""
    return _load_retainer(case_id)


def get_retainer_balance(case_id: str) -> float:
    """Current retainer balance = deposits - draws."""
    entries = _load_retainer(case_id)
    balance = 0.0
    for e in entries:
        if e.get("type") == "deposit":
            balance += e.get("amount", 0)
        elif e.get("type") == "draw":
            balance -= e.get("amount", 0)
    return round(balance, 2)


# ---- Payment Recording ----------------------------------------------------

def record_payment(
    invoice_id: str,
    amount: float,
    date_str: str = "",
    method: str = "",
    note: str = "",
) -> bool:
    """Record a payment against an invoice. Returns True on success."""
    invoices = load_invoices()
    for inv in invoices:
        if inv.get("id") == invoice_id:
            payments = inv.get("payments", [])
            payments.append({
                "id": uuid.uuid4().hex[:8],
                "amount": round(amount, 2),
                "date": date_str or datetime.now().strftime("%Y-%m-%d"),
                "method": method,
                "note": note.strip(),
                "recorded_at": datetime.now().isoformat(),
            })
            inv["payments"] = payments
            # Auto-update status
            total_paid = sum(p.get("amount", 0) for p in payments)
            if total_paid >= inv.get("total", 0):
                inv["status"] = "paid"
            _save_invoices(invoices)
            return True
    return False


def get_payment_history(invoice_id: str) -> list:
    """Get payment history for an invoice."""
    inv = get_invoice(invoice_id)
    if inv:
        return inv.get("payments", [])
    return []


def get_invoice_balance(invoice_id: str) -> float:
    """Invoice total minus sum of payments."""
    inv = get_invoice(invoice_id)
    if not inv:
        return 0.0
    total = inv.get("total", 0)
    payments = inv.get("payments", [])
    paid = sum(p.get("amount", 0) for p in payments)
    return round(total - paid, 2)


def get_aging_report() -> dict:
    """Get invoices grouped by aging buckets (30/60/90+ days)."""
    invoices = load_invoices()
    today = datetime.now()
    buckets = {"current": [], "30_days": [], "60_days": [], "90_plus": []}

    for inv in invoices:
        if inv.get("status") in ("paid", "void"):
            continue
        created = inv.get("date_created", "")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created)
            days = (today - created_dt).days
        except (ValueError, TypeError):
            continue

        inv_summary = {
            "id": inv.get("id"),
            "case_name": inv.get("case_name", ""),
            "client_name": inv.get("client_name", ""),
            "total": inv.get("total", 0),
            "balance": get_invoice_balance(inv["id"]),
            "days_outstanding": days,
            "status": inv.get("status", ""),
        }

        if days <= 30:
            buckets["current"].append(inv_summary)
        elif days <= 60:
            buckets["30_days"].append(inv_summary)
        elif days <= 90:
            buckets["60_days"].append(inv_summary)
        else:
            buckets["90_plus"].append(inv_summary)

    return buckets
