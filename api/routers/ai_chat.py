# ---- AI Chat Router (Streaming SSE) --------------------------------------
# Contextual AI chat for any case module.
# Uses Server-Sent Events for real-time token streaming.

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/chat",
    tags=["AI Chat"],
)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: str = ""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    context_module: str = "general"  # Which module the user is chatting from
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)


# ---- Streaming Chat Endpoint --------------------------------------------

@router.post("")
async def stream_chat(
    case_id: str,
    prep_id: str,
    body: ChatRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Stream an AI chat response using Server-Sent Events."""
    try:
        from api.deps import get_case_manager, get_config

        cm = get_case_manager()
        state = cm.load_prep_state(case_id, prep_id) or {}
        if not state and not cm.get_case_metadata(case_id):
            raise HTTPException(status_code=404, detail="Case not found")

        config = get_config()
        provider = config.get("llm", {}).get("provider", "anthropic")

        # Build context from the state based on which module the user is on
        context_text = _build_module_context(state, body.context_module, case_id, cm)

        async def event_generator():
            try:
                from core.llm import get_llm, invoke_with_retry_streaming
                from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

                llm = get_llm(provider, max_output_tokens=4096)

                system_prompt = f"""You are a legal AI assistant helping an attorney with case analysis.
You have access to the following case context:

{context_text}

Provide clear, actionable legal analysis. Reference specific facts from the case when relevant.
Be direct and concise. Use markdown formatting for clarity."""

                messages = [SystemMessage(content=system_prompt)]

                # Add conversation history (last 20 messages max for context window)
                for msg in body.history[-20:]:
                    if msg.role == "user":
                        messages.append(HumanMessage(content=msg.content))
                    elif msg.role == "assistant":
                        messages.append(AIMessage(content=msg.content))

                messages.append(HumanMessage(content=body.message))

                # Stream via invoke_with_retry_streaming in a thread
                full_text = ""

                def _stream_sync():
                    return list(invoke_with_retry_streaming(llm, messages))

                chunks = await asyncio.to_thread(_stream_sync)

                for event_type, data in chunks:
                    if event_type == "token":
                        yield f"data: {json.dumps({'type': 'token', 'content': data})}\n\n"
                    elif event_type == "done":
                        full_text = data
                        yield f"data: {json.dumps({'type': 'done', 'content': full_text})}\n\n"

                # Save to chat history
                _save_chat_message(cm, case_id, prep_id, "user", body.message, body.context_module)
                _save_chat_message(cm, case_id, prep_id, "assistant", full_text, body.context_module)

            except Exception as e:
                logger.exception("Chat streaming failed")
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat setup failed")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Chat History --------------------------------------------------------

@router.get("/history")
def get_chat_history(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get chat history for this preparation."""
    try:
        from api.deps import get_case_manager

        cm = get_case_manager()
        history = cm.storage.load_prep_json(case_id, prep_id, "chat_history.json", [])
        return {"messages": history[-100:]}  # Last 100 messages
    except Exception as e:
        logger.exception("Failed to load chat history")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/history")
def clear_chat_history(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Clear chat history for this preparation."""
    try:
        from api.deps import get_case_manager

        cm = get_case_manager()
        cm.storage.save_prep_json(case_id, prep_id, "chat_history.json", [])
        return {"status": "cleared"}
    except Exception as e:
        logger.exception("Failed to clear chat history")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Helpers -------------------------------------------------------------

def _save_chat_message(cm, case_id: str, prep_id: str, role: str, content: str, context_module: str = "") -> None:
    """Append a message to the chat history file (prep-level + case-level)."""
    try:
        history = cm.storage.load_prep_json(case_id, prep_id, "chat_history.json", [])
        history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep only last 200 messages
        if len(history) > 200:
            history = history[-200:]
        cm.storage.save_prep_json(case_id, prep_id, "chat_history.json", history)
    except Exception:
        logger.warning("Failed to save chat message", exc_info=True)

    # Also persist to case-level chat history
    try:
        from core.chat_history import save_message
        save_message(case_id, role, content, prep_id=prep_id, context_module=context_module)
    except Exception:
        logger.warning("Failed to save case-level chat message", exc_info=True)


# ---- Case-Level Chat History Endpoints -----------------------------------

case_chat_router = APIRouter(tags=["AI Chat"])


@case_chat_router.get("/cases/{case_id}/chat/history")
def get_case_chat_history(
    case_id: str,
    prep_id: str = "",
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Get case-level chat history, optionally filtered by prep_id."""
    from core.chat_history import load_history
    return {"messages": load_history(case_id, prep_id, min(limit, 200))}


@case_chat_router.delete("/cases/{case_id}/chat/history")
def clear_case_chat_history(
    case_id: str,
    prep_id: str = "",
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Clear case-level chat history."""
    from core.chat_history import clear_history
    count = clear_history(case_id, prep_id)
    return {"status": "cleared", "messages_removed": count}


# ---- Helpers -------------------------------------------------------------

def _build_module_context(state: dict, module: str, case_id: str, cm: object) -> str:
    """Build contextual information based on which module the user is on."""
    parts = []

    # Always include case summary if available
    if state.get("case_summary"):
        summary = str(state["case_summary"])[:3000]
        parts.append(f"## Case Summary\n{summary}")

    # Module-specific context
    if module == "evidence" or module == "consistency":
        if state.get("consistency_check"):
            items = state["consistency_check"][:10]
            parts.append(f"## Consistency Issues\n{json.dumps(items, indent=2, default=str)[:2000]}")
        if state.get("evidence_foundations"):
            items = state["evidence_foundations"][:10]
            parts.append(f"## Evidence Foundations\n{json.dumps(items, indent=2, default=str)[:2000]}")

    elif module == "witnesses" or module == "cross-exam" or module == "direct-exam":
        if state.get("witnesses"):
            parts.append(f"## Witnesses\n{json.dumps(state['witnesses'][:20], indent=2, default=str)[:2000]}")
        if state.get("cross_examination_plan"):
            parts.append(f"## Cross-Exam Plans\n{str(state['cross_examination_plan'])[:2000]}")

    elif module == "strategy":
        if state.get("strategy_notes"):
            parts.append(f"## Strategy Notes\n{str(state['strategy_notes'])[:2000]}")
        if state.get("devils_advocate_notes"):
            parts.append(f"## Devil's Advocate\n{str(state['devils_advocate_notes'])[:2000]}")

    elif module == "investigation":
        if state.get("investigation_plan"):
            items = state["investigation_plan"][:15]
            parts.append(f"## Investigation Plan\n{json.dumps(items, indent=2, default=str)[:2000]}")

    elif module == "research":
        if state.get("legal_research"):
            parts.append(f"## Legal Research\n{str(state['legal_research'])[:3000]}")

    elif module == "timeline":
        if state.get("timeline"):
            items = state["timeline"][:20]
            parts.append(f"## Timeline\n{json.dumps(items, indent=2, default=str)[:2000]}")

    else:
        # General context — include a bit of everything
        for key in ["strategy_notes", "devils_advocate_notes", "investigation_plan"]:
            if state.get(key):
                val = state[key]
                parts.append(f"## {key.replace('_', ' ').title()}\n{str(val)[:1500]}")

    # Cap total context
    combined = "\n\n".join(parts)
    if len(combined) > 12000:
        combined = combined[:12000] + "\n\n[Context truncated for length]"

    return combined or "No analysis data available yet. The user may be asking general legal questions."
