"""Predictive case scoring — outcome and settlement range prediction."""

import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from core.llm import get_llm

logger = logging.getLogger(__name__)


def predict_outcome(case_summary: str, evidence_summary: str = "", witness_summary: str = "") -> dict:
    """Predict case outcome probabilities."""
    llm = get_llm()
    if llm is None:
        return {"error": "No LLM provider configured"}

    prompt = (
        "You are a legal analytics AI. Based on the case information below, predict the outcome.\n\n"
        "Return ONLY valid JSON with this structure:\n"
        '{"win_probability": 0.0-1.0, "lose_probability": 0.0-1.0, "settle_probability": 0.0-1.0, '
        '"confidence": 0.0-1.0, "key_factors": ["factor1", "factor2", ...], '
        '"strengths": ["str1", ...], "weaknesses": ["weak1", ...], '
        '"recommendation": "brief recommendation"}\n\n'
        f"Case Summary:\n{case_summary[:8000]}\n\n"
    )
    if evidence_summary:
        prompt += f"Evidence:\n{evidence_summary[:4000]}\n\n"
    if witness_summary:
        prompt += f"Witnesses:\n{witness_summary[:4000]}\n\n"

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content

        # Extract JSON from response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"error": "Could not parse prediction", "raw": raw[:500]}
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        return {"error": str(e)}


def predict_settlement_range(
    case_summary: str, damages_info: str = "", jurisdiction: str = ""
) -> dict:
    """Estimate settlement value range."""
    llm = get_llm()
    if llm is None:
        return {"error": "No LLM provider configured"}

    prompt = (
        "You are a legal analytics AI specializing in settlement valuation.\n\n"
        "Return ONLY valid JSON:\n"
        '{"low_estimate": number, "mid_estimate": number, "high_estimate": number, '
        '"confidence": 0.0-1.0, "factors": ["factor1", ...], '
        '"comparable_cases": ["case1", ...], "notes": "brief notes"}\n\n'
        f"Case Summary:\n{case_summary[:8000]}\n\n"
    )
    if damages_info:
        prompt += f"Damages Info:\n{damages_info[:4000]}\n\n"
    if jurisdiction:
        prompt += f"Jurisdiction: {jurisdiction}\n\n"

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"error": "Could not parse prediction", "raw": raw[:500]}
    except Exception as e:
        logger.error("Settlement prediction failed: %s", e)
        return {"error": str(e)}
