"""Predictive case scoring — outcome and settlement range prediction."""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _get_llm_client():
    if os.getenv("ANTHROPIC_API_KEY"):
        import anthropic
        return "anthropic", anthropic.Anthropic()
    if os.getenv("XAI_API_KEY"):
        from openai import OpenAI
        return "xai", OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")
    return None, None


def predict_outcome(case_summary: str, evidence_summary: str = "", witness_summary: str = "") -> dict:
    """Predict case outcome probabilities."""
    provider, client = _get_llm_client()
    if client is None:
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
        if provider == "anthropic":
            resp = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text
        else:
            resp = client.chat.completions.create(
                model="grok-2-latest", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content or ""

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
    provider, client = _get_llm_client()
    if client is None:
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
        if provider == "anthropic":
            resp = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text
        else:
            resp = client.chat.completions.create(
                model="grok-2-latest", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content or ""

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"error": "Could not parse prediction", "raw": raw[:500]}
    except Exception as e:
        logger.error("Settlement prediction failed: %s", e)
        return {"error": str(e)}
