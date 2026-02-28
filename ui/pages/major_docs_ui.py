# ---- Major Document Drafter Workspace ------------------------------------
# Full-page workspace for drafting major legal documents (appellate briefs,
# PCR petitions, civil complaints, etc.) section by section.
# Rendered when _md_active is True — replaces the normal tab dispatch in case_view.py.

import json
import logging
import queue
import re
import threading
import uuid
from datetime import datetime

import streamlit as st

from core.state import set_stream_callback, clear_stream_callback

logger = logging.getLogger(__name__)


# ---- Streaming Helper ----------------------------------------------------

def _run_streaming(fn, args=(), kwargs=None, label="Processing..."):
    """Run a node function with streaming token display in st.status.

    Uses set_stream_callback() so invoke_with_retry() auto-switches to llm.stream().
    Returns the result dict from the function, or None on error.
    """
    if kwargs is None:
        kwargs = {}

    token_q = queue.Queue()
    _result = [None]
    _error = [None]

    def _worker():
        try:
            _result[0] = fn(*args, **kwargs)
        except Exception as exc:
            _error[0] = exc
        finally:
            token_q.put(None)  # Sentinel

    set_stream_callback(lambda tok: token_q.put(tok))
    worker = threading.Thread(target=_worker, daemon=True)

    try:
        with st.status(label, expanded=True) as status:
            placeholder = st.empty()
            worker.start()

            accumulated = []
            while True:
                try:
                    tok = token_q.get(timeout=0.3)
                except queue.Empty:
                    if accumulated:
                        placeholder.markdown("".join(accumulated))
                    continue
                if tok is None:
                    break
                accumulated.append(tok)
                if len(accumulated) % 20 == 0:
                    placeholder.markdown("".join(accumulated))

            if accumulated:
                placeholder.markdown("".join(accumulated))

            worker.join(timeout=10)

            if _error[0]:
                status.update(label=f"Error: {_error[0]}", state="error")
                st.error(f"Failed: {_error[0]}")
                logger.exception("Streaming node failed", exc_info=_error[0])
                return None

            status.update(label=label.replace("...", " — done!"), state="complete")
            return _result[0]
    finally:
        clear_stream_callback()


# ---- Entry Point ---------------------------------------------------------

def render_workspace(case_id, case_mgr, results, model_provider, prep_id):
    """Main entry point — replaces the case view main area when _md_active."""

    # Back to Case button
    if st.button("\u2190 Back to Case", key="_md_back", type="secondary"):
        st.session_state._md_active = False
        st.rerun()

    st.markdown("## \U0001f4c4 Major Document Drafter")
    st.caption("Draft publication-ready legal documents section by section.")

    tabs = st.tabs(["Draft Workspace", "Opponent Analysis", "Saved Drafts", "Settings"])

    with tabs[0]:
        _render_draft_workspace(case_id, case_mgr, results, model_provider, prep_id)
    with tabs[1]:
        _render_opponent_analysis(case_id, case_mgr, results, model_provider)
    with tabs[2]:
        _render_saved_drafts(case_id, case_mgr)
    with tabs[3]:
        _render_settings(case_id, case_mgr)


# ---- Tab 1: Draft Workspace ---------------------------------------------

def _render_draft_workspace(case_id, case_mgr, results, model_provider, prep_id):
    from core.nodes.major_docs import DOC_TYPES

    # --- Document Type Selector ---
    doc_types = list(DOC_TYPES.keys())
    selected_type = st.selectbox("Document Type", doc_types, key="_md_doc_type")

    subtypes = DOC_TYPES.get(selected_type, [])
    if subtypes:
        selected_subtype = st.selectbox("Subtype", subtypes, key="_md_doc_subtype")
    elif selected_type == "Custom Document":
        selected_subtype = st.text_input(
            "Custom Document Type", key="_md_custom_type",
            placeholder="e.g., Memorandum of Law",
        )
    else:
        selected_subtype = selected_type

    # --- Configuration Panel ---
    with st.expander("\u2699\ufe0f Document Configuration", expanded=False):
        _render_config_panel(case_id, case_mgr, results)

    # --- Phase Router: Outline \u2192 Drafting \u2192 Assembly ---
    _md_phase = st.session_state.get("_md_phase", "outline")

    if _md_phase == "outline":
        _render_outline_phase(
            case_id, case_mgr, results, model_provider,
            selected_type, selected_subtype,
        )
    elif _md_phase == "drafting":
        _render_drafting_phase(
            case_id, case_mgr, results, model_provider,
            selected_type, selected_subtype,
        )
    elif _md_phase == "assembly":
        _render_assembly_phase(case_id, case_mgr, results, model_provider)


# ---- Configuration Panel ------------------------------------------------

def _render_config_panel(case_id, case_mgr, results):
    """Document configuration: jurisdiction, court, caption, attorney info, tone."""
    prefs = {}
    try:
        prefs = case_mgr.storage.load_json(case_id, "attorney_prefs.json") or {}
    except Exception:
        pass

    c1, c2 = st.columns(2)
    with c1:
        try:
            from core.export.court_docs import get_jurisdiction_list
            jur_list = get_jurisdiction_list()
            jur_keys = [j[0] for j in jur_list]
            jur_labels = {j[0]: j[1] for j in jur_list}
            cur_jur = prefs.get("jurisdiction", "tennessee_state")
            jur_idx = jur_keys.index(cur_jur) if cur_jur in jur_keys else 0
            st.session_state["_md_jurisdiction"] = st.selectbox(
                "Jurisdiction", jur_keys, index=jur_idx,
                format_func=lambda x: jur_labels.get(x, x),
                key="_md_jur_sel",
            )
        except Exception:
            st.session_state["_md_jurisdiction"] = "tennessee_state"

        st.session_state["_md_court_name"] = st.text_input(
            "Court Name", value=prefs.get("court_name", ""), key="_md_court",
        )
        st.session_state["_md_case_number"] = st.text_input(
            "Case Number", value=prefs.get("case_number", ""), key="_md_case_num",
        )

    with c2:
        tones = ["Formal/Persuasive", "Formal/Aggressive", "Formal/Measured"]
        st.session_state["_md_tone"] = st.selectbox("Tone", tones, key="_md_tone_sel")

        lengths = [
            "Standard (~15-25 pages)",
            "Comprehensive (~25-50 pages)",
            "Extensive (~50+ pages)",
        ]
        st.session_state["_md_length"] = st.selectbox(
            "Target Length", lengths, key="_md_length_sel",
        )

    # Caption info
    st.markdown("**Caption**")
    cap1, cap2 = st.columns(2)
    with cap1:
        st.session_state["_md_plaintiff"] = st.text_input(
            "Plaintiff / Petitioner / State",
            value=prefs.get("plaintiff", ""), key="_md_plaintiff_input",
        )
    with cap2:
        st.session_state["_md_defendant"] = st.text_input(
            "Defendant / Respondent",
            value=prefs.get("defendant", results.get("client_name", "")),
            key="_md_defendant_input",
        )

    # Attorney info
    st.markdown("**Attorney Information**")
    a1, a2 = st.columns(2)
    with a1:
        st.session_state["_md_atty_name"] = st.text_input(
            "Attorney Name", value=prefs.get("attorney_name", ""), key="_md_atty_name_in",
        )
        st.session_state["_md_atty_bar"] = st.text_input(
            "Bar Number", value=prefs.get("bar_number", ""), key="_md_atty_bar_in",
        )
        st.session_state["_md_atty_firm"] = st.text_input(
            "Firm", value=prefs.get("firm", ""), key="_md_atty_firm_in",
        )
    with a2:
        st.session_state["_md_atty_address"] = st.text_area(
            "Address", value=prefs.get("address", ""), key="_md_atty_addr_in", height=68,
        )
        st.session_state["_md_atty_phone"] = st.text_input(
            "Phone", value=prefs.get("phone", ""), key="_md_atty_phone_in",
        )
        st.session_state["_md_atty_email"] = st.text_input(
            "Email", value=prefs.get("email", ""), key="_md_atty_email_in",
        )

    # Save prefs
    if st.button("\U0001f4be Save Defaults", key="_md_save_prefs"):
        new_prefs = {
            "jurisdiction": st.session_state.get("_md_jurisdiction", "tennessee_state"),
            "court_name": st.session_state.get("_md_court_name", ""),
            "case_number": st.session_state.get("_md_case_number", ""),
            "plaintiff": st.session_state.get("_md_plaintiff", ""),
            "defendant": st.session_state.get("_md_defendant", ""),
            "attorney_name": st.session_state.get("_md_atty_name", ""),
            "bar_number": st.session_state.get("_md_atty_bar", ""),
            "firm": st.session_state.get("_md_atty_firm", ""),
            "address": st.session_state.get("_md_atty_address", ""),
            "phone": st.session_state.get("_md_atty_phone", ""),
            "email": st.session_state.get("_md_atty_email", ""),
        }
        try:
            case_mgr.storage.save_json(case_id, "attorney_prefs.json", new_prefs)
            st.toast("\u2705 Attorney preferences saved!")
        except Exception as e:
            st.error(f"Failed to save preferences: {e}")


# ---- Phase 1: Outline ---------------------------------------------------

def _render_outline_phase(case_id, case_mgr, results, model_provider,
                           doc_type, doc_subtype):
    custom_instructions = st.text_area(
        "Custom Instructions (optional)",
        key="_md_custom_instr", height=80,
        placeholder="Any specific requirements, arguments to emphasize, or structural preferences...",
    )

    # Generate Outline button
    if st.button("\U0001f3d7\ufe0f Generate Outline", key="_md_gen_outline", type="primary"):
        from core.nodes.major_docs import generate_document_outline

        state = dict(results) if results else {}
        state["current_model"] = model_provider

        result = _run_streaming(
            generate_document_outline,
            args=(state, doc_type, doc_subtype),
            kwargs={
                "custom_instructions": custom_instructions,
                "target_length": st.session_state.get("_md_length", "Standard (~15-25 pages)"),
                "tone": st.session_state.get("_md_tone", "Formal/Persuasive"),
            },
            label="Generating document outline...",
        )

        if result and "error" not in result:
            st.session_state["_md_outline"] = result.get("outline", [])
            st.session_state["_md_doc_title"] = result.get(
                "document_title", doc_subtype.upper(),
            )
            st.rerun()
        elif result and "error" in result:
            st.error(result["error"])

    # Display existing outline for editing
    outline = st.session_state.get("_md_outline", [])
    if not outline:
        return

    st.markdown(f"### {st.session_state.get('_md_doc_title', 'DOCUMENT')}")
    st.caption(f"{len(outline)} sections")

    updated_outline = []
    for i, sec in enumerate(outline):
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 4, 1])
            with c1:
                sec_num = st.text_input(
                    "\u00a7", value=sec.get("section_num", str(i + 1)),
                    key=f"_md_sec_num_{i}", label_visibility="collapsed",
                )
            with c2:
                sec_title = st.text_input(
                    "Title", value=sec.get("title", ""), key=f"_md_sec_title_{i}",
                )
            with c3:
                sec_pages = st.number_input(
                    "Pages", value=sec.get("estimated_pages", 2),
                    min_value=1, max_value=20, key=f"_md_sec_pages_{i}",
                )
            sec_desc = st.text_area(
                "Description", value=sec.get("description", ""),
                key=f"_md_sec_desc_{i}", height=60,
            )
            sec_instr = st.text_input(
                "Special Instructions (optional)",
                value=sec.get("instructions", ""),
                key=f"_md_sec_instr_{i}",
            )

            updated_outline.append({
                "section_num": sec_num,
                "title": sec_title,
                "description": sec_desc,
                "estimated_pages": sec_pages,
                "instructions": sec_instr,
            })

    # Add / Remove section buttons
    btn1, btn2, btn3 = st.columns(3)
    with btn1:
        if st.button("\u2795 Add Section", key="_md_add_section"):
            outline.append({
                "section_num": _next_roman(len(outline)),
                "title": "New Section",
                "description": "",
                "estimated_pages": 2,
                "instructions": "",
            })
            st.session_state["_md_outline"] = outline
            st.rerun()
    with btn2:
        if len(outline) > 1 and st.button("\u2796 Remove Last Section", key="_md_rm_section"):
            outline.pop()
            st.session_state["_md_outline"] = outline
            st.rerun()
    with btn3:
        total_pages = sum(s.get("estimated_pages", 2) for s in updated_outline)
        st.metric("Est. Pages", total_pages)

    # Save updated outline back
    st.session_state["_md_outline"] = updated_outline

    # Approve Outline → start drafting
    st.divider()
    if st.button(
        "\u2705 Approve Outline & Begin Drafting",
        key="_md_approve_outline", type="primary",
    ):
        st.session_state["_md_outline"] = updated_outline
        st.session_state["_md_drafted_sections"] = []
        st.session_state["_md_citation_library"] = []
        st.session_state["_md_phase"] = "drafting"
        _auto_save_draft(case_id, case_mgr, doc_type, doc_subtype)
        st.rerun()


# ---- Phase 2: Drafting --------------------------------------------------

def _render_drafting_phase(case_id, case_mgr, results, model_provider,
                            doc_type, doc_subtype):
    outline = st.session_state.get("_md_outline", [])
    drafted = st.session_state.get("_md_drafted_sections", [])
    citation_library = st.session_state.get("_md_citation_library", [])

    st.markdown(f"### {st.session_state.get('_md_doc_title', 'DOCUMENT')}")

    # Draft Quality Score badge
    _show_quality_badge(doc_type, doc_subtype)

    # Progress
    total = len(outline)
    done = len(drafted)
    if total > 0:
        st.progress(done / total, text=f"Drafted {done} of {total} sections")

    # Citation Library panel
    with st.expander(
        f"\U0001f4da Citation Library ({len(citation_library)} citations)",
        expanded=False,
    ):
        _render_citation_library(
            case_id, case_mgr, results, model_provider, citation_library,
        )

    # Section queue
    for i, sec in enumerate(outline):
        sec_num = sec.get("section_num", "")
        sec_title = sec.get("title", "")

        existing = next(
            (d for d in drafted if d.get("section_num") == sec_num), None,
        )

        if existing:
            _render_drafted_section(
                i, sec_num, sec_title, existing, drafted,
                case_id, case_mgr, doc_type, doc_subtype,
            )
        else:
            _render_undrafted_section(
                i, sec, sec_num, sec_title, done, outline, drafted,
                citation_library, results, model_provider, doc_type,
                case_id, case_mgr, doc_subtype,
            )

    # Draft All Remaining
    undrafted = [
        s for s in outline
        if not any(d.get("section_num") == s.get("section_num") for d in drafted)
    ]
    if undrafted and len(undrafted) > 1:
        st.divider()
        if st.button(
            f"\U0001f680 Draft All Remaining ({len(undrafted)} sections)",
            key="_md_draft_all", type="primary",
        ):
            _draft_all_remaining(
                undrafted, outline, drafted, citation_library,
                results, model_provider, doc_type,
                case_id, case_mgr, doc_subtype,
            )

    # All done?
    if done == total and total > 0:
        st.divider()
        st.success("\U0001f389 All sections drafted!")
        if st.button(
            "\U0001f4cb Review & Assemble Document",
            key="_md_to_assembly", type="primary",
        ):
            st.session_state["_md_phase"] = "assembly"
            st.rerun()

    # Back to outline
    if st.button("\u2190 Back to Outline", key="_md_back_to_outline"):
        st.session_state["_md_phase"] = "outline"
        st.rerun()


def _render_drafted_section(idx, sec_num, sec_title, existing, drafted,
                             case_id, case_mgr, doc_type, doc_subtype):
    """Show an already-drafted section with edit/regenerate controls."""
    with st.expander(f"\u2705 {sec_num}. {sec_title}", expanded=False):
        content = existing.get("content", "")
        st.markdown(content[:3000])
        if len(content) > 3000:
            st.caption(f"... ({len(content)} chars total)")

        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("\U0001f504 Regenerate", key=f"_md_regen_{idx}"):
                st.session_state["_md_drafted_sections"] = [
                    d for d in drafted if d.get("section_num") != sec_num
                ]
                st.rerun()
        with rc2:
            if st.button("\u270f\ufe0f Edit", key=f"_md_edit_sec_{idx}"):
                st.session_state[f"_md_editing_{idx}"] = True
                st.rerun()

        if st.session_state.get(f"_md_editing_{idx}"):
            edited = st.text_area(
                "Edit section content",
                value=content, height=400,
                key=f"_md_edit_content_{idx}",
            )
            if st.button("\U0001f4be Save Edit", key=f"_md_save_edit_{idx}"):
                existing["content"] = edited
                st.session_state.pop(f"_md_editing_{idx}", None)
                _auto_save_draft(case_id, case_mgr, doc_type, doc_subtype)
                st.rerun()


def _render_undrafted_section(idx, sec, sec_num, sec_title, done_count,
                               outline, drafted, citation_library,
                               results, model_provider, doc_type,
                               case_id, case_mgr, doc_subtype):
    """Show an undrafted section with draft button."""
    with st.expander(f"\u2b1c {sec_num}. {sec_title}", expanded=(idx == done_count)):
        st.caption(sec.get("description", ""))

        specific_instr = st.text_input(
            "Additional instructions for this section",
            key=f"_md_spec_instr_{idx}",
            placeholder="Optional: specific emphasis, arguments, evidence to include...",
        )

        if st.button(
            f"\U0001f4dd Draft Section {sec_num}",
            key=f"_md_draft_{idx}", type="primary",
        ):
            from core.nodes.major_docs import draft_document_section

            state = dict(results) if results else {}
            state["current_model"] = model_provider

            result = _run_streaming(
                draft_document_section,
                args=(state, sec, outline, drafted, citation_library, doc_type),
                kwargs={
                    "tone": st.session_state.get("_md_tone", "Formal/Persuasive"),
                    "specific_instructions": specific_instr,
                },
                label=f"Drafting Section {sec_num}: {sec_title}...",
            )

            if result and "error" not in result:
                new_section = {
                    "section_num": sec_num,
                    "title": sec_title,
                    "content": result.get("content", ""),
                    "citations_used": result.get("citations_used", []),
                    "status": "drafted",
                }
                drafted.append(new_section)
                st.session_state["_md_drafted_sections"] = drafted
                _auto_save_draft(case_id, case_mgr, doc_type, doc_subtype)
                st.rerun()
            elif result and "error" in result:
                st.error(result["error"])


def _draft_all_remaining(undrafted, outline, drafted, citation_library,
                          results, model_provider, doc_type,
                          case_id, case_mgr, doc_subtype):
    """Batch-draft all remaining sections with streaming output."""
    from core.nodes.major_docs import draft_document_section

    progress_bar = st.progress(0, text="Starting batch drafting...")

    for idx, sec in enumerate(undrafted):
        sec_num = sec.get("section_num", "")
        sec_title = sec.get("title", "")
        progress_bar.progress(
            idx / len(undrafted),
            text=f"Drafting {sec_num}: {sec_title} ({idx + 1}/{len(undrafted)})...",
        )

        state = dict(results) if results else {}
        state["current_model"] = model_provider

        result = _run_streaming(
            draft_document_section,
            args=(state, sec, outline, drafted, citation_library, doc_type),
            kwargs={"tone": st.session_state.get("_md_tone", "Formal/Persuasive")},
            label=f"Drafting Section {sec_num}: {sec_title}...",
        )

        if result and "error" not in result:
            new_section = {
                "section_num": sec_num,
                "title": sec_title,
                "content": result.get("content", ""),
                "citations_used": result.get("citations_used", []),
                "status": "drafted",
            }
            drafted.append(new_section)
            st.session_state["_md_drafted_sections"] = drafted
            _auto_save_draft(case_id, case_mgr, doc_type, doc_subtype)
        elif result and "error" in result:
            st.error(f"Failed to draft section {sec_num}: {result['error']}")
            break
        else:
            st.error(f"Failed to draft section {sec_num}")
            break

    progress_bar.progress(1.0, text="All sections drafted!")
    st.rerun()


# ---- Citation Library ----------------------------------------------------

def _render_citation_library(case_id, case_mgr, results, model_provider,
                              citation_library):
    # Build from case materials
    if st.button("\U0001f50d Build from Case Materials", key="_md_build_citations"):
        from core.nodes.major_docs import build_citation_library

        state = dict(results) if results else {}
        state["current_model"] = model_provider

        new_citations = _run_streaming(
            build_citation_library,
            args=(state, citation_library),
            label="Extracting citations from case materials...",
        )

        if new_citations is not None:
            st.session_state["_md_citation_library"] = new_citations
            st.rerun()

    # Display existing citations
    for ci, cite in enumerate(citation_library):
        with st.container(border=True):
            st.markdown(
                f"**{cite.get('case_name', '')}** {cite.get('citation', '')}",
            )
            st.caption(cite.get("holding", ""))
            if cite.get("relevance"):
                st.caption(f"_Relevance: {cite.get('relevance')}_")
            if st.button("\U0001f5d1\ufe0f", key=f"_md_del_cite_{ci}", help="Remove"):
                citation_library.pop(ci)
                st.session_state["_md_citation_library"] = citation_library
                st.rerun()

    # Manual add
    st.markdown("**Add Citation Manually**")
    mc1, mc2 = st.columns(2)
    with mc1:
        _cite_name = st.text_input(
            "Case Name", key="_md_new_cite_name",
            placeholder="Miranda v. Arizona",
        )
        _cite_citation = st.text_input(
            "Citation", key="_md_new_cite_cit",
            placeholder="384 U.S. 436 (1966)",
        )
    with mc2:
        _cite_holding = st.text_input(
            "Holding", key="_md_new_cite_hold",
            placeholder="One-sentence holding...",
        )
        _cite_relevance = st.text_input(
            "Relevance", key="_md_new_cite_rel",
            placeholder="How it relates to this case...",
        )

    if st.button("\u2795 Add Citation", key="_md_add_cite", disabled=not _cite_name):
        citation_library.append({
            "case_name": _cite_name,
            "citation": _cite_citation,
            "holding": _cite_holding,
            "relevance": _cite_relevance,
            "source": "manual",
        })
        st.session_state["_md_citation_library"] = citation_library
        st.rerun()

    # Auto-fetch case PDFs
    if citation_library:
        st.divider()
        st.markdown("**\U0001f4e5 Auto-Save Case PDFs**")
        st.caption("Fetch and save PDF copies of cited cases into the case library.")

        if st.button("\U0001f4e5 Fetch & Save Case PDFs", key="_md_fetch_pdfs"):
            from core.nodes.major_docs import fetch_case_pdfs

            with st.spinner("Searching for case PDFs online..."):
                result = fetch_case_pdfs(citation_library, case_id, case_mgr)

            saved = result.get("saved", [])
            not_found = result.get("not_found", [])
            errors = result.get("errors", [])

            if saved:
                for s in saved:
                    st.success(
                        f"\u2705 {s['case_name']} \u2014 saved as {s['filename']} "
                        f"({s.get('source', 'web')})"
                    )
            if not_found:
                for nf in not_found:
                    st.warning(f"\u26a0\ufe0f {nf} \u2014 not found online")
            if errors:
                for err in errors:
                    st.error(f"\u274c {err}")

            st.info(
                f"Summary: Saved {len(saved)} of {len(citation_library)} cited cases "
                f"to Case Library"
            )


# ---- Phase 3: Assembly --------------------------------------------------

def _render_assembly_phase(case_id, case_mgr, results, model_provider):
    outline = st.session_state.get("_md_outline", [])
    drafted = st.session_state.get("_md_drafted_sections", [])
    doc_title = st.session_state.get("_md_doc_title", "DOCUMENT")

    st.markdown(f"### {doc_title}")
    st.caption("Review the assembled document. Click any section to edit.")

    # Draft Quality Score badge
    _show_quality_badge(
        st.session_state.get("_md_doc_type", ""),
        st.session_state.get("_md_doc_subtype",
                              st.session_state.get("_md_custom_type", "")),
    )

    # Check for placeholders
    all_content = " ".join(d.get("content", "") for d in drafted)
    placeholders = re.findall(r'\[([A-Z][A-Z\s]+)\]', all_content)
    if placeholders:
        unique_ph = list(set(placeholders))
        st.warning(
            f"\u26a0\ufe0f {len(unique_ph)} placeholder(s) found: "
            + ", ".join(f"[{p}]" for p in unique_ph[:10])
        )

    # Order sections by outline order
    sec_order = {s.get("section_num"): i for i, s in enumerate(outline)}
    ordered = sorted(drafted, key=lambda d: sec_order.get(d.get("section_num"), 99))

    for sec in ordered:
        sec_num = sec.get("section_num", "")
        sec_title = sec.get("title", "")
        with st.expander(f"{sec_num}. {sec_title}", expanded=True):
            st.markdown(sec.get("content", ""))

            if st.button(
                "\U0001f504 Regenerate", key=f"_md_asm_regen_{sec_num}",
            ):
                st.session_state["_md_drafted_sections"] = [
                    d for d in drafted if d.get("section_num") != sec_num
                ]
                st.session_state["_md_phase"] = "drafting"
                st.rerun()

    # Export to Word
    st.divider()
    st.markdown("### \U0001f4e5 Export")

    if st.button("\U0001f4c4 Export to Word", key="_md_export_word", type="primary"):
        with st.spinner("Generating Word document..."):
            try:
                from core.export.court_docs import generate_major_document_word

                draft_data = _build_draft_data(
                    st.session_state.get("_md_doc_type", ""),
                    st.session_state.get(
                        "_md_doc_subtype",
                        st.session_state.get("_md_custom_type", ""),
                    ),
                )

                attorney_info = {
                    "name": st.session_state.get("_md_atty_name", ""),
                    "bar_number": st.session_state.get("_md_atty_bar", ""),
                    "firm": st.session_state.get("_md_atty_firm", ""),
                    "address": st.session_state.get("_md_atty_address", ""),
                    "phone": st.session_state.get("_md_atty_phone", ""),
                    "email": st.session_state.get("_md_atty_email", ""),
                }
                case_info = {
                    "plaintiff": st.session_state.get("_md_plaintiff", ""),
                    "defendant": st.session_state.get("_md_defendant", ""),
                    "case_number": st.session_state.get("_md_case_number", ""),
                    "court_name": st.session_state.get("_md_court_name", ""),
                    "case_type": results.get("case_type", "civil"),
                }

                doc_buffer = generate_major_document_word(
                    draft_data,
                    jurisdiction=st.session_state.get("_md_jurisdiction", "tennessee_state"),
                    attorney_info=attorney_info,
                    case_info=case_info,
                )

                safe_title = doc_title.replace(" ", "_")[:40]
                st.download_button(
                    "\u2b07\ufe0f Download .docx",
                    data=doc_buffer.getvalue(),
                    file_name=f"{safe_title}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="_md_download_docx",
                )
            except Exception as e:
                st.error(f"Export failed: {e}")
                logger.exception("Major doc export failed")

    # ---- AI Review ----
    st.divider()
    st.markdown("### \U0001f50d AI Brief Review")
    _render_review_section(case_id, case_mgr, results, model_provider, drafted, outline)

    # ---- Citation Verification ----
    st.divider()
    st.markdown("### \U0001f52c Cross-Model Citation Verification")
    _render_citation_verification(
        case_id, case_mgr, results, model_provider, drafted,
        st.session_state.get("_md_citation_library", []),
    )

    # ---- Filing Package ----
    st.divider()
    st.markdown("### \U0001f4e6 Filing Package Builder")
    _render_filing_package(case_id, case_mgr, results, doc_title)

    # Back to drafting
    st.divider()
    if st.button("\u2190 Back to Drafting", key="_md_back_to_drafting"):
        st.session_state["_md_phase"] = "drafting"
        st.rerun()


# ---- Assembly Sub-Sections -----------------------------------------------

def _render_review_section(case_id, case_mgr, results, model_provider,
                            drafted, outline):
    """AI review of the assembled brief."""
    review = st.session_state.get("_md_review_results")

    if st.button("\U0001f50d Review Brief", key="_md_review_brief", type="primary"):
        from core.nodes.major_docs import review_brief

        state = dict(results) if results else {}
        state["current_model"] = model_provider
        citation_library = st.session_state.get("_md_citation_library", [])

        result = _run_streaming(
            review_brief,
            args=(state, drafted, outline, citation_library,
                  st.session_state.get("_md_doc_type", "Brief")),
            label="Reviewing brief...",
        )

        if result and "error" not in result:
            st.session_state["_md_review_results"] = result
            review = result
            st.rerun()
        elif result and "error" in result:
            st.error(result["error"])

    if review:
        score = review.get("overall_score", 0)
        grade = review.get("grade", "?")
        from core.draft_quality import quality_color
        color = quality_color(score)

        st.markdown(
            f"**Review Score:** "
            f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>"
            f"{score}% ({grade})</span>",
            unsafe_allow_html=True,
        )

        # Issues grouped by severity
        issues = review.get("issues", [])
        if issues:
            high = [i for i in issues if i.get("severity") == "high"]
            medium = [i for i in issues if i.get("severity") == "medium"]
            low = [i for i in issues if i.get("severity") == "low"]

            if high:
                st.markdown("**\U0001f534 High Priority Issues**")
                for iss in high:
                    st.warning(
                        f"**[{iss.get('category', '')}] Section {iss.get('section', '?')}**: "
                        f"{iss.get('description', '')}\n\n"
                        f"**Fix:** {iss.get('fix', '')}"
                    )
            if medium:
                st.markdown("**\U0001f7e1 Medium Priority Issues**")
                for iss in medium:
                    st.info(
                        f"**[{iss.get('category', '')}] Section {iss.get('section', '?')}**: "
                        f"{iss.get('description', '')}\n\n"
                        f"**Fix:** {iss.get('fix', '')}"
                    )
            if low:
                with st.expander(f"\U0001f7e2 Low Priority Issues ({len(low)})"):
                    for iss in low:
                        st.caption(
                            f"[{iss.get('category', '')}] Section {iss.get('section', '?')}: "
                            f"{iss.get('description', '')} — Fix: {iss.get('fix', '')}"
                        )

        # Strengths
        strengths = review.get("strengths", [])
        if strengths:
            with st.expander(f"\u2705 Strengths ({len(strengths)})"):
                for s in strengths:
                    st.caption(f"\u2022 {s}")

        # Suggestions
        suggestions = review.get("suggestions", [])
        if suggestions:
            with st.expander(f"\U0001f4a1 Suggestions ({len(suggestions)})"):
                for s in suggestions:
                    st.caption(f"\u2022 {s}")


def _render_citation_verification(case_id, case_mgr, results, model_provider,
                                    drafted, citation_library):
    """Cross-model citation verification UI."""
    # Model selector — must differ from drafting model
    drafting_model = model_provider or "xai"
    all_models = ["gemini", "anthropic", "xai", "claude-opus-4.6"]
    available = [m for m in all_models if m != drafting_model]

    v_model = st.selectbox(
        "Verification Model (different from drafting model)",
        available, key="_md_verify_model",
    )

    verification = st.session_state.get("_md_verification_results")

    if st.button("\U0001f52c Verify Citations", key="_md_verify_cites", type="primary"):
        from core.nodes.major_docs import verify_citations_cross_model

        state = dict(results) if results else {}
        state["current_model"] = model_provider

        result = _run_streaming(
            verify_citations_cross_model,
            args=(state, drafted, citation_library),
            kwargs={"verification_model": v_model},
            label=f"Verifying citations with {v_model}...",
        )

        if result and "error" not in result:
            st.session_state["_md_verification_results"] = result
            verification = result
            st.rerun()
        elif result and "error" in result:
            st.error(result["error"])

    if verification:
        st.info(f"\U0001f4ca {verification.get('summary', '')}")

        verified = verification.get("verified", [])
        flagged = verification.get("flagged", [])

        if verified:
            with st.expander(f"\u2705 Verified ({len(verified)})"):
                for v in verified:
                    conf = v.get("confidence", 0)
                    st.caption(
                        f"\u2705 **{v.get('case_name', '')}** {v.get('citation', '')} "
                        f"— {conf}% confidence"
                    )
                    if v.get("notes"):
                        st.caption(f"   _Note: {v.get('notes')}_")

        if flagged:
            st.markdown("**\u26a0\ufe0f Flagged for Review**")
            for f in flagged:
                conf = f.get("confidence", 0)
                problems = []
                if not f.get("exists", True):
                    problems.append("may not exist")
                if not f.get("citation_correct", True):
                    problems.append("citation format issue")
                if not f.get("holding_accurate", True):
                    problems.append("holding may be inaccurate")
                if not f.get("still_good_law", True):
                    problems.append("may be overruled")

                icon = "\u274c" if conf < 50 else "\u26a0\ufe0f"
                st.warning(
                    f"{icon} **{f.get('case_name', '')}** {f.get('citation', '')} "
                    f"({conf}% confidence)\n\n"
                    f"Issues: {', '.join(problems)}\n\n"
                    f"Notes: {f.get('notes', '')}"
                )


def _render_filing_package(case_id, case_mgr, results, doc_title):
    """Build PDF filing package with exhibits."""
    import os

    # Get case PDF files
    all_files = case_mgr.get_case_files(case_id)
    pdf_files = [f for f in all_files if f.lower().endswith(".pdf")]

    if not pdf_files:
        st.caption("No PDF files in case library for exhibit packaging.")
        return

    st.caption("Select PDF exhibits to include in the filing package.")

    # Exhibit selection
    selected = []
    exhibit_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for i, pdf_path in enumerate(pdf_files):
        basename = os.path.basename(pdf_path)
        letter = exhibit_letters[i] if i < 26 else str(i + 1)
        checked = st.checkbox(
            f"Exhibit {letter}: {basename}",
            key=f"_md_exhibit_{i}",
        )
        if checked:
            selected.append({"letter": letter, "path": pdf_path, "name": basename})

    if not selected:
        return

    if st.button(
        f"\U0001f4e6 Build Filing Package ({len(selected)} exhibits)",
        key="_md_build_package", type="primary",
    ):
        with st.spinner("Building filing package..."):
            try:
                pkg_buffer = _build_filing_package_pdf(
                    doc_title, selected,
                    case_number=st.session_state.get("_md_case_number", ""),
                    court_name=st.session_state.get("_md_court_name", ""),
                )
                safe_title = doc_title.replace(" ", "_")[:30]
                st.download_button(
                    "\u2b07\ufe0f Download Filing Package (PDF)",
                    data=pkg_buffer.getvalue(),
                    file_name=f"{safe_title}_EXHIBIT_PACKAGE.pdf",
                    mime="application/pdf",
                    key="_md_download_pkg",
                )
            except Exception as e:
                st.error(f"Filing package build failed: {e}")
                logger.exception("Filing package build failed")


def _build_filing_package_pdf(doc_title, exhibits, case_number="", court_name=""):
    """Build a merged PDF with cover page, exhibit tabs, and exhibit PDFs."""
    import io
    from fpdf import FPDF
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()

    # 1. Generate cover page + exhibit separator pages with fpdf2
    separator_pdf = FPDF()
    separator_pdf.set_auto_page_break(auto=False)

    # Cover page
    separator_pdf.add_page()
    separator_pdf.set_font("Times", "B", 18)
    separator_pdf.cell(0, 40, "", ln=1)
    separator_pdf.cell(0, 12, "EXHIBIT PACKAGE", ln=1, align="C")
    separator_pdf.ln(10)
    separator_pdf.set_font("Times", "", 14)
    if court_name:
        separator_pdf.cell(0, 10, court_name, ln=1, align="C")
    if case_number:
        separator_pdf.cell(0, 10, f"Case No. {case_number}", ln=1, align="C")
    separator_pdf.ln(10)
    separator_pdf.set_font("Times", "B", 14)
    separator_pdf.cell(0, 10, doc_title, ln=1, align="C")
    separator_pdf.ln(20)
    separator_pdf.set_font("Times", "", 12)
    separator_pdf.cell(0, 10, "TABLE OF EXHIBITS", ln=1, align="C")
    separator_pdf.ln(5)
    for ex in exhibits:
        separator_pdf.cell(0, 8, f"  Exhibit {ex['letter']}: {ex['name']}", ln=1, align="L")

    # Exhibit separator pages
    for ex in exhibits:
        separator_pdf.add_page()
        separator_pdf.set_font("Times", "B", 36)
        separator_pdf.cell(0, 80, "", ln=1)
        separator_pdf.cell(0, 20, f"EXHIBIT {ex['letter']}", ln=1, align="C")
        separator_pdf.ln(10)
        separator_pdf.set_font("Times", "", 14)
        separator_pdf.cell(0, 10, ex["name"], ln=1, align="C")

    # Convert fpdf output to pypdf-readable pages
    sep_bytes = separator_pdf.output()
    sep_reader = PdfReader(io.BytesIO(sep_bytes))

    # Add cover page (page 0)
    writer.add_page(sep_reader.pages[0])

    # Add each exhibit: separator page + actual PDF pages
    for i, ex in enumerate(exhibits):
        # Separator page (i+1 because page 0 is cover)
        writer.add_page(sep_reader.pages[i + 1])

        # Actual exhibit PDF
        try:
            exhibit_reader = PdfReader(ex["path"])
            for page in exhibit_reader.pages:
                writer.add_page(page)
        except Exception as e:
            logger.warning("Could not read exhibit PDF %s: %s", ex["name"], e)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


# ---- Opponent Analysis Tab -----------------------------------------------

def _render_opponent_analysis(case_id, case_mgr, results, model_provider):
    """Tab for uploading and analyzing opposing counsel's brief."""
    st.markdown("## \u2694\ufe0f Opposing Counsel Brief Analyzer")
    st.caption("Upload the opposing party's brief to extract arguments and generate counter-strategies.")

    uploaded = st.file_uploader(
        "Upload Opposing Brief",
        type=["pdf", "docx", "txt"],
        key="_md_opponent_upload",
    )

    if uploaded:
        # Extract text
        text = _extract_document_text(uploaded, uploaded.name)
        st.info(f"Extracted {len(text):,} characters from {uploaded.name}")

        with st.expander("Preview Extracted Text", expanded=False):
            st.text(text[:3000])
            if len(text) > 3000:
                st.caption(f"... ({len(text):,} total characters)")

        if st.button("\U0001f50d Analyze Opposing Brief", key="_md_analyze_opponent", type="primary"):
            from core.nodes.major_docs import analyze_opposing_brief

            state = dict(results) if results else {}
            state["current_model"] = model_provider
            citation_library = st.session_state.get("_md_citation_library", [])

            result = _run_streaming(
                analyze_opposing_brief,
                args=(state, text, citation_library),
                label="Analyzing opposing brief...",
            )

            if result and "error" not in result:
                st.session_state["_md_opponent_analysis"] = result
                st.rerun()
            elif result and "error" in result:
                st.error(result["error"])

    # Display results
    analysis = st.session_state.get("_md_opponent_analysis")
    if not analysis:
        return

    st.divider()

    # Two-column: Their arguments | Our counters
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### \U0001f534 Their Arguments")
        for arg in analysis.get("opponent_arguments", []):
            strength = arg.get("strength", "moderate")
            icon = {
                "strong": "\U0001f534", "moderate": "\U0001f7e1", "weak": "\U0001f7e2"
            }.get(strength, "\u26aa")
            with st.container(border=True):
                st.markdown(f"{icon} **Argument {arg.get('number', '?')}** ({strength})")
                st.caption(arg.get("argument", ""))
                if arg.get("section_ref"):
                    st.caption(f"_Ref: {arg.get('section_ref')}_")

    with col2:
        st.markdown("### \U0001f7e2 Our Counter-Arguments")
        for counter in analysis.get("counter_arguments", []):
            with st.container(border=True):
                st.markdown(f"**Re: Argument {counter.get('opposing_arg_number', '?')}**")
                st.caption(counter.get("counter", ""))
                if counter.get("supporting_evidence"):
                    st.caption(f"_Evidence: {counter.get('supporting_evidence')}_")
                if counter.get("supporting_law"):
                    st.caption(f"_Law: {counter.get('supporting_law')}_")

    # Opponent citations
    opp_cites = analysis.get("opponent_citations", [])
    if opp_cites:
        with st.expander(f"\U0001f4da Opponent's Citations ({len(opp_cites)})"):
            for oc in opp_cites:
                st.caption(
                    f"\u2022 **{oc.get('case_name', '')}** {oc.get('citation', '')} "
                    f"— {oc.get('purpose', '')}"
                )
            if st.button("\U0001f4e5 Import to Citation Library (for reference)",
                          key="_md_import_opp_cites"):
                existing = st.session_state.get("_md_citation_library", [])
                existing_names = {c.get("case_name", "").lower() for c in existing}
                added = 0
                for oc in opp_cites:
                    if oc.get("case_name", "").lower() not in existing_names:
                        existing.append({
                            "case_name": oc.get("case_name", ""),
                            "citation": oc.get("citation", ""),
                            "holding": oc.get("purpose", ""),
                            "relevance": "Cited by opposing counsel",
                            "source": "opponent_brief",
                        })
                        added += 1
                st.session_state["_md_citation_library"] = existing
                st.toast(f"Added {added} citations from opponent's brief")

    # Weaknesses
    weaknesses = analysis.get("weaknesses", [])
    if weaknesses:
        with st.expander(f"\U0001f4a5 Weaknesses in Their Position ({len(weaknesses)})"):
            for w in weaknesses:
                st.caption(f"\u2022 {w}")

    # Response strategy
    strategy = analysis.get("response_strategy", "")
    if strategy:
        with st.expander("\U0001f9e0 Recommended Response Strategy"):
            st.markdown(strategy)


def _extract_document_text(file_obj, filename):
    """Extract text from PDF, DOCX, or TXT file."""
    if filename.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_obj)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            return f"[PDF extraction error: {e}]"
    elif filename.lower().endswith(".docx"):
        try:
            from docx import Document
            doc = Document(file_obj)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            return f"[DOCX extraction error: {e}]"
    else:
        try:
            return file_obj.read().decode("utf-8", errors="replace")
        except Exception:
            return file_obj.read() if isinstance(file_obj.read(), str) else ""


# ---- Tab 3: Saved Drafts ------------------------------------------------

def _render_saved_drafts(case_id, case_mgr):
    drafts = case_mgr.load_major_drafts(case_id)

    if not drafts:
        st.info("No saved drafts yet. Start drafting in the Workspace tab.")
        return

    st.caption(f"{len(drafts)} saved draft(s)")

    for d in drafts:
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            with c1:
                st.markdown(f"**{d.get('title', 'Untitled')}**")
                st.caption(
                    f"{d.get('doc_type', '')} \u2022 {d.get('doc_subtype', '')} \u2022 "
                    f"{d.get('status', 'draft')} \u2022 "
                    f"Updated: {d.get('updated_at', '')[:16]}"
                )
                sec_count = d.get("section_count", 0)
                total_count = d.get("total_sections", 0)
                if total_count:
                    st.caption(f"Sections: {sec_count}/{total_count} drafted")
            with c2:
                if st.button("\U0001f4c2 Load", key=f"_md_load_{d.get('id', '')}"):
                    _load_draft(case_id, case_mgr, d.get("id", ""))
                    st.rerun()
            with c3:
                if st.button("\U0001f5d1\ufe0f", key=f"_md_del_draft_{d.get('id', '')}"):
                    st.session_state[f"_md_confirm_del_{d.get('id', '')}"] = True
                    st.rerun()

            if st.session_state.get(f"_md_confirm_del_{d.get('id', '')}"):
                st.warning("Are you sure? This cannot be undone.")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("Yes, delete", key=f"_md_yes_{d.get('id', '')}"):
                        case_mgr.delete_major_draft(case_id, d.get("id", ""))
                        st.session_state.pop(f"_md_confirm_del_{d.get('id', '')}", None)
                        st.rerun()
                with dc2:
                    if st.button("Cancel", key=f"_md_no_{d.get('id', '')}"):
                        st.session_state.pop(f"_md_confirm_del_{d.get('id', '')}", None)
                        st.rerun()


# ---- Tab 3: Settings ----------------------------------------------------

def _render_settings(case_id, case_mgr):
    prefs = {}
    try:
        prefs = case_mgr.storage.load_json(case_id, "attorney_prefs.json") or {}
    except Exception:
        pass

    st.markdown("### Default Attorney Information")
    st.caption("These defaults are used when creating new documents.")

    a1, a2 = st.columns(2)
    with a1:
        atty_name = st.text_input(
            "Attorney Name", value=prefs.get("attorney_name", ""), key="_md_set_name",
        )
        bar_num = st.text_input(
            "Bar Number", value=prefs.get("bar_number", ""), key="_md_set_bar",
        )
        firm = st.text_input(
            "Firm Name", value=prefs.get("firm", ""), key="_md_set_firm",
        )
    with a2:
        address = st.text_area(
            "Address", value=prefs.get("address", ""), key="_md_set_addr", height=68,
        )
        phone = st.text_input(
            "Phone", value=prefs.get("phone", ""), key="_md_set_phone",
        )
        email = st.text_input(
            "Email", value=prefs.get("email", ""), key="_md_set_email",
        )

    st.markdown("### Default Jurisdiction")
    default_jur = "tennessee_state"
    try:
        from core.export.court_docs import get_jurisdiction_list
        jur_list = get_jurisdiction_list()
        jur_keys = [j[0] for j in jur_list]
        jur_labels = {j[0]: j[1] for j in jur_list}
        cur_jur = prefs.get("jurisdiction", "tennessee_state")
        jur_idx = jur_keys.index(cur_jur) if cur_jur in jur_keys else 0
        default_jur = st.selectbox(
            "Jurisdiction", jur_keys, index=jur_idx,
            format_func=lambda x: jur_labels.get(x, x),
            key="_md_set_jur",
        )
    except Exception:
        pass

    court_name = st.text_input(
        "Default Court Name", value=prefs.get("court_name", ""), key="_md_set_court",
    )

    if st.button("\U0001f4be Save Settings", key="_md_save_settings", type="primary"):
        new_prefs = {
            "attorney_name": atty_name,
            "bar_number": bar_num,
            "firm": firm,
            "address": address,
            "phone": phone,
            "email": email,
            "jurisdiction": default_jur,
            "court_name": court_name,
            "plaintiff": prefs.get("plaintiff", ""),
            "defendant": prefs.get("defendant", ""),
            "case_number": prefs.get("case_number", ""),
        }
        try:
            case_mgr.storage.save_json(case_id, "attorney_prefs.json", new_prefs)
            st.success("\u2705 Settings saved!")
        except Exception as e:
            st.error(f"Failed to save settings: {e}")


# ---- Utility Functions ---------------------------------------------------

_ROMAN = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
]


def _next_roman(n):
    """Return the next Roman numeral for section numbering."""
    return _ROMAN[n] if n < len(_ROMAN) else str(n + 1)


def _build_draft_data(doc_type, doc_subtype):
    """Build a full draft dict from session state."""
    return {
        "id": st.session_state.get("_md_draft_id", str(uuid.uuid4())),
        "doc_type": doc_type,
        "doc_subtype": doc_subtype,
        "title": st.session_state.get("_md_doc_title", "DOCUMENT"),
        "outline": st.session_state.get("_md_outline", []),
        "sections": st.session_state.get("_md_drafted_sections", []),
        "citation_library": st.session_state.get("_md_citation_library", []),
        "status": (
            "complete"
            if st.session_state.get("_md_phase") == "assembly"
            else "in_progress"
        ),
        "tone": st.session_state.get("_md_tone", "Formal/Persuasive"),
        "target_length": st.session_state.get("_md_length", "Standard (~15-25 pages)"),
        "attorney_info": {
            "name": st.session_state.get("_md_atty_name", ""),
            "bar_number": st.session_state.get("_md_atty_bar", ""),
        },
        "review_results": st.session_state.get("_md_review_results"),
        "verification_results": st.session_state.get("_md_verification_results"),
    }


def _show_quality_badge(doc_type, doc_subtype):
    """Display the draft quality score badge as a compact metric."""
    try:
        from core.draft_quality import compute_draft_quality_score, quality_color

        draft_data = _build_draft_data(doc_type, doc_subtype)
        score, grade, breakdown = compute_draft_quality_score(draft_data)
        color = quality_color(score)

        q1, q2 = st.columns([1, 3])
        with q1:
            st.markdown(
                f"<div style='text-align:center; padding:4px 8px; "
                f"background:{color}22; border:1px solid {color}; border-radius:8px;'>"
                f"<span style='font-size:1.4em; font-weight:bold; color:{color};'>"
                f"{score}% ({grade})</span><br>"
                f"<span style='font-size:0.75em; color:#888;'>Draft Quality</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with q2:
            with st.expander("Quality Breakdown", expanded=False):
                for label, passed in breakdown.items():
                    icon = "\u2705" if passed else "\u274c"
                    st.caption(f"{icon} {label}")
    except Exception as e:
        logger.debug("Quality badge error: %s", e)


def _auto_save_draft(case_id, case_mgr, doc_type, doc_subtype):
    """Auto-save current draft state to disk."""
    try:
        draft_data = _build_draft_data(doc_type, doc_subtype)
        draft_id = case_mgr.save_major_draft(case_id, draft_data)
        st.session_state["_md_draft_id"] = draft_id
    except Exception as e:
        logger.warning("Auto-save failed: %s", e)


def _load_draft(case_id, case_mgr, draft_id):
    """Load a saved draft into session state."""
    draft = case_mgr.load_major_draft(case_id, draft_id)
    if not draft:
        st.error("Draft not found.")
        return

    st.session_state["_md_draft_id"] = draft.get("id", draft_id)
    st.session_state["_md_doc_title"] = draft.get("title", "DOCUMENT")
    st.session_state["_md_outline"] = draft.get("outline", [])
    st.session_state["_md_drafted_sections"] = draft.get("sections", [])
    st.session_state["_md_citation_library"] = draft.get("citation_library", [])

    # Determine phase from draft state
    if draft.get("status") == "complete":
        st.session_state["_md_phase"] = "assembly"
    elif draft.get("sections"):
        st.session_state["_md_phase"] = "drafting"
    else:
        st.session_state["_md_phase"] = "outline"

    if draft.get("doc_type"):
        st.session_state["_md_doc_type"] = draft["doc_type"]
    if draft.get("tone"):
        st.session_state["_md_tone"] = draft["tone"]
