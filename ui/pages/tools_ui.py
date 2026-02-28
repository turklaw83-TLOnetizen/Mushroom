"""Tools UI module — ported from legacy ui_modules/tools_ui.py."""
import logging
import os
import json
import streamlit as st

from core.ethical_compliance import *  # noqa: F401,F403 — side-effect import kept for compat
from core.nodes import (
    process_voice_note,
    generate_exhibit_plan,
    generate_exhibit_list,
    scan_conflicts,
)
from core.export import generate_quick_cards_pdf
from ui.shared import get_model_provider

logger = logging.getLogger(__name__)


def _estimate_cost(text_sample: str, model_provider: str) -> str:
    """Lightweight cost badge helper (replaces the old app.estimate_cost)."""
    try:
        from core.cost_tracker import format_cost_badge
        return format_cost_badge(text_sample, model_provider)
    except Exception:
        return ""


def render(case_id, case_mgr, results, tabs, selected_group, nav_groups, model_provider, prep_id):
    """Render the Tools UI tabs."""
    estimate_cost = _estimate_cost

    # --- OCR Dashboard (above tabs) ---
    with st.expander("\U0001f4ca OCR Status Dashboard", expanded=False):
        try:
            from core.ingest import OCRCache
            from ui.shared import PROJECT_ROOT
            import os as _os

            _all_case_files = case_mgr.get_case_files(case_id) or []
            _ocr_case_dir = _os.path.join(str(PROJECT_ROOT / "data" / "cases"), case_id)
            _ocr_cache = OCRCache(_ocr_case_dir)

            if not _all_case_files:
                st.info("No files in this case yet. Upload documents to see OCR status.")
            else:
                # Summary metrics
                _ocr_total = 0
                _ocr_done = 0
                _ocr_pending = 0
                _ocr_errors = 0
                _ocr_rows = []

                for _fp in _all_case_files:
                    _fn = _os.path.basename(_fp)
                    _ext = _os.path.splitext(_fn)[1].lower()
                    if _ext not in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"):
                        continue
                    _ocr_total += 1
                    try:
                        _fsize = _os.path.getsize(_fp) if _os.path.exists(_fp) else 0
                        _fkey = f"{_fn}:{_fsize}"
                        _cached_text = _ocr_cache.get_text(_fkey)
                        if _cached_text and len(_cached_text) > 10:
                            _status = "\u2705 Done"
                            _ocr_done += 1
                        else:
                            _status = "\u23f3 Pending"
                            _ocr_pending += 1
                    except Exception:
                        _status = "\u274c Error"
                        _ocr_errors += 1

                    _ocr_rows.append({
                        "File": _fn,
                        "Status": _status,
                        "Size": f"{_fsize / 1024:.0f} KB" if _fsize else "?",
                    })

                # Metrics row
                _m1, _m2, _m3, _m4 = st.columns(4)
                _m1.metric("Total Files", _ocr_total)
                _m2.metric("OCR Complete", _ocr_done)
                _m3.metric("Pending", _ocr_pending)
                _m4.metric("Errors", _ocr_errors)

                if _ocr_total > 0:
                    st.progress(
                        _ocr_done / _ocr_total,
                        text=f"OCR Progress: {_ocr_done}/{_ocr_total} ({100 * _ocr_done / _ocr_total:.0f}%)",
                    )

                # File table
                if _ocr_rows:
                    for _or in _ocr_rows:
                        _oc1, _oc2, _oc3, _oc4 = st.columns([2, 0.8, 0.6, 0.8])
                        _oc1.markdown(f"\U0001f4c4 {_or['File']}")
                        _oc2.markdown(_or["Status"])
                        _oc3.caption(_or["Size"])
                        with _oc4:
                            if "Pending" in _or["Status"] or "Error" in _or["Status"]:
                                if st.button("Force OCR", key=f"_force_ocr_{_or['File'][:20]}"):
                                    try:
                                        from core.ocr_worker import prioritize_file
                                        prioritize_file(case_id, _or["File"])
                                        st.toast(f"Prioritized {_or['File']} for OCR")
                                    except Exception as _oe:
                                        st.warning(f"Could not prioritize: {_oe}")
        except Exception as _ocr_exc:
            st.warning(f"OCR dashboard unavailable: {_ocr_exc}")

    # --- Tab 0: Voice-to-Brief ---
    with tabs[0]:
        st.subheader("Voice-to-Brief")
        st.caption("Upload audio or paste a transcript — AI extracts action items, new facts, and key quotes.")

        _vb_method = st.radio("Input Method", ["Upload Audio File", "Paste Transcript"], horizontal=True, key="_vb_method")

        transcript_text = ""
        if _vb_method == "Upload Audio File":
            audio_file = st.file_uploader("Upload audio recording", type=["mp3", "wav", "m4a", "ogg", "webm"], key="_vb_audio")
            if audio_file:
                st.audio(audio_file)
                if st.button("Transcribe with Whisper", key="_vb_transcribe"):
                    _oai_key = os.environ.get("OPENAI_API_KEY", "")
                    if not _oai_key:
                        st.error("OpenAI API key required for Whisper transcription. Add it in the sidebar.")
                    else:
                        with st.spinner("Transcribing audio with Whisper..."):
                            try:
                                import openai as _oai
                                _client = _oai.OpenAI(api_key=_oai_key)
                                _resp = _client.audio.transcriptions.create(model="whisper-1", file=audio_file)
                                st.session_state["_vb_transcript"] = _resp.text
                                st.success(f"Transcribed {len(_resp.text.split())} words!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Transcription failed: {e}")

            transcript_text = st.session_state.get("_vb_transcript", "")
            if transcript_text:
                st.text_area("Transcript", value=transcript_text, height=200, disabled=True, key="_vb_transcript_display")
        else:
            transcript_text = st.text_area(
                "Paste transcript here",
                height=200,
                placeholder="Paste your meeting notes, courtroom proceeding transcript, or dictation...",
                key="_vb_paste"
            )

        if transcript_text and st.button(
            f"Extract Brief {estimate_cost(transcript_text[:200], model_provider)}",
            type="primary",
            key="_vb_extract"
        ):
            with st.spinner("Analyzing transcript and extracting structured brief..."):
                vb_result = process_voice_note(st.session_state.agent_results, transcript_text)
                st.session_state.agent_results["voice_brief"] = vb_result.get("voice_brief", {})
                case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                st.rerun()

        vb_data = results.get("voice_brief", {})
        if isinstance(vb_data, dict) and (vb_data.get("summary") or vb_data.get("raw_output")):
            if vb_data.get("parse_error"):
                st.warning("AI output could not be fully parsed. Showing raw output:")
                st.markdown(vb_data.get("raw_output", ""))
            else:
                _vb_type = vb_data.get("recording_type", "unknown").replace("_", " ").title()
                st.markdown(f"**Recording Type:** {_vb_type}")
                st.info(vb_data.get("summary", ""))

                _actions = vb_data.get("action_items", [])
                if _actions:
                    st.markdown("### Action Items")
                    for _ai in _actions:
                        if isinstance(_ai, dict):
                            _pri = _ai.get("priority", "medium")
                            _icon = "HIGH" if _pri == "high" else ("MED" if _pri == "medium" else "LOW")
                            st.markdown(f"- [{_icon}] **{_ai.get('task', '')}** {'(_' + _ai.get('deadline', '') + '_)' if _ai.get('deadline') else ''}")

                _facts = vb_data.get("new_facts", [])
                if _facts:
                    st.markdown("### New Facts Discovered")
                    for _nf in _facts:
                        if isinstance(_nf, dict):
                            st.markdown(f"- **{_nf.get('fact', '')}** — _Source: {_nf.get('source', 'Unknown')}_")
                            if _nf.get("significance"):
                                st.caption(f"  Significance: {_nf['significance']}")

                _quotes = vb_data.get("key_quotes", [])
                if _quotes:
                    st.markdown("### Key Quotes")
                    for _kq in _quotes:
                        if isinstance(_kq, dict):
                            st.markdown(f"> \"{_kq.get('quote', '')}\"  \n> — _{_kq.get('speaker', 'Unknown')}_")
                            if _kq.get("significance"):
                                st.caption(f"  {_kq['significance']}")

                _ci = vb_data.get("client_instructions", [])
                if _ci:
                    st.markdown("### Client Instructions")
                    for _item in _ci:
                        st.markdown(f"- {_item}")

                _at = vb_data.get("agreed_terms", [])
                if _at:
                    st.markdown("### Agreed Terms / Stipulations")
                    for _item in _at:
                        st.markdown(f"- {_item}")

                _fq = vb_data.get("follow_up_questions", [])
                if _fq:
                    st.markdown("### Follow-Up Questions")
                    for _item in _fq:
                        st.markdown(f"- {_item}")

                _su = vb_data.get("suggested_updates", "")
                if _su:
                    st.markdown("### Suggested Case Updates")
                    st.info(_su)

                st.divider()
                st.download_button(
                    "Download Brief as JSON",
                    data=json.dumps(vb_data, indent=2, default=str),
                    file_name=f"voice_brief_{case_id}.json",
                    mime="application/json",
                    key="_dl_vb_json"
                )
        elif not transcript_text:
            st.info("Upload an audio file or paste a transcript to get started.")

    # --- Tab 1: Exhibit Preparation Wizard ---
    with tabs[1]:
        st.subheader("Exhibit Preparation Wizard")
        st.caption("AI-powered exhibit numbering, descriptions, and foundation scripts for admission.")

        if st.button(
            f"Generate Exhibit Plan {estimate_cost(results.get('case_summary', '')[:200] + str(results.get('evidence_foundations', ''))[:200], model_provider)}",
            type="primary",
            key="_gen_exhibit_plan"
        ):
            if results.get("case_summary"):
                with st.spinner("Analyzing exhibits and generating foundation scripts..."):
                    ep_result = generate_exhibit_plan(st.session_state.agent_results)
                    st.session_state.agent_results["exhibit_plan"] = ep_result.get("exhibit_plan", [])
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
            else:
                st.warning("Run a full analysis first so the AI can reference your case facts.")

        ex_data = results.get("exhibit_plan", [])
        if ex_data and isinstance(ex_data, list) and len(ex_data) > 0:
            _ex_types = {}
            for _ex in ex_data:
                if isinstance(_ex, dict):
                    _et = _ex.get("type", "unknown")
                    _ex_types[_et] = _ex_types.get(_et, 0) + 1

            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("Total Exhibits", len(ex_data))
            ec2.metric("Types", ", ".join(_ex_types.keys()) if _ex_types else "N/A")
            ec3.metric("With Scripts", sum(1 for e in ex_data if isinstance(e, dict) and e.get("foundation_script")))

            st.divider()

            for _ei, _ex in enumerate(ex_data):
                if not isinstance(_ex, dict):
                    continue

                _ex_num = _ex.get("number", _ei + 1)
                _ex_file = _ex.get("file", "Unknown")
                _ex_desc = _ex.get("description", "No description")
                _ex_type = _ex.get("type", "unknown")
                _type_icon = {"documentary": "[DOC]", "physical": "[PHY]", "demonstrative": "[DEM]", "testimonial": "[TES]"}.get(_ex_type, "[EXH]")

                with st.expander(f"{_type_icon} **Exhibit {_ex_num}** — {_ex_file}", expanded=False):
                    st.markdown(f"**Description:** {_ex_desc}")
                    st.markdown(f"**Type:** {_ex_type.title()}")

                    if _ex.get("sponsoring_witness"):
                        st.markdown(f"**Sponsoring Witness:** {_ex['sponsoring_witness']}")

                    if _ex.get("order_rationale"):
                        st.markdown(f"**Order Rationale:** {_ex['order_rationale']}")

                    if _ex.get("strategic_notes"):
                        st.info(f"**Strategic Notes:** {_ex['strategic_notes']}")

                    if _ex.get("anticipated_objections"):
                        st.warning(f"**Anticipated Objections:** {_ex['anticipated_objections']}")

                    _script = _ex.get("foundation_script", "")
                    if _script:
                        st.markdown("---")
                        st.markdown("**Foundation Script:**")
                        _formatted = _script.replace("\\n", "\n")
                        st.code(_formatted, language=None)

            st.divider()
            _ep_export = "# EXHIBIT PLAN\n\n"
            for _ex in ex_data:
                if isinstance(_ex, dict):
                    _ep_export += f"## Exhibit {_ex.get('number', '?')}: {_ex.get('file', 'Unknown')}\n"
                    _ep_export += f"**Description:** {_ex.get('description', '')}\n"
                    _ep_export += f"**Type:** {_ex.get('type', '')}\n"
                    _ep_export += f"**Sponsoring Witness:** {_ex.get('sponsoring_witness', 'TBD')}\n"
                    _ep_export += f"**Strategic Notes:** {_ex.get('strategic_notes', '')}\n"
                    _ep_export += f"**Anticipated Objections:** {_ex.get('anticipated_objections', '')}\n\n"
                    _ep_export += f"### Foundation Script\n```\n{_ex.get('foundation_script', 'N/A')}\n```\n\n---\n\n"

            ep_dl_c1, ep_dl_c2 = st.columns(2)
            with ep_dl_c1:
                st.download_button(
                    "Download Exhibit Plan (.md)",
                    data=_ep_export,
                    file_name=f"exhibit_plan_{case_id}.md",
                    mime="text/markdown",
                    key="_dl_ep_md"
                )
            with ep_dl_c2:
                st.download_button(
                    "Download as JSON",
                    data=json.dumps(ex_data, indent=2, default=str),
                    file_name=f"exhibit_plan_{case_id}.json",
                    mime="application/json",
                    key="_dl_ep_json"
                )
        else:
            st.info("No exhibit plan yet. Click the button above to generate one from your case analysis.")

    # --- Tab 2: Exhibit List Builder ---
    with tabs[2]:
        st.subheader("Exhibit List Builder")
        st.caption("Generate a court-ready exhibit list with Bates numbers, AI descriptions, and authentication notes.")

        if st.button(
            f"Build Exhibit List {estimate_cost(str(results.get('case_summary', ''))[:200] + str(results.get('evidence_foundations', ''))[:200], model_provider)}",
            type="primary",
            key="_gen_exhibit_list"
        ):
            if results.get("case_summary"):
                with st.spinner("Building exhibit list with Bates references and AI descriptions..."):
                    _el_result = generate_exhibit_list(st.session_state.agent_results)
                    st.session_state.agent_results["exhibit_list"] = _el_result.get("exhibit_list", [])
                    case_mgr.save_prep_state(case_id, prep_id, st.session_state.agent_results)
                    st.rerun()
            else:
                st.warning("Run a full analysis first so the AI can reference your case facts.")

        _el_data = results.get("exhibit_list", [])
        if _el_data and isinstance(_el_data, list) and len(_el_data) > 0:
            st.divider()
            _el_c1, _el_c2, _el_c3 = st.columns(3)
            _el_c1.metric("Total Exhibits", len(_el_data))
            _el_types = {}
            for _el in _el_data:
                if isinstance(_el, dict):
                    _elt = _el.get("type", "unknown")
                    _el_types[_elt] = _el_types.get(_elt, 0) + 1
            _el_c2.metric("Types", len(_el_types))
            _el_c3.metric("With Bates #", sum(1 for e in _el_data if isinstance(e, dict) and e.get("bates_range")))

            st.divider()

            _el_table = []
            for _eli, _el in enumerate(_el_data):
                if isinstance(_el, dict):
                    _el_table.append({
                        "No.": _el.get("number", _eli + 1),
                        "Description": _el.get("description", "N/A")[:60],
                        "Type": _el.get("type", "N/A").title(),
                        "Bates Range": _el.get("bates_range", "N/A"),
                        "Sponsoring Witness": _el.get("sponsoring_witness", "TBD"),
                        "Status": _el.get("authentication_status", "?")
                    })

            if _el_table:
                import pandas as _el_pd
                _el_df = _el_pd.DataFrame(_el_table)
                st.dataframe(_el_df, use_container_width=True, hide_index=True)

            st.markdown("### Detailed Exhibit Entries")
            for _eli, _el in enumerate(_el_data):
                if not isinstance(_el, dict):
                    continue
                _el_num = _el.get("number", _eli + 1)
                _el_desc = _el.get("description", "No description")
                _el_type_str = _el.get("type", "")
                _el_icon = {
                    "documentary": "[DOC]",
                    "physical": "[PHY]",
                    "demonstrative": "[DEM]",
                    "testimonial": "[TES]",
                    "digital": "[DIG]"
                }.get(_el_type_str, "[EXH]")

                with st.expander(f"{_el_icon} **Exhibit {_el_num}** — {_el_desc[:50]}", expanded=False):
                    st.markdown(f"**Full Description:** {_el_desc}")
                    st.markdown(f"**Type:** {_el_type_str.title()}")
                    if _el.get("bates_range"):
                        st.markdown(f"**Bates Range:** `{_el['bates_range']}`")
                    if _el.get("source_file"):
                        st.markdown(f"**Source File:** {os.path.basename(str(_el['source_file']))}")
                    if _el.get("sponsoring_witness"):
                        st.markdown(f"**Sponsoring Witness:** {_el['sponsoring_witness']}")
                    if _el.get("authentication_method"):
                        st.markdown(f"**Authentication Method:** {_el['authentication_method']}")
                    if _el.get("relevance"):
                        st.info(f"**Relevance:** {_el['relevance']}")
                    if _el.get("anticipated_objections"):
                        st.warning(f"**Anticipated Objections:** {_el['anticipated_objections']}")

            st.divider()
            _el_export = "# EXHIBIT LIST\n\n"
            _el_export += "| No. | Description | Type | Bates Range | Witness | Status |\n"
            _el_export += "|-----|-------------|------|-------------|---------|--------|\n"
            for _el in _el_data:
                if isinstance(_el, dict):
                    _el_export += f"| {_el.get('number', '?')} | {_el.get('description', 'N/A')[:40]} | {_el.get('type', '')} | {_el.get('bates_range', 'N/A')} | {_el.get('sponsoring_witness', 'TBD')} | {_el.get('authentication_status', '?')} |\n"

            el_dl_c1, el_dl_c2 = st.columns(2)
            with el_dl_c1:
                st.download_button(
                    "Download Exhibit List (.md)",
                    data=_el_export,
                    file_name=f"exhibit_list_{case_id}.md",
                    mime="text/markdown",
                    key="_dl_el_md"
                )
            with el_dl_c2:
                st.download_button(
                    "Download as JSON",
                    data=json.dumps(_el_data, indent=2, default=str),
                    file_name=f"exhibit_list_{case_id}.json",
                    mime="application/json",
                    key="_dl_el_json"
                )
        else:
            st.info("No exhibit list yet. Click the button above to generate one from your case analysis.")

    # --- Tab 3: Quick Cards ---
    with tabs[3]:
        st.subheader("Courtroom Quick Cards")
        st.caption("Generate compact, print-ready reference cards for use at counsel table during trial.")

        _qc_type = st.selectbox(
            "Card Type",
            ["witness", "evidence", "objections"],
            format_func=lambda x: {
                "witness": "Witness Cards — key facts, impeachment, cross questions",
                "evidence": "Evidence Foundation Cards — authentication scripts per exhibit",
                "objections": "Objection Quick-Reference — common objections with responses"
            }.get(x, x),
            key="_qc_type_select"
        )

        _qc_desc = {
            "witness": "One card per witness with name, role, alignment color bar, summary, key cross-examination questions, and impeachment points. Color-coded: **green** (friendly), **red** (hostile), **yellow** (neutral).",
            "evidence": "One card per exhibit with title, type, authentication script, anticipated objections, and strategic value. Designed for quick reference when laying foundation.",
            "objections": "Pre-built reference of 12 common trial objections with FRE rule numbers, basis descriptions, and ready-made responses. Always available even without case data."
        }
        st.info(_qc_desc.get(_qc_type, ""))

        _qc_case_name = case_mgr.get_case_metadata(case_id).get("name", "Case") if case_id else "Case"

        if st.button("Generate Quick Cards PDF", type="primary", key="_qc_generate"):
            with st.spinner("Generating print-ready cards..."):
                try:
                    _qc_state = results if results else {}
                    _qc_pdf = generate_quick_cards_pdf(_qc_state, card_type=_qc_type, case_name=_qc_case_name)
                    st.session_state["_qc_pdf_data"] = _qc_pdf.getvalue()
                    st.session_state["_qc_pdf_type"] = _qc_type
                    st.success("Quick cards generated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating cards: {e}")

        _qc_pdf_bytes = st.session_state.get("_qc_pdf_data")
        if _qc_pdf_bytes:
            _qc_fname = f"quick_cards_{st.session_state.get('_qc_pdf_type', 'cards')}_{case_id}.pdf"
            st.download_button(
                "Download Quick Cards PDF",
                data=_qc_pdf_bytes,
                file_name=_qc_fname,
                mime="application/pdf",
                key="_qc_download"
            )
            st.caption("Print on A5 landscape paper for best results. Cards are designed for counsel-table use.")

    # --- Tab 4: Conflict Check Scanner ---
    with tabs[4]:
        st.subheader("Conflict Check Scanner")
        st.caption("Scan all cases for potential conflicts of interest — matches entities by name across your entire case portfolio.")

        # -- Manual Entity Manager --
        st.markdown("### Manage Entities for This Case")
        st.caption("Add parties, witnesses, or organizations that may not appear in uploaded documents.")

        _cc_manual = case_mgr.load_manual_entities(case_id)

        with st.expander("Add New Entity", expanded=False):
            _cc_col1, _cc_col2 = st.columns(2)
            with _cc_col1:
                _cc_name = st.text_input("Entity Name", key="_cc_ent_name", placeholder="e.g. John Smith")
            with _cc_col2:
                _cc_type = st.selectbox("Type", ["PERSON", "ORGANIZATION", "COMPANY", "GOVERNMENT", "OTHER"], key="_cc_ent_type")
            _cc_role = st.text_input("Role / Relationship", key="_cc_ent_role", placeholder="e.g. Plaintiff's spouse, Former employer")
            if st.button("Add Entity", key="_cc_add_ent", type="primary"):
                if _cc_name and _cc_name.strip():
                    case_mgr.save_manual_entity(case_id, _cc_name.strip(), _cc_type, _cc_role.strip())
                    st.success(f"Added **{_cc_name.strip()}** ({_cc_type})")
                    st.rerun()
                else:
                    st.warning("Please enter an entity name.")

        if _cc_manual:
            st.markdown(f"**{len(_cc_manual)} manual entities** for this case:")
            for _me in _cc_manual:
                _me_c1, _me_c2, _me_c3 = st.columns([3, 2, 1])
                with _me_c1:
                    st.markdown(f"**{_me.get('name', 'N/A')}** — {_me.get('type', '')}")
                with _me_c2:
                    st.caption(_me.get("role", ""))
                with _me_c3:
                    if st.button("Remove", key=f"_cc_del_{_me.get('id', '')}"):
                        case_mgr.delete_manual_entity(case_id, _me.get("id", ""))
                        st.rerun()
        else:
            st.info("No manual entities added yet. AI-extracted entities from documents will also be included in the scan.")

        st.divider()

        # -- Run Conflict Scan --
        st.markdown("### Run Conflict Scan")
        if st.button("Scan for Conflicts Across All Cases", type="primary", key="_cc_run_scan"):
            with st.spinner("Loading entities from all cases and scanning for conflicts..."):
                _all_ents = case_mgr.load_all_entities()
                _cc_result = scan_conflicts(case_id, _all_ents)
                st.session_state["_cc_scan_result"] = _cc_result
                st.rerun()

        _cc_result = st.session_state.get("_cc_scan_result")
        if _cc_result:
            _cc_conflicts = _cc_result.get("conflicts", [])
            _cc_scanned = _cc_result.get("cases_scanned", 0)
            _cc_checked = _cc_result.get("entities_checked", 0)

            st.divider()

            _m1, _m2, _m3, _m4 = st.columns(4)
            _high = sum(1 for c in _cc_conflicts if c.get("severity") == "HIGH")
            _med = sum(1 for c in _cc_conflicts if c.get("severity") == "MEDIUM")
            _m1.metric("Total Conflicts", len(_cc_conflicts))
            _m2.metric("High Severity", _high)
            _m3.metric("Medium Severity", _med)
            _m4.metric("Cases Scanned", _cc_scanned)

            if _cc_conflicts:
                st.markdown("---")
                st.markdown("### Potential Conflicts Found")

                for _ci, _conf in enumerate(_cc_conflicts):
                    _sev = _conf.get("severity", "MEDIUM")
                    _sev_icon = "[HIGH]" if _sev == "HIGH" else "[MED]"
                    _sev_badge = f"`{_sev}`"
                    _ent_a = _conf.get("entity_a", "Unknown")
                    _ent_b = _conf.get("entity_b", "Unknown")
                    _case_b = _conf.get("other_case_name", "Unknown Case")
                    _match = _conf.get("match_type", "")

                    with st.expander(f"{_sev_icon} {_sev_badge}  **{_ent_a}** <-> **{_ent_b}** — {_case_b}", expanded=(_sev == "HIGH")):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("**This Case Entity:**")
                            st.markdown(f"- **Name:** {_ent_a}")
                            st.markdown(f"- **Type:** {_conf.get('type_a', 'N/A')}")
                            st.markdown(f"- **Role:** {_conf.get('role_a', 'N/A')}")
                            st.markdown(f"- **Source:** {_conf.get('source_a', 'N/A')}")
                        with c2:
                            st.markdown("**Other Case Entity:**")
                            st.markdown(f"- **Name:** {_ent_b}")
                            st.markdown(f"- **Type:** {_conf.get('type_b', 'N/A')}")
                            st.markdown(f"- **Role:** {_conf.get('role_b', 'N/A')}")
                            st.markdown(f"- **Case:** {_case_b}")
                        st.markdown(f"**Match Type:** {_match}")
                        if _sev == "HIGH":
                            st.error("**HIGH SEVERITY** — Exact or near-exact name match detected. Immediate review recommended.")
                        else:
                            st.warning("**MEDIUM** — Partial name overlap. Review to determine if this is the same individual or entity.")
            else:
                st.success(f"No conflicts found! Scanned {_cc_checked} entities across {_cc_scanned} other cases.")
