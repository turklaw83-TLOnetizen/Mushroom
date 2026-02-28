"""Ethical Compliance UI module — ported from legacy ui_modules/ethical_compliance_ui.py."""
import logging
import os
import json
import streamlit as st
from datetime import datetime

from core import ethical_compliance

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, results, **ctx):
    """Render the Ethical Compliance UI based on active_tab."""
    active_tab = ctx.get("active_tab", "")
    # =====================================================================
    # =====================================================================

    # -- 1. Compliance Dashboard --
    if active_tab == "\U0001f4ca Dashboard":
        st.markdown("## \U0001f4ca Compliance Dashboard")
        st.caption("RPC 1.3 — Aggregate compliance overview across all cases")

        try:
            _dash = ethical_compliance.get_compliance_dashboard(case_mgr)

            # Score gauge
            _score = _dash.get("score", 100)
            _score_color = "\U0001f7e2" if _score >= 80 else "\U0001f7e1" if _score >= 50 else "\U0001f534"
            st.markdown(f"### {_score_color} Compliance Score: **{_score}/100**")
            st.progress(min(_score / 100.0, 1.0))

            _issues = _dash.get("total_issues", 0)
            if _issues == 0:
                st.success("\u2705 All compliance checks passed!")
            else:
                st.warning(f"\u26a0\ufe0f {_issues} issue(s) require attention")

            # Metrics row
            _d1, _d2, _d3, _d4 = st.columns(4)
            _d1.metric("\U0001f534 Overdue Deadlines", len(_dash.get("overdue_deadlines", [])))
            _d2.metric("\U0001f4de Communication Gaps", len(_dash.get("communication_gaps", [])))
            _d3.metric("\U0001f4b0 Missing Fee Agreements", len(_dash.get("missing_fee_agreements", [])))
            _d4.metric("\U0001f464 Prospective Clients", _dash.get("prospective_count", 0))

            # Overdue deadlines
            _overdue = _dash.get("overdue_deadlines", [])
            if _overdue:
                st.markdown("### \U0001f534 Overdue Deadlines")
                for _od in _overdue:
                    with st.expander(f"\U0001f534 {_od.get('urgency', '')} — {_od.get('description', 'No description')}", expanded=True):
                        st.markdown(f"**Case:** {_od.get('case_name', 'Unknown')}")
                        st.markdown(f"**Date:** {_od.get('date', 'N/A')}")
                        st.markdown(f"**Category:** {_od.get('category', 'N/A')}")

            # Upcoming deadlines
            _upcoming = _dash.get("upcoming_deadlines", [])
            if _upcoming:
                st.markdown("### \U0001f7e1 Upcoming Deadlines (Next 7 Days)")
                for _ud in _upcoming:
                    st.markdown(f"- {_ud.get('urgency', '')} — **{_ud.get('description', '')}** ({_ud.get('case_name', '')})")

            # Communication gaps
            _cg = _dash.get("communication_gaps", [])
            if _cg:
                st.markdown("### \U0001f4de Communication Gaps")
                for _gap in _cg[:5]:
                    st.markdown(f"- {_gap.get('urgency', '')} — **{_gap.get('case_name', '')}** (Last contact: {_gap.get('last_contact', 'Never')})")

            # Missing fee agreements
            _mf = _dash.get("missing_fee_agreements", [])
            if _mf:
                st.markdown("### \U0001f4b0 Cases Missing Fee Agreements")
                for _m in _mf:
                    _status_badge = "\U0001f4dd Draft" if _m.get("fee_status") == "draft" else "\u274c None"
                    st.markdown(f"- {_status_badge} — **{_m.get('case_name', '')}**")
        except Exception as e:
            st.error(f"Error loading compliance dashboard: {e}")

    # -- 2. Smart Conflicts --
    if active_tab == "\U0001f50d Smart Conflicts":
        st.markdown("## \U0001f50d Smart Conflict Check")
        st.caption("RPC 1.7 / 1.9 / 1.10 — Enhanced conflict detection with fuzzy matching, nicknames & prospective client screening")

        if st.button("\U0001f50d Run Smart Conflict Scan", key="btn_smart_conflict", type="primary"):
            with st.spinner("Scanning all cases for conflicts..."):
                try:
                    _all_ents = case_mgr.load_all_entities()
                    _prosp = ethical_compliance.load_prospective_clients()
                    _sc_result = ethical_compliance.scan_conflicts_smart(case_id, _all_ents, _prosp)

                    _conflicts = _sc_result.get("conflicts", [])
                    _prosp_hits = _sc_result.get("prospective_hits", [])
                    _msg = _sc_result.get("message", "")

                    if _msg:
                        st.info(_msg)

                    # Metrics
                    _m1, _m2, _m3 = st.columns(3)
                    _m1.metric("\u26a0\ufe0f Cross-Case Conflicts", len(_conflicts))
                    _m2.metric("\U0001f464 Prospective Client Hits", len(_prosp_hits))
                    _m3.metric("\U0001f4ca Cases Scanned", _sc_result.get("cases_scanned", 0))

                    if _conflicts:
                        st.markdown("### \U0001f6a9 Cross-Case Conflicts")
                        for _ci, _cf in enumerate(_conflicts):
                            _sev = _cf.get("severity", "")
                            with st.expander(f"{_sev}  **{_cf.get('name', '')}** \u2194 **{_cf.get('matched_name', '')}** — {_cf.get('other_case', '')}", expanded="HIGH" in _sev):
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.markdown("**Current Case Entity:**")
                                    st.markdown(f"- **Name:** {_cf.get('name', '')}")
                                    st.markdown(f"- **Role:** {_cf.get('current_role', '\u2014')}")
                                with c2:
                                    st.markdown("**Other Case Entity:**")
                                    st.markdown(f"- **Name:** {_cf.get('matched_name', '')}")
                                    st.markdown(f"- **Role:** {_cf.get('other_role', '\u2014')}")
                                    st.markdown(f"- **Case:** {_cf.get('other_case', '')}")
                                st.markdown(f"**Match Type:** `{_cf.get('match_type', '')}` — {_cf.get('explanation', '')}")
                                st.markdown(f"**Confidence:** {int(_cf.get('confidence', 0) * 100)}%")

                    if _prosp_hits:
                        st.markdown("### \U0001f464 Prospective Client Matches (RPC 1.18)")
                        for _ph in _prosp_hits:
                            with st.expander(f"{_ph.get('severity', '')}  **{_ph.get('name', '')}** \u2194 Prospective: **{_ph.get('matched_name', '')}**"):
                                st.markdown(f"**Subject:** {_ph.get('subject', 'N/A')}")
                                st.markdown(f"**Consultation Date:** {_ph.get('date', 'N/A')}")
                                st.markdown(f"**Match:** {_ph.get('explanation', '')}")
                                st.warning("\u26a0\ufe0f RPC 1.18: Information from prospective client consultations may create disqualifying conflicts.")

                    if not _conflicts and not _prosp_hits and not _msg:
                        st.success("\u2705 No conflicts found!")

                except Exception as e:
                    st.error(f"Error running smart conflict scan: {e}")

    # -- 3. Prospective Client Screening --
    if active_tab == "\U0001f464 Prospective Clients":
        st.markdown("## \U0001f464 Prospective Client Screening")
        st.caption("RPC 1.18 — Track consultations with prospective clients for conflict screening")

        # Add new prospective client
        with st.expander("\u2795 Add Prospective Client", expanded=False):
            with st.form("add_prospective_client", clear_on_submit=True):
                _pc_name = st.text_input("Name *", key="pc_name")
                _pc_subject = st.text_input("Subject Matter", key="pc_subject")
                _pc_info = st.text_area("Disclosed Information", key="pc_info", help="Brief summary of what was disclosed during consultation")
                _pc_date = st.date_input("Consultation Date", key="pc_date")
                _pc_notes = st.text_area("Notes", key="pc_notes")
                _pc_reason = st.text_input("Reason Declined (if applicable)", key="pc_reason")
                _pc_submit = st.form_submit_button("\U0001f4be Save Prospective Client", type="primary")

                if _pc_submit and _pc_name:
                    _new_id = ethical_compliance.save_prospective_client(
                        name=_pc_name, subject=_pc_subject,
                        disclosed_info=_pc_info,
                        consultation_date=str(_pc_date),
                        notes=_pc_notes, declined_reason=_pc_reason,
                    )
                    st.success(f"\u2705 Saved prospective client: {_pc_name} (ID: {_new_id})")
                    st.rerun()

        # List existing
        _pc_list = ethical_compliance.load_prospective_clients()
        if _pc_list:
            st.markdown(f"### \U0001f4cb Prospective Clients ({len(_pc_list)})")
            for _pc in sorted(_pc_list, key=lambda x: x.get("date", ""), reverse=True):
                with st.expander(f"\U0001f464 **{_pc.get('name', 'Unknown')}** — {_pc.get('subject', 'No subject')} ({_pc.get('date', '')})"):
                    st.markdown(f"**Name:** {_pc.get('name', '')}")
                    st.markdown(f"**Subject:** {_pc.get('subject', 'N/A')}")
                    st.markdown(f"**Date:** {_pc.get('date', 'N/A')}")
                    if _pc.get("disclosed_info"):
                        st.markdown(f"**Disclosed Info:** {_pc['disclosed_info']}")
                    if _pc.get("notes"):
                        st.markdown(f"**Notes:** {_pc['notes']}")
                    if _pc.get("declined_reason"):
                        st.markdown(f"**Declined Reason:** {_pc['declined_reason']}")
                    if st.button("\U0001f5d1\ufe0f Delete", key=f"del_pc_{_pc.get('id', '')}"):
                        ethical_compliance.delete_prospective_client(_pc["id"])
                        st.success("Deleted.")
                        st.rerun()
        else:
            st.info("No prospective clients recorded yet. Use the form above to add one.")

    # -- 4. Communication Gap Alerts --
    if active_tab == "\U0001f4de Communication Gaps":
        st.markdown("## \U0001f4de Communication Gap Alerts")
        st.caption("RPC 1.4 — Identifies cases where client communication may be overdue")

        _threshold = st.slider("Threshold (days since last contact)", 7, 90, 30, key="comm_threshold")

        if st.button("\U0001f50d Scan for Communication Gaps", key="btn_comm_gaps", type="primary"):
            with st.spinner("Scanning contact logs across all cases..."):
                try:
                    _gaps = ethical_compliance.get_communication_gaps(case_mgr, threshold_days=_threshold)
                    if _gaps:
                        st.warning(f"\u26a0\ufe0f Found {len(_gaps)} case(s) with communication gaps")
                        for _g in _gaps:
                            with st.expander(f"{_g.get('urgency', '')} — **{_g.get('case_name', '')}**", expanded="CRITICAL" in _g.get("urgency", "") or "No contact" in _g.get("urgency", "")):
                                st.markdown(f"**Case:** {_g.get('case_name', '')}")
                                st.markdown(f"**Status:** {_g.get('status', 'active')}")
                                _last = _g.get("last_contact")
                                st.markdown(f"**Last Contact:** {_last or 'Never'}")
                                _days = _g.get("days_since")
                                if _days:
                                    st.markdown(f"**Days Since:** {_days}")
                                st.info("\U0001f4a1 **RPC 1.4**: A lawyer shall keep the client reasonably informed and promptly comply with reasonable requests for information.")
                    else:
                        st.success(f"\u2705 All active cases have been contacted within the last {_threshold} days!")
                except Exception as e:
                    st.error(f"Error scanning communication gaps: {e}")

    # -- 5. Trust Account Ledger --
    if active_tab == "\U0001f3e6 Trust Account":
        st.markdown("## \U0001f3e6 IOLTA Trust Account Manager")
        st.caption("RPC 1.15 — Client trust account tracking, reconciliation, and compliance audit")

        # Current case balance header
        _balance = ethical_compliance.get_trust_balance(case_id)
        _bal_color = "\U0001f7e2" if _balance > 0 else "\U0001f534" if _balance < 0 else "\u26aa"
        st.markdown(f"### {_bal_color} Current Balance: **${_balance:,.2f}**")
        if _balance < 0:
            st.error("\u26a0\ufe0f **CRITICAL:** Negative trust balance violates RPC 1.15(a). Funds must be deposited immediately.")

        _ta_tab1, _ta_tab2, _ta_tab3 = st.tabs(["\U0001f4cb Ledger", "\U0001f4ca Reconciliation", "\U0001f6e1\ufe0f Compliance Audit"])

        with _ta_tab1:
            # Add entry
            with st.expander("\u2795 Add Trust Account Entry", expanded=False):
                with st.form("add_trust_entry", clear_on_submit=True):
                    _te_type = st.selectbox("Type", ["deposit", "disbursement"], key="te_type")
                    _te_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="te_amount")
                    _te_desc = st.text_input("Description", key="te_desc")
                    _te_date = st.date_input("Date", key="te_date")
                    _te_ref = st.text_input("Reference/Check #", key="te_ref")
                    _te_notified = st.checkbox("Client Notified", key="te_notified", help="RPC 1.15 requires prompt notification on receipt of funds")
                    _te_submit = st.form_submit_button("\U0001f4be Save Entry", type="primary")

                    if _te_submit:
                        ethical_compliance.add_trust_entry(
                            case_id=case_id, entry_type=_te_type, amount=_te_amount,
                            description=_te_desc, date_str=str(_te_date),
                            reference=_te_ref, client_notified=_te_notified,
                        )
                        st.success("\u2705 Trust entry saved!")
                        st.rerun()

            # Ledger entries
            _ledger = ethical_compliance.load_trust_ledger(case_id)
            if _ledger:
                st.markdown(f"### \U0001f4cb Ledger ({len(_ledger)} entries)")
                _running = 0.0
                for _le in sorted(_ledger, key=lambda x: x.get("date", "")):
                    _amt = float(_le.get("amount", 0))
                    if _le.get("type") == "deposit":
                        _running += _amt
                        _icon = "\U0001f7e2 +"
                    else:
                        _running -= _amt
                        _icon = "\U0001f534 -"
                    _notif = "\u2705" if _le.get("client_notified") else "\u26a0\ufe0f"
                    with st.expander(f"{_icon}${_amt:,.2f} — {_le.get('description', '')} ({_le.get('date', '')}) | Balance: ${_running:,.2f} | Notified: {_notif}"):
                        st.markdown(f"**Type:** {_le.get('type', '').title()}")
                        st.markdown(f"**Amount:** ${_amt:,.2f}")
                        st.markdown(f"**Description:** {_le.get('description', 'N/A')}")
                        st.markdown(f"**Date:** {_le.get('date', 'N/A')}")
                        st.markdown(f"**Reference:** {_le.get('reference', 'N/A')}")
                        st.markdown(f"**Client Notified:** {'Yes \u2705' if _le.get('client_notified') else 'No \u26a0\ufe0f'}")
                        if st.button("\U0001f5d1\ufe0f Delete Entry", key=f"del_te_{_le.get('id', '')}"):
                            ethical_compliance.delete_trust_entry(case_id, _le["id"])
                            st.success("Deleted.")
                            st.rerun()

                # Sub-ledger breakdown
                _sub = ethical_compliance.get_client_sub_ledger(case_id)
                if _sub and len(_sub) > 1:
                    st.markdown("### \U0001f4ca Balance by Transaction Type")
                    for _desc, _bal in sorted(_sub.items(), key=lambda x: abs(x[1]), reverse=True):
                        _sb_color = "\U0001f7e2" if _bal >= 0 else "\U0001f534"
                        st.markdown(f"- {_sb_color} **{_desc}**: ${_bal:,.2f}")
            else:
                st.info("No trust account entries for this case. Use the form above to add one.")

            # Firm-wide summary
            with st.expander("\U0001f4ca Firm-Wide Trust Summary"):
                try:
                    _summary = ethical_compliance.get_trust_summary(case_mgr)
                    if _summary:
                        for _s in _summary:
                            _b = _s.get("balance", 0)
                            _bc = "\U0001f7e2" if _b > 0 else "\U0001f534" if _b < 0 else "\u26aa"
                            _unnotif = _s.get("unnotified_deposits", 0)
                            _warn = f" | \u26a0\ufe0f {_unnotif} unnotified deposits" if _unnotif else ""
                            st.markdown(f"- {_bc} **{_s.get('case_name', '')}**: ${_b:,.2f} ({_s.get('entries', 0)} entries){_warn}")
                    else:
                        st.info("No trust account data across any cases.")
                except Exception as e:
                    st.error(f"Error loading trust summary: {e}")

        with _ta_tab2:
            st.markdown("### \U0001f4ca Monthly Three-Way Reconciliation")
            st.caption("RPC 1.15 requires monthly reconciliation of: Bank Statement \u2194 Book Balance \u2194 Client Ledger Total")

            with st.form("reconciliation_form", clear_on_submit=True):
                _rc_month = st.text_input("Month (YYYY-MM)", value=datetime.now().strftime("%Y-%m"), key="rc_month")
                _rc1, _rc2, _rc3 = st.columns(3)
                with _rc1:
                    _rc_bank = st.number_input("Bank Statement Balance ($)", min_value=0.0, step=0.01, key="rc_bank")
                with _rc2:
                    _rc_book = st.number_input("Book Balance ($)", value=float(_balance), step=0.01, key="rc_book")
                with _rc3:
                    _rc_client = st.number_input("Client Ledger Total ($)", min_value=0.0, step=0.01, key="rc_client")
                _rc_by = st.text_input("Reconciled By", key="rc_by")
                _rc_notes = st.text_area("Notes (outstanding checks, deposits in transit, etc.)", key="rc_notes")
                _rc_submit = st.form_submit_button("\U0001f4be Record Reconciliation", type="primary")

                if _rc_submit:
                    ethical_compliance.save_reconciliation(
                        case_id=case_id, bank_balance=_rc_bank,
                        book_balance=_rc_book, client_total=_rc_client,
                        reconciled_by=_rc_by, notes=_rc_notes, month=_rc_month,
                    )
                    st.success("\u2705 Reconciliation recorded!")
                    st.rerun()

            # Reconciliation history
            _recs = ethical_compliance.load_reconciliations(case_id)
            if _recs:
                st.markdown(f"### \U0001f4c5 Reconciliation History ({len(_recs)} records)")
                for _rc in sorted(_recs, key=lambda x: x.get("month", ""), reverse=True):
                    _rc_status_icon = "\u2705" if _rc.get("status") == "balanced" else "\u26a0\ufe0f"
                    with st.expander(f"{_rc_status_icon} **{_rc.get('month', 'N/A')}** — {_rc.get('status', '').title()} | Bank: ${_rc.get('bank_balance', 0):,.2f} | Book: ${_rc.get('book_balance', 0):,.2f}"):
                        _m1, _m2, _m3 = st.columns(3)
                        _m1.metric("Bank Balance", f"${_rc.get('bank_balance', 0):,.2f}")
                        _m2.metric("Book Balance", f"${_rc.get('book_balance', 0):,.2f}")
                        _m3.metric("Client Total", f"${_rc.get('client_total', 0):,.2f}")

                        _bb_diff = _rc.get("bank_book_diff", 0)
                        _bc_diff = _rc.get("book_client_diff", 0)
                        if _bb_diff != 0:
                            st.warning(f"Bank \u2194 Book Difference: **${_bb_diff:,.2f}**")
                        if _bc_diff != 0:
                            st.warning(f"Book \u2194 Client Difference: **${_bc_diff:,.2f}**")
                        if _bb_diff == 0 and _bc_diff == 0:
                            st.success("All three balances match — fully reconciled")

                        st.markdown(f"**Reconciled By:** {_rc.get('reconciled_by', 'N/A')}")
                        st.markdown(f"**Date:** {_rc.get('reconciled_at', 'N/A')[:10]}")
                        if _rc.get("notes"):
                            st.markdown(f"**Notes:** {_rc['notes']}")
            else:
                st.info("No reconciliation records yet. Complete the form above for this month.")

            st.info("\U0001f4a1 **RPC 1.15 Tip:** Reconcile at least monthly. Keep all records for 5 years minimum. Discrepancies must be investigated and resolved promptly.")

        with _ta_tab3:
            st.markdown("### \U0001f6e1\ufe0f RPC 1.15 Compliance Audit")
            st.caption("Automated scan for trust account compliance issues across all cases")

            if st.button("\U0001f50d Run Compliance Audit", key="btn_trust_audit", type="primary"):
                with st.spinner("Scanning all trust accounts for compliance issues..."):
                    try:
                        _audit = ethical_compliance.get_trust_compliance_audit(case_mgr)
                        _score = _audit.get("score", 0)

                        # Score display
                        if _score >= 90:
                            st.success(f"\U0001f3c6 **Compliance Score: {_score}/100** — Excellent! ({_audit['passed']}/{_audit['total_checks']} checks passed)")
                        elif _score >= 70:
                            st.warning(f"\u26a0\ufe0f **Compliance Score: {_score}/100** — Needs attention ({_audit['passed']}/{_audit['total_checks']} checks passed)")
                        else:
                            st.error(f"\U0001f534 **Compliance Score: {_score}/100** — Critical issues found ({_audit['passed']}/{_audit['total_checks']} checks passed)")

                        # Violations
                        _violations = _audit.get("violations", [])
                        _warnings = _audit.get("warnings", [])

                        if _violations:
                            st.markdown(f"### \U0001f534 Violations ({len(_violations)})")
                            for _v in _violations:
                                _sev_icon = "\U0001f534" if _v.get("severity") == "CRITICAL" else "\U0001f7e1"
                                with st.expander(f"{_sev_icon} **{_v.get('severity', '')}** — {_v.get('case', '')}"):
                                    st.markdown(f"**Issue:** {_v.get('detail', '')}")
                                    st.markdown(f"**Rule:** {_v.get('rule', '')}")
                                    st.markdown(f"**Case:** {_v.get('case', '')}")

                        if _warnings:
                            st.markdown(f"### \U0001f7e1 Warnings ({len(_warnings)})")
                            for _w in _warnings:
                                with st.expander(f"\U0001f7e1 **{_w.get('severity', '')}** — {_w.get('case', '')}"):
                                    st.markdown(f"**Issue:** {_w.get('detail', '')}")
                                    st.markdown(f"**Rule:** {_w.get('rule', '')}")

                        if not _violations and not _warnings:
                            st.balloons()
                            st.success("\u2705 No compliance issues detected across all trust accounts!")

                    except Exception as e:
                        st.error(f"Error running audit: {e}")

            st.markdown("---")
            st.markdown("#### \U0001f4d6 RPC 1.15 Quick Reference")
            st.markdown("""
    - **Separate Account Required** — All client funds in IOLTA trust account
    - **No Commingling** — Lawyer's personal funds cannot be in trust account (except for bank fees)
    - **Prompt Notification** — Notify client promptly upon receipt of funds
    - **Monthly Reconciliation** — Three-way reconciliation every month
    - **Record Retention** — Complete records maintained for **5 years**
    - **Prompt Delivery** — Deliver funds to client promptly when earned/costs incurred
    - **Disputed Funds** — Keep disputed portions in trust until dispute is resolved
    """)


    # -- 6. Fee Agreement Tracker --
    if active_tab == "\U0001f4b0 Fee Agreements":
        st.markdown("## \U0001f4b0 Fee Agreement Tracker")
        st.caption("RPC 1.5 — Track fee agreements, types, and signed status")

        # Load current agreement
        _fa = ethical_compliance.load_fee_agreement(case_id)
        _fa_status = ethical_compliance.get_fee_agreement_status(case_id)
        _status_badge = {
            "none": "\u274c No Agreement",
            "draft": "\U0001f4dd Draft",
            "signed": "\u2705 Signed",
        }.get(_fa_status, "\u274c None")
        st.markdown(f"### Status: {_status_badge}")

        with st.form("fee_agreement_form"):
            _fa_type = st.selectbox(
                "Fee Type", ethical_compliance.FEE_TYPES,
                index=ethical_compliance.FEE_TYPES.index(_fa.get("fee_type", "Hourly")) if _fa and _fa.get("fee_type") in ethical_compliance.FEE_TYPES else 0,
                key="fa_type",
            )
            _fa_rate = st.text_input("Rate / Amount", value=_fa.get("rate", "") if _fa else "", key="fa_rate")
            _fa_retainer = st.text_input("Retainer Amount", value=_fa.get("retainer", "") if _fa else "", key="fa_retainer")
            _fa_cpct = st.text_input("Contingent % (if applicable)", value=_fa.get("contingent_pct", "") if _fa else "", key="fa_cpct")
            _fa_signed = st.checkbox("Agreement Signed", value=_fa.get("signed", False) if _fa else False, key="fa_signed")
            _fa_sdate = st.text_input("Signed Date", value=_fa.get("signed_date", "") if _fa else "", key="fa_sdate")
            _fa_closing = st.checkbox("Closing Statement Sent (contingent)", value=_fa.get("closing_statement_sent", False) if _fa else False, key="fa_closing")
            _fa_notes = st.text_area("Notes", value=_fa.get("notes", "") if _fa else "", key="fa_notes")
            _fa_submit = st.form_submit_button("\U0001f4be Save Fee Agreement", type="primary")

            if _fa_submit:
                ethical_compliance.save_fee_agreement(
                    case_id=case_id, fee_type=_fa_type, rate=_fa_rate,
                    retainer=_fa_retainer, signed=_fa_signed, signed_date=_fa_sdate,
                    notes=_fa_notes, contingent_pct=_fa_cpct, closing_statement=_fa_closing,
                )
                st.success("\u2705 Fee agreement saved!")
                st.rerun()

        # Firm-wide missing agreements
        with st.expander("\U0001f4ca Cases Missing Fee Agreements"):
            try:
                _missing = ethical_compliance.get_cases_missing_fee_agreement(case_mgr)
                if _missing:
                    st.warning(f"\u26a0\ufe0f {len(_missing)} active case(s) without signed fee agreements")
                    for _m in _missing:
                        _ms = "\U0001f4dd Draft" if _m.get("fee_status") == "draft" else "\u274c None"
                        st.markdown(f"- {_ms} — **{_m.get('case_name', '')}**")
                else:
                    st.success("\u2705 All active cases have signed fee agreements!")
            except Exception as e:
                st.error(f"Error loading missing agreements: {e}")

    # -- 7. Litigation Hold / Evidence Preservation --
    if active_tab == "\U0001f512 Litigation Hold":
        st.markdown("## \U0001f512 Litigation Hold / Evidence Preservation")
        st.caption("RPC 3.4 — Manage litigation holds and evidence preservation checklists")

        _hold = ethical_compliance.load_lit_hold(case_id)
        _is_active = _hold.get("active", False)

        if not _is_active and not _hold.get("checklist"):
            st.info("No litigation hold has been initiated for this case.")
            if st.button("\U0001f680 Initiate Litigation Hold", key="init_lit_hold", type="primary"):
                _hold = ethical_compliance.init_lit_hold(case_id)
                st.success("\u2705 Litigation hold initiated with standard checklist!")
                st.rerun()
        else:
            _hold_badge = "\U0001f7e2 ACTIVE" if _is_active else "\u26ab INACTIVE"
            st.markdown(f"### Status: {_hold_badge}")
            if _hold.get("initiated_date"):
                st.markdown(f"**Initiated:** {_hold['initiated_date']}")

            # Toggle active status
            _new_active = st.checkbox("Hold Active", value=_is_active, key="lit_hold_active")
            if _new_active != _is_active:
                _hold["active"] = _new_active
                ethical_compliance.save_lit_hold(case_id, _hold)
                st.rerun()

            # Checklist
            _checklist = _hold.get("checklist", [])
            if _checklist:
                st.markdown("### \u2705 Preservation Checklist")
                _completed = sum(1 for c in _checklist if c.get("checked"))
                st.progress(_completed / len(_checklist) if _checklist else 0)
                st.markdown(f"**{_completed}/{len(_checklist)}** items completed")

                _categories = {}
                for _item in _checklist:
                    _cat = _item.get("category", "General")
                    _categories.setdefault(_cat, []).append(_item)

                for _cat, _items in _categories.items():
                    st.markdown(f"**{_cat}:**")
                    for _item in _items:
                        _checked = st.checkbox(
                            _item.get("label", ""),
                            value=_item.get("checked", False),
                            key=f"lh_{_item.get('id', '')}",
                        )
                        if _checked != _item.get("checked", False):
                            _item["checked"] = _checked
                            if _checked:
                                _item["date_completed"] = datetime.now().strftime("%Y-%m-%d")
                            ethical_compliance.save_lit_hold(case_id, _hold)
                            st.rerun()

            # Notes
            _hold_notes = st.text_area("Litigation Hold Notes", value=_hold.get("notes", ""), key="lh_notes")
            if st.button("\U0001f4be Save Notes", key="save_lh_notes"):
                _hold["notes"] = _hold_notes
                ethical_compliance.save_lit_hold(case_id, _hold)
                st.success("Notes saved!")

    # -- 8. Withdrawal Checklist --
    if active_tab == "\U0001f4cb Withdrawal":
        st.markdown("## \U0001f4cb Withdrawal Checklist")
        st.caption("RPC 1.16 — Guided checklist for declining or terminating representation")

        _wtype = st.radio("Withdrawal Type", ["Mandatory (RPC 1.16(a))", "Permissive (RPC 1.16(b))"], key="w_type", horizontal=True)
        _wkey = "mandatory" if "Mandatory" in _wtype else "permissive"
        _wdata = ethical_compliance.WITHDRAWAL_CHECKLIST[_wkey]

        st.markdown(f"### {_wdata['title']}")
        st.markdown(f"*{_wdata['description']}*")

        # Triggers
        st.markdown("#### Triggering Conditions")
        for _t in _wdata["triggers"]:
            st.markdown(f"- {_t}")

        # Steps checklist (client-side only, not persisted)
        st.markdown("#### Required Steps")
        for _si, _step in enumerate(_wdata["steps"]):
            _req = "\U0001f534 Required" if _step.get("required") else "\U0001f7e1 Recommended"
            st.checkbox(f"{_req} — {_step['label']}", key=f"ws_{_wkey}_{_si}")

        st.info("\U0001f4a1 **Important:** If litigation is pending, you must obtain court permission before withdrawing. Always protect client interests during the transition.")

    # -- 9. Supervision Tracker --
    if active_tab == "\U0001f441\ufe0f Supervision":
        st.markdown("## \U0001f441\ufe0f Supervision & Delegation Tracker")
        st.caption("RPC 5.1 / 5.3 — Track delegated tasks, supervisory review, and staff assignments")

        # Add entry
        with st.expander("\u2795 Add Delegated Task", expanded=False):
            with st.form("add_supervision", clear_on_submit=True):
                _sv_task = st.text_input("Task Description *", key="sv_task")
                _sv_assignee = st.text_input("Assignee Name *", key="sv_assignee")
                _sv_type = st.selectbox("Assignee Type", ["Attorney", "Paralegal", "Clerk", "Extern"], key="sv_type")
                _sv_supervisor = st.text_input("Supervisor", key="sv_supervisor")
                _sv_due = st.date_input("Due Date", key="sv_due")
                _sv_notes = st.text_area("Notes", key="sv_notes")
                _sv_submit = st.form_submit_button("\U0001f4be Save Delegation", type="primary")

                if _sv_submit and _sv_task and _sv_assignee:
                    ethical_compliance.add_supervision_entry(
                        case_id=case_id, task=_sv_task, assignee=_sv_assignee,
                        supervisor=_sv_supervisor, assignee_type=_sv_type,
                        due_date=str(_sv_due), notes=_sv_notes,
                    )
                    st.success("\u2705 Delegation logged!")
                    st.rerun()

        # List entries
        _sv_log = ethical_compliance.load_supervision_log(case_id)
        if _sv_log:
            st.markdown(f"### \U0001f4cb Delegation Log ({len(_sv_log)} entries)")

            # Summary metrics
            _assigned = sum(1 for e in _sv_log if e.get("status") == "assigned")
            _reviewed = sum(1 for e in _sv_log if e.get("status") == "reviewed")
            _completed = sum(1 for e in _sv_log if e.get("status") == "completed")
            _s1, _s2, _s3 = st.columns(3)
            _s1.metric("\U0001f4cb Assigned", _assigned)
            _s2.metric("\u2705 Reviewed", _reviewed)
            _s3.metric("\U0001f3c6 Completed", _completed)

            for _se in _sv_log:
                _st_icon = {
                    "assigned": "\U0001f4cb",
                    "reviewed": "\u2705",
                    "completed": "\U0001f3c6",
                }.get(_se.get("status", ""), "\U0001f4cb")
                with st.expander(f"{_st_icon} **{_se.get('task', '')}** — {_se.get('assignee', '')} ({_se.get('assignee_type', '')})"):
                    st.markdown(f"**Task:** {_se.get('task', '')}")
                    st.markdown(f"**Assignee:** {_se.get('assignee', '')} ({_se.get('assignee_type', '')})")
                    st.markdown(f"**Supervisor:** {_se.get('supervisor', 'N/A')}")
                    st.markdown(f"**Due Date:** {_se.get('due_date', 'N/A')}")
                    st.markdown(f"**Status:** {_se.get('status', 'assigned')}")
                    if _se.get("notes"):
                        st.markdown(f"**Notes:** {_se['notes']}")

                    # Status update buttons
                    _bc1, _bc2, _bc3 = st.columns(3)
                    with _bc1:
                        if st.button("\u2705 Mark Reviewed", key=f"sv_rev_{_se.get('id', '')}"):
                            ethical_compliance.update_supervision_entry(case_id, _se["id"], {"status": "reviewed"})
                            st.rerun()
                    with _bc2:
                        if st.button("\U0001f3c6 Mark Complete", key=f"sv_comp_{_se.get('id', '')}"):
                            ethical_compliance.update_supervision_entry(case_id, _se["id"], {"status": "completed"})
                            st.rerun()
                    with _bc3:
                        if st.button("\U0001f5d1\ufe0f Delete", key=f"sv_del_{_se.get('id', '')}"):
                            ethical_compliance.delete_supervision_entry(case_id, _se["id"])
                            st.rerun()
        else:
            st.info("No delegated tasks logged for this case. Use the form above to add one.")

    # -- 10. Ethics Quick-Reference --
    if active_tab == "\U0001f4d6 Ethics Reference":
        st.markdown("## \U0001f4d6 Tennessee Rules of Professional Conduct — Quick Reference")
        st.caption(f"Complete TN RPC reference — {len(ethical_compliance.TN_RULES_REFERENCE)} rules across {len(ethical_compliance.TN_RPC_CATEGORIES)} categories")

        # Search + Category filter
        _er_c1, _er_c2 = st.columns([2, 1])
        with _er_c1:
            _search = st.text_input("\U0001f50d Search rules...", key="ethics_search", placeholder="e.g. conflict, trust, communication, pro bono")
        with _er_c2:
            _cat_options = ["All Categories"] + list(ethical_compliance.TN_RPC_CATEGORIES.keys())
            _cat_filter = st.selectbox("\U0001f4c2 Browse by Category", _cat_options, key="ethics_cat")

        # Determine rules to show
        if _search:
            _display_rules = ethical_compliance.search_rules(_search)
            _title = f"Found {len(_display_rules)} matching rule(s) for '{_search}'"
        elif _cat_filter and _cat_filter != "All Categories":
            _display_rules = ethical_compliance.search_rules_by_category(_cat_filter)
            _cat_desc = ethical_compliance.TN_RPC_CATEGORIES.get(_cat_filter, "")
            _title = f"\U0001f4c2 {_cat_filter} ({len(_display_rules)} rules)"
            st.info(f"\U0001f4a1 **{_cat_filter}:** {_cat_desc}")
        else:
            _display_rules = ethical_compliance.TN_RULES_REFERENCE
            _title = f"All Rules ({len(_display_rules)})"

        st.markdown(f"### {_title}")

        if _display_rules:
            for _r in _display_rules:
                _cat_badge = f" `{_r.get('category', '')}`" if _r.get("category") else ""
                with st.expander(f"**{_r['rule']}** — {_r['title']}{_cat_badge}", expanded=bool(_search)):
                    st.markdown(f"**Summary:** {_r['summary']}")
                    st.markdown("**Key Points:**")
                    for _kp in _r.get("key_points", []):
                        st.markdown(f"- {_kp}")
                    _risk_col, _cat_col = st.columns(2)
                    with _risk_col:
                        st.error(f"\u26a0\ufe0f **Risk:** {_r.get('risk', '')}")
                    with _cat_col:
                        st.info(f"\U0001f4c2 **Category:** {_r.get('category', 'N/A')}")
        elif _search:
            st.info(f"No rules found matching '{_search}'. Try broader terms like 'conflict', 'trust', or 'advertising'.")

        # Category overview at bottom
        with st.expander("\U0001f5c2\ufe0f All Categories Overview"):
            for _cat_name, _cat_desc in ethical_compliance.TN_RPC_CATEGORIES.items():
                _cat_count = len(ethical_compliance.search_rules_by_category(_cat_name))
                st.markdown(f"- **{_cat_name}** ({_cat_count} rules) — {_cat_desc}")

    # -- 11. Reporting Obligations --
    if active_tab == "\U0001f6a8 Reporting":
        st.markdown("## \U0001f6a8 Reporting Obligations")
        st.caption("RPC 8.3 — Mandatory reporting of professional misconduct")

        _rpt = ethical_compliance.REPORTING_CHECKLIST

        st.markdown("### When Must You Report?")
        for _w in _rpt.get("when_to_report", []):
            st.markdown(f"- \U0001f534 {_w}")

        st.markdown("### Exceptions to Reporting")
        for _e in _rpt.get("exceptions", []):
            st.markdown(f"- \U0001f7e1 {_e}")

        st.markdown("### How to Report")
        for _h in _rpt.get("how_to_report", []):
            st.markdown(f"- \U0001f4dd {_h}")

        st.markdown("### Consequences of Not Reporting")
        for _c in _rpt.get("consequences_of_not_reporting", []):
            st.markdown(f"- \u26a0\ufe0f {_c}")

        st.info("\U0001f4a1 **RPC 8.3**: A lawyer who knows that another lawyer has committed a violation raising a substantial question about their honesty, trustworthiness, or fitness shall report to the Board of Professional Responsibility.")

    # -- 12. SOL Tracker --
    if active_tab == "\u23f0 SOL Tracker":
        st.markdown("## \u23f0 Statute of Limitations Tracker")
        st.caption("Malpractice Prevention — #1 malpractice claim is missed SOL deadlines")

        _sol_tab1, _sol_tab2, _sol_tab3 = st.tabs(["\U0001f4cb This Case", "\U0001f514 Firm-Wide Alerts", "\U0001f4d6 TN SOL Reference"])

        with _sol_tab1:
            if not case_id:
                st.info("Select a case to track statute of limitations.")
            else:
                _sol_data = ethical_compliance.load_sol_tracking(case_id)
                _sol_claims = _sol_data.get("claims", [])

                st.markdown("### Add Claim to Track")
                with st.form("sol_add_form", clear_on_submit=True):
                    _sol_c1, _sol_c2 = st.columns(2)
                    with _sol_c1:
                        _sol_claim_type = st.selectbox("Claim Type", ethical_compliance.SOL_CLAIM_TYPES, key="_sol_ctype")
                        _sol_incident = st.date_input("Incident / Accrual Date", value=None, key="_sol_incident")
                    with _sol_c2:
                        _sol_entry = next((s for s in ethical_compliance.TN_SOL_TABLE if s["claim_type"] == _sol_claim_type), {})
                        _has_disc = _sol_entry.get("discovery_rule", False)
                        _sol_discovery = st.date_input("Discovery Date (if applicable)", value=None, key="_sol_disc",
                                                       help="Only relevant for claims with discovery rule" if _has_disc else "Not applicable for this claim type")
                        _sol_desc = st.text_input("Description / Notes", key="_sol_desc")
                    _sol_tolling = st.text_area("Tolling Notes", height=68, key="_sol_tolling",
                                                help="Document any tolling arguments: minority, mental incapacity, fraudulent concealment, military service, etc.")
                    if st.form_submit_button("\u2795 Track This Claim", use_container_width=True):
                        if _sol_incident:
                            _disc_str = str(_sol_discovery) if _sol_discovery and _has_disc else ""
                            ethical_compliance.add_sol_claim(
                                case_id, _sol_claim_type, str(_sol_incident),
                                discovery_date=_disc_str, tolling_notes=_sol_tolling,
                                description=_sol_desc,
                            )
                            st.success(f"Now tracking {_sol_claim_type} SOL deadline.")
                            st.rerun()
                        else:
                            st.error("Incident date is required.")

                if _sol_claims:
                    st.markdown("### Tracked Claims")
                    for _sc in _sol_claims:
                        _calc = ethical_compliance.calculate_sol_deadline(
                            _sc.get("claim_type", ""), _sc.get("incident_date", ""), _sc.get("discovery_date", "")
                        )
                        _urg = _calc.get("urgency", "")
                        _days = _calc.get("days_remaining")
                        _dl = _calc.get("deadline", "")

                        with st.expander(f"{_urg} **{_sc['claim_type']}** — Deadline: {_dl} ({_days} days)" if _days is not None else f"\U0001f4cb **{_sc['claim_type']}** — {_dl}", expanded=_days is not None and _days <= 90):
                            _sc1, _sc2 = st.columns(2)
                            with _sc1:
                                st.markdown(f"**Statute:** {_calc.get('statute', '')}")
                                st.markdown(f"**Incident Date:** {_sc.get('incident_date', '')}")
                                if _sc.get("discovery_date"):
                                    st.markdown(f"**Discovery Date:** {_sc['discovery_date']}")
                            with _sc2:
                                st.markdown(f"**Notes:** {_calc.get('notes', '')}")
                                if _sc.get("description"):
                                    st.markdown(f"**Description:** {_sc['description']}")
                            if _sc.get("tolling_notes"):
                                st.warning(f"**Tolling:** {_sc['tolling_notes']}")

                            if _days is not None:
                                _pct = max(0, min(100, int((1 - _days / 365) * 100)))
                                st.progress(_pct / 100, text=f"{_days} days remaining")

                            if st.button("\U0001f5d1\ufe0f Remove", key=f"sol_del_{_sc.get('id')}"):
                                ethical_compliance.delete_sol_claim(case_id, _sc["id"])
                                st.rerun()
                else:
                    st.info("No SOL claims tracked for this case. Add one above.")

        with _sol_tab2:
            st.markdown("### Firm-Wide SOL Alerts")
            _sol_thresh = st.slider("Alert threshold (days)", 30, 365, 90, key="_sol_thresh")
            if st.button("\U0001f50d Scan All Cases", key="_sol_scan"):
                _alerts = ethical_compliance.get_sol_alerts(case_mgr, threshold_days=_sol_thresh)
                if _alerts:
                    for _a in _alerts:
                        _color = "error" if _a.get("days_remaining", 999) <= 30 else "warning" if _a.get("days_remaining", 999) <= 60 else "info"
                        getattr(st, _color)(f"{_a['urgency']} **{_a['case_name']}** — {_a['claim_type']} — Deadline: {_a['deadline']} ({_a['days_remaining']} days)")
                        if _a.get("tolling_notes"):
                            st.caption(f"Tolling: {_a['tolling_notes']}")
                else:
                    st.success("\u2705 No SOL deadlines within the alert threshold.")

        with _sol_tab3:
            st.markdown("### Tennessee Statutes of Limitations")
            st.caption("Quick reference — always verify current law")
            import pandas as pd
            _sol_df = pd.DataFrame(ethical_compliance.TN_SOL_TABLE)
            _sol_df = _sol_df.rename(columns={
                "claim_type": "Claim Type", "years": "Years", "statute": "Statute",
                "discovery_rule": "Discovery Rule", "notes": "Notes"
            })
            st.dataframe(_sol_df, use_container_width=True, hide_index=True)

    # -- 13. Letters (Engagement / Disengagement) --
    if active_tab == "\U0001f4dd Letters":
        st.markdown("## \U0001f4dd Engagement & Disengagement Letters")
        st.caption("RPC 1.2 / 1.5 / 1.16 — Scope, fees, and termination documentation")

        _lt_tab1, _lt_tab2, _lt_tab3 = st.tabs(["\u270f\ufe0f Generate Letter", "\U0001f4cb Letter History", "\U0001f50d Missing Letters Audit"])

        with _lt_tab1:
            _lt_type = st.selectbox("Letter Type", ethical_compliance.LETTER_TYPES, key="_lt_type")
            _tmpl = ethical_compliance.LETTER_TEMPLATES.get(_lt_type, {})

            if _tmpl:
                st.info(f"**{_tmpl.get('description', '')}** — {_tmpl.get('rpc', '')}")

                _required = _tmpl.get("required_fields", [])
                _optional = _tmpl.get("optional_fields", [])

                with st.form("letter_gen_form", clear_on_submit=False):
                    st.markdown("#### Firm Details")
                    _lf1, _lf2 = st.columns(2)
                    with _lf1:
                        _lt_firm = st.text_input("Firm Name", key="_lt_firm")
                        _lt_atty = st.text_input("Attorney Name", key="_lt_atty")
                    with _lf2:
                        _lt_firm_addr = st.text_area("Firm Address", height=68, key="_lt_firm_addr")

                    st.markdown("#### Required Fields")
                    _lt_fields = {}
                    if _lt_firm:
                        _lt_fields["firm_name"] = _lt_firm
                    if _lt_atty:
                        _lt_fields["attorney_name"] = _lt_atty
                    if _lt_firm_addr:
                        _lt_fields["firm_address"] = _lt_firm_addr

                    _lr1, _lr2 = st.columns(2)
                    for _i, _rf in enumerate(_required):
                        _label = _rf.replace("_", " ").title()
                        with _lr1 if _i % 2 == 0 else _lr2:
                            if _rf in ("specific_services", "excluded_services", "reason_declined",
                                       "reason_withdrawal", "conflict_description", "risks_to_client"):
                                _lt_fields[_rf] = st.text_area(_label, height=100, key=f"_lt_r_{_rf}")
                            elif _rf == "fee_type":
                                _lt_fields[_rf] = st.selectbox(_label, ["Hourly", "Flat Fee", "Contingency", "Retainer", "Hybrid"], key=f"_lt_r_{_rf}")
                            elif _rf == "effective_date":
                                _eff = st.date_input(_label, key=f"_lt_r_{_rf}")
                                _lt_fields[_rf] = str(_eff) if _eff else ""
                            else:
                                _lt_fields[_rf] = st.text_input(_label, key=f"_lt_r_{_rf}")

                    if _optional:
                        st.markdown("#### Optional Fields")
                        _lo1, _lo2 = st.columns(2)
                        for _j, _of in enumerate(_optional):
                            _label_o = _of.replace("_", " ").title()
                            with _lo1 if _j % 2 == 0 else _lo2:
                                _lt_fields[_of] = st.text_input(_label_o, key=f"_lt_o_{_of}")

                    _lt_client_addr = st.text_input("Client Address", key="_lt_client_addr")
                    if _lt_client_addr:
                        _lt_fields["client_address"] = _lt_client_addr

                    if st.form_submit_button("\U0001f4c4 Generate Letter", use_container_width=True):
                        _missing_req = [r for r in _required if not _lt_fields.get(r)]
                        if _missing_req:
                            st.error(f"Missing required fields: {', '.join(r.replace('_', ' ').title() for r in _missing_req)}")
                        else:
                            _letter_text = ethical_compliance.generate_letter(_lt_type, _lt_fields)
                            st.session_state["_generated_letter"] = _letter_text
                            st.session_state["_generated_letter_type"] = _lt_type
                            st.session_state["_generated_letter_client"] = _lt_fields.get("client_name", "")

                if st.session_state.get("_generated_letter"):
                    st.markdown("---")
                    st.markdown("### Generated Letter Preview")
                    st.text_area("Letter Content", st.session_state["_generated_letter"], height=500, key="_lt_preview")

                    _lp1, _lp2 = st.columns(2)
                    with _lp1:
                        st.download_button(
                            "\u2b07\ufe0f Download as Text",
                            data=st.session_state["_generated_letter"],
                            file_name=f"{st.session_state.get('_generated_letter_type', 'letter').replace(' ', '_').replace('/', '_').lower()}.txt",
                            mime="text/plain",
                            use_container_width=True,
                        )
                    with _lp2:
                        if case_id and st.button("\U0001f4cb Log to Case History", key="_lt_log", use_container_width=True):
                            ethical_compliance.save_letter_record(
                                case_id,
                                st.session_state.get("_generated_letter_type", ""),
                                st.session_state.get("_generated_letter_client", ""),
                            )
                            st.success("Letter logged to case history.")
                            st.session_state.pop("_generated_letter", None)
                            st.rerun()

        with _lt_tab2:
            if not case_id:
                st.info("Select a case to view letter history.")
            else:
                _lt_records = ethical_compliance.load_letter_records(case_id)
                if _lt_records:
                    st.markdown(f"### Letter History ({len(_lt_records)} records)")
                    for _lr in _lt_records:
                        _sent_icon = "\u2705" if _lr.get("sent") else "\U0001f4e4"
                        with st.expander(f"{_sent_icon} {_lr['letter_type']} — {_lr.get('recipient', 'N/A')} — {_lr.get('created_at', '')[:10]}"):
                            _lrc1, _lrc2 = st.columns(2)
                            with _lrc1:
                                st.markdown(f"**Type:** {_lr['letter_type']}")
                                st.markdown(f"**Recipient:** {_lr.get('recipient', 'N/A')}")
                            with _lrc2:
                                st.markdown(f"**Created:** {_lr.get('created_at', '')[:10]}")
                                _sent_status = "Sent" if _lr.get("sent") else "Not Sent"
                                st.markdown(f"**Status:** {_sent_status}")
                            if _lr.get("notes"):
                                st.markdown(f"**Notes:** {_lr['notes']}")
                            if st.button("\U0001f5d1\ufe0f Delete Record", key=f"lt_del_{_lr['id']}"):
                                ethical_compliance.delete_letter_record(case_id, _lr["id"])
                                st.rerun()
                else:
                    st.info("No letter records for this case.")

        with _lt_tab3:
            st.markdown("### Missing Engagement Letter Audit")
            st.caption("Active cases without an engagement letter or limited scope agreement on file")
            if st.button("\U0001f50d Run Audit", key="_lt_audit"):
                _missing = ethical_compliance.get_cases_missing_engagement_letter(case_mgr)
                if _missing:
                    st.error(f"\u26a0\ufe0f {len(_missing)} active case(s) missing engagement documentation:")
                    for _m in _missing:
                        st.warning(f"**{_m['case_name']}** — Status: {_m['status']} — Other letters on file: {_m['letter_count']}")
                else:
                    st.success("\u2705 All active cases have engagement letters on file.")

    # -- 14. TN Sentencing & Fine Ranges --
    if active_tab == "\U0001f4ca Sentencing":
        st.markdown("## \U0001f4ca Tennessee Sentencing & Fine Ranges")
        st.caption("T.C.A. \u00a7 40-35-111 / 112 — Quick courtroom reference")

        _st_tab1, _st_tab2, _st_tab3, _st_tab4, _st_tab5 = st.tabs([
            "\U0001f50d Quick Lookup", "\U0001f3db\ufe0f Felony Grid", "\U0001f4cb Misdemeanors", "\U0001f4b0 Fines", "\U0001f4d6 Sentencing Context"
        ])

        with _st_tab1:
            st.markdown("### Quick Sentencing Lookup")
            _sq1, _sq2 = st.columns(2)
            with _sq1:
                _sel_class = st.selectbox("Offense Class", ["A", "B", "C", "D", "E"], key="_sent_class")
            with _sq2:
                _sel_range = st.selectbox("Offender Range", [
                    "All Ranges", "Esp. Mitigated", "Range I (Standard)", "Range II (Multiple)",
                    "Range III (Persistent)", "Career Offender"
                ], key="_sent_range")

            _summary = ethical_compliance.get_full_sentencing_summary(_sel_class)
            _filter_range = "" if _sel_range == "All Ranges" else _sel_range
            _filtered = ethical_compliance.get_sentencing_range(_sel_class, _filter_range)

            st.markdown(f"### Class {_sel_class} Felony")
            _ql1, _ql2 = st.columns(2)
            with _ql1:
                st.metric("Max Fine", f"${_summary['max_fine']:,}")
            with _ql2:
                st.metric("Release Eligibility", _summary.get("release_eligibility", "\u2014"))

            if _summary.get("release_notes"):
                st.caption(_summary["release_notes"])

            for _sr in _filtered:
                with st.container():
                    st.markdown(f"**{_sr['range']}** — **{_sr['min_years']}\u2013{_sr['max_years']} years** ({_sr['statute']})")
                    st.caption(_sr.get("notes", ""))
                    st.divider()

        with _st_tab2:
            st.markdown("### Felony Sentencing Ranges")
            st.caption("T.C.A. \u00a7 40-35-112 — All classes and offender ranges")

            # Build a pivot-style grid
            _ranges_order = ["Esp. Mitigated", "Range I (Standard)", "Range II (Multiple)", "Range III (Persistent)", "Career Offender"]
            _grid_data = []
            for _rng in _ranges_order:
                _row = {"Offender Range": _rng}
                for _cls in ["A", "B", "C", "D", "E"]:
                    _match = next((s for s in ethical_compliance.TN_FELONY_SENTENCING if s["class"] == _cls and s["range"] == _rng), None)
                    if _match:
                        _row[f"Class {_cls}"] = f"{_match['min_years']}\u2013{_match['max_years']} yrs"
                    else:
                        _row[f"Class {_cls}"] = "\u2014"
                _grid_data.append(_row)

            import pandas as pd
            _grid_df = pd.DataFrame(_grid_data)
            st.dataframe(_grid_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("#### Detailed View")
            _det_class = st.selectbox("Filter by Class", ["All", "A", "B", "C", "D", "E"], key="_sent_det_cls")
            _det_data = ethical_compliance.TN_FELONY_SENTENCING if _det_class == "All" else [s for s in ethical_compliance.TN_FELONY_SENTENCING if s["class"] == _det_class]
            _det_df = pd.DataFrame(_det_data)
            _det_df = _det_df.rename(columns={"class": "Class", "range": "Offender Range", "min_years": "Min (yrs)", "max_years": "Max (yrs)", "statute": "Statute", "notes": "Notes"})
            st.dataframe(_det_df, use_container_width=True, hide_index=True)

        with _st_tab3:
            st.markdown("### Misdemeanor Sentencing")
            st.caption("T.C.A. \u00a7 40-35-111(e)")
            import pandas as pd
            _misd_df = pd.DataFrame(ethical_compliance.TN_MISDEMEANOR_SENTENCING)
            _misd_df = _misd_df.rename(columns={"class": "Class", "max_jail": "Max Jail", "max_jail_days": "Max Days", "statute": "Statute", "notes": "Notes"})
            st.dataframe(_misd_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Misdemeanor Fines")
            _misd_fines = [f for f in ethical_compliance.TN_FINE_SCHEDULE if "Misdemeanor" in f["class"]]
            _mf_df = pd.DataFrame(_misd_fines)
            _mf_df = _mf_df.rename(columns={"class": "Class", "max_fine": "Max Fine ($)", "statute": "Statute", "notes": "Notes"})
            st.dataframe(_mf_df, use_container_width=True, hide_index=True)

        with _st_tab4:
            st.markdown("### Fine Schedule")
            st.caption("T.C.A. \u00a7 40-35-111(b) — Maximum fines by offense class")
            import pandas as pd
            _fine_df = pd.DataFrame(ethical_compliance.TN_FINE_SCHEDULE)
            _fine_df = _fine_df.rename(columns={"class": "Offense Class", "max_fine": "Max Fine ($)", "statute": "Statute", "notes": "Notes"})
            st.dataframe(_fine_df, use_container_width=True, hide_index=True)

            st.info("\U0001f4a1 **Note:** For any felony, the court may also impose a fine equal to the amount of gain from the offense if greater than the statutory maximum (T.C.A. \u00a7 40-35-111(b)).")

        with _st_tab5:
            st.markdown("### Release Eligibility")
            st.caption("T.C.A. \u00a7 40-35-501 — Minimum service before release eligibility")
            import pandas as pd
            _rel_df = pd.DataFrame(ethical_compliance.TN_RELEASE_ELIGIBILITY)
            _rel_df = _rel_df.rename(columns={"class": "Offense Class", "percentage": "Min Service", "notes": "Notes"})
            st.dataframe(_rel_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Probation Eligibility")
            st.caption("T.C.A. \u00a7 40-35-303")
            _prob_df = pd.DataFrame(ethical_compliance.TN_PROBATION_ELIGIBILITY)
            _prob_df = _prob_df.rename(columns={"class": "Offense Class", "presumption": "Presumption", "statute": "Statute", "notes": "Notes"})
            st.dataframe(_prob_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Community Corrections Eligibility")
            st.caption("T.C.A. \u00a7 40-36-106")
            _cc_elig = [c for c in ethical_compliance.TN_COMMUNITY_CORRECTIONS if "eligible" in c]
            _cc_inelig = [c for c in ethical_compliance.TN_COMMUNITY_CORRECTIONS if "ineligible" in c]
            if _cc_elig:
                st.markdown("**\u2705 Eligible:**")
                for _ce in _cc_elig:
                    st.markdown(f"- {_ce['eligible']} ({_ce['statute']}) — {_ce['notes']}")
            if _cc_inelig:
                st.markdown("**\u274c Ineligible:**")
                for _ci in _cc_inelig:
                    st.markdown(f"- {_ci['ineligible']} ({_ci['statute']}) — {_ci['notes']}")

            st.markdown("---")
            st.warning("\u26a0\ufe0f **Disclaimer:** This is a quick reference only. Always verify current statutes and any applicable amendments. Certain offenses carry mandatory minimums or enhanced penalties that override these general ranges.")
