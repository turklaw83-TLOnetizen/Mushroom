"""AI document summarization — single doc, batch, key facts extraction."""

import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from core.llm import get_llm

logger = logging.getLogger(__name__)


def summarize_document(text: str, max_length: int = 500) -> str:
    """Summarize a single document."""
    llm = get_llm()
    if llm is None:
        return "No LLM provider configured for summarization."

    prompt = (
        f"Summarize the following legal document in {max_length} words or less. "
        "Focus on key facts, parties, dates, and legal significance.\n\n"
        f"Document:\n{text[:15000]}"
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
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
    llm = get_llm()
    if llm is None:
        return ["No LLM provider configured."]

    prompt = (
        "Extract the key facts from this legal document as a bulleted list. "
        "Include: parties involved, key dates, claims/charges, amounts, "
        "and any critical legal points.\n\n"
        f"Document:\n{text[:15000]}"
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content

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
