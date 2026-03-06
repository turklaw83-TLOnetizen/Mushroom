# ---- Conflict of Interest Router -----------------------------------------
# Check new clients/matters against existing data for conflicts.
# Uses 7-level smart matching from core.ethical_compliance:
#   exact, nickname (156-name map), fuzzy (>= 0.85), initial ("J. Smith"),
#   partial (shared parts), substring, long-fuzzy.
# Critical for bar compliance.

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conflicts", tags=["Conflict Check"])


# ── Request / Response Models ─────────────────────────────────────────

class ConflictCheckRequest(BaseModel):
    party_name: str
    party_type: str = "client"  # client | opposing | witness | other
    company: str = ""
    aliases: list[str] = []


class ConflictResult(BaseModel):
    has_conflict: bool
    matches: list[dict] = []
    match_details: list[dict] = []
    confidence: float = 0.0
    severity: str = "none"  # none | low | potential | confirmed


# ── Helpers ───────────────────────────────────────────────────────────

def _collect_all_entities(cm) -> dict:
    """Gather entities across every case via CaseManager.load_all_entities()."""
    return cm.load_all_entities(include_analysis=True)


def _match_name_against_entities(
    query_name: str,
    all_entities: dict,
    source_label: str = "case_entity",
) -> list[dict]:
    """Run smart_name_match for *query_name* against every entity in every case."""
    from core.ethical_compliance import smart_name_match

    hits: list[dict] = []
    seen = set()

    for case_id, entities in all_entities.items():
        for ent in entities:
            ent_name = ent.get("name", "")
            if not ent_name:
                continue

            match_type, confidence, explanation = smart_name_match(query_name, ent_name)
            if not match_type:
                continue

            dedup_key = f"{ent_name.lower().strip()}|{case_id}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            hits.append({
                "source": source_label,
                "name": ent_name,
                "role": ent.get("role", ""),
                "id": ent.get("id", ""),
                "case_id": case_id,
                "match_type": match_type,
                "confidence": confidence,
                "explanation": explanation,
                "severity": _confidence_to_severity(confidence),
            })

    return hits


def _match_name_against_crm(query_name: str) -> list[dict]:
    """Search CRM clients and run smart_name_match on each hit."""
    from core.crm import search_clients
    from core.ethical_compliance import smart_name_match

    hits: list[dict] = []
    client_hits = search_clients(query_name)
    for hit in client_hits:
        hit_name = hit.get("name", "")
        match_type, confidence, explanation = smart_name_match(query_name, hit_name)
        if not match_type:
            # CRM search returned it so there's *some* match; treat as partial
            match_type = "partial"
            confidence = 0.5
            explanation = f'CRM search match: "{query_name}" ~ "{hit_name}"'

        hits.append({
            "source": "crm_client",
            "name": hit_name,
            "id": hit.get("id", ""),
            "cases": hit.get("cases", []),
            "match_type": match_type,
            "confidence": confidence,
            "explanation": explanation,
            "severity": _confidence_to_severity(confidence),
        })

    return hits


def _match_name_against_prospective(query_name: str) -> list[dict]:
    """Check query_name against prospective client records."""
    from core.ethical_compliance import load_prospective_clients, smart_name_match

    hits: list[dict] = []
    prospective = load_prospective_clients()

    for pc in prospective:
        pc_name = pc.get("name", "")
        if not pc_name:
            continue

        match_type, confidence, explanation = smart_name_match(query_name, pc_name)
        if not match_type:
            continue

        hits.append({
            "source": "prospective_client",
            "name": pc_name,
            "id": pc.get("id", ""),
            "subject": pc.get("subject", ""),
            "date": pc.get("date", pc.get("consultation_date", "")),
            "match_type": match_type,
            "confidence": confidence,
            "explanation": explanation,
            "severity": _confidence_to_severity(confidence),
        })

    return hits


def _confidence_to_severity(confidence: float) -> str:
    """Map a 0-1 confidence score to a severity label."""
    if confidence >= 0.9:
        return "confirmed"
    if confidence >= 0.7:
        return "potential"
    if confidence > 0.0:
        return "low"
    return "none"


def _overall_severity(matches: list[dict]) -> str:
    """Determine the worst severity across all matches."""
    if not matches:
        return "none"
    max_conf = max(m.get("confidence", 0.0) for m in matches)
    return _confidence_to_severity(max_conf)


def _dedup_matches(matches: list[dict]) -> list[dict]:
    """Remove duplicate matches (same name + same source + same case)."""
    seen = set()
    deduped: list[dict] = []
    for m in matches:
        key = (
            m.get("name", "").lower().strip(),
            m.get("source", ""),
            m.get("case_id", m.get("id", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    return deduped


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/check")
def check_conflicts(
    body: ConflictCheckRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """
    Check a party name (+ aliases) against all existing clients, opposing
    parties, witnesses, prospective clients, and CRM records using 7-level
    smart name matching. Returns matches with confidence scores.
    """
    try:
        from api.deps import get_case_manager

        cm = get_case_manager()
        all_entities = _collect_all_entities(cm)

        all_matches: list[dict] = []

        # ── Primary name ──
        all_matches.extend(_match_name_against_entities(body.party_name, all_entities))
        all_matches.extend(_match_name_against_crm(body.party_name))
        all_matches.extend(_match_name_against_prospective(body.party_name))

        # ── Aliases ──
        for alias in body.aliases:
            alias_entity_hits = _match_name_against_entities(
                alias, all_entities, source_label="case_entity_alias",
            )
            for hit in alias_entity_hits:
                hit["alias"] = alias
            all_matches.extend(alias_entity_hits)

            alias_crm_hits = _match_name_against_crm(alias)
            for hit in alias_crm_hits:
                hit["source"] = "crm_alias"
                hit["alias"] = alias
            all_matches.extend(alias_crm_hits)

            alias_prospective_hits = _match_name_against_prospective(alias)
            for hit in alias_prospective_hits:
                hit["alias"] = alias
            all_matches.extend(alias_prospective_hits)

        # ── Company name (if provided) ──
        if body.company:
            company_hits = _match_name_against_entities(
                body.company, all_entities, source_label="company_match",
            )
            all_matches.extend(company_hits)

        # Dedup & sort by confidence descending
        all_matches = _dedup_matches(all_matches)
        all_matches.sort(key=lambda m: m.get("confidence", 0.0), reverse=True)

        has_conflict = len(all_matches) > 0
        severity = _overall_severity(all_matches)
        max_confidence = max(
            (m.get("confidence", 0.0) for m in all_matches), default=0.0
        )

        return ConflictResult(
            has_conflict=has_conflict,
            matches=all_matches,
            match_details=all_matches,
            confidence=max_confidence,
            severity=severity,
        )

    except Exception as e:
        logger.exception("Conflict check failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/smart-search")
def smart_search(
    name: str = Query(..., min_length=2, description="Name to search for"),
    user: dict = Depends(get_current_user),
):
    """
    Real-time smart name lookup across all cases, CRM, and prospective
    clients. Returns matches with confidence scores for frontend type-ahead.
    """
    try:
        from api.deps import get_case_manager

        cm = get_case_manager()
        all_entities = _collect_all_entities(cm)

        results: list[dict] = []
        results.extend(_match_name_against_entities(name, all_entities))
        results.extend(_match_name_against_crm(name))
        results.extend(_match_name_against_prospective(name))

        results = _dedup_matches(results)
        results.sort(key=lambda m: m.get("confidence", 0.0), reverse=True)

        return {
            "query": name,
            "results": results,
            "total": len(results),
            "max_confidence": max(
                (r.get("confidence", 0.0) for r in results), default=0.0
            ),
        }

    except Exception as e:
        logger.exception("Smart search failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
def conflict_history(
    user: dict = Depends(get_current_user),
):
    """List recent conflict checks (audit trail)."""
    # In a production system, this would return stored conflict check results
    return {"items": [], "total": 0}
