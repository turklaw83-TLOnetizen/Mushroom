# ---- Strategy Chat Router ------------------------------------------------
# SSE streaming chat endpoint for case-aware AI conversation.
# Uses core/llm infrastructure for LLM calls.

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/chat", tags=["Chat"])


# ---- Schemas -------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str = "user"  # user | assistant
    content: str = ""
    timestamp: str = ""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    prep_id: str = ""
    history: List[ChatMessage] = Field(default_factory=list)
    system_context: str = ""  # extra instructions


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)


# ---- Endpoints -----------------------------------------------------------

@router.post("/stream")
async def stream_chat(
    case_id: str,
    body: ChatRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Stream a strategy chat response via SSE."""
    import asyncio

    cm = get_case_manager()
    case_data = cm.get_case(case_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found")

    # Build context from case data + analysis results
    context_parts = [
        f"Case: {case_data.get('name', 'Unknown')}",
        f"Type: {case_data.get('case_type', 'N/A')}",
        f"Category: {case_data.get('case_category', 'N/A')}",
        f"Client: {case_data.get('client_name', 'N/A')}",
        f"Jurisdiction: {case_data.get('jurisdiction', 'N/A')}",
        f"Phase: {case_data.get('phase', 'N/A')}",
    ]

    # Include analysis results if prep selected
    prep_context = ""
    if body.prep_id:
        state = cm.load_prep_state(case_id, body.prep_id) or {}
        if state.get("case_summary"):
            prep_context += f"\n\nCase Summary:\n{str(state['case_summary'])[:4000]}"
        if state.get("strategy_notes"):
            prep_context += f"\n\nStrategy Notes:\n{str(state['strategy_notes'])[:3000]}"
        if state.get("witnesses"):
            wit_summary = ", ".join(
                w.get("name", "Unknown") for w in state["witnesses"][:20]
                if isinstance(w, dict)
            )
            prep_context += f"\n\nKey Witnesses: {wit_summary}"

    # Include directives
    directives = cm.load_directives(case_id)
    directives_block = ""
    if directives:
        lines = [f"- [{d.get('category', 'instruction')}] {d.get('text', '')}" for d in directives]
        directives_block = "\n\nAttorney Directives:\n" + "\n".join(lines)

    system_prompt = f"""You are an expert legal strategist working on a case. You help attorneys by providing strategic analysis, case theory development, and tactical recommendations.

Case Information:
{chr(10).join(context_parts)}
{prep_context}
{directives_block}

{body.system_context}

Respond helpfully and concisely. Reference specific case details when relevant. If asked about something not in the case data, say so."""

    # Build messages for LLM
    messages = [{"role": "system", "content": system_prompt}]
    for msg in body.history[-20:]:  # Last 20 messages for context
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    async def event_stream():
        try:
            from core.llm import get_llm
            llm = get_llm()

            # Stream tokens
            full_response = []
            for chunk in llm.stream(messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    full_response.append(token)
                    yield f"data: {json.dumps({'token': token})}\n\n"

            # Save to chat history
            try:
                _save_chat_message(cm, case_id, body.prep_id, "user", body.message)
                _save_chat_message(cm, case_id, body.prep_id, "assistant", "".join(full_response))
            except Exception as save_err:
                logger.warning("Failed to save chat history: %s", save_err)

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.exception("Chat stream error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=ChatHistoryResponse)
def get_chat_history(
    case_id: str,
    prep_id: str = "",
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Get chat history for a case."""
    cm = get_case_manager()
    filename = f"chat_history_{prep_id}.json" if prep_id else "chat_history.json"
    messages = cm.storage.load_json(case_id, filename, [])
    return {"messages": messages[-limit:]}


@router.delete("/history")
def clear_chat_history(
    case_id: str,
    prep_id: str = "",
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Clear chat history for a case."""
    cm = get_case_manager()
    filename = f"chat_history_{prep_id}.json" if prep_id else "chat_history.json"
    cm.storage.save_json(case_id, filename, [])
    return {"status": "cleared"}


# ---- Helpers -------------------------------------------------------------

def _save_chat_message(cm, case_id: str, prep_id: str, role: str, content: str):
    """Append a message to chat history."""
    filename = f"chat_history_{prep_id}.json" if prep_id else "chat_history.json"
    messages = cm.storage.load_json(case_id, filename, [])
    messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 200 messages
    if len(messages) > 200:
        messages = messages[-200:]
    cm.storage.save_json(case_id, filename, messages)
