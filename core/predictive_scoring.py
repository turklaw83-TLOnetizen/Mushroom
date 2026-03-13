# ---- Predictive Case Outcome Scoring ---------------------------------------
# Multi-dimensional case quality assessment using analysis data.
# Unlike readiness scoring (binary: has data or not), this evaluates
# the QUALITY of evidence, witnesses, element coverage, legal authority,
# narrative coherence, and adversarial resilience.
#
# Key design decisions:
#   - NO LLM calls — pure data analysis of existing state. Fast and free.
#   - Concrete signals, not vibes — scores based on countable, measurable data.
#   - Graceful degradation — missing data gets neutral 50 with a note.
#   - Trend tracking — each score snapshot is saved for historical comparison.

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Dimension weights (must sum to 100)
DIMENSION_WEIGHTS = {
    "evidence_strength": 25,
    "witness_reliability": 20,
    "element_coverage": 20,
    "legal_authority": 10,
    "narrative_coherence": 15,
    "adversarial_resilience": 10,
}

_GRADE_THRESHOLDS = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0, "F"),
]

_OVERALL_LABELS = {
    "A": "Strong Case",
    "B": "Moderate Case",
    "C": "Developing Case",
    "D": "Weak Case",
    "F": "Critical Gaps",
}


def _to_grade(score: int) -> str:
    """Convert a 0-100 score to a letter grade."""
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


# ---------------------------------------------------------------------------
# Individual Dimension Scorers
# ---------------------------------------------------------------------------

def _score_evidence_strength(state: dict) -> dict:
    """Score evidence dimension based on foundations data.

    Signals assessed:
    - Number of evidence items identified
    - Presence of admissibility arguments vs attack vectors
    - Any items flagged as weak or with raw fallback
    - Ratio of evidence items to charges
    """
    foundations = state.get("evidence_foundations", [])
    charges = state.get("charges", [])

    signals: List[str] = []
    concerns: List[str] = []

    if not foundations or not isinstance(foundations, list):
        return {
            "score": 30,
            "grade": _to_grade(30),
            "signals": [],
            "concerns": ["No evidence foundations analysis available — run analysis first"],
        }

    # Filter out raw/fallback entries
    real_items = [f for f in foundations if isinstance(f, dict) and not f.get("_raw")]
    raw_items = [f for f in foundations if isinstance(f, dict) and f.get("_raw")]

    item_count = len(real_items)

    if item_count == 0:
        if raw_items:
            return {
                "score": 35,
                "grade": _to_grade(35),
                "signals": ["Evidence analysis produced results but could not be structured"],
                "concerns": ["Evidence foundations could not be parsed into structured items"],
            }
        return {
            "score": 30,
            "grade": _to_grade(30),
            "signals": [],
            "concerns": ["No evidence items identified in analysis"],
        }

    # Base score: more evidence items = better foundation
    if item_count >= 10:
        base = 75
        signals.append(f"Thorough evidence audit: {item_count} exhibits identified")
    elif item_count >= 5:
        base = 60
        signals.append(f"Solid evidence base: {item_count} exhibits identified")
    elif item_count >= 3:
        base = 50
        signals.append(f"Moderate evidence base: {item_count} exhibits identified")
    else:
        base = 40
        concerns.append(f"Limited evidence base: only {item_count} exhibits identified")

    # Bonus: all items have admissibility foundations
    items_with_admissibility = sum(
        1 for f in real_items
        if f.get("admissibility") and len(str(f["admissibility"])) > 20
    )
    if items_with_admissibility == item_count and item_count > 0:
        base += 10
        signals.append("All evidence items have admissibility foundations documented")
    elif items_with_admissibility > 0:
        ratio_pct = int(items_with_admissibility / item_count * 100)
        if ratio_pct < 50:
            concerns.append(f"Only {ratio_pct}% of evidence items have admissibility foundations")

    # Penalty: items with strong attack vectors
    items_with_attacks = sum(
        1 for f in real_items
        if f.get("attack") and len(str(f["attack"])) > 50
    )
    if items_with_attacks > item_count * 0.6:
        base -= 5
        concerns.append(
            f"{items_with_attacks}/{item_count} evidence items have significant attack vectors"
        )

    # Charge coverage ratio
    charge_count = len(charges) if isinstance(charges, list) else 0
    if charge_count > 0 and item_count > 0:
        ratio = item_count / charge_count
        if ratio >= 3:
            base += 5
            signals.append(f"Good evidence-to-charge ratio ({item_count} items for {charge_count} charges)")
        elif ratio < 1:
            base -= 5
            concerns.append(f"Fewer evidence items ({item_count}) than charges ({charge_count})")

    score = max(0, min(100, base))
    return {"score": score, "grade": _to_grade(score), "signals": signals, "concerns": concerns}


def _score_witness_reliability(state: dict) -> dict:
    """Score witness dimension based on witness data and examination plans.

    Signals assessed:
    - Number and type distribution of witnesses
    - Presence of cross/direct examination plans
    - Defense vs prosecution witness balance
    """
    witnesses = state.get("witnesses", [])
    cross_plan = state.get("cross_examination_plan", [])
    direct_plan = state.get("direct_examination_plan", [])

    signals: List[str] = []
    concerns: List[str] = []

    if not witnesses or not isinstance(witnesses, list):
        return {
            "score": 30,
            "grade": _to_grade(30),
            "signals": [],
            "concerns": ["No witnesses identified — run analysis to classify witnesses"],
        }

    real_witnesses = [w for w in witnesses if isinstance(w, dict) and w.get("name")]
    count = len(real_witnesses)

    if count == 0:
        return {
            "score": 30,
            "grade": _to_grade(30),
            "signals": [],
            "concerns": ["Witness list exists but no named witnesses found"],
        }

    # Type distribution
    by_type: Dict[str, int] = {}
    for w in real_witnesses:
        wtype = str(w.get("type", "Unknown")).lower()
        by_type[wtype] = by_type.get(wtype, 0) + 1

    defense_count = by_type.get("defense", 0)
    state_count = by_type.get("state", 0)
    swing_count = by_type.get("swing", 0)

    # Base score from witness count
    if count >= 6:
        base = 65
        signals.append(f"Comprehensive witness list: {count} witnesses identified")
    elif count >= 3:
        base = 55
        signals.append(f"Adequate witness pool: {count} witnesses identified")
    else:
        base = 40
        concerns.append(f"Limited witness pool: only {count} witnesses")

    # Defense witnesses are good
    if defense_count >= 2:
        base += 10
        signals.append(f"{defense_count} defense-favorable witnesses available")
    elif defense_count == 0:
        base -= 5
        concerns.append("No defense-favorable witnesses identified")

    # Swing witnesses are risks
    if swing_count > count * 0.5 and count > 2:
        base -= 5
        concerns.append(f"{swing_count} swing witnesses — unpredictable testimony risk")

    # Examination plans boost score
    has_cross = isinstance(cross_plan, list) and len(cross_plan) > 0
    has_direct = isinstance(direct_plan, list) and len(direct_plan) > 0

    if has_cross and has_direct:
        base += 10
        signals.append("Both cross and direct examination plans prepared")
    elif has_cross:
        base += 5
        signals.append("Cross-examination plan prepared")
    elif has_direct:
        base += 5
        signals.append("Direct examination plan prepared")
    else:
        concerns.append("No examination plans prepared — run cross/direct examination analysis")

    score = max(0, min(100, base))
    return {"score": score, "grade": _to_grade(score), "signals": signals, "concerns": concerns}


def _score_element_coverage(state: dict) -> dict:
    """Score element coverage dimension.

    Signals assessed:
    - Number of legal elements mapped
    - Strength distribution (High/Medium/Low)
    - Element-to-charge coverage
    - Any gaps identified
    """
    elements = state.get("legal_elements", [])
    charges = state.get("charges", [])

    signals: List[str] = []
    concerns: List[str] = []

    if not elements or not isinstance(elements, list):
        return {
            "score": 30,
            "grade": _to_grade(30),
            "signals": [],
            "concerns": ["No legal elements analysis available — run analysis first"],
        }

    real_elements = [e for e in elements if isinstance(e, dict) and not e.get("_raw")]
    if not real_elements:
        return {
            "score": 35,
            "grade": _to_grade(35),
            "signals": [],
            "concerns": ["Elements analysis produced results but could not be structured"],
        }

    elem_count = len(real_elements)

    # Strength distribution
    strength_counts: Dict[str, int] = {}
    for e in real_elements:
        s = str(e.get("strength", "Unknown")).lower()
        strength_counts[s] = strength_counts.get(s, 0) + 1

    high = strength_counts.get("high", 0)
    medium = strength_counts.get("medium", 0)
    low = strength_counts.get("low", 0)

    # Base score from element count and strength
    if elem_count >= 8:
        base = 60
    elif elem_count >= 4:
        base = 50
    else:
        base = 40

    # High-strength elements are concerning for defense (prosecution can prove)
    # Low-strength elements are favorable for defense (prosecution weak)
    total_rated = high + medium + low
    if total_rated > 0:
        # For defense: more "Low" strength = better (prosecution weaker)
        low_ratio = low / total_rated
        high_ratio = high / total_rated

        if low_ratio > 0.5:
            base += 15
            signals.append(f"Prosecution weak on {low}/{total_rated} elements ({int(low_ratio*100)}%)")
        elif low_ratio > 0.3:
            base += 8
            signals.append(f"Some prosecution weakness: {low}/{total_rated} elements rated Low")

        if high_ratio > 0.7:
            base -= 10
            concerns.append(
                f"Prosecution strong on {high}/{total_rated} elements ({int(high_ratio*100)}%) — "
                "significant challenge"
            )
        elif high_ratio > 0.4:
            base -= 5
            concerns.append(f"Prosecution has solid evidence for {high}/{total_rated} elements")

    # Charge coverage
    charge_count = len(charges) if isinstance(charges, list) else 0
    if charge_count > 0:
        covered_charges = set()
        for e in real_elements:
            charge_name = e.get("charge", "")
            if charge_name:
                covered_charges.add(charge_name.lower().strip())

        if len(covered_charges) >= charge_count:
            base += 5
            signals.append(f"All {charge_count} charges have element mapping")
        elif len(covered_charges) > 0:
            concerns.append(
                f"Only {len(covered_charges)}/{charge_count} charges have element mapping"
            )
        else:
            concerns.append("No charges have element mapping")

    score = max(0, min(100, base))
    return {"score": score, "grade": _to_grade(score), "signals": signals, "concerns": concerns}


def _score_legal_authority(state: dict) -> dict:
    """Score legal research dimension.

    Signals assessed:
    - Presence and volume of legal research data
    - Research summary quality
    """
    research_data = state.get("legal_research_data", [])
    research_summary = state.get("research_summary", "")

    signals: List[str] = []
    concerns: List[str] = []

    has_data = isinstance(research_data, list) and len(research_data) > 0
    has_summary = isinstance(research_summary, str) and len(research_summary.strip()) > 50

    if not has_data and not has_summary:
        return {
            "score": 50,
            "grade": _to_grade(50),
            "signals": ["Legal research not yet conducted — neutral score assigned"],
            "concerns": ["Run legal research module for case law analysis"],
        }

    base = 55

    # Data volume
    if has_data:
        data_count = len(research_data)
        if data_count >= 10:
            base += 15
            signals.append(f"Extensive legal research: {data_count} sources identified")
        elif data_count >= 5:
            base += 10
            signals.append(f"Adequate legal research: {data_count} sources")
        else:
            base += 5
            signals.append(f"Limited legal research: {data_count} sources")

    # Summary quality (based on length as proxy)
    if has_summary:
        summary_len = len(research_summary.strip())
        if summary_len >= 1000:
            base += 10
            signals.append("Detailed research summary available")
        elif summary_len >= 300:
            base += 5
            signals.append("Research summary available")
    else:
        concerns.append("No research summary generated")

    score = max(0, min(100, base))
    return {"score": score, "grade": _to_grade(score), "signals": signals, "concerns": concerns}


def _score_narrative_coherence(state: dict) -> dict:
    """Score narrative consistency dimension.

    Signals assessed:
    - Number and severity of contradictions from consistency check
    - Timeline completeness
    - Case summary availability
    """
    consistency = state.get("consistency_check", [])
    timeline = state.get("timeline", [])
    case_summary = state.get("case_summary", "")
    strategy = state.get("strategy_notes", "")

    signals: List[str] = []
    concerns: List[str] = []

    base = 60

    # Case summary
    if not case_summary or not isinstance(case_summary, str) or len(case_summary.strip()) < 50:
        base -= 15
        concerns.append("No case summary available — core narrative not established")
    else:
        signals.append("Case summary established")

    # Strategy
    if strategy and isinstance(strategy, str) and len(strategy.strip()) > 100:
        base += 5
        signals.append("Defense strategy narrative documented")

    # Consistency check — contradictions are bad for narrative
    if isinstance(consistency, list) and len(consistency) > 0:
        real_contradictions = [
            c for c in consistency
            if isinstance(c, dict) and not c.get("_raw")
        ]
        contradiction_count = len(real_contradictions)

        if contradiction_count == 0:
            base += 10
            signals.append("Consistency check found no contradictions")
        elif contradiction_count <= 2:
            base += 5
            signals.append(f"Minor inconsistencies: {contradiction_count} contradictions found")
            concerns.append(f"{contradiction_count} factual contradictions identified — review needed")
        elif contradiction_count <= 5:
            base -= 5
            concerns.append(
                f"{contradiction_count} factual contradictions found — narrative at risk"
            )
        else:
            base -= 15
            concerns.append(
                f"Significant narrative problems: {contradiction_count} contradictions detected"
            )

        # Check for "Major" severity notes
        major = sum(
            1 for c in real_contradictions
            if "major" in str(c.get("notes", "")).lower()
        )
        if major > 0:
            base -= 5
            concerns.append(f"{major} contradictions flagged as major discrepancies")
    else:
        # No consistency check run
        concerns.append("Consistency check not yet run — run to identify contradictions")

    # Timeline completeness
    if isinstance(timeline, list) and len(timeline) > 0:
        real_events = [t for t in timeline if isinstance(t, dict) and t.get("headline")]
        event_count = len(real_events)
        if event_count >= 10:
            base += 5
            signals.append(f"Detailed timeline: {event_count} events mapped")
        elif event_count >= 5:
            base += 3
            signals.append(f"Timeline available: {event_count} events")
        else:
            signals.append(f"Basic timeline: {event_count} events")
    else:
        concerns.append("No timeline available — temporal narrative not established")

    score = max(0, min(100, base))
    return {"score": score, "grade": _to_grade(score), "signals": signals, "concerns": concerns}


def _score_adversarial_resilience(
    state: dict,
    data_dir: Optional[str] = None,
    case_id: Optional[str] = None,
    prep_id: Optional[str] = None,
) -> dict:
    """Score adversarial resilience using War Game data if available.

    Signals assessed:
    - War Game overall score (if sessions exist)
    - Jury verdict from War Game
    - Devil's advocate concern count and severity
    """
    devils_advocate = state.get("devils_advocate_notes", "")

    signals: List[str] = []
    concerns: List[str] = []

    base = 50  # Neutral default when no War Game data

    # Try to load War Game sessions
    war_game_score = None
    war_game_verdict = None

    if data_dir and case_id and prep_id:
        try:
            from core.war_game import load_war_game_sessions, load_war_game_session

            sessions = load_war_game_sessions(data_dir, case_id, prep_id)
            # Use the most recent completed session
            for session_meta in sessions:
                if session_meta.get("status") == "completed" and session_meta.get("overall_score") is not None:
                    war_game_score = session_meta["overall_score"]
                    # Load full session for verdict
                    full_session = load_war_game_session(
                        data_dir, case_id, prep_id, session_meta["id"]
                    )
                    if full_session and full_session.get("report"):
                        war_game_verdict = full_session["report"].get("verdict")
                    break
        except Exception as exc:
            logger.debug("Could not load War Game sessions: %s", exc)

    if war_game_score is not None:
        # Use War Game score directly (it's 0-100)
        base = int(war_game_score)
        signals.append(f"War Game score: {war_game_score}/100")

        if war_game_verdict:
            verdict_lower = str(war_game_verdict).lower()
            if verdict_lower in ("not_guilty", "not_liable"):
                base += 5
                signals.append(f"War Game jury verdict: {war_game_verdict}")
            elif verdict_lower in ("guilty", "liable"):
                base -= 5
                concerns.append(f"War Game jury verdict: {war_game_verdict}")
            elif verdict_lower == "hung":
                signals.append("War Game jury resulted in hung jury — case is contested")
    else:
        signals.append("No War Game sessions completed — run War Game for accurate scoring")

    # Devil's advocate analysis
    if devils_advocate and isinstance(devils_advocate, str) and len(devils_advocate.strip()) > 100:
        base += 5
        signals.append("Devil's advocate analysis completed")

        # Count concern indicators in the text
        concern_indicators = [
            "weakness", "vulnerable", "risk", "gap", "problem",
            "undermine", "exploit", "challenge", "insufficient",
        ]
        da_lower = devils_advocate.lower()
        indicator_count = sum(1 for ind in concern_indicators if ind in da_lower)

        if indicator_count >= 6:
            base -= 10
            concerns.append(
                f"Devil's advocate identified multiple vulnerability areas ({indicator_count} concern indicators)"
            )
        elif indicator_count >= 3:
            base -= 5
            concerns.append(
                f"Devil's advocate flagged some concerns ({indicator_count} concern indicators)"
            )
        elif indicator_count < 2:
            base += 5
            signals.append("Devil's advocate found few exploitable weaknesses")
    else:
        concerns.append("No devil's advocate analysis — run for vulnerability assessment")

    score = max(0, min(100, base))
    return {"score": score, "grade": _to_grade(score), "signals": signals, "concerns": concerns}


# ---------------------------------------------------------------------------
# Main Scoring Function
# ---------------------------------------------------------------------------

def compute_predictive_score(
    state: dict,
    data_dir: Optional[str] = None,
    case_id: Optional[str] = None,
    prep_id: Optional[str] = None,
) -> dict:
    """Compute a multi-dimensional predictive case score.

    Unlike readiness scoring (binary: has data or not), this evaluates
    the QUALITY of each dimension.

    Dimensions (each 0-100):
        1. evidence_strength — Evidence foundations, admissibility, gaps
        2. witness_reliability — Witness pool, types, examination plans
        3. element_coverage — Legal element mapping and prosecution strength
        4. legal_authority — Research data and case law support
        5. narrative_coherence — Consistency, timeline, story strength
        6. adversarial_resilience — War Game scores, devil's advocate

    Args:
        state: The agent state dict with analysis results.
        data_dir: Root data directory (for War Game data access).
        case_id: The case identifier (for War Game data access).
        prep_id: The preparation identifier (for War Game data access).

    Returns:
        Dict with ``overall_score``, ``overall_grade``, ``overall_label``,
        ``dimensions``, ``top_strengths``, ``top_vulnerabilities``,
        ``trend``, ``previous_score``, and ``computed_at``.
    """
    # Compute each dimension
    dimensions = {
        "evidence_strength": _score_evidence_strength(state),
        "witness_reliability": _score_witness_reliability(state),
        "element_coverage": _score_element_coverage(state),
        "legal_authority": _score_legal_authority(state),
        "narrative_coherence": _score_narrative_coherence(state),
        "adversarial_resilience": _score_adversarial_resilience(
            state, data_dir, case_id, prep_id
        ),
    }

    # Compute weighted overall score
    weighted_sum = 0.0
    total_weight = 0.0
    for dim_name, dim_data in dimensions.items():
        weight = DIMENSION_WEIGHTS.get(dim_name, 0)
        weighted_sum += dim_data["score"] * weight
        total_weight += weight

    overall_score = int(weighted_sum / total_weight) if total_weight > 0 else 0
    overall_grade = _to_grade(overall_score)
    overall_label = _OVERALL_LABELS.get(overall_grade, "Unknown")

    # Extract top strengths (highest-scoring signals)
    top_strengths: List[dict] = []
    for dim_name, dim_data in dimensions.items():
        for signal in dim_data.get("signals", []):
            if "not yet" not in signal.lower() and "neutral" not in signal.lower():
                top_strengths.append({
                    "dimension": dim_name,
                    "signal": signal,
                    "impact": dim_data["score"],
                })
    top_strengths.sort(key=lambda s: s["impact"], reverse=True)
    top_strengths = top_strengths[:5]  # Top 5

    # Extract top vulnerabilities (concerns from lowest-scoring dimensions)
    top_vulnerabilities: List[dict] = []
    dim_list = sorted(dimensions.items(), key=lambda d: d[1]["score"])
    for dim_name, dim_data in dim_list:
        for concern in dim_data.get("concerns", []):
            suggested_action = _suggest_action(dim_name, concern)
            top_vulnerabilities.append({
                "dimension": dim_name,
                "concern": concern,
                "suggested_action": suggested_action,
                "impact": dim_data["score"],
            })
    top_vulnerabilities = top_vulnerabilities[:7]  # Top 7

    # Trend: load previous score if available
    trend = None
    previous_score = None
    if data_dir and case_id and prep_id:
        history = load_score_history(data_dir, case_id, prep_id)
        if history:
            previous_score = history[0].get("overall_score")
            if previous_score is not None:
                diff = overall_score - previous_score
                if diff > 3:
                    trend = "improving"
                elif diff < -3:
                    trend = "declining"
                else:
                    trend = "stable"

    return {
        "overall_score": overall_score,
        "overall_grade": overall_grade,
        "overall_label": overall_label,
        "dimensions": dimensions,
        "top_strengths": top_strengths,
        "top_vulnerabilities": top_vulnerabilities,
        "trend": trend,
        "previous_score": previous_score,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _suggest_action(dimension: str, concern: str) -> str:
    """Generate a suggested action for a vulnerability."""
    concern_lower = concern.lower()

    if "run analysis" in concern_lower or "not yet" in concern_lower:
        return "Run the relevant analysis module to generate data"
    if "war game" in concern_lower:
        return "Complete a War Game session for adversarial stress-testing"
    if "consistency" in concern_lower or "contradiction" in concern_lower:
        return "Review contradictions and prepare explanations for each discrepancy"
    if "examination" in concern_lower:
        return "Run cross and direct examination analysis for all witnesses"
    if "timeline" in concern_lower:
        return "Run timeline analysis to establish temporal narrative"
    if "witness" in concern_lower and "limited" in concern_lower:
        return "Investigate additional potential witnesses to strengthen case"
    if "evidence" in concern_lower and "limited" in concern_lower:
        return "Conduct additional evidence discovery and audit"
    if "element" in concern_lower and "gap" in concern_lower:
        return "Focus investigation on elements with insufficient evidence"
    if "research" in concern_lower:
        return "Run legal research module for case law analysis"
    if "prosecution strong" in concern_lower or "prosecution has solid" in concern_lower:
        return "Develop specific defense strategies targeting prosecution's strongest elements"
    if "devil" in concern_lower:
        return "Run devil's advocate analysis for vulnerability assessment"
    if "narrative" in concern_lower or "summary" in concern_lower:
        return "Run case analysis to establish core narrative"

    # Generic fallback based on dimension
    dim_actions = {
        "evidence_strength": "Review and strengthen evidence foundations",
        "witness_reliability": "Prepare witness examination strategies",
        "element_coverage": "Map evidence to each legal element",
        "legal_authority": "Conduct legal research for supporting authority",
        "narrative_coherence": "Address identified inconsistencies and strengthen narrative",
        "adversarial_resilience": "Run War Game to stress-test case under adversarial pressure",
    }
    return dim_actions.get(dimension, "Address the identified concern")


# ---------------------------------------------------------------------------
# Persistence for Trend Tracking
# ---------------------------------------------------------------------------

def _scores_dir(data_dir: str, case_id: str, prep_id: str) -> Path:
    """Return the directory where predictive score snapshots are stored."""
    return Path(data_dir) / "cases" / case_id / "predictive_scores" / prep_id


def save_score_snapshot(
    data_dir: str, case_id: str, prep_id: str, score: dict
) -> str:
    """Save a score snapshot to disk for trend tracking.

    Args:
        data_dir: Root data directory.
        case_id: The case identifier.
        prep_id: The preparation identifier.
        score: The full score dict from ``compute_predictive_score``.

    Returns:
        The snapshot ID (filename stem).
    """
    snapshot_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    ) + "_" + uuid.uuid4().hex[:6]

    # Save a compact version (no need for full dimension details in history)
    snapshot = {
        "id": snapshot_id,
        "overall_score": score.get("overall_score"),
        "overall_grade": score.get("overall_grade"),
        "overall_label": score.get("overall_label"),
        "dimension_scores": {
            dim: data.get("score")
            for dim, data in score.get("dimensions", {}).items()
        },
        "trend": score.get("trend"),
        "computed_at": score.get("computed_at"),
    }

    directory = _scores_dir(data_dir, case_id, prep_id)
    os.makedirs(directory, exist_ok=True)

    path = directory / f"{snapshot_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2, default=str)

    logger.info(
        "Saved predictive score snapshot %s (score=%s) for case %s prep %s",
        snapshot_id, score.get("overall_score"), case_id, prep_id,
    )
    return snapshot_id


def load_score_history(
    data_dir: str, case_id: str, prep_id: str
) -> List[dict]:
    """Load score history for trend analysis, newest first.

    Args:
        data_dir: Root data directory.
        case_id: The case identifier.
        prep_id: The preparation identifier.

    Returns:
        List of score snapshot dicts sorted newest first.
    """
    directory = _scores_dir(data_dir, case_id, prep_id)
    if not directory.exists():
        return []

    snapshots: List[dict] = []
    for fp in directory.glob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                snapshots.append(data)
        except Exception:
            logger.warning("Skipping corrupt score snapshot file %s", fp)
            continue

    snapshots.sort(key=lambda s: s.get("computed_at", ""), reverse=True)
    return snapshots
