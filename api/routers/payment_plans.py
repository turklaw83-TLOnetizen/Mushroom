# ---- Payment Plan Router --------------------------------------------------
# CRUD for per-client payment plans (multiple plans per client),
# payment recording, and AI plan generation.

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/crm/clients/{client_id}/payment-plan",
    tags=["Payment Plans"],
)


# ---- Request Models ------------------------------------------------------

class CreatePaymentPlanRequest(BaseModel):
    total_amount: float = Field(..., gt=0)
    down_payment: float = Field(default=0.0, ge=0)
    recurring_amount: float = Field(..., gt=0)
    frequency: str = Field(..., pattern=r"^(weekly|biweekly|monthly)$")
    start_date: str = Field(..., min_length=10, max_length=10)
    client_name: str = Field(default="", max_length=400)
    notes: str = Field(default="", max_length=5000)
    late_fee_amount: float = Field(default=0.0, ge=0)
    late_fee_grace_days: int = Field(default=3, ge=0, le=30)


class UpdatePaymentPlanRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=5000)
    late_fee_amount: Optional[float] = Field(default=None, ge=0)
    late_fee_grace_days: Optional[int] = Field(default=None, ge=0, le=30)
    status: Optional[str] = Field(default=None, pattern=r"^(active|paused|cancelled)$")


class RecordPaymentRequest(BaseModel):
    amount: float = Field(..., gt=0)
    method: str = Field(default="", max_length=50)
    payer_name: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=2000)
    scheduled_payment_id: str = Field(default="", max_length=20)
    date: str = Field(default="", max_length=10)


class AIPaymentPlanRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)
    client_name: str = Field(default="", max_length=400)


# ---- List / Create (no plan_id) ------------------------------------------

@router.get("")
def list_plans(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all payment plans for a client."""
    try:
        from core.billing import load_payment_plans, mark_overdue_payments
        mark_overdue_payments(client_id)
        plans = load_payment_plans(client_id)
        return {"plans": plans}
    except Exception:
        logger.exception("Failed to load payment plans")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
def create_plan(
    client_id: str,
    body: CreatePaymentPlanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new payment plan for a client (multiple allowed)."""
    try:
        from core.billing import create_payment_plan
        user_name = user.get("name", user.get("user_id", ""))
        plan = create_payment_plan(
            client_id=client_id,
            total_amount=body.total_amount,
            down_payment=body.down_payment,
            recurring_amount=body.recurring_amount,
            frequency=body.frequency,
            start_date=body.start_date,
            client_name=body.client_name,
            notes=body.notes,
            late_fee_amount=body.late_fee_amount,
            late_fee_grace_days=body.late_fee_grace_days,
            created_by=user_name,
        )
        return {"status": "created", "plan": plan}
    except Exception:
        logger.exception("Failed to create payment plan")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ai-generate")
async def ai_generate_plan(
    client_id: str,
    body: AIPaymentPlanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Parse natural language into payment plan parameters using AI."""
    try:
        from core.billing import parse_payment_plan_from_text
        result = await asyncio.to_thread(
            parse_payment_plan_from_text,
            body.text,
            client_id,
            body.client_name,
        )
        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])
        return {"status": "parsed", "plan_params": result}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to parse payment plan")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Single Plan Operations (with plan_id) -------------------------------

@router.get("/{plan_id}")
def get_plan(
    client_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific payment plan."""
    try:
        from core.billing import load_payment_plan
        plan = load_payment_plan(client_id, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Payment plan not found")
        return {"plan": plan}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to load payment plan")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{plan_id}")
def update_plan(
    client_id: str,
    plan_id: str,
    body: UpdatePaymentPlanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update payment plan parameters."""
    try:
        from core.billing import update_payment_plan
        updates = body.model_dump(exclude_none=True)
        if not updates:
            return {"status": "no_changes"}
        user_name = user.get("name", user.get("user_id", ""))
        if not update_payment_plan(client_id, plan_id, updates, updated_by=user_name):
            raise HTTPException(status_code=404, detail="No payment plan found")
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update payment plan")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{plan_id}")
def delete_plan(
    client_id: str,
    plan_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a specific payment plan."""
    try:
        from core.billing import delete_payment_plan
        if not delete_payment_plan(client_id, plan_id):
            raise HTTPException(status_code=404, detail="No payment plan found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete payment plan")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{plan_id}/payments")
def record_payment(
    client_id: str,
    plan_id: str,
    body: RecordPaymentRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Record a payment against a specific plan."""
    try:
        from core.billing import record_plan_payment
        user_name = user.get("name", user.get("user_id", ""))
        payment_id = record_plan_payment(
            client_id=client_id,
            plan_id=plan_id,
            amount=body.amount,
            method=body.method,
            payer_name=body.payer_name,
            note=body.note,
            scheduled_payment_id=body.scheduled_payment_id,
            date_str=body.date,
            recorded_by=user_name,
        )
        if not payment_id:
            raise HTTPException(status_code=404, detail="No active payment plan found")
        return {"status": "recorded", "payment_id": payment_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to record payment")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{plan_id}/status")
def plan_status(
    client_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    """Get computed plan status summary for a specific plan."""
    try:
        from core.billing import get_plan_status, mark_overdue_payments
        mark_overdue_payments(client_id)
        return get_plan_status(client_id, plan_id)
    except Exception:
        logger.exception("Failed to get plan status")
        raise HTTPException(status_code=500, detail="Internal server error")
