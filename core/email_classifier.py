"""Email classifier — AI-powered email-to-case matching."""

import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage

from core.llm import get_llm

logger = logging.getLogger(__name__)


def classify_email(
    sender: str,
    subject: str,
    body: str,
    cases: list[dict],
) -> dict:
    """Classify an email to a case using AI.

    Args:
        sender: Email sender address
        subject: Email subject
        body: Email body text
        cases: List of {id, name, client_name, description} for matching

    Returns:
        {case_id, confidence, reasoning}
    """
    # First try rule-based matching
    rule_match = _rule_based_match(sender, subject, body, cases)
    if rule_match and rule_match["confidence"] > 0.8:
        return rule_match

    llm = get_llm()
    if llm is None:
        return rule_match or {"case_id": None, "confidence": 0, "reasoning": "No LLM available"}

    case_list = "\n".join(
        f"- ID: {c['id']}, Name: {c.get('name', '')}, Client: {c.get('client_name', '')}"
        for c in cases[:50]
    )

    prompt = (
        "Match this email to the most likely case. Return ONLY JSON:\n"
        '{"case_id": "id or null", "confidence": 0.0-1.0, "reasoning": "brief reason"}\n\n'
        f"From: {sender}\nSubject: {subject}\nBody: {body[:2000]}\n\n"
        f"Cases:\n{case_list}"
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception as e:
        logger.error("Email classification failed: %s", e)

    return rule_match or {"case_id": None, "confidence": 0, "reasoning": "Classification failed"}


def classify_batch(
    emails: list[dict],
    cases: list[dict],
) -> list[dict]:
    """Classify multiple emails."""
    return [
        {
            "email_id": e.get("id", ""),
            **classify_email(
                e.get("sender", ""),
                e.get("subject", ""),
                e.get("body", ""),
                cases,
            ),
        }
        for e in emails
    ]


def _rule_based_match(sender: str, subject: str, body: str, cases: list[dict]) -> Optional[dict]:
    """Simple rule-based matching before LLM."""
    combined = f"{sender} {subject} {body}".lower()

    best_match = None
    best_score = 0

    for case in cases:
        score = 0
        # Check case number/ID in email
        if case["id"].lower() in combined:
            score += 5
        # Check client name
        client = case.get("client_name", "").lower()
        if client and len(client) > 2 and client in combined:
            score += 3
        # Check case name words
        name_words = set(re.findall(r"\w{4,}", case.get("name", "").lower()))
        matches = sum(1 for w in name_words if w in combined)
        score += matches

        if score > best_score:
            best_score = score
            best_match = case

    if best_match and best_score >= 3:
        confidence = min(best_score / 8, 1.0)
        return {
            "case_id": best_match["id"],
            "confidence": round(confidence, 2),
            "reasoning": f"Rule-based match (score: {best_score})",
        }
    return None
