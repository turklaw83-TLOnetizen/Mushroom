# ---- Statute of Limitations Router ---------------------------------------
# Track and calculate SOL deadlines by case type + jurisdiction.

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/sol", tags=["Statute of Limitations"])


# Common SOL periods (years) by case type — would be a full database in production
SOL_PERIODS: dict[str, dict[str, int]] = {
    "personal_injury": {"default": 2, "CA": 2, "TX": 2, "NY": 3, "FL": 4},
    "medical_malpractice": {"default": 2, "CA": 1, "TX": 2, "NY": 2, "FL": 2},
    "breach_of_contract": {"default": 4, "CA": 4, "TX": 4, "NY": 6, "FL": 5},
    "property_damage": {"default": 3, "CA": 3, "TX": 2, "NY": 3, "FL": 4},
    "employment": {"default": 2, "CA": 2, "TX": 2, "NY": 3, "FL": 4},
    "fraud": {"default": 3, "CA": 3, "TX": 4, "NY": 6, "FL": 4},
    "wrongful_death": {"default": 2, "CA": 2, "TX": 2, "NY": 2, "FL": 2},
    "product_liability": {"default": 2, "CA": 2, "TX": 2, "NY": 3, "FL": 4},
    "defamation": {"default": 1, "CA": 1, "TX": 1, "NY": 1, "FL": 2},
    "criminal": {"default": 0},
}


class SOLCalculation(BaseModel):
    incident_date: str
    case_type: str
    jurisdiction: str = "default"


@router.get("/deadline")
def get_sol_deadline(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get SOL deadline for a case based on stored metadata."""
    try:
        from api.deps import get_case_manager
        cm = get_case_manager()
        case_meta = cm.get_case(case_id)
        if not case_meta:
            raise HTTPException(status_code=404, detail="Case not found")

        case_type = case_meta.get("case_category", "").lower().replace(" ", "_")
        jurisdiction = case_meta.get("jurisdiction", "default")
        incident_date_str = case_meta.get("incident_date", "")

        if not incident_date_str or not case_type:
            return {
                "status": "incomplete",
                "message": "Case needs incident_date and case_category to calculate SOL",
            }

        incident_date = datetime.fromisoformat(incident_date_str)
        periods = SOL_PERIODS.get(case_type, SOL_PERIODS.get("breach_of_contract", {"default": 4}))
        years = periods.get(jurisdiction, periods.get("default", 4))

        deadline = incident_date + timedelta(days=years * 365)
        days_remaining = (deadline - datetime.now()).days

        return {
            "status": "calculated",
            "incident_date": incident_date_str,
            "case_type": case_type,
            "jurisdiction": jurisdiction,
            "sol_years": years,
            "deadline": deadline.isoformat()[:10],
            "days_remaining": days_remaining,
            "is_expired": days_remaining < 0,
            "is_urgent": 0 < days_remaining < 90,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate")
def calculate_sol(
    case_id: str,
    body: SOLCalculation,
    user: dict = Depends(get_current_user),
):
    """Calculate SOL deadline for given parameters."""
    try:
        incident_date = datetime.fromisoformat(body.incident_date)
        case_type = body.case_type.lower().replace(" ", "_")
        periods = SOL_PERIODS.get(case_type, {"default": 4})
        years = periods.get(body.jurisdiction, periods.get("default", 4))

        deadline = incident_date + timedelta(days=years * 365)
        days_remaining = (deadline - datetime.now()).days

        return {
            "case_type": case_type,
            "jurisdiction": body.jurisdiction,
            "sol_years": years,
            "deadline": deadline.isoformat()[:10],
            "days_remaining": days_remaining,
            "is_expired": days_remaining < 0,
            "is_urgent": 0 < days_remaining < 90,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reference")
def sol_reference(
    user: dict = Depends(get_current_user),
):
    """Get SOL reference table for all case types and jurisdictions."""
    return {"periods": SOL_PERIODS}
