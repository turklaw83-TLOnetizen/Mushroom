"""Core Analysis UI module -- ported from ui_modules/core_analysis_ui.py."""
import logging
import os
import json
import re

import altair as alt
import pandas as pd
import streamlit as st
from datetime import datetime, date
from streamlit_agraph import agraph, Node, Edge, Config

from core.nodes import (
    analyze_case, generate_devils_advocate,
    generate_timeline, generate_voir_dire,
    challenge_finding, refine_strategy, generate_client_report,
)
from core.llm import get_llm, invoke_with_retry_streaming
from core.state import get_case_context
from core.append_only import safe_update_and_save
from core.readiness import compute_readiness_score
from core.citations import render_with_references
from core.cost_tracker import format_cost_badge
from ui.shared import render_module_notes, render_quick_ask

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers that were previously imported from app.py.
# These are thin wrappers; the real logic will be filled in by the main app
# or by shared helpers.  For now they are defined locally so the module loads.
# ---------------------------------------------------------------------------

def _run_single_node(node_fn, label, state, case_mgr, case_id, prep_id, model_provider, agent_results):
    """Run a single analysis node with spinner, save results, show friendly errors."""
    from ui.shared import run_single_node as _shared_run
    return _shared_run(node_fn, label, state, case_mgr, case_id, prep_id, model_provider, agent_results)


def _render_module_export(title, data, key):
    """Render export buttons for a module section."""
    if data:
        with st.expander(f"Export {title}", expanded=False):
            if isinstance(data, str):
                st.download_button(
                    f"Download {title} (.md)",
                    data=data,
                    file_name=f"{key}.md",
                    mime="text/markdown",
                    key=f"export_{key}",
                )
            elif isinstance(data, (list, dict)):
                st.download_button(
                    f"Download {title} (.json)",
                    data=json.dumps(data, indent=2, default=str),
                    file_name=f"{key}.json",
                    mime="application/json",
                    key=f"export_{key}",
                )


def _build_analysis_context(agent_results):
    """Build a context string from current analysis results."""
    parts = []
    for key in ("case_summary", "strategy_notes", "witnesses", "timeline"):
        val = agent_results.get(key)
        if val:
            parts.append(f"## {key}\n{str(val)[:2000]}")
    return "\n\n".join(parts)


def _build_chat_messages(prompt, relevant_docs, allow_general, persona, analysis_context=""):
    """Build chat messages for the co-counsel LLM call."""
    from langchain_core.messages import SystemMessage, HumanMessage
    doc_text = "\n\n".join([d.page_content[:1500] for d in relevant_docs]) if relevant_docs else ""
    system_msg = f"""You are {persona}, a legal co-counsel AI assistant.

CASE DOCUMENTS:
{doc_text[:8000]}

ANALYSIS CONTEXT:
{analysis_context[:4000]}

RULES:
- Base answers on the documents provided unless general knowledge is allowed.
- Be concise but thorough."""
    if allow_general:
        system_msg += "\n- You may also use your general legal knowledge."
    return [SystemMessage(content=system_msg), HumanMessage(content=prompt)]


def _stream_chat(llm, messages):
    """Generator that yields tokens for st.write_stream."""
    for event_type, data in invoke_with_retry_streaming(llm, messages):
        if event_type == "token":
            yield data


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render(case_id, case_mgr, results, tabs, selected_group, nav_groups, model_provider, prep_id):
    """Render the Core Analysis UI based on active_tab."""
    current_prep_name = st.session_state.get("current_prep_name", "")

    # Safe alias — prevents NoneType errors when no preparation is loaded
    _agent_results = st.session_state.agent_results or {}

    # Alias helpers
    run_single_node = _run_single_node
    render_module_export = _render_module_export
    build_analysis_context = _build_analysis_context
    estimate_cost = lambda text, mp: format_cost_badge(text, mp)

    with tabs[0]:  # CHAT
        st.subheader("Active Co-Counsel Chat")

        col_opts1, col_opts2 = st.columns([2, 1])
        with col_opts1:
            # Document Focus Mode
            all_files = case_mgr.get_case_files(st.session_state.current_case_id)
            file_names = [os.path.basename(f) for f in all_files]
            selected_files = st.multiselect("Focus on specific documents:", file_names, default=file_names)
        with col_opts2:
            persona = st.selectbox("Co-Counsel Persona:", [
                "General Assistant",
                "The Strategist",
                "The Bulldog",
                "The Scholar",
                "The Judge"
            ])
            allow_general = st.checkbox("Allow General Knowledge", help="Check to let AI answer based on its training data.")

        # Load persisted chat history if session is empty
        if not st.session_state.chat_history and case_id and prep_id:
            _saved_chat = case_mgr.load_chat_history(case_id, prep_id)
            if _saved_chat:
                st.session_state.chat_history = _saved_chat

        # Clear chat button
        if st.session_state.chat_history:
            if st.button("Clear Chat History", key="_clear_chat"):
                st.session_state.chat_history = []
                if case_id and prep_id:
                    case_mgr.clear_chat_history(case_id, prep_id)
                st.rerun()

        # Chat History Display
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input(f"Ask {persona} about the case..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            if selected_files:
                raw_docs = _agent_results.get("raw_documents", [])
                relevant_docs = [d for d in raw_docs if os.path.basename(d.metadata.get("source", "")) in selected_files]
            else:
                relevant_docs = []

            with st.chat_message("assistant"):
                _analysis_ctx = build_analysis_context(st.session_state.agent_results) if st.session_state.agent_results else ""
                _chat_msgs = _build_chat_messages(prompt, relevant_docs, allow_general, persona, analysis_context=_analysis_ctx)
                _chat_llm = get_llm(st.session_state.get("model_provider", "xai"))
                try:
                    st.markdown(f"**{persona}:**")
                    answer = st.write_stream(_stream_chat(_chat_llm, _chat_msgs))
                except Exception as _chat_exc:
                    from ui.shared import friendly_error
                    answer = None
                    st.error(friendly_error(_chat_exc))
                if answer:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"**{persona}**: {answer}"})

            if case_id and prep_id:
                case_mgr.save_chat_history(case_id, prep_id, st.session_state.chat_history)

    with tabs[1]:  # SUMMARY
        st.subheader("Case Analysis")

        # Check if any analysis has been run
        _has_any_analysis = any(
            results.get(k) for k in (
                "case_summary", "strategy_notes", "witnesses", "timeline",
                "evidence_foundations", "cross_examination_plan",
            )
        )

        if not _has_any_analysis:
            st.info(
                "\U0001f4cb **No analysis data yet.** Run a full case analysis from the "
                "Analysis Engine above to populate this dashboard.\n\n"
                "Upload documents first, then click **Run Full Analysis** to get started."
            )

        render_module_export("Case Summary", results.get("case_summary"), "summary")

        # --- Readiness Score Gauge ---
        score, grade, breakdown = compute_readiness_score(results)
        rs_col1, rs_col2, rs_col3 = st.columns([1, 2, 1])
        with rs_col1:
            grade_colors = {"A": "green", "B": "blue", "C": "orange", "D": "red", "F": "red"}
            st.markdown(f"### :{grade_colors.get(grade, 'gray')}[{grade}]")
            st.metric("Readiness", f"{score}%")
        with rs_col2:
            st.progress(score / 100, text=f"Case Readiness: {score}%")
            bd_items = [f"**{k}**: {'Done' if v else 'Missing'}" for k, v in breakdown.items()]
            st.caption(" . ".join(bd_items))
        with rs_col3:
            crit_witnesses = [w for w in results.get('witnesses', []) if isinstance(w, dict) and w.get('_critical')]
            crit_evidence = [e for e in results.get('evidence_foundations', []) if isinstance(e, dict) and e.get('_critical')]
            crit_timeline = [t for t in results.get('timeline', []) if isinstance(t, dict) and t.get('_critical')]
            _cx_crit_cnt = 0
            for _cxb in results.get('cross_examination_plan', []):
                if isinstance(_cxb, dict):
                    for _cxt in _cxb.get('topics', []):
                        if isinstance(_cxt, dict):
                            _cx_crit_cnt += sum(1 for _q in _cxt.get('questions', []) if isinstance(_q, dict) and _q.get('_critical'))
            _dx_crit_cnt = 0
            for _dxb in results.get('direct_examination_plan', []):
                if isinstance(_dxb, dict):
                    for _dxt in _dxb.get('topics', []):
                        if isinstance(_dxt, dict):
                            _dx_crit_cnt += sum(1 for _q in _dxt.get('questions', []) if isinstance(_q, dict) and _q.get('_critical'))
            total_crit = len(crit_witnesses) + len(crit_evidence) + len(crit_timeline) + _cx_crit_cnt + _dx_crit_cnt
            if total_crit:
                st.metric("Critical Items", total_crit)
            else:
                st.caption("No items flagged as critical yet")

        st.divider()

        # --- Critical Items Dashboard ---
        crit_witnesses = [w for w in results.get('witnesses', []) if isinstance(w, dict) and w.get('_critical')]
        crit_evidence = [e for e in results.get('evidence_foundations', []) if isinstance(e, dict) and e.get('_critical')]
        crit_timeline = [t for t in results.get('timeline', []) if isinstance(t, dict) and t.get('_critical')]
        crit_cross = []
        for _cxb in results.get('cross_examination_plan', []):
            if isinstance(_cxb, dict):
                for _cxt in _cxb.get('topics', []):
                    if isinstance(_cxt, dict):
                        for _cxq in _cxt.get('questions', []):
                            if isinstance(_cxq, dict) and _cxq.get('_critical'):
                                crit_cross.append({**_cxq, '_witness': _cxb.get('witness', '')})
        crit_direct = []
        for _dxb in results.get('direct_examination_plan', []):
            if isinstance(_dxb, dict):
                for _dxt in _dxb.get('topics', []):
                    if isinstance(_dxt, dict):
                        for _dxq in _dxt.get('questions', []):
                            if isinstance(_dxq, dict) and _dxq.get('_critical'):
                                crit_direct.append({**_dxq, '_witness': _dxb.get('witness', '')})
        if crit_witnesses or crit_evidence or crit_timeline or crit_cross or crit_direct:
            _total_crit = len(crit_witnesses) + len(crit_evidence) + len(crit_timeline) + len(crit_cross) + len(crit_direct)
            with st.expander(f"Critical Items Dashboard ({_total_crit} items)", expanded=True):
                if crit_witnesses:
                    st.markdown("**Critical Witnesses:**")
                    for w in crit_witnesses:
                        st.markdown(f"- **{w.get('name', 'Unknown')}** -- {w.get('goal', '')}")
                if crit_evidence:
                    st.markdown("**Critical Evidence:**")
                    for e in crit_evidence:
                        st.markdown(f"- **{e.get('evidence', e.get('name', 'Unknown'))}** -- {e.get('foundation_type', '')}")
                if crit_timeline:
                    st.markdown("**Critical Timeline Events:**")
                    for t in crit_timeline:
                        st.markdown(f"- **{t.get('date', '')}** -- {t.get('event', t.get('headline', ''))}")
                if crit_cross:
                    st.markdown("**Critical Cross-Exam Questions:**")
                    for q in crit_cross:
                        st.markdown(f"- [{q.get('_witness', '')}] **{q.get('question', '')}**")
                if crit_direct:
                    st.markdown("**Critical Direct-Exam Questions:**")
                    for q in crit_direct:
                        st.markdown(f"- [{q.get('_witness', '')}] **{q.get('question', '')}**")
            st.divider()

        # ---- CASE STRENGTH DASHBOARD ----
        with st.expander("**Case Strength Dashboard** -- Visual overview of case readiness", expanded=True):
            _analysis_categories = {
                "Case Summary": bool(results.get("case_summary")),
                "Strategy": bool(results.get("strategy_notes")),
                "Witnesses": bool(results.get("witnesses")),
                "Cross-Exam": bool(results.get("cross_examination_plan")),
                "Direct-Exam": bool(results.get("direct_examination_plan")),
                "Timeline": bool(results.get("timeline")),
                "Evidence": bool(results.get("evidence_foundations")),
                "Conflicts": bool(results.get("consistency_check")),
                "Elements": bool(results.get("elements_map")),
                "Investigation": bool(results.get("investigation_plan")),
                "Entities": bool(results.get("entities")),
                "Devil's Advocate": bool(results.get("devils_advocate_notes")),
                "Voir Dire": bool(results.get("voir_dire_strategy")),
                "Legal Research": bool(results.get("legal_research_data")),
            }

            _saved_fp = results.get("_docs_fingerprint", "")
            _current_fp = case_mgr.compute_docs_fingerprint(case_id) if case_id else ""
            _is_stale = bool(_saved_fp and _current_fp and _saved_fp != _current_fp)

            if _is_stale:
                st.warning("**Documents changed** since last analysis. Modules may be out of date -- re-run to update.")

            _statuses = []
            for _mod_name, _mod_done in _analysis_categories.items():
                if _mod_done and _is_stale:
                    _statuses.append("Stale")
                elif _mod_done:
                    _statuses.append("Complete")
                else:
                    _statuses.append("Missing")

            _strength_data = pd.DataFrame({
                "Module": list(_analysis_categories.keys()),
                "Status": _statuses,
                "Value": [1 for _ in _analysis_categories],
            })

            _color_scale = alt.Scale(domain=["Complete", "Missing", "Stale"], range=["#22c55e", "#ef4444", "#f59e0b"])
            _strength_chart = alt.Chart(_strength_data).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("Module:N", sort=list(_analysis_categories.keys()), title=None),
                x=alt.X("Value:Q", title=None, axis=None),
                color=alt.Color("Status:N", scale=_color_scale, legend=alt.Legend(orient="bottom")),
                tooltip=["Module", "Status"]
            ).properties(title="Analysis Coverage", height=350)

            _dash_col1, _dash_col2 = st.columns([2, 1])

            with _dash_col1:
                st.altair_chart(_strength_chart, use_container_width=True)

            with _dash_col2:
                _witnesses = results.get("witnesses", [])
                if _witnesses and isinstance(_witnesses, list):
                    _w_types = {}
                    for _w in _witnesses:
                        if isinstance(_w, dict):
                            _wt = _w.get("type", "Unknown")
                            _w_types[_wt] = _w_types.get(_wt, 0) + 1
                    st.markdown("**Witness Breakdown**")
                    for _wt, _wc in sorted(_w_types.items(), key=lambda x: -x[1]):
                        st.markdown(f"**{_wt}**: {_wc}")
                    st.caption(f"Total: {len([w for w in _witnesses if isinstance(w, dict)])} witnesses")
                else:
                    st.info("No witnesses analyzed yet")

                st.markdown("---")

                _evidence = results.get("evidence_foundations", [])
                if _evidence and isinstance(_evidence, list):
                    st.markdown(f"**Evidence Items**: {len(_evidence)}")

                _timeline = results.get("timeline", [])
                if _timeline and isinstance(_timeline, list):
                    st.markdown(f"**Timeline Events**: {len(_timeline)}")

                _entities = results.get("entities", [])
                if _entities and isinstance(_entities, list):
                    st.markdown(f"**Entities**: {len(_entities)}")

            _da = results.get("devils_advocate_notes", "")
            if _da:
                st.markdown("---")
                st.markdown("**Risk Areas** (from Devil's Advocate)")
                _da_lines = [l.strip() for l in str(_da).split("\n") if l.strip() and len(l.strip()) > 20]
                for _risk in _da_lines[:5]:
                    if _risk.startswith(("-", "*", "\u2022", "1", "2", "3")):
                        st.markdown(f"- {_risk}")
                    else:
                        st.markdown(f"- {_risk[:200]}{'...' if len(_risk) > 200 else ''}")

        st.divider()

        # ---- Module Confidence Indicators ----
        try:
            from core.analysis_quality import score_all_modules, get_weak_modules
            _case_files_list = case_mgr.get_case_files(case_id) or []
            _confidence_scores = score_all_modules(results, _case_files_list)
            if _confidence_scores:
                with st.expander("\U0001f3af **Module Confidence Scores**", expanded=False):
                    st.caption("AI-assessed quality of each analysis module's output.")
                    _conf_cols = st.columns(3)
                    for _ci, (_ck, _cv) in enumerate(_confidence_scores.items()):
                        _c_score = _cv.get("score", 0)
                        _c_label = _cv.get("label", "Unknown")
                        _c_color = _cv.get("color", "gray")
                        _c_icon = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}.get(_c_color, "\u26aa")
                        _c_display = _cv.get("display_name", _ck)
                        with _conf_cols[_ci % 3]:
                            st.markdown(
                                f"{_c_icon} **{_c_display}**: {_c_score}/100 ({_c_label})"
                            )
                    # Weak modules action
                    _weak = get_weak_modules(results, _case_files_list)
                    if _weak:
                        st.divider()
                        st.warning(f"**{len(_weak)} weak module{'s' if len(_weak) != 1 else ''}** may benefit from re-analysis.")
                        if st.button("\U0001f504 Re-analyze Weak Modules", key="_regen_weak_modules"):
                            try:
                                from core.bg_analysis import start_background_analysis
                                from ui.shared import PROJECT_ROOT
                                _data_dir = str(PROJECT_ROOT / "data")
                                start_background_analysis(
                                    case_id=case_id,
                                    prep_id=prep_id,
                                    data_dir=_data_dir,
                                    existing_state=st.session_state.agent_results,
                                    prep_type=results.get("prep_type", "trial"),
                                    model_provider=model_provider,
                                    active_modules=_weak,
                                )
                                st.toast("\U0001f504 Re-analyzing weak modules...")
                                st.rerun()
                            except Exception as _regen_exc:
                                st.error(f"Failed to start re-analysis: {_regen_exc}")
        except Exception:
            pass

        # ---- AI Auto-Suggested Next Steps ----
        _step_modules = [
            ("case_summary",        "Case Summary",         "Foundation for all other modules. Run first.",                "generate_summary"),
            ("strategy_notes",      "Strategy Notes",       "Identifies defense theory, strengths & weaknesses.",          "generate_strategy"),
            ("witnesses",           "Witness Analysis",     "Needed before cross/direct exam planning.",                   "generate_witness"),
            ("evidence_foundations","Evidence Foundations", "Admissibility & suppression analysis for each exhibit.",      "generate_evidence"),
            ("cross_examination_plan","Cross-Examination",  "Requires witness list. High trial-impact.",                   "generate_cross"),
            ("direct_examination_plan","Direct Examination", "Requires witness list. Prepare your own witnesses.",          "generate_direct"),
            ("timeline",            "Timeline",             "Chronological event mapping for narrative.",                  "generate_timeline"),
            ("consistency_check",   "Conflict Check",       "Finds contradictions across documents.",                      "generate_consistency"),
            ("legal_elements",      "Elements Mapping",     "Maps facts to required legal elements per charge.",           "generate_elements"),
            ("devils_advocate_notes","Devil's Advocate",     "Stress-tests your case from prosecution's view.",             "generate_devils"),
            ("investigation_plan",  "Investigation Plan",   "External tasks: interviews, subpoenas, FOIA.",               "generate_investigation"),
            ("entities",            "Entity Extraction",    "People, places, orgs mentioned in documents.",               "generate_entities"),
            ("voir_dire_strategy",  "Voir Dire",            "Jury selection strategy. Needs case summary first.",          "generate_voir_dire"),
        ]

        _done = [key for key, _, _, _ in _step_modules if results.get(key)]
        _missing = [(key, label, reason, gen) for key, label, reason, gen in _step_modules if not results.get(key)]
        _pct = int(100 * len(_done) / len(_step_modules)) if _step_modules else 0

        with st.expander(f"**Suggested Next Steps** -- {len(_done)}/{len(_step_modules)} modules ({_pct}%)", expanded=bool(_missing)):
            if _missing:
                _priority_order = {
                    "case_summary": 0,
                    "strategy_notes": 1,
                    "witnesses": 2,
                    "evidence_foundations": 3,
                    "cross_examination_plan": 4,
                    "direct_examination_plan": 4,
                    "timeline": 3,
                    "consistency_check": 5,
                    "legal_elements": 5,
                    "devils_advocate_notes": 6,
                    "investigation_plan": 6,
                    "entities": 7,
                    "voir_dire_strategy": 8,
                }
                _sorted_missing = sorted(_missing, key=lambda x: _priority_order.get(x[0], 99))

                _has_summary = bool(results.get("case_summary"))
                _has_witnesses = bool(results.get("witnesses"))

                for _si, (_mk, _ml, _mr, _mg) in enumerate(_sorted_missing[:5]):
                    _priority = "High" if _si < 2 else ("Medium" if _si < 4 else "Low")
                    _blocked = ""
                    if _mk in ("cross_examination_plan", "direct_examination_plan") and not _has_witnesses:
                        _blocked = " _Needs Witness Analysis first_"
                    elif _mk != "case_summary" and not _has_summary:
                        _blocked = " _Needs Case Summary first_"

                    st.markdown(f"**{_priority}** -- **{_ml}**{_blocked}")
                    st.caption(_mr)

                if len(_sorted_missing) > 5:
                    st.caption(f"_+ {len(_sorted_missing) - 5} more modules available_")
            else:
                st.success("All modules complete! Your case is fully analyzed.")
                st.caption("You can re-run any module to update its analysis with new information.")

        if st.button(f"Regenerate Summary {estimate_cost(str(_agent_results.get('raw_documents', '')[:50000]), model_provider)}", key="regen_summary"):
            run_single_node(analyze_case, "Regenerating Case Summary", _agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, _agent_results)
            st.rerun()

        # --- Dashboard Analytics ---
        st.markdown("### Case Analytics")

        raw_docs = _agent_results.get("raw_documents", [])
        doc_types = [d.metadata.get("source", "Unknown").split('.')[-1] if '.' in d.metadata.get("source", "") else "txt" for d in raw_docs]
        df_docs = pd.DataFrame({"File Type": doc_types, "Count": [1]*len(doc_types)})

        entities = _agent_results.get("entities", [])
        if entities and isinstance(entities, list):
            ent_types = [e.get("type", "Unknown") for e in entities if isinstance(e, dict)]
        else:
            ent_types = []
        df_ents = pd.DataFrame({"Entity Type": ent_types, "Count": [1]*len(ent_types)})

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            if not df_docs.empty:
                chart1 = alt.Chart(df_docs).mark_bar().encode(
                    x=alt.X("File Type", sort='-y'),
                    y="count()",
                    color=alt.Color("File Type", legend=None)
                ).properties(title="Evidence Content Mix", height=250)
                st.altair_chart(chart1, use_container_width=True)
            else:
                st.info("No documents to visualize.")

        with col_chart2:
            if not df_ents.empty:
                chart2 = alt.Chart(df_ents).mark_bar().encode(
                    x=alt.X("Entity Type", sort='-y'),
                    y="count()",
                    color=alt.Color("Entity Type", scale=alt.Scale(scheme='tableau10'), legend=None)
                ).properties(title="Key Entity Distribution", height=250)
                st.altair_chart(chart2, use_container_width=True)
            else:
                st.info("No entities extracted for visualization.")

        st.divider()
        rendered_summary = render_with_references(results.get("case_summary", "No summary."))
        st.markdown(rendered_summary, unsafe_allow_html=True)

        # Challenge This: Case Summary
        _challenge_key_sum = f"_challenge_summary_{prep_id}"
        if st.button("Challenge Summary", key=_challenge_key_sum, help="AI devil's advocate will attack this analysis"):
            with st.spinner("Generating counter-arguments..."):
                _challenge_result = challenge_finding(
                    results.get("case_summary", "")[:2000],
                    results.get("case_summary", ""),
                    model_provider
                )
                st.session_state[f"_challenge_result_summary_{prep_id}"] = _challenge_result
        if st.session_state.get(f"_challenge_result_summary_{prep_id}"):
            with st.expander("**Challenge Results -- Summary**", expanded=True):
                st.markdown(st.session_state[f"_challenge_result_summary_{prep_id}"])

        st.markdown("#### Defense Strategy")
        strategy_text = results.get("strategy_notes", "No strategy.")
        rendered_strategy = render_with_references(strategy_text)
        st.markdown(rendered_strategy, unsafe_allow_html=True)

        # Challenge This: Strategy
        _challenge_key_str = f"_challenge_strategy_{prep_id}"
        if st.button("Challenge Strategy", key=_challenge_key_str, help="AI devil's advocate will attack this strategy"):
            with st.spinner("Generating counter-arguments..."):
                _challenge_result_s = challenge_finding(
                    results.get("strategy_notes", "")[:2000],
                    results.get("case_summary", ""),
                    model_provider
                )
                st.session_state[f"_challenge_result_strategy_{prep_id}"] = _challenge_result_s
        if st.session_state.get(f"_challenge_result_strategy_{prep_id}"):
            with st.expander("**Challenge Results -- Strategy**", expanded=True):
                st.markdown(st.session_state[f"_challenge_result_strategy_{prep_id}"])

        # Module Notes: Summary Tab
        st.divider()
        if prep_id:
            with st.expander("**Attorney Notes -- Summary**", expanded=False):
                _sum_notes = case_mgr.load_module_notes(case_id, prep_id, "summary")
                _new_sum_notes = st.text_area("Your notes on this summary:", value=_sum_notes, height=120, key=f"_notes_summary_{prep_id}")
                if _new_sum_notes != _sum_notes:
                    case_mgr.save_module_notes(case_id, prep_id, "summary", _new_sum_notes)
                    st.toast("Notes saved", icon="Done")

        st.divider()
        with st.expander("**Refine Strategy** -- Chat with the AI to adapt this strategy", expanded=bool(results.get("strategy_chat_history"))):
            chat_history = results.get("strategy_chat_history", [])

            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        st.chat_message("user").markdown(f"**You:** {msg['content']}")
                    else:
                        st.chat_message("assistant").markdown(msg["content"])
            else:
                st.caption("Tell the AI how to adjust the strategy. Examples:")
                st.caption("- *'Focus more on self-defense rather than alibi'*")
                st.caption("- *'Add a section on suppression of evidence'*")
                st.caption("- *'Make the tone more aggressive'*")

            user_instruction = st.chat_input("How should the strategy change?", key="strategy_chat_input")

            if user_instruction:
                st.chat_message("user").markdown(f"**You:** {user_instruction}")

                with st.chat_message("assistant"):
                    with st.status("Refining strategy...", expanded=True) as status:
                        st.write("Analyzing current strategy and your instructions...")

                        try:
                            from langchain_core.messages import SystemMessage, HumanMessage

                            _s_llm = get_llm(_agent_results.get("current_model"))
                            _s_ctx = get_case_context(_agent_results)
                            _s_strategy = results.get("strategy_notes", "")
                            _s_summary = results.get("case_summary", "")
                            _s_charges = results.get("charges", [])

                            _s_messages = [
                                SystemMessage(content=f"""You are a {_s_ctx['strategy_role']}. Refine the strategy based on the attorney's instruction.

CURRENT STRATEGY:
{_s_strategy}

CASE SUMMARY:
{_s_summary}

CHARGES: {_s_charges}

RULES:
- Rewrite the ENTIRE strategy incorporating the instruction.
- Maintain markdown format. Keep original content not asked to change.
- Add a brief "Changes Made" section at the end.""")
                            ]
                            for _sm in chat_history:
                                if _sm["role"] == "user":
                                    _s_messages.append(HumanMessage(content=_sm["content"]))
                                else:
                                    _s_messages.append(SystemMessage(content=_sm["content"]))
                            _s_messages.append(HumanMessage(content=user_instruction))

                            # Stream tokens
                            _stream_placeholder = st.empty()
                            _streamed_text = ""
                            for _kind, _data in invoke_with_retry_streaming(_s_llm, _s_messages):
                                if _kind == "token":
                                    _streamed_text += _data
                                    _stream_placeholder.markdown(_streamed_text + "\u258c")
                                elif _kind == "done":
                                    _streamed_text = _data
                            _stream_placeholder.markdown(_streamed_text)

                            _changes_match = re.search(r"(?:Changes Made|## Changes|### Changes).*", _streamed_text, re.DOTALL | re.IGNORECASE)
                            _changes_section = _changes_match.group(0) if _changes_match else "Strategy updated."

                            updates = {
                                "strategy_notes": _streamed_text,
                                "strategy_chat_history": chat_history + [
                                    {"role": "user", "content": user_instruction},
                                    {"role": "assistant", "content": _changes_section}
                                ]
                            }
                        except Exception:
                            updates = refine_strategy(
                                st.session_state.agent_results,
                                user_instruction,
                                chat_history
                            )
                            new_strategy = updates.get("strategy_notes", "")
                            if new_strategy:
                                st.markdown(str(new_strategy)[:500] + ("..." if len(str(new_strategy)) > 500 else ""))

                        status.update(label="Strategy refined!", state="complete")

                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, updates)
                st.rerun()

            if chat_history:
                if st.button("Reset Refinement History", key="reset_strategy_chat"):
                    st.session_state.agent_results["strategy_chat_history"] = []
                    case_mgr.save_prep_state(st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results)
                    st.rerun()

        # --- Client Report Generator ---
        st.divider()
        with st.expander("**Generate Client Report** -- Plain-language case briefing for your client"):
            st.caption("Creates a report written in simple English that you can share with your client.")
            if st.button(f"Generate Client Report {estimate_cost(results.get('case_summary', '') + results.get('strategy_notes', ''), model_provider)}", key="gen_client_report", type="primary"):
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
                    key="dl_client_report"
                )

        # Quick-Ask: Summary
        render_quick_ask("case_summary", "Case Summary", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[2]:  # NETWORK
        st.subheader("Interactive Entity Network")

        entities = results.get("entities", [])
        relationships = results.get("relationships", [])

        if not entities and not relationships:
            st.info("No network data found. Run analysis to extract.")
        else:
            nodes = []
            edges = []

            for e in entities:
                if isinstance(e, dict):
                    e_id = e.get('id', str(e))
                    e_type = e.get('type', '?')
                    color = "#90caf9"
                    if e_type == "PERSON": color = "#ffcdd2"
                    elif e_type == "ORGANIZATION": color = "#c8e6c9"
                    elif e_type == "DATE": color = "#fff9c4"
                    nodes.append(Node(
                        id=e_id,
                        label=e.get('name', e_id),
                        size=25,
                        shape="dot",
                        color=color
                    ))

            for r in relationships:
                if isinstance(r, dict):
                    src = r.get("source")
                    dst = r.get("target")
                    rel = r.get("relation")
                    if src and dst:
                        edges.append(Edge(
                            source=src,
                            target=dst,
                            label=rel,
                            color="#bdbdbd"
                        ))

            config = Config(
                width=700,
                height=500,
                directed=True,
                physics=True,
                hierarchy=False,
                nodeHighlightBehavior=True,
                highlightColor="#F7A7A6",
                collapsible=False
            )

            return_value = agraph(nodes=nodes, edges=edges, config=config)

            with st.expander("Raw Network Data"):
                st.write(relationships)

    with tabs[3]:  # DEVIL'S ADVOCATE
        ctx_type = results.get('case_type', 'criminal')
        devil_title = "Opposing Counsel Rebuttal" if ctx_type != 'criminal' else "Prosecution Rebuttal"
        st.subheader(f"{devil_title} (Devil's Advocate)")

        if st.button(f"Regenerate Critique {estimate_cost(results.get('strategy_notes', '') + results.get('case_summary', ''), model_provider)}", key="regen_devils"):
            run_single_node(generate_devils_advocate, "Regenerating Devil's Advocate", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        da_text = results.get("devils_advocate_notes", "")
        if da_text:
            critique_label = "opposing counsel" if ctx_type != 'criminal' else "a hostile Prosecutor"
            st.markdown(f"The following is a critique of your strategy from the perspective of {critique_label}.")
            rendered_da = render_with_references(da_text)
            st.warning(rendered_da)
        else:
            st.info(
                "No critique generated yet. Click **Regenerate Critique** above or run "
                "the full analysis to generate a Devil's Advocate rebuttal of your strategy."
            )
        render_module_notes(case_mgr, case_id, prep_id, "devils_advocate", "Devil's Advocate")

        # Quick-Ask: Devil's Advocate
        render_quick_ask("devils_advocate_notes", "Devil's Advocate", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[4]:  # NOTES
        st.subheader("Attorney Notes & Scratchpad")

        notes_tab_case, notes_tab_prep, notes_tab_costs = st.tabs(["Case Notes", f"{current_prep_name} Notes", "Cost History"])

        with notes_tab_case:
            st.caption("Shared across all preparations for this case.")
            _case_notes_key = f"_case_notes_{case_id}"
            existing_case_notes = case_mgr.load_case_notes(case_id)
            if _case_notes_key not in st.session_state:
                st.session_state[_case_notes_key] = existing_case_notes
            case_notes = st.text_area(
                "Case-level notes",
                value=st.session_state[_case_notes_key],
                height=300,
                placeholder="Free-form notes about this case -- hearing dates, reminders, key observations...",
                key=f"_case_notes_input_{case_id}",
                label_visibility="collapsed"
            )
            if st.button("Save Case Notes", key="_save_case_notes"):
                case_mgr.save_case_notes(case_id, case_notes)
                st.session_state[_case_notes_key] = case_notes
                st.success("Case notes saved!")

        with notes_tab_prep:
            if prep_id:
                st.caption(f"Notes specific to this preparation: **{current_prep_name}**")
                _prep_notes_key = f"_prep_notes_{case_id}_{prep_id}"
                existing_prep_notes = case_mgr.load_notes(case_id, prep_id)
                if _prep_notes_key not in st.session_state:
                    st.session_state[_prep_notes_key] = existing_prep_notes
                prep_notes = st.text_area(
                    "Preparation notes",
                    value=st.session_state[_prep_notes_key],
                    height=300,
                    placeholder="Notes about this preparation -- strategy thoughts, hearing observations, witness impressions...",
                    key=f"_prep_notes_input_{case_id}_{prep_id}",
                    label_visibility="collapsed"
                )
                if st.button("Save Prep Notes", key="_save_prep_notes"):
                    case_mgr.save_notes(case_id, prep_id, prep_notes)
                    st.session_state[_prep_notes_key] = prep_notes
                    st.success("Preparation notes saved!")
            else:
                st.info("Select a preparation to add notes.")

        with notes_tab_costs:
            st.caption("API costs logged for this preparation.")
            if prep_id:
                cost_history = case_mgr.get_cost_history(case_id, prep_id)
                if cost_history:
                    cost_df = pd.DataFrame(cost_history)
                    total_cost = sum(e.get("cost", 0) for e in cost_history)
                    total_tokens = sum(e.get("tokens", 0) for e in cost_history)
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.metric("Total Cost", f"${total_cost:.4f}")
                    cc2.metric("Total Tokens", f"{total_tokens:,}")
                    cc3.metric("API Calls", len(cost_history))
                    st.dataframe(cost_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No cost data logged yet. Run an analysis to start tracking.")
            else:
                st.info("Select a preparation to view costs.")

    with tabs[5]:  # DEADLINES
        st.subheader("Deadline & Court Date Tracker")

        if prep_id:
            prep_deadlines = case_mgr.load_deadlines(case_id, prep_id)
            _today = date.today()
            for dl in prep_deadlines:
                try:
                    _dl_date = date.fromisoformat(dl.get('date', ''))
                    _days = (_dl_date - _today).days
                    if _days < 0:
                        st.error(f"**OVERDUE by {abs(_days)} day(s):** {dl.get('label', 'Untitled')} -- {dl.get('date', '')}")
                    elif _days == 0:
                        st.error(f"**DUE TODAY:** {dl.get('label', 'Untitled')} -- {dl.get('date', '')}")
                    elif _days <= 3:
                        st.warning(f"**Due in {_days} day(s):** {dl.get('label', 'Untitled')} -- {dl.get('date', '')}")
                except (ValueError, TypeError):
                    pass

            st.divider()

            with st.expander("Add New Deadline", expanded=not bool(prep_deadlines)):
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    dl_label = st.text_input("Deadline Label", placeholder="e.g. Motion to Suppress Hearing", key="_dl_label")
                    dl_date_val = st.date_input("Date", key="_dl_date")
                with dl_col2:
                    dl_category = st.selectbox("Category", ["Court Date", "Filing Deadline", "Statute of Limitations", "Discovery", "Deposition", "Custom"], key="_dl_cat")
                    dl_time = st.text_input("Time (optional)", placeholder="e.g. 9:00 AM", key="_dl_time")

                dl_reminder_options = st.multiselect(
                    "Remind me",
                    options=[30, 14, 7, 3, 1, 0],
                    default=[7, 3, 1, 0],
                    format_func=lambda x: f"{x} days before" if x > 0 else "Day-of",
                    key="_dl_reminders"
                )

                if st.button("Add Deadline", type="primary", key="_dl_add"):
                    if dl_label and dl_date_val:
                        new_dl = {
                            "label": dl_label,
                            "date": dl_date_val.isoformat(),
                            "category": dl_category,
                            "time": dl_time,
                            "reminder_days": sorted(dl_reminder_options, reverse=True),
                        }
                        case_mgr.save_deadline(case_id, prep_id, new_dl)
                        st.success(f"Deadline added: {dl_label} on {dl_date_val}")
                        st.rerun()
                    else:
                        st.warning("Please enter a label and date.")

            if prep_deadlines:
                st.markdown(f"### {len(prep_deadlines)} Deadline(s)")
                for idx, dl in enumerate(prep_deadlines):
                    dl_id = dl.get('id', '')
                    days_rem = 999
                    try:
                        _dl_d = date.fromisoformat(dl.get('date', ''))
                        days_rem = (_dl_d - _today).days
                    except (ValueError, TypeError):
                        pass

                    if days_rem < 0:
                        icon = "OVERDUE"
                    elif days_rem == 0:
                        icon = "TODAY"
                    elif days_rem <= 3:
                        icon = "SOON"
                    elif days_rem <= 7:
                        icon = "UPCOMING"
                    else:
                        icon = ""

                    _dl_editing = st.session_state.get("_editing_dl_id") == dl_id

                    with st.container(border=True):
                        if _dl_editing:
                            # --- Inline edit form ---
                            st.markdown(f"**Editing:** {dl.get('label', 'Untitled')}")
                            _dle_c1, _dle_c2 = st.columns(2)
                            with _dle_c1:
                                _dle_label = st.text_input("Label", value=dl.get("label", ""), key=f"_dle_label_{dl_id}")
                                try:
                                    _dle_date_default = date.fromisoformat(dl.get("date", ""))
                                except (ValueError, TypeError):
                                    _dle_date_default = _today
                                _dle_date = st.date_input("Date", value=_dle_date_default, key=f"_dle_date_{dl_id}")
                            with _dle_c2:
                                _cat_options = ["Court Date", "Filing Deadline", "Statute of Limitations", "Discovery", "Deposition", "Custom"]
                                _cat_idx = 0
                                if dl.get("category") in _cat_options:
                                    _cat_idx = _cat_options.index(dl["category"])
                                _dle_cat = st.selectbox("Category", _cat_options, index=_cat_idx, key=f"_dle_cat_{dl_id}")
                                _dle_time = st.text_input("Time", value=dl.get("time", ""), key=f"_dle_time_{dl_id}")

                            _dle_reminders = st.multiselect(
                                "Reminders",
                                options=[30, 14, 7, 3, 1, 0],
                                default=[r for r in dl.get("reminder_days", [7, 3, 1, 0]) if r in [30, 14, 7, 3, 1, 0]],
                                format_func=lambda x: f"{x} days before" if x > 0 else "Day-of",
                                key=f"_dle_rem_{dl_id}"
                            )

                            _dle_save_col, _dle_cancel_col, _ = st.columns([1, 1, 3])
                            with _dle_save_col:
                                if st.button("Save", key=f"_dle_save_{dl_id}", type="primary"):
                                    if _dle_label.strip():
                                        updated_dl = {
                                            "id": dl_id,
                                            "label": _dle_label.strip(),
                                            "date": _dle_date.isoformat(),
                                            "category": _dle_cat,
                                            "time": _dle_time,
                                            "reminder_days": sorted(_dle_reminders, reverse=True),
                                        }
                                        case_mgr.save_deadline(case_id, prep_id, updated_dl)
                                        st.session_state.pop("_editing_dl_id", None)
                                        st.rerun()
                                    else:
                                        st.warning("Label is required.")
                            with _dle_cancel_col:
                                if st.button("Cancel", key=f"_dle_cancel_{dl_id}"):
                                    st.session_state.pop("_editing_dl_id", None)
                                    st.rerun()
                        else:
                            # --- Display mode ---
                            dc1, dc2, dc3, dc4 = st.columns([3, 1, 0.5, 0.5])
                            with dc1:
                                st.markdown(f"**{dl.get('label', 'Untitled')}** {f'({icon})' if icon else ''}")
                                st.caption(f"{dl.get('category', '')} -- {dl.get('date', '')} {dl.get('time', '')}")
                                if days_rem < 0:
                                    st.markdown(f"*OVERDUE by {abs(days_rem)} day(s)*")
                                elif days_rem == 0:
                                    st.markdown(f"***DUE TODAY***")
                                else:
                                    st.markdown(f"*{days_rem} day(s) remaining*")
                            with dc2:
                                reminders = dl.get('reminder_days', [])
                                st.caption(f"Reminders: {', '.join(str(r)+'d' for r in reminders)}")
                            with dc3:
                                if st.button("✏️", key=f"_dl_edit_{dl_id}_{idx}", help="Edit deadline"):
                                    st.session_state["_editing_dl_id"] = dl_id
                                    st.rerun()
                            with dc4:
                                if st.button("🗑️", key=f"_dl_del_{dl_id}_{idx}", help="Delete deadline"):
                                    case_mgr.delete_deadline(case_id, prep_id, dl_id)
                                    st.rerun()
            else:
                st.info("No deadlines set for this preparation. Add one above!")
        else:
            st.info("Select a preparation to manage deadlines.")

    with tabs[6]:  # READINESS
        st.subheader("Trial Readiness Dashboard")

        if results:
            score, grade, breakdown = compute_readiness_score(results)

            _sc1, _sc2, _sc3 = st.columns([1, 1, 2])
            with _sc1:
                st.metric("Readiness Score", f"{score}/100")
            with _sc2:
                st.metric("Grade", f"{grade}")
            with _sc3:
                st.progress(min(score / 100, 1.0), text=f"{score}% ready")

            st.divider()

            st.markdown("### Module Status Checklist")

            _module_status = {
                "Case Summary": {
                    "key": "case_summary",
                    "check": lambda r: bool(r.get('case_summary') and len(str(r['case_summary'])) > 50),
                    "points": 10, "max": 10,
                },
                "Strategy Notes": {
                    "key": "strategy_notes",
                    "check": lambda r: bool(r.get('strategy_notes') and len(str(r['strategy_notes'])) > 50),
                    "points": 10, "max": 10,
                },
                "Witnesses": {
                    "key": "witnesses",
                    "check": lambda r: isinstance(r.get('witnesses', []), list) and len(r.get('witnesses', [])) > 0,
                    "points": 10, "max": 10,
                },
                "Cross-Examination": {
                    "key": "cross_examination_plan",
                    "check": lambda r: isinstance(r.get('cross_examination_plan', []), list) and len(r.get('cross_examination_plan', [])) > 0,
                    "points": 10, "max": 10,
                },
                "Direct-Examination": {
                    "key": "direct_examination_plan",
                    "check": lambda r: isinstance(r.get('direct_examination_plan', []), list) and len(r.get('direct_examination_plan', [])) > 0,
                    "points": 10, "max": 10,
                },
                "Legal Elements": {
                    "key": "legal_elements",
                    "check": lambda r: isinstance(r.get('legal_elements', []), list) and len(r.get('legal_elements', [])) > 0,
                    "points": 15, "max": 15,
                },
                "Investigation Plan": {
                    "key": "investigation_plan",
                    "check": lambda r: isinstance(r.get('investigation_plan', []), list) and len(r.get('investigation_plan', [])) > 0,
                    "points": 15, "max": 15,
                },
                "Timeline": {
                    "key": "timeline",
                    "check": lambda r: isinstance(r.get('timeline', []), list) and len(r.get('timeline', [])) > 0,
                    "points": 5, "max": 5,
                },
                "Consistency Check": {
                    "key": "consistency_check",
                    "check": lambda r: (isinstance(r.get('consistency_check', []), list) and len(r.get('consistency_check', [])) > 0) or (isinstance(r.get('consistency_check', ''), str) and len(r.get('consistency_check', '')) > 50),
                    "points": 5, "max": 5,
                },
                "Entities": {
                    "key": "entities",
                    "check": lambda r: isinstance(r.get('entities', []), list) and len(r.get('entities', [])) > 0,
                    "points": 5, "max": 5,
                },
                "Devil's Advocate": {
                    "key": "devils_advocate_notes",
                    "check": lambda r: bool(r.get('devils_advocate_notes') and len(str(r['devils_advocate_notes'])) > 50),
                    "points": 5, "max": 5,
                },
            }

            _done_modules = []
            _missing_modules = []
            _partial_modules = []

            for mod_name, mod_info in _module_status.items():
                _is_done = mod_info['check'](results)

                if mod_info['key'] == 'investigation_plan' and _is_done:
                    inv = results.get('investigation_plan', [])
                    if isinstance(inv, list) and len(inv) > 0:
                        total_tasks = len(inv)
                        done_tasks = sum(1 for t in inv if isinstance(t, dict) and t.get('status') == 'completed')
                        if 0 < done_tasks < total_tasks:
                            _partial_modules.append((mod_name, mod_info, f"{done_tasks}/{total_tasks} tasks done"))
                            continue

                if _is_done:
                    _done_modules.append((mod_name, mod_info))
                else:
                    _missing_modules.append((mod_name, mod_info))

            for mod_name, mod_info in _done_modules:
                data = results.get(mod_info['key'], '')
                _count = ""
                if isinstance(data, list):
                    _count = f" ({len(data)} items)"
                elif isinstance(data, str):
                    _count = f" ({len(data.split())} words)"
                st.markdown(f"Done -- **{mod_name}**{_count} -- *{mod_info['points']}/{mod_info['max']} pts*")

            for mod_name, mod_info, detail in _partial_modules:
                st.markdown(f"In Progress -- **{mod_name}** -- {detail} -- *partial credit*")

            for mod_name, mod_info in _missing_modules:
                st.markdown(f"Missing -- **{mod_name}** -- *0/{mod_info['max']} pts -- Not yet generated*")

            st.divider()

            if _missing_modules:
                st.markdown("### Gap Analysis")
                _gap_points = sum(m[1]['max'] for m in _missing_modules)
                st.warning(f"**{len(_missing_modules)} module(s)** not yet completed, worth **{_gap_points} points**. Run analysis on these to improve your readiness score.")

                _gap_recommendations = {
                    'case_summary': 'Run the full analysis or click "Regenerate Summary" on the Summary tab.',
                    'strategy_notes': 'The Strategy module runs automatically during full analysis.',
                    'witnesses': 'Run full analysis or regenerate on the Witnesses tab.',
                    'cross_examination_plan': 'Navigate to Cross-Exam tab and click Regenerate.',
                    'direct_examination_plan': 'Navigate to Direct-Exam tab and click Regenerate.',
                    'legal_elements': 'Navigate to Elements tab and click Regenerate.',
                    'investigation_plan': 'Navigate to Investigation tab and click Regenerate.',
                    'timeline': 'Navigate to Timeline tab and click Regenerate.',
                    'consistency_check': 'Navigate to Conflicts tab and click Regenerate.',
                    'entities': 'Navigate to Entities tab and click Regenerate.',
                    'devils_advocate_notes': "Navigate to Devil's Advocate tab and click Regenerate.",
                }

                for mod_name, mod_info in _missing_modules:
                    rec = _gap_recommendations.get(mod_info['key'], 'Run the full analysis.')
                    st.info(f"**{mod_name}**: {rec}")
            else:
                st.success("**All modules are complete!** Your case preparation is fully ready.")
        else:
            st.info("Run analysis first to see your trial readiness dashboard.")

        # Custom Checklist Builder
        st.divider()
        with st.expander("**Custom Checklist** -- Build your own task list for this case", expanded=False):
            _ck_case_id = st.session_state.current_case_id
            _ck_prep_id = st.session_state.current_prep_id
            if _ck_case_id and _ck_prep_id:
                _cl_items = case_mgr.load_checklist(_ck_case_id, _ck_prep_id)

                _cl_total = len(_cl_items)
                _cl_done = sum(1 for i in _cl_items if i.get("checked"))
                if _cl_total > 0:
                    _cl_pct = _cl_done / _cl_total
                    st.progress(_cl_pct, text=f"{_cl_done}/{_cl_total} tasks complete ({_cl_pct:.0%})")

                st.caption("Start with a template or add your own items:")
                _tmpl_cols = st.columns([1, 1, 1, 1])
                _tmpl_names = list(case_mgr.CHECKLIST_TEMPLATES.keys())
                for _ti, _tn in enumerate(_tmpl_names):
                    with _tmpl_cols[_ti % 4]:
                        if st.button(f"{_tn}", key=f"_cl_tmpl_{_ti}", use_container_width=True):
                            case_mgr.load_checklist_template(_ck_case_id, _ck_prep_id, _tn)
                            st.rerun()

                with st.form("add_checklist_item", clear_on_submit=True):
                    _ac_cols = st.columns([3, 1, 1, 0.5])
                    with _ac_cols[0]:
                        _cl_text = st.text_input("Task", placeholder="e.g., File motion to suppress", label_visibility="collapsed")
                    with _ac_cols[1]:
                        _cl_cat = st.selectbox("Category", ["General", "Documents", "Witnesses", "Motions", "Research", "Exhibits", "Strategy", "Client", "Admin", "Court", "Evidence", "Statements", "Jury"], label_visibility="collapsed")
                    with _ac_cols[2]:
                        _cl_pri = st.selectbox("Priority", ["high", "medium", "low"], index=1, label_visibility="collapsed")
                    with _ac_cols[3]:
                        _cl_submit = st.form_submit_button("+", use_container_width=True)
                    if _cl_submit and _cl_text:
                        case_mgr.add_checklist_item(_ck_case_id, _ck_prep_id, _cl_text, _cl_cat, _cl_pri)
                        st.rerun()

                if _cl_items:
                    _priority_icons = {"high": "HIGH", "medium": "MED", "low": "LOW"}
                    _categories = {}
                    for _ci in _cl_items:
                        _cat = _ci.get("category", "General")
                        _categories.setdefault(_cat, []).append(_ci)

                    for _cat_name in sorted(_categories.keys()):
                        _cat_items = _categories[_cat_name]
                        _cat_done = sum(1 for i in _cat_items if i.get("checked"))
                        st.markdown(f"**{_cat_name}** ({_cat_done}/{len(_cat_items)})")

                        for _item in _cat_items:
                            _item_id = _item.get("id", "")
                            _is_checked = _item.get("checked", False)
                            _pri_icon = _priority_icons.get(_item.get("priority", "medium"), "MED")

                            _ic1, _ic2, _ic3 = st.columns([0.05, 0.85, 0.1])
                            with _ic1:
                                _new_checked = st.checkbox(
                                    "done",
                                    value=_is_checked,
                                    key=f"_cl_chk_{_item_id}",
                                    label_visibility="collapsed"
                                )
                                if _new_checked != _is_checked:
                                    case_mgr.toggle_checklist_item(_ck_case_id, _ck_prep_id, _item_id, _new_checked)
                                    st.rerun()
                            with _ic2:
                                _display_text = f"~~{_item['text']}~~" if _is_checked else _item["text"]
                                st.markdown(f"[{_pri_icon}] {_display_text}")
                            with _ic3:
                                if st.button("Delete", key=f"_cl_del_{_item_id}"):
                                    case_mgr.delete_checklist_item(_ck_case_id, _ck_prep_id, _item_id)
                                    st.rerun()

                    st.divider()
                    _bulk_cols = st.columns(3)
                    with _bulk_cols[0]:
                        if _cl_done > 0 and st.button("Clear Completed", key="_cl_clear_done"):
                            _remaining = [i for i in _cl_items if not i.get("checked")]
                            case_mgr.save_checklist(_ck_case_id, _ck_prep_id, _remaining)
                            st.rerun()
                    with _bulk_cols[1]:
                        if _cl_total > 0 and st.button("Check All", key="_cl_check_all"):
                            for _ci in _cl_items:
                                _ci["checked"] = True
                                _ci["completed_at"] = datetime.now().isoformat()
                            case_mgr.save_checklist(_ck_case_id, _ck_prep_id, _cl_items)
                            st.rerun()
                    with _bulk_cols[2]:
                        if _cl_total > 0 and st.button("Clear All", key="_cl_clear_all"):
                            case_mgr.save_checklist(_ck_case_id, _ck_prep_id, [])
                            st.rerun()
                else:
                    st.info("No checklist items yet. Load a template or add your own above.")
            else:
                st.info("Select a preparation to use the checklist.")
