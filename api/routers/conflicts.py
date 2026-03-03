# ---- Conflict of Interest Router -----------------------------------------
# Check new clients/matters against existing data for conflicts.
# Critical for bar compliance.

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conflicts", tags=["Conflict Check"])


class ConflictCheckRequest(BaseModel):
    party_name: str
    party_type: str = "client"  # client | opposing | witness | other
    company: str = ""
    aliases: list[str] = []


class ConflictResult(BaseModel):
    has_conflict: bool
    matches: list[dict] = []
    severity: str = "none"  # none | potential | confirmed


@router.post("/check")
def check_conflicts(
    body: ConflictCheckRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """
    Check a party name against all existing clients, opposing parties,
    and witnesses across all cases. Returns potential conflicts.
    """
    try:
        from core.crm import search_clients
        from core.search import global_search

        matches = []

        # Search CRM clients
        client_hits = search_clients(body.party_name)
        for hit in client_hits:
            matches.append({
                "source": "crm_client",
                "name": hit.get("name", ""),
                "id": hit.get("id", ""),
                "cases": hit.get("cases", []),
                "match_type": "name",
            })

        # Search across all cases for opposing parties / witnesses
        from api.deps import get_case_manager
        cm = get_case_manager()
        case_hits = global_search(body.party_name, cm)
        for hit in case_hits:
            if hit.get("type") in ("witness", "opposing_party", "case"):
                matches.append({
                    "source": hit.get("type", "case"),
                    "name": hit.get("name", hit.get("title", "")),
                    "id": hit.get("id", ""),
                    "case_id": hit.get("case_id", ""),
                    "match_type": "name",
                })

        # Check aliases
        for alias in body.aliases:
            alias_hits = search_clients(alias)
            for hit in alias_hits:
                matches.append({
                    "source": "crm_alias",
                    "name": hit.get("name", ""),
                    "id": hit.get("id", ""),
                    "cases": hit.get("cases", []),
                    "match_type": "alias",
                    "alias": alias,
                })

        # Determine severity
        has_conflict = len(matches) > 0
        severity = "none"
        if has_conflict:
            severity = "confirmed" if any(m.get("source") == "crm_client" for m in matches) else "potential"

        return ConflictResult(
            has_conflict=has_conflict,
            matches=matches,
            severity=severity,
        )

    except Exception as e:
        logger.exception("Conflict check failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
def conflict_history(
    user: dict = Depends(get_current_user),
):
    """List recent conflict checks (audit trail)."""
    # In a production system, this would return stored conflict check results
    return {"items": [], "total": 0}
