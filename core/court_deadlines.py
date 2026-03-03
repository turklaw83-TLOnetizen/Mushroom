"""Court deadline calculator — jurisdiction-specific rule engine."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Federal holidays (US) 2024-2027
FEDERAL_HOLIDAYS = {
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 10, 12),
    date(2026, 11, 11), date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 5, 31),
    date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 10, 11),
    date(2027, 11, 11), date(2027, 11, 25), date(2027, 12, 24),
}

# Default federal rules (FRCP)
FEDERAL_RULES = {
    "response_to_complaint": {"days": 21, "business_days": False, "description": "Answer to complaint (FRCP 12(a))"},
    "response_to_complaint_us": {"days": 60, "business_days": False, "description": "Answer when US is defendant (FRCP 12(a)(2))"},
    "motion_to_dismiss": {"days": 21, "business_days": False, "description": "Motion to dismiss (FRCP 12(b))"},
    "discovery_cutoff": {"days": 180, "business_days": False, "description": "Default discovery period"},
    "motion_for_summary_judgment": {"days": 30, "business_days": False, "description": "Response to MSJ"},
    "appeal_deadline": {"days": 30, "business_days": False, "description": "Notice of appeal (FRAP 4(a))"},
    "appeal_deadline_criminal": {"days": 14, "business_days": False, "description": "Criminal appeal (FRAP 4(b))"},
    "interrogatories_response": {"days": 30, "business_days": False, "description": "Response to interrogatories (FRCP 33)"},
    "rfa_response": {"days": 30, "business_days": False, "description": "Response to RFA (FRCP 36)"},
    "deposition_notice": {"days": 14, "business_days": False, "description": "Reasonable notice for deposition"},
    "expert_disclosure": {"days": 90, "business_days": False, "description": "Expert report deadline (FRCP 26(a)(2))"},
    "pretrial_motions": {"days": 14, "business_days": False, "description": "Pretrial motions deadline"},
}


def add_business_days(start: date, days: int, holidays: set[date] = None) -> date:
    """Add business days (skip weekends and holidays)."""
    if holidays is None:
        holidays = FEDERAL_HOLIDAYS
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            added += 1
    return current


def calculate_deadline(
    jurisdiction: str,
    rule_type: str,
    trigger_date: date,
    business_days: Optional[bool] = None,
    custom_days: Optional[int] = None,
) -> dict:
    """Calculate a court deadline based on jurisdiction and rule type."""
    # Look up the rule
    rules = FEDERAL_RULES  # Default to federal
    rule = rules.get(rule_type)

    if rule is None:
        return {
            "error": f"Unknown rule type: {rule_type}",
            "available_rules": list(rules.keys()),
        }

    days = custom_days if custom_days is not None else rule["days"]
    use_business = business_days if business_days is not None else rule.get("business_days", False)

    if use_business:
        deadline = add_business_days(trigger_date, days)
    else:
        deadline = trigger_date + timedelta(days=days)
        # If deadline falls on weekend/holiday, move to next business day
        while deadline.weekday() >= 5 or deadline in FEDERAL_HOLIDAYS:
            deadline += timedelta(days=1)

    return {
        "rule_type": rule_type,
        "description": rule["description"],
        "jurisdiction": jurisdiction,
        "trigger_date": trigger_date.isoformat(),
        "deadline": deadline.isoformat(),
        "calendar_days": (deadline - trigger_date).days,
        "business_days_used": use_business,
        "days_from_now": (deadline - date.today()).days,
    }


def get_available_rules(jurisdiction: str = "federal") -> list[dict]:
    """Get all available rules for a jurisdiction."""
    rules = FEDERAL_RULES
    return [
        {"rule_type": k, "days": v["days"], "description": v["description"], "business_days": v.get("business_days", False)}
        for k, v in rules.items()
    ]
