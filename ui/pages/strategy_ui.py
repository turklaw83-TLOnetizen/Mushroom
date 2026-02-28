"""Strategy & Jury UI module -- ported from ui_modules/strategy_ui.py."""
import logging
import os
import io
import json
import datetime as _dt

import altair as alt
import pandas as pd
import streamlit as st
from openai import OpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.nodes import (
    evaluate_case_theory, generate_voir_dire,
    generate_mock_jury, generate_jury_instructions,
    generate_client_report, generate_statements,
    predict_opponent_strategy,
)
from core.llm import get_llm
from core.append_only import safe_update_and_save
from core.cost_tracker import format_cost_badge
from core.export import generate_pdf_report
from ui.shared import render_module_notes, render_quick_ask

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local helpers (previously imported from app)
# ---------------------------------------------------------------------------

def _run_single_node(node_fn, label, state, case_mgr, case_id, prep_id, model_provider, agent_results):
    """Run a single analysis node with spinner, save results, show friendly errors."""
    from ui.shared import run_single_node as _shared_run
    return _shared_run(node_fn, label, state, case_mgr, case_id, prep_id, model_provider, agent_results)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render(case_id, case_mgr, results, tabs, selected_group, nav_groups, model_provider, prep_id):
    """Render the Strategy & Jury UI based on active_tab."""
    run_single_node = _run_single_node
    estimate_cost = lambda text, mp: format_cost_badge(text, mp)

    with tabs[0]:  # VOIR DIRE
        st.subheader("Voir Dire Strategy")

        if st.button(f"Regenerate Voir Dire {estimate_cost(results.get('strategy_notes', '') + results.get('case_summary', ''), model_provider)}", key="regen_voir_dire"):
            run_single_node(generate_voir_dire, "Regenerating Voir Dire Strategy", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        vd_data = results.get("voir_dire", {})
        if isinstance(vd_data, str):
            try:
                vd_data = json.loads(vd_data.replace("```json", "").replace("```", ""))
            except (json.JSONDecodeError, ValueError):
                logger.info("Failed to parse voir_dire JSON, falling back to raw string")

        if vd_data and isinstance(vd_data, dict):
            with st.expander("Ideal Juror Profile", expanded=True):
                st.info(vd_data.get("ideal_juror", "No profile generated."))

            with st.expander("Red Flags (Strikes)", expanded=True):
                st.error(vd_data.get("red_flags", "No red flags identified."))

            st.markdown("### Voir Dire Questions")
            questions = vd_data.get("questions", [])
            if questions:
                for i, q in enumerate(questions):
                    with st.container(border=True):
                        st.markdown(f"**{i+1}. {q.get('question')}**")
                        st.caption(f"Goal: {q.get('goal')}")
            else:
                st.warning("No questions generated.")
        else:
            if isinstance(vd_data, str):
                st.markdown(vd_data)
            else:
                st.info("Run analysis to generate Voir Dire strategy.")
        render_module_notes(case_mgr, case_id, prep_id, "voir_dire", "Voir Dire")

        # Quick-Ask: Voir Dire
        render_quick_ask("voir_dire", "Voir Dire Strategy", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[1]:  # MOCK JURY
        st.subheader("Mock Jury Focus Group")
        st.caption("Simulate diverse juror reactions to your case strategy to identify weaknesses.")

        col_mj1, col_mj2 = st.columns([1, 1])
        with col_mj1:
            if st.button(f"Assemble Mock Jury {estimate_cost(str(results.get('case_summary', '')) + results.get('strategy_notes', ''), model_provider)}", key="run_mock_jury", type="primary"):
                with st.spinner("Conducting focus group simulation..."):
                    updates = generate_mock_jury(st.session_state.agent_results)
                    safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, updates)
                    st.rerun()

        feedback = results.get("mock_jury_feedback", [])

        if feedback:
            st.markdown("### Juror Feedback")
            st.markdown("Here is how different personalities types reacted to your current Defense Strategy.")

            cols = st.columns(3)
            for i, juror in enumerate(feedback):
                with cols[i % 3]:
                    with st.container(border=True):
                        role = juror.get('juror', 'Juror')
                        verdict = juror.get('verdict', 'Undecided')
                        reaction = juror.get('reaction', '')

                        st.markdown(f"**{role}**")

                        if "Not Guilty" in verdict:
                            st.markdown(f":green[**{verdict}**]")
                        elif "Guilty" in verdict:
                            st.markdown(f":red[**{verdict}**]")
                        else:
                            st.markdown(f":orange[**{verdict}**]")

                        st.caption(f"\"{reaction}\"")
        else:
            st.info("No focus group data yet. Click 'Assemble Mock Jury' to start.")
        render_module_notes(case_mgr, case_id, prep_id, "mock_jury", "Mock Jury")

        # Quick-Ask: Mock Jury
        render_quick_ask("mock_jury", "Mock Jury Analysis", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[6]:  # CASE THEORY
        st.subheader("Case Theory Builder")
        st.caption("Write your case theory and have AI evaluate it against all available evidence.")

        _existing_theory = results.get("case_theory", {})
        if isinstance(_existing_theory, str):
            try:
                _existing_theory = json.loads(_existing_theory)
            except (json.JSONDecodeError, ValueError):
                logger.info("Failed to parse case_theory JSON, falling back to empty dict")
                _existing_theory = {}

        _default_text = _existing_theory.get("theory_text", "") if isinstance(_existing_theory, dict) else ""

        _theory_input = st.text_area(
            "Your Case Theory",
            value=_default_text,
            height=200,
            placeholder="Write your case theory here -- the narrative that explains what happened and why the jury/judge should rule in your client's favor...\n\nExample: 'The defendant acted in self-defense when confronted by an aggressive attacker who had a history of violent behavior. The evidence will show...'",
            key="_theory_input"
        )

        if st.button(f"Evaluate Theory {estimate_cost(_theory_input or '', model_provider)}", key="run_theory_eval", type="primary", disabled=(not _theory_input or not _theory_input.strip())):
            with st.spinner("Evaluating case theory against evidence..."):
                _theory_result = evaluate_case_theory(st.session_state.agent_results, _theory_input.strip())
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, _theory_result)
                st.rerun()

        if _existing_theory and isinstance(_existing_theory, dict) and not _existing_theory.get("_parse_error"):
            _score = _existing_theory.get("overall_score", 0)
            _grade = _existing_theory.get("grade", "?")
            _verdict = _existing_theory.get("verdict", "")

            if _score >= 85: _score_color = "#22c55e"
            elif _score >= 70: _score_color = "#3b82f6"
            elif _score >= 55: _score_color = "#eab308"
            elif _score >= 40: _score_color = "#f97316"
            else: _score_color = "#ef4444"

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {_score_color}18, {_score_color}08);
                        border-left: 5px solid {_score_color}; border-radius: 0 12px 12px 0;
                        padding: 20px 24px; margin: 16px 0;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="font-size: 48px; font-weight: 800; color: {_score_color};">{_score}</div>
                    <div>
                        <div style="font-size: 24px; font-weight: 700;">Grade: {_grade}</div>
                        <div style="opacity: 0.8; margin-top: 4px;">{_verdict}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            _jury_appeal = _existing_theory.get("jury_appeal", {})
            if isinstance(_jury_appeal, dict) and _jury_appeal:
                _ja1, _ja2, _ja3 = st.columns(3)
                with _ja1:
                    _er = _jury_appeal.get("emotional_resonance", "?")
                    st.metric("Emotional Resonance", f"{_er.title()}")
                with _ja2:
                    _si = _jury_appeal.get("simplicity", "?")
                    st.metric("Simplicity", f"{_si.title()}")
                with _ja3:
                    _cr = _jury_appeal.get("credibility", "?")
                    st.metric("Credibility", f"{_cr.title()}")
                if _jury_appeal.get("notes"):
                    st.caption(f"{_jury_appeal['notes']}")

            _strengths = _existing_theory.get("strengths", [])
            if _strengths and isinstance(_strengths, list):
                with st.expander(f"Strengths ({len(_strengths)})", expanded=True):
                    for _s in _strengths:
                        if isinstance(_s, dict):
                            st.markdown(f"**{_s.get('point', '')}**")
                            _evs = _s.get("supporting_evidence", [])
                            if isinstance(_evs, list):
                                for _ev in _evs:
                                    st.caption(f"  {_ev}")
                            st.divider()

            _weaknesses = _existing_theory.get("weaknesses", [])
            if _weaknesses and isinstance(_weaknesses, list):
                with st.expander(f"Weaknesses ({len(_weaknesses)})", expanded=True):
                    for _w in _weaknesses:
                        if isinstance(_w, dict):
                            _risk = _w.get("risk_level", "")
                            st.markdown(f"**{_w.get('point', '')}** -- _{_risk}_")
                            _ue = _w.get("undermining_evidence", [])
                            if isinstance(_ue, list):
                                for _u in _ue:
                                    st.caption(f"  {_u}")
                            if _w.get("mitigation"):
                                st.info(f"Mitigation: {_w['mitigation']}")
                            st.divider()

            _gaps = _existing_theory.get("evidence_gaps", [])
            if _gaps and isinstance(_gaps, list):
                with st.expander(f"Evidence Gaps ({len(_gaps)})", expanded=False):
                    for _g in _gaps:
                        if isinstance(_g, dict):
                            _imp = _g.get("importance", "")
                            st.markdown(f"**{_g.get('gap', '')}** -- _{_imp}_")
                            if _g.get("how_to_fill"):
                                st.caption(f"  {_g['how_to_fill']}")
                            st.divider()

            _counters = _existing_theory.get("opponent_counter_theories", [])
            if _counters and isinstance(_counters, list):
                with st.expander(f"Opponent Counter-Theories ({len(_counters)})", expanded=False):
                    for _ct in _counters:
                        if isinstance(_ct, dict):
                            _plaus = _ct.get("plausibility", "")
                            st.markdown(f"**{_ct.get('theory', '')}** -- _{_plaus} plausibility_")
                            if _ct.get("rebuttal"):
                                st.success(f"Rebuttal: {_ct['rebuttal']}")
                            st.divider()

            _recs = _existing_theory.get("recommendations", [])
            if _recs and isinstance(_recs, list):
                with st.expander("Recommendations", expanded=True):
                    for _ri, _r in enumerate(_recs):
                        st.markdown(f"{_ri+1}. {_r}")

        elif _existing_theory and isinstance(_existing_theory, dict) and _existing_theory.get("_parse_error"):
            st.warning("Theory evaluation returned but could not be parsed. Raw output:")
            st.code(_existing_theory.get("raw_output", ""))
        elif not _theory_input:
            st.info("Write your case theory above and click 'Evaluate Theory' to get an AI-powered scorecard.")
        render_module_notes(case_mgr, case_id, prep_id, "case_theory", "Case Theory")

    with tabs[7]:  # JURY INSTRUCTIONS
        st.subheader("Jury Instruction Generator")
        st.caption("Generate draft jury instructions, special requests, and verdict forms.")

        if st.button(f"Generate Instructions {estimate_cost(str(results.get('charges', '')) + str(results.get('legal_elements', '')), model_provider)}", key="run_jury_instr", type="primary"):
            with st.spinner("Generating jury instructions..."):
                _instr_result = generate_jury_instructions(st.session_state.agent_results)
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, _instr_result)
                st.rerun()

        _instr_data = results.get("jury_instructions", {})
        if isinstance(_instr_data, str):
            try:
                _instr_data = json.loads(_instr_data)
            except (json.JSONDecodeError, ValueError):
                logger.info("Failed to parse jury_instructions JSON, falling back to empty dict")
                _instr_data = {}

        if _instr_data and isinstance(_instr_data, dict) and not _instr_data.get("_parse_error"):
            _std = _instr_data.get("standard_instructions", [])
            if _std and isinstance(_std, list):
                with st.expander(f"Standard Instructions ({len(_std)})", expanded=True):
                    for _si in _std:
                        if isinstance(_si, dict):
                            _cat = _si.get("category", "")
                            with st.container(border=True):
                                st.markdown(f"**{_si.get('number', '')}. {_si.get('title', '')}** -- _{_cat}_")
                                st.markdown(_si.get("text", ""))
                                _src = _si.get("source", "")
                                _notes = _si.get("notes", "")
                                if _src or _notes:
                                    _meta_parts = []
                                    if _src: _meta_parts.append(f"{_src}")
                                    if _notes: _meta_parts.append(f"{_notes}")
                                    st.caption(" | ".join(_meta_parts))

            _special = _instr_data.get("special_instructions", [])
            if _special and isinstance(_special, list):
                with st.expander(f"Special Instructions ({len(_special)})", expanded=True):
                    for _sp in _special:
                        if isinstance(_sp, dict):
                            with st.container(border=True):
                                st.markdown(f"**{_sp.get('number', '')}. {_sp.get('title', '')}**")
                                st.markdown(_sp.get("text", ""))
                                if _sp.get("justification"):
                                    st.info(f"Justification: {_sp['justification']}")
                                if _sp.get("strategic_value"):
                                    st.success(f"Strategic Value: {_sp['strategic_value']}")

            _contested = _instr_data.get("contested_instructions", [])
            if _contested and isinstance(_contested, list):
                with st.expander(f"Contested Instructions ({len(_contested)})", expanded=True):
                    for _ci in _contested:
                        if isinstance(_ci, dict):
                            with st.container(border=True):
                                st.markdown(f"**{_ci.get('title', '')}**")
                                st.markdown(f"*Their proposed text:* {_ci.get('text', '')}")
                                if _ci.get("our_objection"):
                                    st.error(f"Our Objection: {_ci['our_objection']}")
                                if _ci.get("alternative"):
                                    st.success(f"Our Alternative: {_ci['alternative']}")

            _verdicts = _instr_data.get("verdict_forms", [])
            if _verdicts and isinstance(_verdicts, list):
                with st.expander(f"Verdict Forms ({len(_verdicts)})", expanded=False):
                    for _vf in _verdicts:
                        if isinstance(_vf, dict):
                            with st.container(border=True):
                                _lesser = " _(Lesser Included)_" if _vf.get("lesser_included") else ""
                                st.markdown(f"**Form {_vf.get('form_number', '')}. {_vf.get('title', '')}**{_lesser}")
                                st.code(_vf.get("text", ""), language=None)
                                if _vf.get("notes"):
                                    st.caption(f"{_vf['notes']}")

            _conf_strat = _instr_data.get("instruction_conference_strategy", "")
            if _conf_strat:
                with st.expander("Instruction Conference Strategy", expanded=False):
                    st.markdown(_conf_strat)

        elif _instr_data and isinstance(_instr_data, dict) and _instr_data.get("_parse_error"):
            st.warning("Instructions were generated but could not be parsed. Raw output:")
            st.code(_instr_data.get("raw_output", ""))
        else:
            st.info("Click 'Generate Instructions' to create draft jury instructions based on your case analysis.")
        render_module_notes(case_mgr, case_id, prep_id, "jury_instructions", "Jury Instructions")

    with tabs[2]:  # SIMULATOR
        st.subheader("Voice Simulator")
        st.caption("Practice Cross-Examination, Opening, and Closing with Real-Time AI Audio")

        c1, c2 = st.columns(2)
        with c1:
            sim_mode = st.selectbox("Mode", ["Cross-Examination", "Opening Statement", "Closing Argument"])
        with c2:
            if sim_mode == "Cross-Examination":
                sim_persona = st.selectbox("Persona", ["Hostile Witness", "Confused Witness", "Expert Witness", "Police Officer"])
            else:
                sim_persona = st.selectbox("Persona", ["Bored Jury", "Strict Judge", "Sympathetic Jury"])

        if "sim_messages" not in st.session_state:
            st.session_state.sim_messages = []

        if st.button("Reset Simulation"):
            st.session_state.sim_messages = []
            st.rerun()

        st.markdown("---")
        for msg in st.session_state.sim_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "audio" in msg:
                    st.audio(msg["audio"], format="audio/mp3")

        st.markdown("### Your Turn")
        audio_value = st.audio_input("Record your voice")

        if audio_value:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            if "last_audio_id" not in st.session_state:
                st.session_state.last_audio_id = None

            current_audio_id = audio_value.size

            if current_audio_id != st.session_state.last_audio_id:
                st.session_state.last_audio_id = current_audio_id

                with st.spinner("Transcribing..."):
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_value,
                        response_format="text"
                    )
                    user_text = str(transcript)

                st.session_state.sim_messages.append({"role": "user", "content": user_text})

                with st.spinner(f"{sim_persona} is thinking..."):
                    case_context = f"CASE SUMMARY: {st.session_state.agent_results.get('case_summary', '')}" if st.session_state.agent_results else ""

                    system_prompt = f"""
                    You are roleplaying as: {sim_persona} in a legal simulation.
                    MODE: {sim_mode}

                    {case_context}

                    INSTRUCTIONS:
                    - Respond verbally (keep it conversational, natural, brief).
                    - If 'Cross-Examination': Be resistant, evasive, or helpful based on persona.
                    - If 'Opening/Closing': React to the lawyer's argument. Interrupt if 'Strict Judge'. Look bored if 'Bored Jury' (describe reaction in text, speak the interruption).
                    """

                    llm = get_llm(model_provider)
                    messages = [SystemMessage(content=system_prompt)]
                    for m in st.session_state.sim_messages:
                        messages.append(HumanMessage(content=m["content"]) if m["role"] == "user" else SystemMessage(content=m["content"]))

                    response_text = llm.invoke(messages).content

                    voice = "alloy"
                    if "Judge" in sim_persona or "Officer" in sim_persona: voice = "onyx"
                    elif "Witness" in sim_persona: voice = "echo"
                    elif "Jury" in sim_persona: voice = "shimmer"

                    response_audio = client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=response_text
                    )

                    audio_bio = io.BytesIO()
                    for chunk in response_audio.iter_bytes():
                        audio_bio.write(chunk)

                    st.session_state.sim_messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "audio": audio_bio
                    })

                st.rerun()

    with tabs[3]:  # CLIENT REPORT
        st.subheader("Client-Facing Report")
        st.caption("Generate a plain-language case briefing to share with your client.")

        if st.button(
            f"Generate Report {estimate_cost(results.get('case_summary', '') + results.get('strategy_notes', ''), model_provider)}",
            type="primary",
            key="gen_client_report_tab"
        ):
            with st.spinner("Writing client-facing report..."):
                report = generate_client_report(st.session_state.agent_results)
                st.session_state["client_report"] = report

        if st.session_state.get("client_report"):
            st.markdown(st.session_state["client_report"])
            st.download_button(
                "Download Report (.md)",
                st.session_state["client_report"],
                file_name="client_report.md",
                mime="text/markdown",
                key="dl_client_report_tab"
            )
        else:
            st.info("Click the button above to generate a client-friendly report.")

    with tabs[4]:  # STATEMENTS
        st.subheader("Opening & Closing Statement Generator")
        st.caption("Generate persuasive, section-by-section statements that synthesize ALL analysis modules")

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            stmt_type = st.selectbox("Statement Type", ["opening", "closing"], format_func=lambda x: x.title(), key="_stmt_type")
        with sc2:
            stmt_tone = st.selectbox("Tone", ["measured", "aggressive", "empathetic"], format_func=lambda x: x.title(), key="_stmt_tone")
        with sc3:
            stmt_audience = st.selectbox("Audience", ["jury", "bench"], format_func=lambda x: {"jury": "Jury Trial", "bench": "Bench Trial (Judge)"}.get(x, x), key="_stmt_audience")

        st.caption({
            "measured": "**Measured**: Professional, logical, methodical. Let the facts speak.",
            "aggressive": "**Aggressive**: Declarative, challenging, controlled anger.",
            "empathetic": "**Empathetic**: Storytelling, emotional connection, real people.",
        }.get(stmt_tone, ""))

        if stmt_audience == "bench":
            st.info("**Bench trial mode:** Statement will prioritize legal reasoning, element-by-element analysis, and formal tone over emotional storytelling.")

        _btn_c1, _btn_c2 = st.columns(2)
        with _btn_c1:
            if st.button(
                f"Generate {stmt_type.title()} Statement {estimate_cost(results.get('case_summary', '') + results.get('strategy_notes', ''), model_provider)}",
                type="primary",
                key="_gen_statement"
            ):
                if results.get("case_summary"):
                    with st.spinner(f"Drafting {stmt_type} statement ({stmt_tone} tone, {stmt_audience})..."):
                        stmt_result = generate_statements(st.session_state.agent_results, stmt_type, stmt_tone, stmt_audience)
                        stmt_obj = stmt_result.get("statement", {})
                        st.session_state.agent_results["statement"] = stmt_obj
                        if "statement_versions" not in st.session_state.agent_results:
                            st.session_state.agent_results["statement_versions"] = []
                        stmt_obj["timestamp"] = _dt.datetime.now().isoformat()
                        st.session_state.agent_results["statement_versions"].append(dict(stmt_obj))
                        if f"statement_{stmt_type}" not in st.session_state.agent_results:
                            st.session_state.agent_results[f"statement_{stmt_type}"] = {}
                        st.session_state.agent_results[f"statement_{stmt_type}"] = dict(stmt_obj)
                        case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                        st.rerun()
                else:
                    st.warning("Run a full analysis first to generate meaningful statements.")

        with _btn_c2:
            if st.button(
                f"Generate BOTH (Opening + Closing) {estimate_cost(results.get('case_summary', '') + results.get('strategy_notes', ''), model_provider)} x2",
                key="_gen_both_stmts",
                help="Generates both opening and closing statements for side-by-side comparison"
            ):
                if results.get("case_summary"):
                    with st.spinner(f"Drafting opening statement ({stmt_tone} tone, {stmt_audience})..."):
                        r1 = generate_statements(st.session_state.agent_results, "opening", stmt_tone, stmt_audience)
                        st.session_state.agent_results["statement_opening"] = r1.get("statement", {})
                    with st.spinner(f"Drafting closing statement ({stmt_tone} tone, {stmt_audience})..."):
                        r2 = generate_statements(st.session_state.agent_results, "closing", stmt_tone, stmt_audience)
                        st.session_state.agent_results["statement_closing"] = r2.get("statement", {})
                    st.session_state.agent_results["statement"] = r2.get("statement", {})
                    if "statement_versions" not in st.session_state.agent_results:
                        st.session_state.agent_results["statement_versions"] = []
                    for _sv in [r1.get("statement", {}), r2.get("statement", {})]:
                        _sv["timestamp"] = _dt.datetime.now().isoformat()
                        st.session_state.agent_results["statement_versions"].append(dict(_sv))
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
                else:
                    st.warning("Run a full analysis first to generate meaningful statements.")

        # Helper to render a statement with sectioned output
        def _render_statement(sdata, label=""):
            if not isinstance(sdata, dict) or not sdata.get("content"):
                return
            _sections = sdata.get("sections", [])
            _word_count = sdata.get("word_count", len(sdata.get("content", "").split()))
            _est_mins = sdata.get("est_minutes", round(_word_count / 130, 1))
            _aud = sdata.get("audience", "jury")

            _m1, _m2, _m3, _m4 = st.columns(4)
            _m1.metric("Type", sdata.get("type", "").title())
            _m2.metric("Tone", sdata.get("tone", "").title())
            _m3.metric("Words", f"{_word_count:,}")
            _m4.metric("Speaking Time", f"~{_est_mins} min")

            if _aud == "bench":
                st.caption("Bench Trial -- formatted for judge, not jury")

            st.divider()

            if _sections:
                for _sec in _sections:
                    if isinstance(_sec, dict):
                        with st.expander(f"{_sec.get('heading', 'Section')}", expanded=True):
                            st.markdown(_sec.get("content", ""))
            else:
                with st.container(border=True):
                    st.markdown(sdata["content"])

            st.divider()
            with st.expander("Practice Mode", expanded=False):
                st.caption("Use this to practice delivering the statement. Target speaking pace is ~130 words/minute.")
                _pace_col1, _pace_col2 = st.columns(2)
                with _pace_col1:
                    _target_mins = st.slider("Target time (minutes)", 1, 15, int(max(1, _est_mins)), key=f"_practice_target_{label}")
                with _pace_col2:
                    _target_words = _target_mins * 130
                    if _word_count > _target_words * 1.15:
                        st.warning(f"Statement is ~{_word_count} words but target is {_target_words} words ({_target_mins} min). Consider trimming.")
                    elif _word_count < _target_words * 0.85:
                        st.info(f"Statement is ~{_word_count} words -- under target of {_target_words} words ({_target_mins} min). Room to elaborate.")
                    else:
                        st.success(f"Statement is ~{_word_count} words -- good match for {_target_mins} min target.")

                st.markdown("**Full Statement (for reading aloud):**")
                with st.container(border=True):
                    st.markdown(sdata["content"])

            st.divider()
            _dl1, _dl2 = st.columns(2)
            with _dl1:
                st.download_button(
                    "Download (.md)",
                    data=sdata["content"],
                    file_name=f"{sdata.get('type', 'statement')}_{case_id}.md",
                    mime="text/markdown",
                    key=f"_dl_stmt_md_{label}"
                )
            with _dl2:
                try:
                    stmt_pdf_state = {"case_summary": sdata["content"], "strategy_notes": ""}
                    stmt_pdf = generate_pdf_report(stmt_pdf_state, f"{sdata.get('type','Statement').title()} -- {case_id}")
                    st.download_button(
                        "Download (.pdf)",
                        data=stmt_pdf,
                        file_name=f"{sdata.get('type', 'statement')}_{case_id}.pdf",
                        mime="application/pdf",
                        key=f"_dl_stmt_pdf_{label}"
                    )
                except Exception:
                    pass

        _has_opening = isinstance(results.get("statement_opening"), dict) and results.get("statement_opening", {}).get("content")
        _has_closing = isinstance(results.get("statement_closing"), dict) and results.get("statement_closing", {}).get("content")

        if _has_opening and _has_closing:
            st.divider()
            st.markdown("### Side-by-Side Comparison")
            _sbs1, _sbs2 = st.columns(2)
            with _sbs1:
                st.markdown("#### Opening Statement")
                _render_statement(results["statement_opening"], "opening")
            with _sbs2:
                st.markdown("#### Closing Statement")
                _render_statement(results["statement_closing"], "closing")
        elif isinstance(results.get("statement"), dict) and results.get("statement", {}).get("content"):
            st.divider()
            _render_statement(results["statement"], "single")
        else:
            st.info("No statement generated yet. Select type, tone, and audience, then click Generate.")

        _versions = results.get("statement_versions", [])
        if _versions:
            st.divider()
            with st.expander(f"Version History ({len(_versions)} drafts)", expanded=False):
                for _vi, _ver in enumerate(reversed(_versions)):
                    if isinstance(_ver, dict):
                        _v_type = _ver.get("type", "?").title()
                        _v_tone = _ver.get("tone", "?").title()
                        _v_aud = _ver.get("audience", "?").title()
                        _v_words = _ver.get("word_count", len(_ver.get("content", "").split()))
                        _v_ts = _ver.get("timestamp", "")
                        _v_label = f"v{len(_versions) - _vi}"
                        with st.expander(f"{_v_label}: {_v_type} | {_v_tone} | {_v_aud} | {_v_words} words" + (f" | {_v_ts[:16]}" if _v_ts else "")):
                            st.markdown(_ver.get("content", "No content"))
                            if st.button(f"Restore this version", key=f"_restore_stmt_{_vi}"):
                                st.session_state.agent_results["statement"] = dict(_ver)
                                st.session_state.agent_results[f"statement_{_ver.get('type', 'opening')}"] = dict(_ver)
                                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                                st.rerun()
        render_module_notes(case_mgr, case_id, prep_id, "statements", "Statements")

    with tabs[5]:  # OPPONENT PLAYBOOK
        st.subheader("AI Opponent Playbook Predictor")
        st.caption("Predict opposing counsel's likely strategy, motions, witness order, and weak points they'll target -- powered by AI analysis.")

        _op_has_summary = bool(results.get("case_summary"))
        if not _op_has_summary:
            st.warning("Run at least the **Case Summary** analysis first so the AI has case context to work with.")

        if st.button(
            f"Generate Opponent Playbook {estimate_cost(str(results.get('case_summary', ''))[:200], model_provider)}",
            type="primary",
            key="_gen_opp_playbook",
            disabled=not _op_has_summary,
        ):
            with st.spinner("Analyzing the case from opposing counsel's perspective..."):
                _op_result = predict_opponent_strategy(st.session_state.agent_results)
                st.session_state.agent_results["opponent_playbook"] = _op_result.get("opponent_playbook", {})
                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                st.rerun()

        _playbook = results.get("opponent_playbook")
        if _playbook:
            if _playbook.get("error"):
                st.error(f"Error: {_playbook['error']}")
            else:
                _sections = _playbook.get("sections", [])
                _raw = _playbook.get("raw", "")

                if _sections:
                    st.divider()
                    st.markdown(f"### Playbook -- {len(_sections)} sections analyzed")

                    for _si, _sec in enumerate(_sections):
                        _title = _sec.get("title", "Section")
                        _content = _sec.get("content", "")
                        _expanded = (_si == 0) or ("THREAT" in _title.upper())

                        with st.expander(f"{_title}", expanded=_expanded):
                            st.markdown(_content)

                    st.divider()

                    _dl_c1, _dl_c2 = st.columns(2)
                    with _dl_c1:
                        st.download_button(
                            "Download Full Playbook",
                            data=_raw,
                            file_name=f"opponent_playbook_{case_id}.md",
                            mime="text/markdown",
                            key="_dl_opp_playbook_md"
                        )
                    with _dl_c2:
                        try:
                            _op_pdf_state = {"case_summary": _raw, "strategy_notes": ""}
                            _op_pdf = generate_pdf_report(_op_pdf_state, f"Opponent Playbook -- {case_id}")
                            st.download_button(
                                "Download as PDF",
                                data=_op_pdf,
                                file_name=f"opponent_playbook_{case_id}.pdf",
                                mime="application/pdf",
                                key="_dl_opp_playbook_pdf"
                            )
                        except Exception:
                            pass

                elif _raw:
                    st.divider()
                    with st.container(border=True):
                        st.markdown(_raw)
                else:
                    st.info("Playbook generated but no content found. Try generating again.")
        render_module_notes(case_mgr, case_id, prep_id, "opponent_playbook", "Opponent Playbook")
