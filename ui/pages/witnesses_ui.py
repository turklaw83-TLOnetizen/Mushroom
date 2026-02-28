"""Witnesses & Exam UI module -- ported from ui_modules/witnesses_ui.py."""
import logging
import os
import json

import pandas as pd
import streamlit as st
from datetime import datetime, date
from streamlit_pdf_viewer import pdf_viewer

from core.nodes import (
    develop_strategy, generate_cross_questions,
    generate_direct_questions, generate_witness_prep,
    generate_interview_plan, analyze_deposition,
    generate_deposition_outline,
)
from core.append_only import safe_update_and_save
from core.cost_tracker import format_cost_badge
from ui.shared import render_module_notes, render_quick_ask

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local helpers (previously imported from app)
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


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render(case_id, case_mgr, results, tabs, selected_group, nav_groups, model_provider, prep_id):
    """Render the Witnesses & Exam UI based on active_tab."""
    run_single_node = _run_single_node
    render_module_export = _render_module_export
    estimate_cost = lambda text, mp: format_cost_badge(text, mp)

    with tabs[0]:  # WITNESSES
        st.subheader("Witness Analysis")
        render_module_export("Witnesses", results.get("witnesses"), "witnesses")

        if st.button(f"Regenerate Witnesses {estimate_cost(results.get('case_summary', ''), model_provider)}", key="regen_witnesses"):
            run_single_node(develop_strategy, "Regenerating Witness Analysis", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        witnesses = results.get("witnesses", [])
        if witnesses:
            critical_count = sum(1 for w in witnesses if isinstance(w, dict) and w.get('_critical'))
            if critical_count:
                st.info(f"**{critical_count} critical witness(es)** flagged")

            # Editable Witness Table
            with st.expander("**Edit Witness List** -- Modify names, roles, or flag critical", expanded=False):
                _w_edit = []
                for _w in witnesses:
                    if isinstance(_w, dict):
                        _w_edit.append({
                            "Name": _w.get("name", ""),
                            "Type": _w.get("type", ""),
                            "Goal": _w.get("goal", ""),
                            "Key Points": ", ".join(_w.get("key_points", [])) if isinstance(_w.get("key_points"), list) else str(_w.get("key_points", "")),
                            "Critical": _w.get("_critical", False),
                        })
                if _w_edit:
                    _w_df = pd.DataFrame(_w_edit)
                    _w_edited = st.data_editor(
                        _w_df,
                        column_config={
                            "Name": st.column_config.TextColumn("Name", width="medium"),
                            "Type": st.column_config.SelectboxColumn("Type", options=["Prosecution/Plaintiff", "Defense", "Expert", "Neutral", "Character"], width="small"),
                            "Goal": st.column_config.TextColumn("Goal", width="large"),
                            "Key Points": st.column_config.TextColumn("Key Points", width="large"),
                            "Critical": st.column_config.CheckboxColumn("Critical", width="small"),
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        key="_witness_editor"
                    )

                    if st.button("Save Witness Changes", key="_save_witness_edits"):
                        _new_witnesses = []
                        for _, row in _w_edited.iterrows():
                            kp = row.get("Key Points", "")
                            key_points_list = [k.strip() for k in kp.split(",")] if kp else []
                            _new_witnesses.append({
                                "name": row.get("Name", ""),
                                "type": row.get("Type", ""),
                                "goal": row.get("Goal", ""),
                                "key_points": key_points_list,
                                "_critical": bool(row.get("Critical", False)),
                            })
                        st.session_state.agent_results["witnesses"] = _new_witnesses
                        case_mgr.save_prep_state(st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results)
                        st.success("Witnesses updated!")
                        st.rerun()

            # Display witness cards
            for w_idx, w in enumerate(witnesses):
                if isinstance(w, dict):
                    star_prefix = "** " if w.get('_critical') else ""
                    w_name = w.get('name', 'Unknown')
                    w_type = w.get('type', '')
                    w_goal = w.get('goal', '')

                    with st.expander(f"{star_prefix}**{w_name}** ({w_type})", expanded=w.get('_critical', False)):
                        w_card_col1, w_card_col2, w_flag_col = st.columns([2, 2, 0.5])
                        with w_card_col1:
                            st.markdown(f"**Role:** {w.get('type', 'N/A')}")
                            st.markdown(f"**Goal:** {w_goal}")
                        with w_card_col2:
                            st.markdown(f"**Key Points:**")
                            key_pts = w.get('key_points', [])
                            if isinstance(key_pts, list):
                                for kp in key_pts:
                                    st.markdown(f"- {kp}")
                            elif isinstance(key_pts, str):
                                st.markdown(key_pts)
                        with w_flag_col:
                            is_crit_w = w.get('_critical', False)
                            w_flag_label = "Critical" if is_crit_w else "Flag"
                            if st.button(w_flag_label, key=f"_flag_w_{w_idx}", help="Toggle critical flag"):
                                witnesses[w_idx]['_critical'] = not is_crit_w
                                st.session_state.agent_results['witnesses'] = witnesses
                                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                                st.rerun()
        else:
            st.info("No witnesses identified. Run analysis or add them manually above.")

        # Module Notes: Witnesses Tab
        st.divider()
        with st.expander("**Attorney Notes -- Witnesses**", expanded=False):
            _w_notes = case_mgr.load_module_notes(case_id, prep_id, "witnesses")
            _new_w_notes = st.text_area("Your notes on witnesses:", value=_w_notes, height=120, key=f"_notes_witnesses_{prep_id}")
            if _new_w_notes != _w_notes:
                case_mgr.save_module_notes(case_id, prep_id, "witnesses", _new_w_notes)
                st.toast("Notes saved", icon="Done")

        # Quick-Ask: Witnesses
        render_quick_ask("witnesses", "Witness Analysis", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[1]:  # CROSS-EXAMINATION
        st.subheader("Cross-Examination Plan")

        if st.button(f"Regenerate Cross-Exam {estimate_cost(str(results.get('witnesses', '')), model_provider)}", key="regen_cross"):
            run_single_node(generate_cross_questions, "Regenerating Cross-Exam", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        cross_plan = results.get("cross_examination_plan", [])

        c_data = []
        if isinstance(cross_plan, str):
            try:
                c_data = json.loads(cross_plan.replace("```json", "").replace("```", ""))
            except Exception:
                st.markdown(cross_plan)
        elif isinstance(cross_plan, list):
            c_data = cross_plan

        if c_data:
            for w_block in c_data:
                if isinstance(w_block, dict):
                    w_name = w_block.get("witness", "Unknown Witness")
                    w_topics = w_block.get("topics", [])
                    with st.expander(f"**{w_name}** ({len(w_topics)} topic(s))", expanded=False):
                        for t in w_topics:
                            if isinstance(t, dict):
                                st.markdown(f"**Topic:** {t.get('topic')}")
                                for q_idx, q in enumerate(t.get("questions", [])):
                                    if isinstance(q, dict):
                                        crit_marker = " [CRITICAL]" if q.get('_critical') else ""
                                        st.markdown(f"- **Q{q_idx + 1}:** {q.get('question', '')}{crit_marker}")
                                        if q.get('follow_up'):
                                            st.caption(f"  Follow-up: {q['follow_up']}")
                                    elif isinstance(q, str):
                                        st.markdown(f"- Q{q_idx + 1}: {q}")
                                st.divider()
        else:
            st.info("No cross-examination plan generated. Analyze witnesses first.")
        render_module_notes(case_mgr, case_id, prep_id, "cross_examination", "Cross-Examination")

        # Quick-Ask: Cross-Examination
        render_quick_ask("cross_examination_plan", "Cross-Examination", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[2]:  # DIRECT-EXAMINATION
        st.subheader("Direct-Examination Plan")

        if st.button(f"Regenerate Direct-Exam {estimate_cost(str(results.get('witnesses', '')), model_provider)}", key="regen_direct"):
            run_single_node(generate_direct_questions, "Regenerating Direct-Exam", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        direct_plan = results.get("direct_examination_plan", [])

        d_data = []
        if isinstance(direct_plan, str):
            try:
                d_data = json.loads(direct_plan.replace("```json", "").replace("```", ""))
            except Exception:
                st.markdown(direct_plan)
        elif isinstance(direct_plan, list):
            d_data = direct_plan

        if d_data:
            for w_block in d_data:
                if isinstance(w_block, dict):
                    w_name = w_block.get("witness", "Unknown Witness")
                    w_topics = w_block.get("topics", [])
                    with st.expander(f"**{w_name}** ({len(w_topics)} topic(s))", expanded=False):
                        for t in w_topics:
                            if isinstance(t, dict):
                                st.markdown(f"**Topic:** {t.get('topic')}")
                                for q_idx, q in enumerate(t.get("questions", [])):
                                    if isinstance(q, dict):
                                        crit_marker = " [CRITICAL]" if q.get('_critical') else ""
                                        st.markdown(f"- **Q{q_idx + 1}:** {q.get('question', '')}{crit_marker}")
                                        if q.get('follow_up'):
                                            st.caption(f"  Follow-up: {q['follow_up']}")
                                    elif isinstance(q, str):
                                        st.markdown(f"- Q{q_idx + 1}: {q}")
                                st.divider()
        else:
            st.info("No direct-examination plan generated. Analyze witnesses first.")
        render_module_notes(case_mgr, case_id, prep_id, "direct_examination", "Direct-Examination")

        # Quick-Ask: Direct Examination
        render_quick_ask("direct_examination_plan", "Direct Examination", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[3]:  # DEPOSITION ANALYSIS
        st.subheader("Deposition Analysis")
        st.caption("Paste a deposition transcript to find contradictions, admissions, and impeachment material.")

        depo_text = st.text_area(
            "Deposition Transcript",
            height=300,
            placeholder="Paste the full deposition transcript here...",
            key="depo_input"
        )

        if st.button(
            f"Analyze Deposition {estimate_cost(str(depo_text[:100]) + results.get('case_summary', ''), model_provider)}",
            type="primary",
            disabled=not depo_text,
            key="analyze_depo_btn"
        ):
            with st.spinner("Analyzing deposition against case documents..."):
                updates = analyze_deposition(st.session_state.agent_results, depo_text)
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, updates)
                st.rerun()

        depo_result = results.get("deposition_analysis", "")
        if depo_result:
            st.divider()
            st.markdown(depo_result)
        else:
            st.info("No deposition analysis yet. Paste a transcript above and click Analyze.")

    with tabs[4]:  # DEPO OUTLINE
        st.subheader("Deposition Outline Generator")
        st.caption("Generate a strategic deposition outline with topic areas, suggested questions, and impeachment angles.")

        _depo_witnesses = []
        _raw_wit = results.get("witnesses", [])
        if isinstance(_raw_wit, list):
            for _w in _raw_wit:
                if isinstance(_w, dict):
                    _depo_witnesses.append(_w.get("name", "Unknown"))
                elif isinstance(_w, str):
                    _depo_witnesses.append(_w)

        _depo_col1, _depo_col2 = st.columns(2)
        with _depo_col1:
            _depo_witness = st.text_input(
                "Deponent Name",
                placeholder="e.g., Officer James Rodriguez",
                key="_depo_outline_witness"
            )
            if _depo_witnesses:
                st.markdown("**Known Witnesses:**")
                _sel_wit = st.selectbox("Or select from analyzed witnesses", options=[""] + _depo_witnesses, key="_depo_sel_wit")
                if _sel_wit:
                    _depo_witness = _sel_wit

        with _depo_col2:
            _depo_role = st.selectbox(
                "Deponent Role",
                options=["witness", "expert", "plaintiff", "defendant", "officer", "investigator", "other"],
                format_func=lambda x: {"witness": "Fact Witness", "expert": "Expert Witness", "plaintiff": "Plaintiff", "defendant": "Defendant", "officer": "Law Enforcement", "investigator": "Investigator", "other": "Other"}.get(x, x),
                key="_depo_outline_role"
            )

        _depo_topics = st.text_area(
            "Topic Seeds (optional -- add specific areas you want covered)",
            placeholder="e.g., chain of custody, timeline discrepancies, witness credibility, prior statements",
            height=80,
            key="_depo_outline_topics"
        )

        if st.button(
            f"Generate Deposition Outline {estimate_cost(str(results.get('case_summary', ''))[:200], model_provider)}",
            type="primary",
            disabled=not _depo_witness,
            key="_gen_depo_outline"
        ):
            if results.get("case_summary"):
                with st.spinner(f"Building strategic deposition outline for {_depo_witness}..."):
                    _depo_state = dict(st.session_state.agent_results)
                    _depo_state["deposition_target"] = {
                        "name": _depo_witness,
                        "role": _depo_role,
                        "topic_seeds": [t.strip() for t in _depo_topics.split(",") if t.strip()] if _depo_topics else []
                    }
                    _outline_result = generate_deposition_outline(
                        _depo_state,
                        witness_name=_depo_witness,
                        witness_role=_depo_role,
                        topics=_depo_topics or "",
                    )
                    st.session_state.agent_results["deposition_outline"] = _outline_result.get("deposition_outline", "")
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
            else:
                st.warning("Run a full analysis first so the AI can reference your case facts.")

        _depo_outline = results.get("deposition_outline", "")
        if _depo_outline:
            st.divider()
            if isinstance(_depo_outline, str):
                st.markdown(_depo_outline)
            elif isinstance(_depo_outline, dict):
                if _depo_outline.get("deponent"):
                    st.markdown(f"### Deposition of: **{_depo_outline['deponent']}**")
                if _depo_outline.get("goals"):
                    st.markdown("#### Deposition Goals")
                    for _g in _depo_outline["goals"]:
                        st.markdown(f"- {_g}")
                if _depo_outline.get("topic_areas"):
                    st.markdown("#### Topic Areas")
                    for _ti, _ta in enumerate(_depo_outline["topic_areas"]):
                        if isinstance(_ta, dict):
                            with st.expander(f"**{_ti+1}. {_ta.get('topic', 'Topic')}** -- {_ta.get('purpose', '')}", expanded=_ti == 0):
                                if _ta.get("questions"):
                                    for _qi, _q in enumerate(_ta["questions"]):
                                        st.markdown(f"**Q{_qi+1}.** {_q}")
                                if _ta.get("follow_ups"):
                                    st.markdown("**Follow-up Questions:**")
                                    for _fu in _ta["follow_ups"]:
                                        st.markdown(f"  > {_fu}")
                                if _ta.get("impeachment_angle"):
                                    st.warning(f"**Impeachment Angle:** {_ta['impeachment_angle']}")
                                if _ta.get("objection_risks"):
                                    st.info(f"**Objection Risks:** {_ta['objection_risks']}")
                        elif isinstance(_ta, str):
                            st.markdown(f"{_ti+1}. {_ta}")

                if _depo_outline.get("closing_questions"):
                    st.markdown("#### Closing / Pin-Down Questions")
                    for _cq in _depo_outline["closing_questions"]:
                        st.markdown(f"- {_cq}")

            st.divider()
            _depo_export = _depo_outline if isinstance(_depo_outline, str) else json.dumps(_depo_outline, indent=2, default=str)
            _dl_c1, _dl_c2 = st.columns(2)
            with _dl_c1:
                st.download_button(
                    "Download Outline (.md)",
                    data=_depo_export,
                    file_name=f"depo_outline_{case_id}.md",
                    mime="text/markdown",
                    key="_dl_depo_outline_md"
                )
            with _dl_c2:
                st.download_button(
                    "Download as JSON",
                    data=json.dumps({"deposition_outline": _depo_outline}, indent=2, default=str),
                    file_name=f"depo_outline_{case_id}.json",
                    mime="application/json",
                    key="_dl_depo_outline_json"
                )
        else:
            st.info("No deposition outline yet. Enter a deponent name and click Generate above.")

    with tabs[-2]:  # WITNESS PREP (second-to-last)
        st.subheader("Witness Preparation Tool")
        st.caption("Simulate opposing counsel cross-examination -- prepare your witnesses for the worst")

        discovered_witnesses = results.get("witnesses", [])
        witness_names = []
        for w in discovered_witnesses:
            if isinstance(w, dict):
                name = w.get("name", "")
                if name:
                    witness_names.append(name)

        st.markdown("#### Select a Witness to Prepare")

        wp_col1, wp_col2 = st.columns(2)
        with wp_col1:
            if witness_names:
                selected_witness = st.selectbox(
                    "Choose from discovered witnesses",
                    ["\u2014 Select \u2014"] + witness_names,
                    key="wp_witness_select"
                )
                if selected_witness != "\u2014 Select \u2014":
                    witness_data = next((w for w in discovered_witnesses if isinstance(w, dict) and w.get("name") == selected_witness), {})
                    auto_role = witness_data.get("role", witness_data.get("type", ""))
                else:
                    selected_witness = ""
                    auto_role = ""
            else:
                st.info("No witnesses discovered yet. Run analysis first, or enter manually below.")
                selected_witness = ""
                auto_role = ""

        with wp_col2:
            manual_witness = st.text_input("Or enter witness name manually", key="wp_manual_name", placeholder="e.g. Officer John Smith")

        final_witness = manual_witness.strip() if manual_witness.strip() else selected_witness

        wp_detail_col1, wp_detail_col2 = st.columns(2)
        with wp_detail_col1:
            witness_role = st.text_input(
                "Witness Role / Title",
                value=auto_role if not manual_witness.strip() else "",
                key="wp_role",
                placeholder="e.g. Arresting Officer, Expert Witness, Eyewitness"
            )
        with wp_detail_col2:
            witness_goal = st.text_input(
                "Your Goal with This Witness",
                key="wp_goal",
                placeholder="e.g. Establish timeline inconsistency, Undermine credibility"
            )

        if st.button(
            f"Generate Mock Cross-Examination",
            type="primary",
            disabled=not final_witness,
            key="wp_generate_btn",
            help="Simulates aggressive opposing counsel questioning with coaching notes"
        ):
            if final_witness:
                with st.spinner(f"Opposing counsel is preparing cross-examination for {final_witness}..."):
                    wp_result = generate_witness_prep(
                        st.session_state.agent_results,
                        final_witness,
                        witness_role,
                        witness_goal
                    )
                    if "witness_preps" not in st.session_state:
                        st.session_state["witness_preps"] = {}
                    st.session_state["witness_preps"][final_witness] = wp_result.get("witness_prep", {})
                    if "witness_preps" not in st.session_state.agent_results:
                        st.session_state.agent_results["witness_preps"] = {}
                    st.session_state.agent_results["witness_preps"][final_witness] = wp_result.get("witness_prep", {})
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
            else:
                st.warning("Please select or enter a witness name first.")

        all_preps = st.session_state.agent_results.get("witness_preps", {})
        if not all_preps:
            all_preps = st.session_state.get("witness_preps", {})

        if all_preps:
            st.divider()
            st.markdown("#### Prepared Witnesses")
            for wname, wdata in all_preps.items():
                content = wdata.get("content", "") if isinstance(wdata, dict) else str(wdata)
                role_tag = wdata.get("role", "") if isinstance(wdata, dict) else ""
                with st.expander(f"{wname}" + (f" -- {role_tag}" if role_tag else ""), expanded=(wname == final_witness)):
                    st.markdown(content)
                    st.divider()
                    dl_col1, dl_col2 = st.columns(2)
                    with dl_col1:
                        st.download_button(
                            "Download Prep (.md)",
                            content,
                            file_name=f"witness_prep_{wname.replace(' ', '_').lower()}.md",
                            mime="text/markdown",
                            key=f"dl_wp_{wname}"
                        )
                    with dl_col2:
                        if st.button(f"Regenerate", key=f"regen_wp_{wname}"):
                            with st.spinner(f"Regenerating prep for {wname}..."):
                                wp_result = generate_witness_prep(
                                    st.session_state.agent_results,
                                    wname,
                                    wdata.get("role", "") if isinstance(wdata, dict) else "",
                                    wdata.get("goal", "") if isinstance(wdata, dict) else ""
                                )
                                st.session_state.agent_results["witness_preps"][wname] = wp_result.get("witness_prep", {})
                                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                                st.rerun()
        elif not final_witness:
            st.info("Select a witness above and click Generate to create a mock cross-examination prep package.")

    with tabs[-1]:  # INTERVIEW PLANNER (always last in Witnesses & Exam)
        st.subheader("Witness Interview Planner")
        st.caption("Generate structured pre-trial interview prep sheets for your witness meetings")

        _ip_discovered = results.get("witnesses", [])
        _ip_names = []
        for _ipw in _ip_discovered:
            if isinstance(_ipw, dict):
                _ipn = _ipw.get("name", "")
                if _ipn:
                    _ip_names.append(_ipn)

        _ip_col1, _ip_col2 = st.columns(2)
        with _ip_col1:
            if _ip_names:
                _ip_selected = st.selectbox(
                    "Choose from discovered witnesses",
                    ["\u2014 Select \u2014"] + _ip_names,
                    key="_ip_witness_select"
                )
                if _ip_selected != "\u2014 Select \u2014":
                    _ip_wdata = next((_w for _w in _ip_discovered if isinstance(_w, dict) and _w.get("name") == _ip_selected), {})
                    _ip_auto_role = _ip_wdata.get("role", _ip_wdata.get("type", ""))
                else:
                    _ip_selected = ""
                    _ip_auto_role = ""
            else:
                st.info("No witnesses discovered yet. Run analysis first, or enter manually.")
                _ip_selected = ""
                _ip_auto_role = ""

        with _ip_col2:
            _ip_manual = st.text_input("Or enter witness name manually", key="_ip_manual_name", placeholder="e.g. Jane Doe")

        _ip_final = _ip_manual.strip() if _ip_manual.strip() else _ip_selected

        _ip_d1, _ip_d2 = st.columns(2)
        with _ip_d1:
            _ip_role = st.text_input(
                "Witness Role / Title",
                value=_ip_auto_role if not _ip_manual.strip() else "",
                key="_ip_role",
                placeholder="e.g. Eyewitness, Expert, Character Witness"
            )
        with _ip_d2:
            _ip_type = st.selectbox(
                "Interview Type",
                ["initial", "follow_up", "pre_testimony"],
                format_func=lambda x: {"initial": "Initial Interview", "follow_up": "Follow-Up Meeting", "pre_testimony": "Pre-Testimony Prep"}.get(x, x),
                key="_ip_type"
            )

        st.caption({
            "initial": "**Initial**: First meeting -- build rapport, discover full story, assess credibility",
            "follow_up": "**Follow-Up**: Fill gaps, verify facts, address new developments",
            "pre_testimony": "**Pre-Testimony**: Final prep -- review testimony, prepare for cross, courtroom demeanor",
        }.get(_ip_type, ""))

        if st.button(
            f"Generate Interview Plan {estimate_cost(results.get('case_summary', '') + results.get('strategy_notes', ''), model_provider)}",
            type="primary",
            disabled=not _ip_final,
            key="_ip_generate_btn",
            help="Creates a comprehensive interview preparation package"
        ):
            if _ip_final:
                with st.spinner(f"Preparing interview plan for {_ip_final}..."):
                    _ip_result = generate_interview_plan(
                        st.session_state.agent_results,
                        _ip_final,
                        _ip_role,
                        _ip_type
                    )
                    if "interview_plans" not in st.session_state.agent_results:
                        st.session_state.agent_results["interview_plans"] = {}
                    st.session_state.agent_results["interview_plans"][_ip_final] = _ip_result.get("interview_plan", {})
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
            else:
                st.warning("Please select or enter a witness name first.")

        _all_ips = st.session_state.agent_results.get("interview_plans", {})

        if _all_ips:
            st.divider()
            st.markdown("#### Interview Plans")
            _section_icons = {
                "INTERVIEW AGENDA": "AGENDA",
                "KEY QUESTIONS": "QUESTIONS",
                "DOCUMENTS TO BRING": "DOCUMENTS",
                "LANDMINE ALERTS": "LANDMINES",
                "DO NOT ASK": "DO NOT ASK",
                "FOLLOW-UP TASKS": "FOLLOW-UP",
            }
            for _ipname, _ipdata in _all_ips.items():
                _ip_content = _ipdata.get("content", "") if isinstance(_ipdata, dict) else str(_ipdata)
                _ip_sections = _ipdata.get("sections", {}) if isinstance(_ipdata, dict) else {}
                _ip_role_tag = _ipdata.get("role", "") if isinstance(_ipdata, dict) else ""
                _ip_type_tag = _ipdata.get("type", "") if isinstance(_ipdata, dict) else ""
                _type_label = {"initial": "[Initial]", "follow_up": "[Follow-Up]", "pre_testimony": "[Pre-Testimony]"}.get(_ip_type_tag, "")

                with st.expander(f"{_type_label} {_ipname}" + (f" -- {_ip_role_tag}" if _ip_role_tag else "") + (f" ({_ip_type_tag.replace('_', ' ').title()})" if _ip_type_tag else ""), expanded=(_ipname == _ip_final)):
                    if _ip_sections:
                        for _sec_name, _sec_content in _ip_sections.items():
                            _sec_label = _section_icons.get(_sec_name.upper(), _sec_name)
                            with st.container(border=True):
                                st.markdown(f"#### [{_sec_label}] {_sec_name}")
                                st.markdown(_sec_content)
                    else:
                        st.markdown(_ip_content)

                    st.divider()
                    _ip_dl1, _ip_dl2, _ip_dl3 = st.columns(3)
                    with _ip_dl1:
                        st.download_button(
                            "Download (.md)",
                            _ip_content,
                            file_name=f"interview_plan_{_ipname.replace(' ', '_').lower()}.md",
                            mime="text/markdown",
                            key=f"dl_ip_{_ipname}"
                        )
                    with _ip_dl2:
                        if st.button(f"Regenerate", key=f"regen_ip_{_ipname}"):
                            with st.spinner(f"Regenerating interview plan for {_ipname}..."):
                                _ip_result = generate_interview_plan(
                                    st.session_state.agent_results,
                                    _ipname,
                                    _ipdata.get("role", "") if isinstance(_ipdata, dict) else "",
                                    _ipdata.get("type", "initial") if isinstance(_ipdata, dict) else "initial"
                                )
                                st.session_state.agent_results["interview_plans"][_ipname] = _ip_result.get("interview_plan", {})
                                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                                st.rerun()
                    with _ip_dl3:
                        if st.button(f"Delete", key=f"del_ip_{_ipname}"):
                            del st.session_state.agent_results["interview_plans"][_ipname]
                            case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                            st.rerun()
        elif not _ip_final:
            st.info("Select a witness above and choose an interview type to generate a preparation package.")
