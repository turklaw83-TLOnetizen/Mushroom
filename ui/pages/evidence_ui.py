"""Evidence & Facts UI module -- ported from ui_modules/evidence_ui.py."""
import logging
import os
import re
import json

import pandas as pd
import streamlit as st
from datetime import datetime, date
from streamlit_timeline import timeline as st_timeline

from core.nodes import (
    generate_exhibit_plan, generate_exhibit_list,
    generate_evidence_foundations, generate_consistency_check,
    generate_elements_map, generate_timeline, extract_entities,
    analyze_medical_records, generate_medical_chronology,
    generate_cross_reference_matrix,
    evaluate_missing_discovery, compare_documents,
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
    """Render the Evidence & Facts UI based on active_tab."""
    run_single_node = _run_single_node
    render_module_export = _render_module_export
    estimate_cost = lambda text, mp: format_cost_badge(text, mp)

    with tabs[0]:  # EVIDENCE FOUNDATIONS
        st.subheader("Evidentiary Foundations & Admissibility")
        render_module_export("Evidence", results.get("evidence_foundations"), "evidence")

        if st.button(f"Regenerate Evidence Analysis {estimate_cost(results.get('case_summary', '') + str(st.session_state.agent_results.get('raw_documents', '')[:10000]), model_provider)}", key="regen_evidence"):
            run_single_node(generate_evidence_foundations, "Regenerating Evidence Foundations", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        foundations = results.get("evidence_foundations", [])

        evidence_data = []
        if isinstance(foundations, str):
            try:
                clean_json = foundations.replace("```json", "").replace("```", "")
                evidence_data = json.loads(clean_json)
            except Exception:
                st.markdown(foundations)
        elif isinstance(foundations, list):
            evidence_data = foundations

        if evidence_data:
            for ev_idx, item in enumerate(evidence_data):
                if isinstance(item, dict):
                    star_prefix = "** " if item.get('_critical') else ""
                    with st.expander(f"{star_prefix}Exhibit: {item.get('item', 'Unknown Item')}"):
                        ec1, ec2, ec_flag = st.columns([2, 2, 0.5])
                        with ec1:
                            st.success("Predicate for Admission")
                            st.markdown(item.get('admissibility', 'N/A'))
                        with ec2:
                            st.error("Suppression / Attack Strategy")
                            st.markdown(item.get('attack', 'N/A'))
                        with ec_flag:
                            is_crit_ev = item.get('_critical', False)
                            ev_flag_label = "Critical" if is_crit_ev else "Flag"
                            if st.button(ev_flag_label, key=f"_flag_ev_{ev_idx}", help="Toggle critical flag"):
                                evidence_data[ev_idx]['_critical'] = not is_crit_ev
                                st.session_state.agent_results['evidence_foundations'] = evidence_data
                                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                                st.rerun()
        else:
            st.info("No physical evidence identified to analyze.")

        # Evidence Tagging & Linking
        if evidence_data and case_id and prep_id:
            with st.expander("Evidence Links -- Tag to Witnesses, Charges & Timeline", expanded=False):
                _witnesses = results.get("witnesses", [])
                _wit_names = [w.get("name", f"Witness {i}") for i, w in enumerate(_witnesses) if isinstance(w, dict)]
                _charges = results.get("charges", [])
                _charge_names = [c if isinstance(c, str) else c.get("name", f"Charge {i}") if isinstance(c, dict) else str(c) for i, c in enumerate(_charges)] if isinstance(_charges, list) else []
                _tl_events = results.get("timeline_events", [])
                _tl_labels = [e.get("event", e.get("description", f"Event {i}"))[:60] for i, e in enumerate(_tl_events) if isinstance(e, dict)]

                _existing_tags = case_mgr.load_evidence_tags(case_id, prep_id)
                _tags_map = {t.get("evidence_item", ""): t for t in _existing_tags}

                _updated_tags = []
                for ev_item in evidence_data:
                    if isinstance(ev_item, dict):
                        ev_name = ev_item.get("item", ev_item.get("evidence", "Unknown"))
                        existing = _tags_map.get(ev_name, {})

                        st.markdown(f"**{ev_name}**")
                        tc1, tc2, tc3 = st.columns(3)
                        with tc1:
                            linked_witnesses = st.multiselect(
                                "Witnesses", _wit_names,
                                default=existing.get("linked_witnesses", []),
                                key=f"_etag_w_{ev_name[:20]}"
                            )
                        with tc2:
                            linked_charges = st.multiselect(
                                "Charges", _charge_names,
                                default=existing.get("linked_charges", []),
                                key=f"_etag_c_{ev_name[:20]}"
                            )
                        with tc3:
                            linked_timeline = st.multiselect(
                                "Timeline", _tl_labels,
                                default=existing.get("linked_timeline", []),
                                key=f"_etag_t_{ev_name[:20]}"
                            )
                        _updated_tags.append({
                            "evidence_item": ev_name,
                            "linked_witnesses": linked_witnesses,
                            "linked_charges": linked_charges,
                            "linked_timeline": linked_timeline,
                        })
                        st.divider()

                if st.button("Save Evidence Tags", key="_save_ev_tags", use_container_width=True):
                    case_mgr.save_evidence_tags(case_id, prep_id, _updated_tags)
                    st.success("Evidence tags saved!")

        # Annotations for Evidence
        if evidence_data and case_id and prep_id:
            with st.expander("Evidence Annotations", expanded=False):
                _all_annots = case_mgr.load_annotations(case_id, prep_id)
                _ev_annots = {a["target_id"]: a for a in _all_annots if a.get("target_type") == "evidence"}

                _new_annots = list(_all_annots)
                for ev_item in evidence_data:
                    if isinstance(ev_item, dict):
                        ev_name = ev_item.get("item", ev_item.get("evidence", "Unknown"))
                        existing_note = _ev_annots.get(ev_name, {}).get("note", "")
                        note = st.text_area(
                            f"{ev_name}", value=existing_note,
                            key=f"_annot_ev_{ev_name[:20]}", height=60,
                            placeholder="Add a note about this evidence..."
                        )
                        if note != existing_note:
                            _new_annots = [a for a in _new_annots if not (a.get("target_type") == "evidence" and a.get("target_id") == ev_name)]
                            if note.strip():
                                _new_annots.append({
                                    "target_type": "evidence",
                                    "target_id": ev_name,
                                    "note": note,
                                    "created_at": str(date.today()),
                                })

                if st.button("Save Evidence Notes", key="_save_ev_notes", use_container_width=True):
                    case_mgr.save_annotations(case_id, prep_id, _new_annots)
                    st.success("Annotations saved!")

        # Module Notes: Evidence Tab
        st.divider()
        with st.expander("**Attorney Notes -- Evidence**", expanded=False):
            _ev_notes = case_mgr.load_module_notes(case_id, prep_id, "evidence")
            _new_ev_notes = st.text_area("Your notes on evidence:", value=_ev_notes, height=120, key=f"_notes_evidence_{prep_id}")
            if _new_ev_notes != _ev_notes:
                case_mgr.save_module_notes(case_id, prep_id, "evidence", _new_ev_notes)
                st.toast("Notes saved", icon="Done")

        # Quick-Ask: Evidence
        render_quick_ask("evidence_foundations", "Evidence Foundations", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[1]:  # CONFLICTS
        st.subheader("Statement Consistency & Contradictions")

        if st.button(f"Regenerate Conflicts {estimate_cost(results.get('case_summary', ''), model_provider)}", key="regen_conflicts"):
            run_single_node(generate_consistency_check, "Regenerating Conflict Analysis", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        conflicts = results.get("consistency_check", [])
        c_data = []
        if isinstance(conflicts, str):
            try:
                c_data = json.loads(conflicts.replace("```json", "").replace("```", ""))
            except Exception:
                st.markdown(conflicts)
        elif isinstance(conflicts, list):
            c_data = conflicts

        if c_data:
            for idx, c in enumerate(c_data):
                if isinstance(c, dict):
                    severity = c.get('severity', '').lower()
                    if 'high' in severity or 'major' in severity:
                        sev_badge = "**Critical**"
                    elif 'medium' in severity:
                        sev_badge = "**Moderate**"
                    else:
                        sev_badge = "**Notable**"
                    st.markdown(f"#### {sev_badge} -- {c.get('fact', 'Contradiction')}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        with st.container(border=True):
                            st.markdown("**Source A**")
                            st.info(c.get('source_a', 'N/A'))
                    with col_b:
                        with st.container(border=True):
                            st.markdown("**Source B**")
                            st.error(c.get('source_b', 'N/A'))
                    if c.get('notes'):
                        st.caption(f"{c.get('notes')}")
                    st.markdown("---")
        else:
            st.success("No major contradictions detected (or none returned).")
        render_module_notes(case_mgr, case_id, prep_id, "conflicts", "Conflicts")

        # Quick-Ask: Consistency
        render_quick_ask("consistency_check", "Consistency Check", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[2]:  # ELEMENTS
        st.subheader("Elements of the Offense")

        if st.button("Regenerate Elements Map", key="regen_elements"):
            with st.spinner("Mapping evidence to elements..."):
                updates = generate_elements_map(st.session_state.agent_results)
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, updates)
                st.rerun()

        # Charge Management UI
        st.markdown("### Manage Charges")

        if "charges" not in st.session_state.agent_results or not isinstance(st.session_state.agent_results["charges"], list):
            st.session_state.agent_results["charges"] = []

        with st.expander("Add New Charge", expanded=False):
            with st.form("new_charge_form"):
                c1, c2 = st.columns(2)
                with c1:
                    nc_name = st.text_input("Charge Name (e.g. Assault 2)")
                    nc_statute = st.text_input("Statute Number (e.g. RSA 631:2)")
                with c2:
                    nc_level = st.selectbox("Level", ["Felony", "Misdemeanor", "Violation"])
                    nc_class = st.selectbox("Class", ["A", "B", "Unclassified"])

                nc_text = st.text_area("Statute Text", height=100, help="Paste the exact legislative text.")
                nc_instr = st.text_area("Jury Instructions", height=100, help="Paste relevant model jury instructions.")

                if st.form_submit_button("Add Charge"):
                    if nc_name:
                        new_charge = {
                            "name": nc_name,
                            "statute_number": nc_statute,
                            "level": nc_level,
                            "class": nc_class,
                            "statute_text": nc_text,
                            "jury_instructions": nc_instr,
                            "id": len(st.session_state.agent_results["charges"]) + 1
                        }
                        st.session_state.agent_results["charges"].append(new_charge)
                        case_mgr.save_prep_state(st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results)
                        st.success(f"Added: {nc_name}")
                        st.rerun()

        current_charges = st.session_state.agent_results["charges"]
        if current_charges:
            st.markdown(f"**Active Charges ({len(current_charges)})**")
            for i, charge in enumerate(current_charges):
                with st.expander(f"{i+1}. {charge.get('name')} ({charge.get('statute_number')})", expanded=False):
                    st.markdown(f"**Severity:** {charge.get('level')} {charge.get('class')}")
                    st.caption(f"**Statute:** {charge.get('statute_text')[:100]}...")

                    if st.button("Delete Charge", key=f"del_charge_{i}"):
                        st.session_state.agent_results["charges"].pop(i)
                        case_mgr.save_prep_state(st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results)
                        st.rerun()
        else:
            st.info("No charges defined. Add a charge to begin analysis.")

        elements = results.get("legal_elements", [])
        e_data = []
        if isinstance(elements, str):
            try:
                e_data = json.loads(elements.replace("```json", "").replace("```", ""))
            except Exception:
                st.markdown(elements)
        elif isinstance(elements, list):
            e_data = elements

        if st.button(f"Regenerate Elements Map {estimate_cost(results.get('case_summary', '') + str(results.get('charges', '')), model_provider)}"):
            with st.spinner("Analyzing evidence against specific charges..."):
                updates = generate_elements_map(st.session_state.agent_results)
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, updates)
                st.rerun()

        if e_data:
            for e in e_data:
                if isinstance(e, dict):
                    strength = e.get('strength', 'Low').lower()
                    if 'high' in strength:
                        badge_color, bar_val = 'red', 90
                    elif 'medium' in strength:
                        badge_color, bar_val = 'orange', 50
                    else:
                        badge_color, bar_val = 'green', 15
                    ec1, ec2 = st.columns([3, 1])
                    with ec1:
                        st.markdown(f"**Charge:** {e.get('charge')} | **Element:** {e.get('element')}")
                        st.markdown(f"Evidence: {e.get('evidence')}")
                    with ec2:
                        st.markdown(f"**:{badge_color}[{e.get('strength', 'Unknown')}]**")
                        st.progress(bar_val)
                    st.divider()

            # Evidence Strength Heatmap
            with st.expander("Evidence Strength Heatmap", expanded=False):
                st.markdown("Color-coded matrix of evidence strength against legal elements per charge.")

                _hm_charges = {}
                for e in e_data:
                    if not isinstance(e, dict):
                        continue
                    _c = str(e.get('charge', 'Unknown'))
                    _el = str(e.get('element', 'Unknown'))
                    _str = str(e.get('strength', 'Low')).lower()
                    _ev = str(e.get('evidence', ''))

                    if _c not in _hm_charges:
                        _hm_charges[_c] = {}
                    _hm_charges[_c][_el] = {'strength': _str, 'evidence': _ev}

                if _hm_charges:
                    _all_elements = []
                    for _ch_data in _hm_charges.values():
                        for _el_name in _ch_data.keys():
                            if _el_name not in _all_elements:
                                _all_elements.append(_el_name)

                    _hm_rows = []
                    for _charge_name, _elements_dict in _hm_charges.items():
                        _row = {'Charge': _charge_name}
                        for _el_name in _all_elements:
                            if _el_name in _elements_dict:
                                _s = _elements_dict[_el_name]['strength']
                                if 'high' in _s:
                                    _row[_el_name] = 'High'
                                elif 'medium' in _s or 'moderate' in _s:
                                    _row[_el_name] = 'Medium'
                                else:
                                    _row[_el_name] = 'Low'
                            else:
                                _row[_el_name] = 'N/A'
                        _hm_rows.append(_row)

                    _hm_df = pd.DataFrame(_hm_rows).set_index('Charge')

                    def _color_heatmap(val):
                        if 'High' in str(val):
                            return 'background-color: #ffcccc; color: #8b0000; font-weight: bold'
                        elif 'Medium' in str(val):
                            return 'background-color: #fff3cd; color: #856404; font-weight: bold'
                        elif 'Low' in str(val):
                            return 'background-color: #d4edda; color: #155724; font-weight: bold'
                        return 'background-color: #f8f9fa; color: #6c757d'

                    _styled = _hm_df.style.map(_color_heatmap)
                    st.dataframe(_styled, use_container_width=True, height=min(400, 80 + len(_hm_rows) * 45))

                    _total = sum(len(v) for v in _hm_charges.values())
                    _high = sum(1 for _cd in _hm_charges.values() for _ed in _cd.values() if 'high' in _ed['strength'])
                    _med = sum(1 for _cd in _hm_charges.values() for _ed in _cd.values() if 'medium' in _ed['strength'] or 'moderate' in _ed['strength'])
                    _low = _total - _high - _med

                    _s1, _s2, _s3, _s4 = st.columns(4)
                    with _s1:
                        st.metric("Total Elements", _total)
                    with _s2:
                        st.metric("High Strength", _high)
                    with _s3:
                        st.metric("Medium", _med)
                    with _s4:
                        st.metric("Low", _low)
                else:
                    st.info("No heatmap data available. Regenerate elements map first.")
        else:
            st.info("No legal elements mapped.")
        render_module_notes(case_mgr, case_id, prep_id, "legal_elements", "Legal Elements")

    with tabs[3]:  # TIMELINE
        st.subheader("Chronological Timeline")

        if st.button(f"Regenerate Timeline {estimate_cost(results.get('case_summary', ''), model_provider)}", key="regen_timeline"):
            run_single_node(generate_timeline, "Regenerating Timeline", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        timeline_data = results.get("timeline", [])

        t_data = []
        if isinstance(timeline_data, str):
            try:
                clean_json = timeline_data.replace("```json", "").replace("```", "")
                t_data = json.loads(clean_json)
            except (json.JSONDecodeError, ValueError):
                logger.info("Failed to parse timeline JSON, t_data remains empty")
        elif isinstance(timeline_data, list):
            t_data = timeline_data

        if t_data:
            vis_events = []
            for event in t_data:
                if "year" in event:
                    evt_obj = {
                        "start_date": {
                            "year": str(event.get("year")),
                            "month": str(event.get("month", "1")),
                            "day": str(event.get("day", "1")),
                        },
                        "text": {
                            "headline": event.get("headline", "Event"),
                            "text": f"{event.get('text', '')}\n\nTime: {event.get('time', '')}\nSource: {event.get('source', '')}"
                        }
                    }
                    vis_events.append(evt_obj)
                elif "date" in event:
                    date_str = event.get("date", "")
                    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
                    if match:
                        evt_obj = {
                            "start_date": {
                                "year": match.group(1),
                                "month": match.group(2),
                                "day": match.group(3)
                            },
                            "text": {
                                "headline": event.get("event", "Event"),
                                "text": f"{event.get('time', '')} - Source: {event.get('source', '')}"
                            }
                        }
                        vis_events.append(evt_obj)

            if vis_events:
                st_timeline({"events": vis_events}, height=500)
            else:
                st.warning("Ensure timeline data is generated correctly. Click 'Regenerate Timeline'.")

            _crit_tl_count = sum(1 for _te in t_data if isinstance(_te, dict) and _te.get('_critical'))
            if _crit_tl_count:
                st.info(f"**{_crit_tl_count} critical event(s)** flagged")

            with st.expander("**Edit Timeline Data** -- Modify dates, events, or add new entries", expanded=False):
                _t_edit = []
                for _t in t_data:
                    if isinstance(_t, dict):
                        _t_edit.append({
                            "Date": _t.get("date", ""),
                            "Time": _t.get("time", ""),
                            "Event": _t.get("event", ""),
                            "Source": _t.get("source", ""),
                            "Critical": _t.get("_critical", False),
                        })
                if _t_edit:
                    _t_df = pd.DataFrame(_t_edit)
                    _t_edited = st.data_editor(
                        _t_df,
                        column_config={
                            "Date": st.column_config.TextColumn("Date", width="small"),
                            "Time": st.column_config.TextColumn("Time", width="small"),
                            "Event": st.column_config.TextColumn("Event", width="large"),
                            "Source": st.column_config.TextColumn("Source", width="medium"),
                            "Critical": st.column_config.CheckboxColumn("Critical", width="small"),
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        key="_timeline_editor"
                    )

                    if st.button("Save Timeline Changes", key="_save_timeline_edits"):
                        _new_timeline = []
                        for _, row in _t_edited.iterrows():
                            _new_timeline.append({
                                "date": row.get("Date", ""),
                                "time": row.get("Time", ""),
                                "event": row.get("Event", ""),
                                "source": row.get("Source", ""),
                                "_critical": bool(row.get("Critical", False)),
                            })
                        st.session_state.agent_results["timeline"] = _new_timeline
                        case_mgr.save_prep_state(st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results)
                        st.success("Timeline updated!")
                        st.rerun()
        else:
            st.info("No timeline data found. Click 'Regenerate Timeline'.")

        # Module Notes: Timeline Tab
        st.divider()
        with st.expander("**Attorney Notes -- Timeline**", expanded=False):
            _tl_notes = case_mgr.load_module_notes(case_id, prep_id, "timeline")
            _new_tl_notes = st.text_area("Your notes on the timeline:", value=_tl_notes, height=120, key=f"_notes_timeline_{prep_id}")
            if _new_tl_notes != _tl_notes:
                case_mgr.save_module_notes(case_id, prep_id, "timeline", _new_tl_notes)
                st.toast("Notes saved", icon="Done")

        # Quick-Ask: Timeline
        render_quick_ask("timeline", "Timeline", results, case_id, prep_id, case_mgr, model_provider)

    with tabs[4]:  # ENTITIES
        st.subheader("Knowledge Graph Entities")

        if st.button(f"Regenerate Entities {estimate_cost(str(st.session_state.agent_results.get('raw_documents', '')[:50000]), model_provider)}", key="regen_entities"):
            run_single_node(extract_entities, "Regenerating Entities", st.session_state.agent_results, case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, model_provider, st.session_state.agent_results)
            st.rerun()

        entities = results.get("entities", [])

        def display_entity_table(e_list, type_filter):
            filtered = [e for e in e_list if isinstance(e, dict) and e.get('type') == type_filter]
            if filtered:
                st.markdown(f"### {type_filter}")
                st.dataframe(filtered, use_container_width=True)

        entity_data = []
        if isinstance(entities, str):
            try:
                entity_data = json.loads(entities.replace("```json", "").replace("```", ""))
            except (json.JSONDecodeError, ValueError):
                logger.info("Failed to parse entities JSON")
        elif isinstance(entities, list):
            entity_data = entities

        if entity_data:
            c1, c2 = st.columns(2)
            with c1:
                display_entity_table(entity_data, "PERSON")
                display_entity_table(entity_data, "ORGANIZATION")
            with c2:
                display_entity_table(entity_data, "PLACE")
                display_entity_table(entity_data, "DATE")
        else:
            if isinstance(entities, str):
                st.markdown(entities)
            else:
                st.info("No entities extracted.")
        render_module_notes(case_mgr, case_id, prep_id, "entities", "Entities")

    with tabs[5]:  # MEDICAL RECORDS
        st.subheader("Medical Records Evaluation")
        st.caption("Paste medical records, treatment notes, or IME reports for AI-powered analysis.")

        med_text = st.text_area(
            "Paste medical records here",
            height=250,
            placeholder="Paste treatment records, discharge summaries, billing statements, IME reports, or any medical documentation...",
            key="med_records_input"
        )

        if st.button(
            f"Analyze Medical Records {estimate_cost(med_text[:200] if med_text else '', model_provider)}",
            key="analyze_med_records",
            type="primary",
            disabled=not med_text
        ):
            with st.spinner("Analyzing medical records -- extracting timeline, gaps, causation, damages..."):
                med_result = analyze_medical_records(st.session_state.agent_results, med_text)
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, med_result)
                st.rerun()

        st.divider()

        med_data = results.get("medical_records_analysis", {})

        if med_data.get("raw_analysis"):
            st.markdown(med_data["raw_analysis"])
        elif med_data and not med_data.get("error"):
            # 1. TREATMENT TIMELINE
            with st.expander("Treatment Timeline", expanded=True):
                tl = med_data.get("treatment_timeline", [])
                if tl:
                    df = pd.DataFrame(tl)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No treatment timeline data extracted.")

            # 2. GAP ANALYSIS
            with st.expander("Gaps in Treatment", expanded=True):
                gaps = med_data.get("gap_analysis", [])
                if gaps:
                    for g in gaps:
                        if isinstance(g, dict):
                            risk = g.get('risk_level', '').upper()
                            if 'HIGH' in risk:
                                st.error(f"**{g.get('gap_days', '?')} day gap** ({g.get('gap_start')} -> {g.get('gap_end')})")
                            elif 'MEDIUM' in risk:
                                st.warning(f"**{g.get('gap_days', '?')} day gap** ({g.get('gap_start')} -> {g.get('gap_end')})")
                            else:
                                st.info(f"**{g.get('gap_days', '?')} day gap** ({g.get('gap_start')} -> {g.get('gap_end')})")
                            gc1, gc2 = st.columns(2)
                            with gc1:
                                st.markdown(f"**Between:** {g.get('between')}")
                                st.markdown(f"**Opposing Argument:** {g.get('opposing_argument')}")
                            with gc2:
                                st.markdown(f"**Counter-Argument:** {g.get('counter_argument')}")
                            st.divider()
                else:
                    st.success("No significant gaps in treatment detected.")

            # 3. CAUSATION MAP
            with st.expander("Causation Map", expanded=True):
                cmap = med_data.get("causation_map", [])
                if cmap:
                    for cm in cmap:
                        if isinstance(cm, dict):
                            strength = cm.get('strength', '').upper()
                            if 'STRONG' in strength:
                                s_color = 'green'
                            elif 'MODERATE' in strength:
                                s_color = 'orange'
                            else:
                                s_color = 'red'
                            st.markdown(f"### {cm.get('injury')} -- :{s_color}[{strength}]")
                            st.markdown(f"**Mechanism:** {cm.get('mechanism')}")
                            if cm.get('pre_existing'):
                                st.warning(f"Pre-existing -- Aggravation: {cm.get('aggravation')}")
                            st.markdown(f"**Supporting Evidence:** {cm.get('supporting_evidence')}")
                            st.divider()
                else:
                    st.info("No causation data extracted.")

            # 4. DAMAGES ESTIMATE
            with st.expander("Damages Estimate", expanded=True):
                dmg = med_data.get("damages_estimate", {})
                if dmg and isinstance(dmg, dict):
                    dm1, dm2, dm3, dm4 = st.columns(4)
                    dm1.metric("Past Medical", f"${dmg.get('past_medical', 0):,.2f}" if isinstance(dmg.get('past_medical'), (int, float)) else str(dmg.get('past_medical', 'N/A')))
                    dm2.metric("Future Medical", f"${dmg.get('future_medical', 0):,.2f}" if isinstance(dmg.get('future_medical'), (int, float)) else str(dmg.get('future_medical', 'N/A')))
                    dm3.metric("Total Specials", f"${dmg.get('total_specials', 0):,.2f}" if isinstance(dmg.get('total_specials'), (int, float)) else str(dmg.get('total_specials', 'N/A')))
                    dm4.metric("Multiplier", str(dmg.get('multiplier_range', 'N/A')))

                    st.markdown(f"**Settlement Range:** {dmg.get('settlement_range', 'N/A')}")
                    st.markdown(f"**Past Pain & Suffering:** {dmg.get('past_pain_suffering', 'N/A')}")
                    st.markdown(f"**Future Pain & Suffering:** {dmg.get('future_pain_suffering', 'N/A')}")
                    st.markdown(f"**Lost Wages (Past):** {dmg.get('lost_wages_past', 'N/A')}")
                    st.markdown(f"**Lost Wages (Future):** {dmg.get('lost_wages_future', 'N/A')}")

                    bills = dmg.get('itemized_bills', [])
                    if bills and isinstance(bills, list):
                        st.markdown("#### Itemized Medical Bills")
                        st.dataframe(pd.DataFrame(bills), use_container_width=True, hide_index=True)

                    if dmg.get('notes'):
                        st.caption(f"{dmg.get('notes')}")
                else:
                    st.info("No damages data extracted.")

            # 5. PRE-EXISTING CONDITIONS
            with st.expander("Pre-Existing Conditions", expanded=False):
                pre_ex = med_data.get("pre_existing_conditions", [])
                if pre_ex:
                    for pe in pre_ex:
                        if isinstance(pe, dict):
                            with st.container(border=True):
                                st.markdown(f"### {pe.get('condition')}")
                                st.markdown(f"**Documented Since:** {pe.get('documented_since')}")
                                st.markdown(f"**Current Status:** {pe.get('current_status')}")
                                pe1, pe2 = st.columns(2)
                                with pe1:
                                    st.success(f"**Eggshell Argument:** {pe.get('eggshell_argument')}")
                                    st.info(f"**Counter-Strategy:** {pe.get('counter_strategy')}")
                                with pe2:
                                    st.error(f"**Defense Attack:** {pe.get('defense_attack')}")
                else:
                    st.success("No pre-existing conditions identified.")

            # 6. IME CRITIQUE
            with st.expander("IME Report Critique", expanded=False):
                ime = med_data.get("ime_critique", {})
                if ime and isinstance(ime, dict):
                    st.markdown(f"**Examiner:** {ime.get('examiner', 'Unknown')}")
                    reliability = ime.get('overall_reliability', 'N/A').upper()
                    if reliability == 'LOW':
                        st.error(f"Overall Reliability: **{reliability}**")
                    elif reliability == 'MODERATE':
                        st.warning(f"Overall Reliability: **{reliability}**")
                    elif reliability == 'HIGH':
                        st.success(f"Overall Reliability: **{reliability}**")
                    else:
                        st.info(f"Reliability: {reliability}")

                    if ime.get('bias_indicators'):
                        st.markdown("#### Bias Indicators")
                        for b in ime['bias_indicators']:
                            st.markdown(f"- {b}")
                    if ime.get('omissions'):
                        st.markdown("#### Omissions")
                        for o in ime['omissions']:
                            st.markdown(f"- {o}")
                    if ime.get('contradictions'):
                        st.markdown("#### Contradictions with Treating Physicians")
                        for c in ime['contradictions']:
                            st.markdown(f"- {c}")
                    if ime.get('attack_points'):
                        st.markdown("#### Cross-Examination Attack Points")
                        for a in ime['attack_points']:
                            st.markdown(f"- {a}")
                else:
                    st.info("No IME report data available.")

            # 7. ICD/CPT DECODER
            with st.expander("ICD/CPT Code Decoder", expanded=False):
                codes = med_data.get("icd_cpt_decoder", [])
                if codes:
                    st.dataframe(pd.DataFrame(codes), use_container_width=True, hide_index=True)
                else:
                    st.info("No medical codes found in the records.")

        elif med_data.get("error"):
            st.error(f"Error: {med_data['error']}")
        else:
            st.info("Paste medical records above and click 'Analyze' to get started.")

    with tabs[6]:  # MEDICAL CHRONOLOGY
        st.subheader("Medical Chronology")
        st.caption("AI-generated chronological narrative of all medical treatment -- organized by date with provider details, diagnoses, and treatment progression.")

        _case_type = results.get("case_type", "")
        if "civil" not in str(_case_type).lower():
            st.warning("Medical Chronology is designed for civil litigation cases. Switch to a civil case type to use this feature.")
        else:
            if st.button(
                f"Generate Medical Chronology {estimate_cost(str(results.get('case_summary', ''))[:200], model_provider)}",
                key="_gen_med_chronology",
                type="primary",
            ):
                with st.spinner("Building medical chronology -- organizing treatment records, identifying gaps, mapping providers..."):
                    chrono_result = generate_medical_chronology(st.session_state.agent_results)
                    safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, chrono_result)
                    st.rerun()

            st.divider()

            chrono_data = results.get("medical_chronology", {})

            if chrono_data and isinstance(chrono_data, dict) and not chrono_data.get("error"):
                # 1. CHRONOLOGICAL ENTRIES
                with st.expander("Chronological Entries", expanded=True):
                    entries = chrono_data.get("entries", [])
                    if entries and isinstance(entries, list):
                        for ei, entry in enumerate(entries):
                            if isinstance(entry, dict):
                                _visit_type = entry.get("visit_type", "Visit")
                                with st.container(border=True):
                                    _c1, _c2 = st.columns([1, 3])
                                    with _c1:
                                        st.markdown(f"### {entry.get('date', 'Unknown Date')}")
                                        st.caption(f"**{_visit_type.title()}**")
                                    with _c2:
                                        st.markdown(f"**Provider:** {entry.get('provider', 'Unknown')}")
                                        st.markdown(f"**Facility:** {entry.get('facility', 'N/A')}")
                                        if entry.get('diagnosis'):
                                            st.markdown(f"**Diagnosis:** {entry.get('diagnosis')}")
                                        if entry.get('procedures'):
                                            st.markdown(f"**Procedures:** {entry.get('procedures')}")
                                        if entry.get('medications_prescribed'):
                                            st.info(f"**Medications:** {entry.get('medications_prescribed')}")
                                        if entry.get('referrals'):
                                            st.caption(f"Referral: {entry.get('referrals')}")
                                        if entry.get('notes'):
                                            st.caption(f"{entry.get('notes')}")
                    else:
                        st.info("No chronological entries generated yet.")

                # 2. NARRATIVE SUMMARY
                with st.expander("Treatment Narrative", expanded=True):
                    narrative = chrono_data.get("narrative", "")
                    if narrative:
                        st.markdown(narrative)
                    else:
                        st.info("No narrative summary available.")

                # 3. TREATMENT GAPS
                with st.expander("Treatment Gaps", expanded=True):
                    gaps = chrono_data.get("gaps", [])
                    if gaps and isinstance(gaps, list):
                        for g in gaps:
                            if isinstance(g, dict):
                                _risk = g.get("risk", g.get("risk_level", "")).upper()
                                if "HIGH" in _risk or "CRITICAL" in _risk:
                                    st.error(f"**{g.get('duration', '?')} gap** -- {g.get('from_date', '?')} -> {g.get('to_date', '?')}")
                                elif "MEDIUM" in _risk or "MODERATE" in _risk:
                                    st.warning(f"**{g.get('duration', '?')} gap** -- {g.get('from_date', '?')} -> {g.get('to_date', '?')}")
                                else:
                                    st.info(f"**{g.get('duration', '?')} gap** -- {g.get('from_date', '?')} -> {g.get('to_date', '?')}")
                                st.markdown(f"**Between:** {g.get('between_providers', g.get('between', 'N/A'))}")
                                if g.get('significance'):
                                    st.caption(f"{g.get('significance')}")
                                st.divider()
                    else:
                        st.success("No significant treatment gaps identified.")

                # 4. PROVIDER SUMMARY TABLE
                with st.expander("Provider Summary", expanded=False):
                    providers = chrono_data.get("providers", [])
                    if providers and isinstance(providers, list):
                        st.dataframe(pd.DataFrame(providers), use_container_width=True, hide_index=True)
                    else:
                        st.info("No provider summary available.")

                # 5. MEDICATION TIMELINE
                with st.expander("Medication Timeline", expanded=False):
                    medications = chrono_data.get("medications", [])
                    if medications and isinstance(medications, list):
                        for med in medications:
                            if isinstance(med, dict):
                                _med_name = med.get("medication", "Unknown")
                                _start = med.get("start_date", "?")
                                _end = med.get("end_date", "Ongoing")
                                _prescriber = med.get("prescriber", "")
                                with st.container(border=True):
                                    _mc1, _mc2 = st.columns([2, 1])
                                    with _mc1:
                                        st.markdown(f"**{_med_name}**")
                                        st.caption(f"{_start} -> {_end}")
                                    with _mc2:
                                        if _prescriber:
                                            st.caption(f"Prescribed by: {_prescriber}")
                                        if med.get("dosage"):
                                            st.caption(f"Dosage: {med.get('dosage')}")
                    else:
                        st.info("No medication data available.")

                # 6. INJURY PROGRESSION
                with st.expander("Injury Progression", expanded=False):
                    progression = chrono_data.get("progression", [])
                    if progression and isinstance(progression, list):
                        for prog in progression:
                            if isinstance(prog, dict):
                                _status = prog.get("status", "").lower()
                                if "worsened" in _status or "deteriorat" in _status:
                                    _prog_label = "Worsened"
                                elif "improved" in _status or "resolved" in _status:
                                    _prog_label = "Improved"
                                else:
                                    _prog_label = "Stable"
                                st.markdown(f"[{_prog_label}] **{prog.get('condition', 'Unknown')}** -- {prog.get('date_range', '')}")
                                st.caption(f"Status: {prog.get('status', 'N/A')} | Details: {prog.get('details', '')}")
                                st.divider()
                    else:
                        st.info("No injury progression data available.")

            elif chrono_data and chrono_data.get("error"):
                st.error(f"Error generating chronology: {chrono_data['error']}")
            else:
                st.info("Click 'Generate Medical Chronology' to build a chronological narrative from your uploaded medical records.")

    with tabs[-3]:  # CROSS-REFS
        st.subheader("Document Cross-Reference Matrix")
        st.caption("Discover how your case documents relate -- supports, contradicts, supplements, or neutral.")

        if st.button(
            f"Build Cross-Reference Matrix {estimate_cost(str(results.get('case_summary', ''))[:200], model_provider)}",
            type="primary",
            key="_gen_xref"
        ):
            if results.get("raw_documents"):
                with st.spinner("Analyzing document relationships..."):
                    xref_result = generate_cross_reference_matrix(st.session_state.agent_results)
                    st.session_state.agent_results["cross_reference_matrix"] = xref_result.get("cross_reference_matrix", [])
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
            else:
                st.warning("Upload case documents first to generate a cross-reference matrix.")

        xref_data = results.get("cross_reference_matrix", [])
        if xref_data and isinstance(xref_data, list) and len(xref_data) > 0:
            _rel_counts = {}
            for _xr in xref_data:
                if isinstance(_xr, dict):
                    _rel = _xr.get("relationship", "unknown")
                    _rel_counts[_rel] = _rel_counts.get(_rel, 0) + 1

            stat_cols = st.columns(min(len(_rel_counts), 5))
            for _ri, (_rk, _rv) in enumerate(_rel_counts.items()):
                if _ri < len(stat_cols):
                    with stat_cols[_ri]:
                        st.metric(f"{_rk.title()}", _rv)

            st.divider()

            _filter_rel = st.multiselect(
                "Filter by relationship",
                options=list(_rel_counts.keys()),
                default=list(_rel_counts.keys()),
                format_func=lambda x: x.title(),
                key="_xref_filter"
            )

            for _xi, _xr in enumerate(xref_data):
                if not isinstance(_xr, dict):
                    continue
                _xrel = _xr.get("relationship", "unknown")
                if _xrel not in _filter_rel:
                    continue

                _strength = _xr.get("strength", "")
                _doc_a = os.path.basename(str(_xr.get("doc_a", "?")))
                _doc_b = os.path.basename(str(_xr.get("doc_b", "?")))

                with st.expander(f"**{_doc_a}** <-> **{_doc_b}** -- {_xrel.title()} ({_strength})", expanded=(_xrel == "contradicts")):
                    st.markdown(f"**Relationship:** {_xrel.title()} ({_strength})")
                    st.markdown(f"**Details:** {_xr.get('details', 'N/A')}")
                    if _xr.get("key_facts"):
                        st.markdown(f"**Key Facts:** {_xr.get('key_facts')}")
        else:
            st.info("No cross-reference data yet. Click the button above to analyze document relationships.")

    with tabs[-2]:  # DOC COMPARE
        # Visual Side-by-Side Document Compare
        try:
            from ui.pages import doc_compare_ui
            doc_compare_ui.render(case_id=case_id, case_mgr=case_mgr, results=results)
        except Exception as _dce:
            logger.debug("Doc compare unavailable: %s", _dce)
        st.divider()
        st.subheader("AI Document Comparison")
        st.caption("Compare two documents side-by-side -- find contradictions, timeline conflicts, and factual differences.")

        _case_files = []
        _raw_docs = results.get("raw_documents", [])
        if isinstance(_raw_docs, list):
            for _doc in _raw_docs:
                if isinstance(_doc, dict):
                    _case_files.append(_doc.get("source", _doc.get("file", "Unknown")))
                elif hasattr(_doc, "metadata"):
                    _case_files.append(_doc.metadata.get("source", "Unknown"))
        _case_files = list(dict.fromkeys(_case_files))

        if len(_case_files) < 2:
            st.warning("Upload at least 2 documents to use the comparison tool. Run a full analysis first.")
        else:
            _cmp_col1, _cmp_col2 = st.columns(2)
            with _cmp_col1:
                _doc_a = st.selectbox("Document A", options=_case_files, key="_cmp_doc_a")
            with _cmp_col2:
                _remaining = [f for f in _case_files if f != _doc_a]
                _doc_b = st.selectbox("Document B", options=_remaining if _remaining else _case_files, key="_cmp_doc_b")

            _cmp_focus = st.text_input(
                "Focus Area (optional)",
                placeholder="e.g., timeline of events, witness statements, damages amounts",
                key="_cmp_focus"
            )

            if st.button(
                f"Compare Documents {estimate_cost(str(results.get('case_summary', ''))[:200], model_provider)}",
                type="primary",
                key="_gen_doc_compare"
            ):
                if results.get("case_summary"):
                    with st.spinner(f"Comparing {os.path.basename(str(_doc_a))} vs {os.path.basename(str(_doc_b))}..."):
                        _cmp_state = dict(st.session_state.agent_results)
                        _cmp_state["comparison_request"] = {
                            "doc_a": _doc_a,
                            "doc_b": _doc_b,
                            "focus": _cmp_focus
                        }
                        _cmp_result = compare_documents(_cmp_state)
                        st.session_state.agent_results["document_comparison"] = _cmp_result.get("document_comparison", "")
                        case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                        st.rerun()
                else:
                    st.warning("Run a full analysis first so the AI can reference your case facts.")

        _cmp_data = results.get("document_comparison", "")
        if _cmp_data:
            st.divider()
            if isinstance(_cmp_data, str):
                st.markdown(_cmp_data)
            elif isinstance(_cmp_data, dict):
                if _cmp_data.get("summary"):
                    st.markdown(f"### Comparison Summary")
                    st.markdown(_cmp_data["summary"])

                if _cmp_data.get("contradictions"):
                    st.markdown("### Contradictions & Conflicts")
                    for _ci, _con in enumerate(_cmp_data["contradictions"]):
                        if isinstance(_con, dict):
                            with st.expander(f"**{_con.get('topic', f'Issue {_ci+1}')}** -- {_con.get('severity', 'Unknown')} severity", expanded=True):
                                _sc1, _sc2 = st.columns(2)
                                with _sc1:
                                    st.markdown(f"**Doc A says:**\n> {_con.get('doc_a_position', 'N/A')}")
                                with _sc2:
                                    st.markdown(f"**Doc B says:**\n> {_con.get('doc_b_position', 'N/A')}")
                                if _con.get("significance"):
                                    st.info(f"**Significance:** {_con['significance']}")
                                if _con.get("impeachment_value"):
                                    st.warning(f"**Impeachment Value:** {_con['impeachment_value']}")
                        elif isinstance(_con, str):
                            st.markdown(f"- {_con}")

                if _cmp_data.get("agreements"):
                    st.markdown("### Points of Agreement")
                    for _ag in _cmp_data["agreements"]:
                        if isinstance(_ag, dict):
                            st.markdown(f"- **{_ag.get('topic', '')}**: {_ag.get('detail', '')}")
                        elif isinstance(_ag, str):
                            st.markdown(f"- {_ag}")

                if _cmp_data.get("strategic_implications"):
                    st.markdown("### Strategic Implications")
                    st.markdown(_cmp_data["strategic_implications"])

            st.divider()
            _cmp_export = _cmp_data if isinstance(_cmp_data, str) else json.dumps(_cmp_data, indent=2, default=str)
            _dl_c1, _dl_c2 = st.columns(2)
            with _dl_c1:
                st.download_button(
                    "Download Comparison (.md)",
                    data=_cmp_export,
                    file_name=f"doc_comparison_{case_id}.md",
                    mime="text/markdown",
                    key="_dl_doc_cmp_md"
                )
            with _dl_c2:
                st.download_button(
                    "Download as JSON",
                    data=json.dumps({"document_comparison": _cmp_data}, indent=2, default=str),
                    file_name=f"doc_comparison_{case_id}.json",
                    mime="application/json",
                    key="_dl_doc_cmp_json"
                )
        else:
            if len(_case_files) >= 2:
                st.info("No comparison yet. Select two documents and click Compare above.")

    with tabs[-1]:  # MISSING DISCOVERY
        st.subheader("Missing Discovery Evaluator")
        st.caption("Analyze your case file for discovery that may be missing from the opposing side's production.")

        if st.button(f"Evaluate Missing Discovery {estimate_cost(str(results.get('case_summary', '')) + str(results.get('evidence_foundations', '')), model_provider)}", key="run_missing_disc", type="primary", use_container_width=True):
            with st.spinner("Analyzing case materials for missing discovery..."):
                _md_result = evaluate_missing_discovery(st.session_state.agent_results)
                safe_update_and_save(case_mgr, st.session_state.current_case_id, st.session_state.current_prep_id, st.session_state.agent_results, _md_result)
                st.rerun()

        _md_data = results.get("missing_discovery", {})
        if isinstance(_md_data, str):
            try:
                _md_data = json.loads(_md_data)
            except Exception:
                _md_data = {}

        if _md_data and isinstance(_md_data, dict) and not _md_data.get("_parse_error"):
            _total = _md_data.get("total_items", 0)
            _summary = _md_data.get("summary", "")
            if _summary:
                st.info(f"**{_total} potential missing items identified** -- {_summary}")

            _tiers = [
                ("definitely_exists", "Definitely Exists", "These items are explicitly referenced in your current documents but have NOT been produced.", "error"),
                ("probably_exists", "Probably Exists", "These items very likely exist given the facts and circumstances of this case.", "warning"),
                ("should_exist", "Should Exist", "Standard discovery items for this type of case that have not been provided.", "info"),
                ("might_exist", "Might Exist", "Speculative but potentially valuable -- worth requesting.", "info"),
            ]

            for _tier_key, _tier_label, _tier_desc, _tier_type in _tiers:
                _items = _md_data.get(_tier_key, [])
                if _items and isinstance(_items, list):
                    with st.expander(f"{_tier_label} ({len(_items)} items)", expanded=(_tier_key == "definitely_exists")):
                        st.caption(_tier_desc)
                        for _mi, _item in enumerate(_items):
                            if isinstance(_item, dict):
                                _imp = _item.get("importance", "")
                                _dtype = _item.get("discovery_type", "")

                                with st.container(border=True):
                                    st.markdown(f"**{_item.get('item', 'Unknown')}**")
                                    st.caption(f"_{_item.get('basis', '')}_ | Importance: **{_imp}** | Type: {_dtype}")
                            elif isinstance(_item, str):
                                st.markdown(f"- {_item}")

            _letter = _md_data.get("draft_letter", "")
            if _letter:
                st.divider()
                with st.expander("**Draft Discovery Request Letter**", expanded=False):
                    st.markdown(_letter)
                    st.download_button(
                        "Download Letter as TXT",
                        data=_letter,
                        file_name=f"discovery_request_{case_id}.txt",
                        mime="text/plain",
                        key="_dl_disc_letter"
                    )

        elif _md_data and isinstance(_md_data, dict) and _md_data.get("_parse_error"):
            st.warning("Analysis was generated but could not be parsed. Raw output:")
            st.code(_md_data.get("raw_output", ""))
        else:
            st.info("Click 'Evaluate Missing Discovery' to analyze your case file for gaps in opposing counsel's production.")
