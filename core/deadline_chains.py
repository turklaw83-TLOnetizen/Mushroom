"""
deadline_chains.py -- Deadline Chain Calculator for Morning Brief

Given a single triggering event (e.g., "Motion to Suppress filed March 10"),
generates the entire downstream deadline chain based on jurisdictional rules.

An attorney enters ONE event and the system auto-generates all downstream
deadlines, then creates calendar events and/or tasks for each deadline.

Example:
    "Motion to Suppress filed March 10" ->
        Response due: March 24 (14 days)
        Reply to response: March 31 (7 days after response)
        Hearing window opens: April 7 (14 days after reply)
"""

import logging
import secrets
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")

CHAIN_CATEGORIES = ["criminal", "civil", "discovery", "trial_prep", "appellate"]

# ---------------------------------------------------------------------------
# Built-in chain templates
# ---------------------------------------------------------------------------
# Each step's `from_step` is either "trigger" (offset from the trigger date)
# or an integer index referencing a previous step's computed date.
# ---------------------------------------------------------------------------

_CHAIN_TEMPLATES: List[Dict] = [
    # ── Criminal ──────────────────────────────────────────────────────────
    {
        "id": "motion_to_suppress",
        "name": "Motion to Suppress",
        "category": "criminal",
        "jurisdiction": "general",
        "description": (
            "Generates response, reply, and hearing deadlines for a "
            "motion to suppress evidence."
        ),
        "trigger_event": "Motion to Suppress filed",
        "steps": [
            {
                "label": "Response to Motion to Suppress Due",
                "offset_days": 14,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Reply to Response Due",
                "offset_days": 7,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Hearing Window Opens",
                "offset_days": 14,
                "from_step": 1,
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "motion_to_dismiss",
        "name": "Motion to Dismiss",
        "category": "criminal",
        "jurisdiction": "general",
        "description": (
            "Generates response, reply, and hearing deadlines for a "
            "motion to dismiss charges."
        ),
        "trigger_event": "Motion to Dismiss filed",
        "steps": [
            {
                "label": "Response to Motion to Dismiss Due",
                "offset_days": 14,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Reply to Response Due",
                "offset_days": 7,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Hearing on Motion to Dismiss",
                "offset_days": 21,
                "from_step": 1,
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "arraignment",
        "name": "Arraignment",
        "category": "criminal",
        "jurisdiction": "general",
        "description": (
            "Post-arraignment chain: discovery request, preliminary "
            "motions deadline, and trial date target."
        ),
        "trigger_event": "Arraignment held",
        "steps": [
            {
                "label": "Discovery Request Due",
                "offset_days": 10,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": True,
            },
            {
                "label": "Preliminary Motions Deadline",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Target Trial Date",
                "offset_days": 90,
                "from_step": "trigger",
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "plea_offer",
        "name": "Plea Offer Received",
        "category": "criminal",
        "jurisdiction": "general",
        "description": (
            "Client review period, response deadline, and follow-up "
            "status conference after a plea offer."
        ),
        "trigger_event": "Plea offer received",
        "steps": [
            {
                "label": "Client Review Period Ends",
                "offset_days": 14,
                "from_step": "trigger",
                "category": "Client Meeting",
                "is_business_days": False,
            },
            {
                "label": "Response to Plea Offer Due",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Status Conference",
                "offset_days": 7,
                "from_step": 1,
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "bail_hearing",
        "name": "Bail / Bond Hearing",
        "category": "criminal",
        "jurisdiction": "general",
        "description": (
            "Expedited hearing deadline after bail/bond motion filed "
            "(5 business days)."
        ),
        "trigger_event": "Bail/Bond motion filed",
        "steps": [
            {
                "label": "Bail/Bond Hearing",
                "offset_days": 5,
                "from_step": "trigger",
                "category": "Court Date",
                "is_business_days": True,
            },
        ],
    },

    # ── Civil ─────────────────────────────────────────────────────────────
    {
        "id": "complaint_filed",
        "name": "Complaint Filed (Civil)",
        "category": "civil",
        "jurisdiction": "general",
        "description": (
            "Full civil case timeline from complaint through trial: "
            "answer, initial disclosures, discovery, dispositive motions, "
            "pre-trial conference, and trial."
        ),
        "trigger_event": "Complaint filed / served",
        "steps": [
            {
                "label": "Answer Due",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Initial Disclosures Due",
                "offset_days": 14,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Discovery Deadline",
                "offset_days": 120,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Dispositive Motions Deadline",
                "offset_days": 30,
                "from_step": 2,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Pre-Trial Conference",
                "offset_days": 30,
                "from_step": 3,
                "category": "Court Date",
                "is_business_days": False,
            },
            {
                "label": "Trial",
                "offset_days": 60,
                "from_step": 4,
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "motion_for_summary_judgment",
        "name": "Motion for Summary Judgment",
        "category": "civil",
        "jurisdiction": "general",
        "description": (
            "Response, reply, and hearing deadlines for a motion for "
            "summary judgment."
        ),
        "trigger_event": "Motion for Summary Judgment filed",
        "steps": [
            {
                "label": "Response to MSJ Due",
                "offset_days": 21,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Reply in Support of MSJ Due",
                "offset_days": 14,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Hearing on MSJ",
                "offset_days": 28,
                "from_step": 1,
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "discovery_request",
        "name": "Discovery Request Served",
        "category": "civil",
        "jurisdiction": "general",
        "description": (
            "Response deadline and motion to compel window after a "
            "discovery request is served."
        ),
        "trigger_event": "Discovery request served",
        "steps": [
            {
                "label": "Discovery Response Due",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Motion to Compel Window Opens",
                "offset_days": 14,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "deposition_notice",
        "name": "Deposition Notice",
        "category": "civil",
        "jurisdiction": "general",
        "description": (
            "Deposition date (reasonable notice) and transcript review "
            "period after a deposition notice is served."
        ),
        "trigger_event": "Deposition notice served",
        "steps": [
            {
                "label": "Deposition Date",
                "offset_days": 14,
                "from_step": "trigger",
                "category": "Deposition",
                "is_business_days": False,
            },
            {
                "label": "Transcript Review Period Ends",
                "offset_days": 30,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
        ],
    },

    # ── Discovery ─────────────────────────────────────────────────────────
    {
        "id": "interrogatories_served",
        "name": "Interrogatories Served",
        "category": "discovery",
        "jurisdiction": "general",
        "description": (
            "Response deadline and follow-up window after "
            "interrogatories are served."
        ),
        "trigger_event": "Interrogatories served",
        "steps": [
            {
                "label": "Interrogatory Responses Due",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Follow-Up / Supplementation Deadline",
                "offset_days": 7,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "request_for_production",
        "name": "Request for Production",
        "category": "discovery",
        "jurisdiction": "general",
        "description": (
            "Response deadline and meet-and-confer window for a "
            "request for production of documents."
        ),
        "trigger_event": "Request for Production served",
        "steps": [
            {
                "label": "Production Response Due",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Meet and Confer Deadline (if dispute)",
                "offset_days": 14,
                "from_step": 0,
                "category": "Client Meeting",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "subpoena_duces_tecum",
        "name": "Subpoena Duces Tecum",
        "category": "discovery",
        "jurisdiction": "general",
        "description": (
            "Compliance date and motion-to-quash window for a "
            "subpoena duces tecum."
        ),
        "trigger_event": "Subpoena duces tecum issued",
        "steps": [
            {
                "label": "Motion to Quash Deadline",
                "offset_days": 10,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Compliance / Production Date",
                "offset_days": 14,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
        ],
    },

    # ── Trial Prep ────────────────────────────────────────────────────────
    {
        "id": "trial_date_set",
        "name": "Trial Date Set",
        "category": "trial_prep",
        "jurisdiction": "general",
        "description": (
            "Reverse-engineered deadlines from the trial date: "
            "exhibit list, witness list, jury instructions, and "
            "pre-trial conference."
        ),
        "trigger_event": "Trial date set",
        "steps": [
            {
                "label": "Pre-Trial Conference",
                "offset_days": -7,
                "from_step": "trigger",
                "category": "Court Date",
                "is_business_days": False,
            },
            {
                "label": "Jury Instructions Due",
                "offset_days": -7,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Exhibit List Due",
                "offset_days": -14,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Witness List Due",
                "offset_days": -14,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Trial Begins",
                "offset_days": 0,
                "from_step": "trigger",
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
    {
        "id": "witness_disclosed",
        "name": "Witness Disclosed",
        "category": "trial_prep",
        "jurisdiction": "general",
        "description": (
            "Post-disclosure chain: deposition scheduling window "
            "and subpoena service deadline relative to trial."
        ),
        "trigger_event": "Witness disclosed",
        "steps": [
            {
                "label": "Deposition Scheduling Window Closes",
                "offset_days": 30,
                "from_step": "trigger",
                "category": "Deposition",
                "is_business_days": False,
            },
            {
                "label": "Subpoena Service Deadline (est. 10d before trial)",
                "offset_days": 10,
                "from_step": 0,
                "category": "Filing Deadline",
                "is_business_days": True,
            },
        ],
    },

    # ── Appellate ─────────────────────────────────────────────────────────
    {
        "id": "notice_of_appeal",
        "name": "Notice of Appeal Filed",
        "category": "appellate",
        "jurisdiction": "general",
        "description": (
            "Full appellate timeline: transcript order, appellant brief, "
            "appellee brief, reply brief, and oral argument."
        ),
        "trigger_event": "Notice of Appeal filed",
        "steps": [
            {
                "label": "Transcript Order Due",
                "offset_days": 10,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": True,
            },
            {
                "label": "Appellant Brief Due",
                "offset_days": 40,
                "from_step": "trigger",
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Appellee Brief Due",
                "offset_days": 30,
                "from_step": 1,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Reply Brief Due",
                "offset_days": 14,
                "from_step": 2,
                "category": "Filing Deadline",
                "is_business_days": False,
            },
            {
                "label": "Oral Argument (estimated)",
                "offset_days": 30,
                "from_step": 3,
                "category": "Court Date",
                "is_business_days": False,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _calculate_date(
    start_date: str,
    offset_days: int,
    is_business_days: bool = False,
) -> str:
    """Calculate a target date from a start date plus an offset.

    Args:
        start_date: The reference date in YYYY-MM-DD format.
        offset_days: Number of days (or business days) to add.  May be
            negative (for deadlines computed backwards from a future event
            such as a trial date).
        is_business_days: When True, skip weekends (Saturday=5, Sunday=6)
            in the offset count.

    Returns:
        The computed date as a YYYY-MM-DD string.
    """
    dt = date.fromisoformat(start_date)

    if not is_business_days:
        dt += timedelta(days=offset_days)
        return dt.isoformat()

    # Business-day walk: advance one calendar day at a time, counting
    # only weekdays toward the offset.
    direction = 1 if offset_days >= 0 else -1
    remaining = abs(offset_days)
    while remaining > 0:
        dt += timedelta(days=direction)
        if dt.weekday() < 5:  # Mon-Fri
            remaining -= 1

    return dt.isoformat()


def _get_template(chain_id: str) -> Optional[Dict]:
    """Look up a chain template by its ID."""
    for t in _CHAIN_TEMPLATES:
        if t["id"] == chain_id:
            return t
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_chain_categories() -> List[str]:
    """Return the list of deadline chain categories.

    Returns:
        ["criminal", "civil", "discovery", "trial_prep", "appellate"]
    """
    return list(CHAIN_CATEGORIES)


def get_available_chains(
    category: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> List[Dict]:
    """Return all available deadline chain templates.

    Each template dict contains:
        id, name, category, jurisdiction, description, trigger_event,
        steps (list of step definitions).

    Args:
        category: Optional filter -- only return chains in this category.
        jurisdiction: Optional filter -- only return chains for this
            jurisdiction (e.g. "general", "federal", "state_ga").

    Returns:
        A list of chain template dicts, sorted by category then name.
    """
    chains = list(_CHAIN_TEMPLATES)
    if category:
        chains = [c for c in chains if c["category"] == category]
    if jurisdiction:
        chains = [c for c in chains if c["jurisdiction"] == jurisdiction]
    chains.sort(key=lambda c: (c["category"], c["name"]))
    return chains


def generate_chain(
    chain_id: str,
    trigger_date: str,
    case_id: str = "",
    case_name: str = "",
    custom_params: Optional[Dict] = None,
) -> Dict:
    """Generate a complete deadline chain from a trigger date.

    The trigger date is the date of the initiating event (e.g. the date
    a motion was filed).  Each step in the template is resolved to a
    concrete calendar date based on its ``offset_days`` and ``from_step``
    fields.

    Args:
        chain_id: The ID of a built-in template (see ``get_available_chains``).
        trigger_date: The trigger event date in YYYY-MM-DD format.
        case_id: Optional case identifier to associate with the chain.
        case_name: Optional case name for labeling purposes.
        custom_params: Optional dict for overriding individual step offsets.
            Keys like ``"step_0_days"`` replace the ``offset_days`` on the
            corresponding step (zero-indexed).  Keys like ``"step_1_business"``
            (bool) override ``is_business_days`` for that step.

    Returns:
        A dict describing the generated chain::

            {
                "chain_id": "motion_to_suppress",
                "chain_name": "Motion to Suppress",
                "trigger_date": "2026-03-10",
                "trigger_event": "Motion to Suppress filed",
                "case_id": "...",
                "case_name": "...",
                "deadlines": [ ... ],
                "generated_at": "ISO timestamp"
            }

    Raises:
        ValueError: If ``chain_id`` does not match any template, or if
            ``trigger_date`` is not a valid YYYY-MM-DD string.
    """
    template = _get_template(chain_id)
    if template is None:
        raise ValueError(
            f"Unknown chain template '{chain_id}'. "
            f"Use get_available_chains() to list available templates."
        )

    # Validate trigger date
    try:
        date.fromisoformat(trigger_date)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid trigger_date '{trigger_date}': expected YYYY-MM-DD format."
        ) from exc

    custom_params = custom_params or {}

    # Resolve each step to a concrete date.
    # ``computed_dates`` maps step index -> YYYY-MM-DD string.
    computed_dates: Dict[int, str] = {}
    deadlines: List[Dict] = []

    for idx, step in enumerate(template["steps"]):
        # Allow custom overrides for offset and business-day flag
        offset = custom_params.get(f"step_{idx}_days", step["offset_days"])
        is_biz = custom_params.get(
            f"step_{idx}_business", step["is_business_days"]
        )

        # Determine the base date for this step
        from_step = step["from_step"]
        if from_step == "trigger":
            base_date = trigger_date
        elif isinstance(from_step, int) and from_step in computed_dates:
            base_date = computed_dates[from_step]
        else:
            # Fallback: if from_step references a step not yet computed
            # (shouldn't happen with well-formed templates), use trigger.
            logger.warning(
                "Chain '%s' step %d references unknown from_step %r; "
                "falling back to trigger date.",
                chain_id, idx, from_step,
            )
            base_date = trigger_date

        computed_date = _calculate_date(base_date, offset, is_business_days=is_biz)
        computed_dates[idx] = computed_date

        # Calculate total calendar days from trigger for informational purposes
        trigger_dt = date.fromisoformat(trigger_date)
        step_dt = date.fromisoformat(computed_date)
        days_from_trigger = (step_dt - trigger_dt).days

        deadline_id = f"chain_{secrets.token_hex(4)}"
        deadlines.append({
            "id": deadline_id,
            "step_index": idx,
            "label": step["label"],
            "date": computed_date,
            "category": step.get("category", "Other"),
            "days_from_trigger": days_from_trigger,
            "is_business_days": is_biz,
            "from_step": from_step,
            "status": "pending",
        })

    # Sort deadlines chronologically (important for templates with negative
    # offsets like trial_date_set)
    deadlines.sort(key=lambda d: d["date"])

    return {
        "chain_id": chain_id,
        "chain_name": template["name"],
        "trigger_date": trigger_date,
        "trigger_event": template.get("trigger_event", ""),
        "case_id": case_id,
        "case_name": case_name,
        "deadlines": deadlines,
        "generated_at": datetime.now().isoformat(),
    }


def apply_chain(
    data_dir: str,
    chain_result: Dict,
    create_calendar_events: bool = True,
    create_tasks: bool = True,
) -> Dict:
    """Persist a generated chain as calendar events and/or tasks.

    Takes the output dict from ``generate_chain()`` and creates concrete
    records in the calendar and task systems.

    Args:
        data_dir: Root data directory (e.g. ``"data"``).  Used by the
            task system which stores per-case JSON files.
        chain_result: The dict returned by ``generate_chain()``.
        create_calendar_events: If True, create a calendar event for
            each deadline via ``core.calendar_events.add_event()``.
        create_tasks: If True, create a task for each deadline via
            ``core.tasks.add_task()``.  Requires a non-empty ``case_id``
            in the chain result.

    Returns:
        A summary dict::

            {
                "events_created": int,
                "tasks_created": int,
                "event_ids": [str, ...],
                "task_ids": [str, ...],
                "chain_id": str,
                "chain_name": str,
            }
    """
    event_ids: List[str] = []
    task_ids: List[str] = []

    case_id = chain_result.get("case_id", "")
    case_name = chain_result.get("case_name", "")
    chain_name = chain_result.get("chain_name", "")
    trigger_date = chain_result.get("trigger_date", "")
    deadlines = chain_result.get("deadlines", [])

    if create_calendar_events:
        # Lazy import to avoid circular dependency
        from core.calendar_events import add_event  # noqa: F811

        for dl in deadlines:
            description = (
                f"Auto-generated by deadline chain: {chain_name}\n"
                f"Trigger event: {chain_result.get('trigger_event', '')}\n"
                f"Trigger date: {trigger_date}\n"
                f"Days from trigger: {dl.get('days_from_trigger', '?')}"
            )
            if case_name:
                description += f"\nCase: {case_name}"

            eid = add_event(
                title=dl["label"],
                event_type=dl.get("category", "Other"),
                event_date=dl["date"],
                case_id=case_id,
                description=description,
                reminder_days=[7, 3, 1, 0],
            )
            event_ids.append(eid)
            logger.debug(
                "Created calendar event %s for '%s' on %s",
                eid, dl["label"], dl["date"],
            )

    if create_tasks and case_id:
        # Lazy import to avoid circular dependency
        from core.tasks import add_task  # noqa: F811

        # Map deadline categories to task priorities
        _category_priority = {
            "Court Date": "urgent",
            "Filing Deadline": "high",
            "Deposition": "high",
            "Client Meeting": "medium",
            "Mediation": "medium",
            "Consultation": "medium",
            "Internal": "low",
            "Other": "medium",
        }

        # Map deadline categories to task categories
        _category_task_cat = {
            "Court Date": "Court Appearance",
            "Filing Deadline": "Filing",
            "Deposition": "Deposition",
            "Client Meeting": "Client Communication",
            "Mediation": "Other",
            "Consultation": "Client Communication",
            "Internal": "Administrative",
            "Other": "Other",
        }

        for dl in deadlines:
            dl_category = dl.get("category", "Other")
            priority = _category_priority.get(dl_category, "medium")
            task_category = _category_task_cat.get(dl_category, "Other")

            task_desc = (
                f"Deadline chain: {chain_name}\n"
                f"Trigger: {chain_result.get('trigger_event', '')} "
                f"({trigger_date})\n"
                f"Days from trigger: {dl.get('days_from_trigger', '?')}"
            )

            tid = add_task(
                data_dir=data_dir,
                case_id=case_id,
                title=dl["label"],
                description=task_desc,
                priority=priority,
                due_date=dl["date"],
                category=task_category,
                assigned_by="deadline_chain",
            )
            task_ids.append(tid)
            logger.debug(
                "Created task %s for '%s' due %s",
                tid, dl["label"], dl["date"],
            )

    elif create_tasks and not case_id:
        logger.warning(
            "Skipping task creation: no case_id in chain result for '%s'.",
            chain_name,
        )

    summary = {
        "events_created": len(event_ids),
        "tasks_created": len(task_ids),
        "event_ids": event_ids,
        "task_ids": task_ids,
        "chain_id": chain_result.get("chain_id", ""),
        "chain_name": chain_name,
    }

    logger.info(
        "Applied chain '%s': %d events, %d tasks created.",
        chain_name, len(event_ids), len(task_ids),
    )

    return summary


# ---------------------------------------------------------------------------
# Convenience / query helpers
# ---------------------------------------------------------------------------

def preview_chain(chain_id: str, trigger_date: str) -> List[Dict]:
    """Quick preview of a chain without case context.

    Returns just the list of deadline dicts (date + label) for UI
    display before the user commits to applying the chain.

    Args:
        chain_id: Template ID.
        trigger_date: Trigger date in YYYY-MM-DD format.

    Returns:
        List of dicts with keys: label, date, category, days_from_trigger.
    """
    result = generate_chain(chain_id, trigger_date)
    return [
        {
            "label": d["label"],
            "date": d["date"],
            "category": d["category"],
            "days_from_trigger": d["days_from_trigger"],
        }
        for d in result["deadlines"]
    ]


def get_chains_for_category(category: str) -> List[Dict]:
    """Return all chain templates in a given category.

    This is a convenience wrapper around ``get_available_chains(category=...)``.

    Args:
        category: One of the values from ``get_chain_categories()``.

    Returns:
        List of matching chain template dicts.
    """
    return get_available_chains(category=category)


def search_chains(query: str) -> List[Dict]:
    """Search chain templates by name, description, or trigger event.

    Performs a case-insensitive substring match across the name,
    description, and trigger_event fields.

    Args:
        query: Search string.

    Returns:
        List of matching chain template dicts.
    """
    q = query.lower()
    results = []
    for t in _CHAIN_TEMPLATES:
        searchable = " ".join([
            t.get("name", ""),
            t.get("description", ""),
            t.get("trigger_event", ""),
            t.get("category", ""),
        ]).lower()
        if q in searchable:
            results.append(t)
    return results


def get_chain_summary(chain_id: str) -> Optional[Dict]:
    """Return a compact summary of a chain template.

    Useful for tooltips or quick-reference cards in the UI.

    Args:
        chain_id: Template ID.

    Returns:
        Dict with keys: id, name, category, trigger_event, step_count,
        total_span_description; or None if not found.
    """
    template = _get_template(chain_id)
    if template is None:
        return None

    # Compute the total span by generating from a reference date
    try:
        preview = generate_chain(chain_id, "2026-01-01")
        deadlines = preview["deadlines"]
        if deadlines:
            first = date.fromisoformat(deadlines[0]["date"])
            last = date.fromisoformat(deadlines[-1]["date"])
            span_days = (last - first).days
            if span_days <= 0:
                span_desc = "Same day"
            elif span_days < 7:
                span_desc = f"{span_days} day{'s' if span_days != 1 else ''}"
            elif span_days < 30:
                weeks = span_days // 7
                span_desc = f"~{weeks} week{'s' if weeks != 1 else ''}"
            else:
                months = span_days // 30
                span_desc = f"~{months} month{'s' if months != 1 else ''}"
        else:
            span_desc = "No steps"
    except Exception:
        span_desc = "Unknown"

    return {
        "id": template["id"],
        "name": template["name"],
        "category": template["category"],
        "jurisdiction": template["jurisdiction"],
        "trigger_event": template["trigger_event"],
        "step_count": len(template["steps"]),
        "total_span_description": span_desc,
    }
