# ---- Payment Feed Router --------------------------------------------------
# Primary: ingest forwarded payment notification emails.
# Secondary: upload CSV exports from Chime/Venmo/Cash App.
# Classify, confirm, and record transactions.

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/payment-feed",
    tags=["Payment Feed"],
)


# ---- Request Models ------------------------------------------------------

class ClassifyRequest(BaseModel):
    client_id: str = Field(..., max_length=50)
    plan_id: str = Field(..., max_length=50)


class DismissRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class ReclassifyRequest(BaseModel):
    client_id: str = Field(..., max_length=50)
    plan_id: str = Field(default="", max_length=50)
    client_name: str = Field(default="", max_length=200)


class IngestEmailRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=1000)
    body: str = Field(..., min_length=1, max_length=50000)
    sender_email: str = Field(default="", max_length=500)


# ---- Endpoints -----------------------------------------------------------

@router.post("/ingest-email")
async def ingest_email_endpoint(
    request: IngestEmailRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """
    Ingest a forwarded payment notification email.
    Auto-detects platform (Venmo/Cash App/Chime), parses transaction
    details, classifies to a client, and saves to the feed.
    """
    try:
        from core.payment_feed import ingest_email
        txn = await asyncio.to_thread(
            ingest_email, request.subject, request.body, request.sender_email,
        )
        if not txn:
            return {
                "status": "no_payment_found",
                "message": "Could not extract a payment from this email. "
                           "Make sure it's a Venmo, Cash App, or Chime notification.",
            }
        return {
            "status": "imported",
            "transaction": txn,
            "classified": txn.get("status") == "classified",
            "suggested_client": txn.get("suggested_client_name", ""),
        }
    except Exception:
        logger.exception("Failed to ingest email")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    platform: str = Form(default="generic"),
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Upload a CSV file from a payment platform, parse and classify transactions."""
    try:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        # Read file content
        content = await file.read()
        file_data = content.decode("utf-8", errors="replace")

        from core.payment_feed import import_transactions
        transactions = await asyncio.to_thread(import_transactions, file_data, platform)

        classified = sum(1 for t in transactions if t.get("status") == "classified")
        return {
            "status": "imported",
            "total": len(transactions),
            "classified": classified,
            "unclassified": len(transactions) - classified,
            "transactions": transactions,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to upload and parse CSV")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending")
def list_pending(
    user: dict = Depends(get_current_user),
):
    """List unclassified and classified (but not yet recorded) transactions."""
    try:
        from core.payment_feed import get_unclassified
        return {"items": get_unclassified()}
    except Exception:
        logger.exception("Failed to list pending transactions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/all")
def list_all(
    status: str = "",
    user: dict = Depends(get_current_user),
):
    """List all feed items, optionally filtered by status."""
    try:
        from core.payment_feed import get_feed
        return {"items": get_feed(status_filter=status)}
    except Exception:
        logger.exception("Failed to list feed items")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{txn_id}/classify")
def classify_transaction(
    txn_id: str,
    body: ClassifyRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Confirm a transaction classification and record as a payment."""
    try:
        from core.payment_feed import confirm_and_record
        user_name = user.get("name", user.get("user_id", ""))
        payment_id = confirm_and_record(
            transaction_id=txn_id,
            client_id=body.client_id,
            plan_id=body.plan_id,
            user=user_name,
        )
        if not payment_id:
            raise HTTPException(status_code=404, detail="Transaction not found or already recorded")
        return {"status": "recorded", "payment_id": payment_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to classify transaction")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{txn_id}/dismiss")
def dismiss_transaction(
    txn_id: str,
    body: DismissRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Dismiss a transaction (not a client payment)."""
    try:
        from core.payment_feed import dismiss_transaction as _dismiss
        if not _dismiss(txn_id, body.reason):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"status": "dismissed"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to dismiss transaction")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{txn_id}/reclassify")
def reclassify_transaction(
    txn_id: str,
    body: ReclassifyRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Manually reassign a transaction to a different client."""
    try:
        from core.payment_feed import reclassify_transaction as _reclassify
        if not _reclassify(txn_id, body.client_id, body.plan_id, body.client_name):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"status": "reclassified"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to reclassify transaction")
        raise HTTPException(status_code=500, detail="Internal server error")
