"""AI document summarization — single doc, batch, key facts extraction."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _get_llm_client():
    """Get the best available LLM client."""
    if os.getenv("ANTHROPIC_API_KEY"):
        import anthropic
        return "anthropic", anthropic.Anthropic()
    if os.getenv("XAI_API_KEY"):
        from openai import OpenAI
        return "xai", OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")
    return None, None


def summarize_document(text: str, max_length: int = 500) -> str:
    """Summarize a single document."""
    provider, client = _get_llm_client()
    if client is None:
        return "No LLM provider configured for summarization."

    prompt = (
        f"Summarize the following legal document in {max_length} words or less. "
        "Focus on key facts, parties, dates, and legal significance.\n\n"
        f"Document:\n{text[:15000]}"
    )

    try:
        if provider == "anthropic":
            resp = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        else:
            resp = client.chat.completions.create(
                model="grok-2-latest", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""
    except Exception as e:
        logger.error("Summarization failed: %s", e)
        return f"Summarization error: {e}"


def summarize_batch(documents: list[dict], max_length: int = 300) -> list[dict]:
    """Summarize multiple documents. Each doc: {id, text, filename}."""
    results = []
    for doc in documents:
        summary = summarize_document(doc.get("text", ""), max_length)
        results.append({
            "id": doc.get("id", ""),
            "filename": doc.get("filename", ""),
            "summary": summary,
        })
    return results


def extract_key_facts(text: str) -> list[str]:
    """Extract key facts as bullet points."""
    provider, client = _get_llm_client()
    if client is None:
        return ["No LLM provider configured."]

    prompt = (
        "Extract the key facts from this legal document as a bulleted list. "
        "Include: parties involved, key dates, claims/charges, amounts, "
        "and any critical legal points.\n\n"
        f"Document:\n{text[:15000]}"
    )

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

        # Parse bullet points
        facts = []
        for line in raw.splitlines():
            line = line.strip().lstrip("•-*").strip()
            if line:
                facts.append(line)
        return facts or [raw]
    except Exception as e:
        logger.error("Fact extraction failed: %s", e)
        return [f"Error: {e}"]
