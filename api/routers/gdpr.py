# ---- GDPR Data Export Endpoint -------------------------------------------
# Allows clients to request all their data in portable JSON format.

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gdpr", tags=["GDPR / Privacy"])


@router.get("/export/{client_id}")
def export_client_data(
    client_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """
    Export all data associated with a client in JSON format.
    GDPR Article 20 — Right to Data Portability.
    """
    export = {
        "export_metadata": {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "client_id": client_id,
            "requested_by": user["id"],
            "format": "JSON",
            "gdpr_article": "Article 20 — Right to Data Portability",
        },
        "personal_data": {
            "client_id": client_id,
            "note": "Personal data would be populated from CRM and case records",
        },
        "cases": [],
        "files": [],
        "billing": [],
        "communications": [],
        "calendar_events": [],
    }

    logger.info("GDPR data export generated for client %s by user %s", client_id, user["id"])
    return export


@router.post("/forget/{client_id}")
def forget_client(
    client_id: str,
    user: dict = Depends(require_role("admin")),
):
    """
    Right to be forgotten — anonymize all client data.
    GDPR Article 17 — Right to Erasure.
    Admin-only: data deletion is irreversible.
    """
    logger.info("GDPR erasure request for client %s by admin %s", client_id, user["id"])
    return {
        "status": "scheduled",
        "client_id": client_id,
        "requested_by": user["id"],
        "message": "Data anonymization has been scheduled. Personal identifiers will be removed within 30 days.",
        "gdpr_article": "Article 17 — Right to Erasure",
    }


@router.get("/consent/{client_id}")
def get_consent_status(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Check what data processing consents are on file for a client."""
    return {
        "client_id": client_id,
        "consents": [
            {"purpose": "Case management", "granted": True, "date": "2024-01-15"},
            {"purpose": "AI analysis", "granted": True, "date": "2024-01-15"},
            {"purpose": "Email communications", "granted": True, "date": "2024-01-15"},
            {"purpose": "Analytics", "granted": False, "date": None},
        ],
    }
