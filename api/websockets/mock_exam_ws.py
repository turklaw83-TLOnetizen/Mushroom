# ---- Mock Exam WebSocket --------------------------------------------------
# Interactive chat endpoint for mock examination sessions.
# Streams witness responses token-by-token and sends coaching in parallel.

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


async def _authenticate_ws(token: str) -> dict | None:
    """Verify a WebSocket token (same logic as HTTP auth)."""
    if not token:
        return None
    try:
        from api.auth import _verify_clerk_session, _verify_jwt, _get_clerk_secret_key

        if _get_clerk_secret_key():
            claims = await _verify_clerk_session(token)
            if claims:
                return {
                    "id": claims.get("sub", ""),
                    "role": claims.get(
                        "role",
                        claims.get("public_metadata", {}).get("role", "attorney"),
                    ),
                }
        claims = _verify_jwt(token)
        if claims:
            return {"id": claims.get("sub", ""), "role": claims.get("role", "attorney")}
    except Exception:
        pass
    return None


def _find_witness(state: dict, witness_name: str) -> dict:
    """Find a witness in the prep state by name."""
    for w in state.get("witnesses", []):
        if isinstance(w, dict):
            name = w.get("name", w.get("witness", ""))
            if name.lower() == witness_name.lower():
                return w
    return {"name": witness_name, "type": "Unknown"}


def _save_session(cm, case_id: str, prep_id: str, session_id: str, session_data: dict):
    """Persist session data and update index message count."""
    try:
        cm.save_mock_exam_data(case_id, prep_id, session_id, session_data)
        # Update message count in index
        sessions = cm.load_mock_exam_sessions(case_id, prep_id)
        for s in sessions:
            if s.get("id") == session_id:
                s["message_count"] = sum(
                    1 for m in session_data.get("messages", [])
                    if m.get("role") == "attorney"
                )
                break
        cm.save_mock_exam_sessions(case_id, prep_id, sessions)
    except Exception as e:
        logger.error("Failed to save session %s: %s", session_id, e)


@router.websocket("/ws/mock-exam/{case_id}/{prep_id}/{session_id}")
async def mock_exam_chat(
    websocket: WebSocket,
    case_id: str,
    prep_id: str,
    session_id: str,
    token: str = Query(default=""),
):
    """
    Interactive mock examination WebSocket.

    Client sends: {"content": "attorney's question"}
    Server sends:
        {"type": "witness_start"}
        {"type": "witness_token", "token": "..."}
        {"type": "witness_done", "message": {...}}
        {"type": "objection", "message": {...}}
        {"type": "ruling", "ruling": "sustained|overruled", "explanation": "..."}
        {"type": "coaching", "coaching": {...}}
        {"type": "error", "message": "..."}
        {"type": "session_loaded", "messages": [...], "coaching_notes": [...]}
    """
    user = await _authenticate_ws(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(
        "Mock exam WS connected: case=%s prep=%s session=%s user=%s",
        case_id, prep_id, session_id, user.get("id"),
    )

    from api.deps import get_case_manager
    cm = get_case_manager()

    # Load case state and session
    state = cm.load_prep_state(case_id, prep_id) or {}
    session_data = cm.load_mock_exam_data(case_id, prep_id, session_id)
    if not session_data:
        await websocket.send_json({"type": "error", "message": "Session not found."})
        await websocket.close(code=4004, reason="Session not found")
        return

    witness = _find_witness(state, session_data.get("witness_name", ""))

    # Pre-gather document text (one-time, expensive)
    from core.nodes.mock_exam import (
        _gather_witness_document_text,
        analyze_question_for_coaching,
        generate_objection,
        stream_witness_response,
    )
    from core.state import get_case_context

    document_text = await asyncio.to_thread(
        _gather_witness_document_text, case_id, session_data.get("witness_name", ""), state
    )

    # Send existing messages to hydrate client
    await websocket.send_json({
        "type": "session_loaded",
        "messages": session_data.get("messages", []),
        "coaching_notes": session_data.get("coaching_notes", []),
    })

    try:
        while True:
            # Receive attorney's question
            raw = await websocket.receive_json()
            question = raw.get("content", "").strip()
            if not question:
                continue

            # Save attorney message
            attorney_msg = {
                "id": f"msg_{uuid.uuid4().hex[:8]}",
                "role": "attorney",
                "content": question,
                "timestamp": datetime.now().isoformat(),
            }
            session_data["messages"].append(attorney_msg)

            # ── Phase 1: Coaching analysis (parallel with witness response) ──
            coaching_task = asyncio.create_task(
                asyncio.to_thread(
                    analyze_question_for_coaching,
                    state, question, session_data["exam_type"],
                    witness, session_data["messages"][-6:],
                )
            )

            # ── Phase 2: Opposing counsel objection (if enabled) ──
            if session_data.get("opposing_counsel_mode"):
                try:
                    ctx = get_case_context(state)
                    objection = await asyncio.to_thread(
                        generate_objection,
                        state, question, session_data["exam_type"],
                        witness, ctx.get("opponent", "opposing counsel"),
                    )
                    if objection.get("objects"):
                        obj_msg = {
                            "id": f"msg_{uuid.uuid4().hex[:8]}",
                            "role": "objection",
                            "content": objection.get("basis", "Objection"),
                            "timestamp": datetime.now().isoformat(),
                            "metadata": objection,
                        }
                        session_data["messages"].append(obj_msg)
                        await websocket.send_json({"type": "objection", "message": obj_msg})

                        ruling = objection.get("ruling_suggestion", "overruled")
                        await websocket.send_json({
                            "type": "ruling",
                            "ruling": ruling,
                            "explanation": objection.get("explanation", ""),
                        })

                        if ruling == "sustained":
                            # Attorney must rephrase — skip witness response
                            _save_session(cm, case_id, prep_id, session_id, session_data)
                            # Still await coaching
                            coaching = await coaching_task
                            if coaching:
                                _send_coaching(session_data, coaching, attorney_msg["id"])
                                await websocket.send_json({
                                    "type": "coaching",
                                    "coaching": session_data["coaching_notes"][-1],
                                })
                            continue
                except Exception as e:
                    logger.warning("Objection generation failed: %s", e)

            # ── Phase 3: Stream witness response ──
            await websocket.send_json({"type": "witness_start"})

            full_response = ""
            try:
                # Use asyncio.Queue for true token-by-token streaming
                queue: asyncio.Queue = asyncio.Queue()

                def _run_stream():
                    try:
                        for event_type, text in stream_witness_response(
                            state, witness, session_data["exam_type"],
                            session_data["messages"], document_text,
                            state.get("current_model"),
                        ):
                            queue.put_nowait((event_type, text))
                    except Exception as e:
                        queue.put_nowait(("error", str(e)))
                    finally:
                        queue.put_nowait(None)  # Sentinel

                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, _run_stream)

                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    event_type, text = item
                    if event_type == "token":
                        await websocket.send_json({"type": "witness_token", "token": text})
                        full_response = text  # streaming accumulates in invoke_with_retry_streaming
                    elif event_type == "done":
                        full_response = text
                    elif event_type == "error":
                        await websocket.send_json({"type": "error", "message": text})
                        full_response = ""
                        break

            except Exception as e:
                logger.error("Witness streaming error: %s", e)
                await websocket.send_json({
                    "type": "error",
                    "message": "Unable to generate witness response. Please try again.",
                })
                full_response = ""

            if full_response:
                witness_msg = {
                    "id": f"msg_{uuid.uuid4().hex[:8]}",
                    "role": "witness",
                    "content": full_response,
                    "timestamp": datetime.now().isoformat(),
                }
                session_data["messages"].append(witness_msg)
                await websocket.send_json({"type": "witness_done", "message": witness_msg})

            # ── Phase 4: Send coaching results ──
            try:
                coaching = await coaching_task
                if coaching:
                    _send_coaching(session_data, coaching, attorney_msg["id"])
                    await websocket.send_json({
                        "type": "coaching",
                        "coaching": session_data["coaching_notes"][-1],
                    })
            except Exception as e:
                logger.warning("Coaching delivery failed: %s", e)

            # Persist after each exchange
            _save_session(cm, case_id, prep_id, session_id, session_data)

    except WebSocketDisconnect:
        logger.info("Mock exam WS disconnected: session=%s", session_id)
        _save_session(cm, case_id, prep_id, session_id, session_data)
    except Exception as e:
        logger.error("Mock exam WS error: session=%s, error=%s", session_id, e)
        try:
            await websocket.close(code=1011, reason=str(e)[:100])
        except Exception:
            pass
        _save_session(cm, case_id, prep_id, session_id, session_data)


def _send_coaching(session_data: dict, coaching: dict, message_id: str):
    """Format and append a coaching note to the session."""
    # Determine coaching type
    if coaching.get("objectionable"):
        ctype = "objection_warning"
    elif coaching.get("impeachment_opportunity"):
        ctype = "impeachment_opportunity"
    elif coaching.get("door_warning"):
        ctype = "door_opened"
    else:
        ctype = "technique_tip"

    # Build content string
    parts = []
    if coaching.get("objection_basis"):
        parts.append(f"Objectionable: {coaching['objection_basis']}")
    for tip in coaching.get("technique_tips", []):
        parts.append(tip)
    if coaching.get("impeachment_opportunity"):
        parts.append(f"Impeachment opportunity: {coaching['impeachment_opportunity']}")
    if coaching.get("door_warning"):
        parts.append(f"Door warning: {coaching['door_warning']}")

    if not parts:
        return

    entry = {
        "message_id": message_id,
        "type": ctype,
        "content": " | ".join(parts),
        "severity": coaching.get("severity", "info"),
    }
    session_data.setdefault("coaching_notes", []).append(entry)
