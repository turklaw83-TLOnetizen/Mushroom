"""Billing UI module — ported from legacy ui_modules/billing_ui.py."""
import logging
import streamlit as st
from datetime import datetime

from core import billing

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, results, **ctx):
    """Render all tabs for the Billing nav group."""
    tabs = ctx.get("tabs", [])

    # -- 1. Time Tracker -------------------------------------------------------
    with tabs[0]:  # Time Tracker
        st.markdown("## \u23f1\ufe0f Time Tracker")
        _bill_case_id = st.session_state.current_case_id
        _bill_settings = billing.load_billing_settings()

        # -- Summary metrics --
        _time_entries = billing.load_time_entries(_bill_case_id)
        _total_hrs = sum(t.get("duration_hours", 0) for t in _time_entries)
        _billable_hrs = sum(t.get("duration_hours", 0) for t in _time_entries if t.get("billable", True))
        _billable_amt = sum(t.get("duration_hours", 0) * t.get("rate", 0) for t in _time_entries if t.get("billable", True))
        _unbilled = billing.get_unbilled_time(_bill_case_id)
        _unbilled_amt = sum(t.get("duration_hours", 0) * t.get("rate", 0) for t in _unbilled)

        _tm1, _tm2, _tm3, _tm4 = st.columns(4)
        _tm1.metric("Total Hours", f"{_total_hrs:.1f}")
        _tm2.metric("Billable Hours", f"{_billable_hrs:.1f}")
        _tm3.metric("Billable Amount", f"${_billable_amt:,.2f}")
        _tm4.metric("Unbilled", f"${_unbilled_amt:,.2f}")

        st.markdown("---")

        # -- Quick Timer --
        _timer_sub1, _timer_sub2 = st.tabs(["\U0001f4dd Manual Entry", "\u23f1\ufe0f Quick Timer"])

        with _timer_sub1:
            st.markdown("### Log Time Entry")
            _tc1, _tc2 = st.columns(2)
            with _tc1:
                _te_date = st.date_input("Date", value=datetime.now().date(), key="_te_date")
                _te_hours = st.number_input("Hours", min_value=0.0, max_value=24.0, value=0.5, step=0.25, key="_te_hours")
                _te_rate = st.number_input("Rate ($/hr)", min_value=0.0, value=float(_bill_settings.get("default_rate", 350.0)), step=25.0, key="_te_rate")
            with _tc2:
                _te_activity = st.selectbox("Activity Type", billing.ACTIVITY_TYPES, key="_te_activity")
                _te_billable = st.checkbox("Billable", value=True, key="_te_billable")
                _te_desc = st.text_area("Description", placeholder="What did you work on?", key="_te_desc", height=80)

            if st.button("\u2795 Add Time Entry", type="primary", key="_te_add", use_container_width=True):
                if _te_desc.strip():
                    billing.add_time_entry(
                        case_id=_bill_case_id,
                        duration_hours=_te_hours,
                        description=_te_desc.strip(),
                        activity_type=_te_activity,
                        billable=_te_billable,
                        rate=_te_rate,
                        date_str=_te_date.strftime("%Y-%m-%d"),
                    )
                    st.success("\u2705 Time entry added!")
                    st.rerun()
                else:
                    st.warning("Please enter a description.")

        with _timer_sub2:
            st.markdown("### Quick Timer")
            st.caption("Start a timer and it will calculate the duration for you.")

            if "_timer_running" not in st.session_state:
                st.session_state["_timer_running"] = False
                st.session_state["_timer_start"] = None

            if not st.session_state["_timer_running"]:
                _qt_activity = st.selectbox("Activity Type", billing.ACTIVITY_TYPES, key="_qt_act")
                _qt_desc = st.text_input("What are you working on?", key="_qt_desc")
                if st.button("\u25b6\ufe0f Start Timer", type="primary", key="_qt_start"):
                    st.session_state["_timer_running"] = True
                    st.session_state["_timer_start"] = datetime.now().isoformat()
                    st.session_state["_qt_activity_val"] = _qt_activity
                    st.session_state["_qt_desc_val"] = _qt_desc
                    st.rerun()
            else:
                _start_time = datetime.fromisoformat(st.session_state["_timer_start"])
                _elapsed = datetime.now() - _start_time
                _elapsed_hrs = _elapsed.total_seconds() / 3600
                _elapsed_mins = _elapsed.total_seconds() / 60

                st.markdown(f"""
                <div style="text-align:center; padding:2rem; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius:12px; border:1px solid rgba(255,255,255,0.1);">
                    <div style="font-size:3rem; font-weight:700; color:#00ff88;">\u23f1\ufe0f {int(_elapsed_mins)}m {int(_elapsed.total_seconds() % 60)}s</div>
                    <div style="color:rgba(255,255,255,0.6); margin-top:0.5rem;">
                        {st.session_state.get('_qt_activity_val', '')} — {st.session_state.get('_qt_desc_val', '')}
                    </div>
                    <div style="color:rgba(255,255,255,0.4); margin-top:0.25rem;">
                        {_elapsed_hrs:.2f} hours (${_elapsed_hrs * _bill_settings.get('default_rate', 350):,.2f})
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("\u23f9\ufe0f Stop & Save", type="primary", key="_qt_stop", use_container_width=True):
                    _rounded_hrs = round(_elapsed_hrs * 4) / 4  # Round to nearest 0.25
                    if _rounded_hrs < 0.25:
                        _rounded_hrs = 0.25
                    billing.add_time_entry(
                        case_id=_bill_case_id,
                        duration_hours=_rounded_hrs,
                        description=st.session_state.get("_qt_desc_val", "Timer entry"),
                        activity_type=st.session_state.get("_qt_activity_val", "Other"),
                        billable=True,
                        rate=_bill_settings.get("default_rate", 350.0),
                        date_str=datetime.now().strftime("%Y-%m-%d"),
                    )
                    st.session_state["_timer_running"] = False
                    st.session_state["_timer_start"] = None
                    st.success(f"\u2705 Saved {_rounded_hrs:.2f} hours!")
                    st.rerun()

        # -- Time Entry History --
        st.markdown("---")
        st.markdown("### \U0001f4cb Time Entry History")

        _time_entries = billing.load_time_entries(_bill_case_id)
        if _time_entries:
            for _tidx, _te in enumerate(_time_entries):
                _billed_tag = "\U0001f512 Billed" if _te.get("billed_invoice_id") else "\U0001f4dd Unbilled"
                _bill_flag = "\U0001f4b0" if _te.get("billable") else "\U0001f4cc"
                _te_total = _te.get("duration_hours", 0) * _te.get("rate", 0)

                with st.expander(
                    f"{_bill_flag} {_te.get('date', '')} — {_te.get('duration_hours', 0):.2f}h — "
                    f"{_te.get('activity_type', '')} — ${_te_total:,.2f} [{_billed_tag}]",
                    expanded=False
                ):
                    st.markdown(f"**Description:** {_te.get('description', '')}")
                    _d1, _d2, _d3, _d4 = st.columns(4)
                    _d1.caption(f"Rate: ${_te.get('rate', 0):,.2f}/hr")
                    _d2.caption(f"Hours: {_te.get('duration_hours', 0):.2f}")
                    _d3.caption(f"Billable: {'Yes' if _te.get('billable') else 'No'}")
                    _d4.caption(f"ID: {_te.get('id', '')}")

                    if not _te.get("billed_invoice_id"):
                        if st.button("\U0001f5d1\ufe0f Delete", key=f"_del_te_{_te.get('id')}"):
                            billing.delete_time_entry(_bill_case_id, _te.get("id", ""))
                            st.success("Deleted!")
                            st.rerun()
        else:
            st.info("No time entries yet. Use the form above to log your first entry.")

    # -- 2. Expenses -----------------------------------------------------------
    with tabs[1]:  # Expenses
        st.markdown("## \U0001f4b5 Expense Tracker")
        _exp_case_id = st.session_state.current_case_id

        # -- Expense metrics --
        _expenses = billing.load_expenses(_exp_case_id)
        _total_exp = sum(e.get("amount", 0) for e in _expenses)
        _unbilled_exp = billing.get_unbilled_expenses(_exp_case_id)
        _unbilled_exp_amt = sum(e.get("amount", 0) for e in _unbilled_exp)
        _reimb_amt = sum(e.get("amount", 0) for e in _expenses if e.get("reimbursable", True))

        _em1, _em2, _em3 = st.columns(3)
        _em1.metric("Total Expenses", f"${_total_exp:,.2f}")
        _em2.metric("Unbilled", f"${_unbilled_exp_amt:,.2f}")
        _em3.metric("Reimbursable", f"${_reimb_amt:,.2f}")

        st.markdown("---")

        # -- Add Expense Form --
        st.markdown("### \u2795 Log Expense")
        _ec1, _ec2 = st.columns(2)
        with _ec1:
            _ex_date = st.date_input("Date", value=datetime.now().date(), key="_ex_date")
            _ex_amount = st.number_input("Amount ($)", min_value=0.0, value=0.0, step=5.0, key="_ex_amount")
            _ex_category = st.selectbox("Category", billing.EXPENSE_CATEGORIES, key="_ex_category")
        with _ec2:
            _ex_desc = st.text_input("Description", placeholder="What was the expense for?", key="_ex_desc")
            _ex_reimb = st.checkbox("Reimbursable / Billable to Client", value=True, key="_ex_reimb")
            _ex_receipt = st.text_input("Receipt / Reference Note", placeholder="Receipt #, vendor, etc.", key="_ex_receipt")

        if st.button("\u2795 Add Expense", type="primary", key="_ex_add", use_container_width=True):
            if _ex_amount > 0:
                billing.add_expense(
                    case_id=_exp_case_id,
                    amount=_ex_amount,
                    category=_ex_category,
                    description=_ex_desc.strip(),
                    reimbursable=_ex_reimb,
                    receipt_note=_ex_receipt.strip(),
                    date_str=_ex_date.strftime("%Y-%m-%d"),
                )
                st.success("\u2705 Expense logged!")
                st.rerun()
            else:
                st.warning("Amount must be greater than $0.")

        # -- Category Breakdown --
        st.markdown("---")
        if _expenses:
            st.markdown("### \U0001f4ca Category Breakdown")
            _cat_totals = {}
            for _ex in _expenses:
                _cat = _ex.get("category", "Other")
                _cat_totals[_cat] = _cat_totals.get(_cat, 0) + _ex.get("amount", 0)

            _sorted_cats = sorted(_cat_totals.items(), key=lambda x: x[1], reverse=True)
            for _cat_name, _cat_total in _sorted_cats:
                _pct = (_cat_total / _total_exp * 100) if _total_exp > 0 else 0
                st.markdown(f"**{_cat_name}** — ${_cat_total:,.2f} ({_pct:.0f}%)")
                st.progress(min(_pct / 100, 1.0))

        # -- Expense History --
        st.markdown("### \U0001f4cb Expense History")
        if _expenses:
            for _eidx, _ex in enumerate(_expenses):
                _ex_billed = "\U0001f512 Billed" if _ex.get("billed_invoice_id") else "\U0001f4dd Unbilled"
                with st.expander(
                    f"{'\U0001f4b0' if _ex.get('reimbursable') else '\U0001f4cc'} {_ex.get('date', '')} — "
                    f"${_ex.get('amount', 0):,.2f} — {_ex.get('category', '')} [{_ex_billed}]",
                    expanded=False
                ):
                    if _ex.get("description"):
                        st.markdown(f"**Description:** {_ex.get('description')}")
                    if _ex.get("receipt_note"):
                        st.caption(f"\U0001f4ce Receipt: {_ex.get('receipt_note')}")
                    _e1, _e2 = st.columns(2)
                    _e1.caption(f"Reimbursable: {'Yes' if _ex.get('reimbursable') else 'No'}")
                    _e2.caption(f"ID: {_ex.get('id', '')}")

                    if not _ex.get("billed_invoice_id"):
                        if st.button("\U0001f5d1\ufe0f Delete", key=f"_del_ex_{_ex.get('id')}"):
                            billing.delete_expense(_exp_case_id, _ex.get("id", ""))
                            st.success("Deleted!")
                            st.rerun()
        else:
            st.info("No expenses logged yet.")

    # -- 3. Retainer -----------------------------------------------------------
    with tabs[2]:  # Retainer
        st.markdown("## \U0001f4b0 Retainer Account")
        _ret_case_id = st.session_state.current_case_id

        # Retainer balance
        _ret_balance = billing.get_retainer_balance(_ret_case_id)
        _ret_history = billing.load_retainer_history(_ret_case_id)
        _total_deposits = sum(h.get("amount", 0) for h in _ret_history if h.get("type") == "deposit")
        _total_draws = sum(h.get("amount", 0) for h in _ret_history if h.get("type") == "draw")

        _rb1, _rb2, _rb3 = st.columns(3)
        _rb1.metric("Current Balance", f"${_ret_balance:,.2f}")
        _rb2.metric("Total Deposits", f"${_total_deposits:,.2f}")
        _rb3.metric("Total Draws", f"${_total_draws:,.2f}")

        if _ret_balance < 500 and _total_deposits > 0:
            st.warning("\u26a0\ufe0f Retainer balance is low. Consider requesting a replenishment.")
        elif _ret_balance <= 0 and _total_deposits > 0:
            st.error("\U0001f6a8 Retainer balance is exhausted!")

        st.markdown("---")

        # Deposit form
        st.markdown("### \u2795 Record Deposit")
        _rd1, _rd2 = st.columns(2)
        with _rd1:
            _dep_amount = st.number_input(
                "Deposit Amount ($)", min_value=0.0, value=0.0, step=100.0, key="_ret_dep_amount",
            )
            _dep_date = st.date_input("Date", value=datetime.now().date(), key="_ret_dep_date")
        with _rd2:
            _dep_note = st.text_area("Note", placeholder="Retainer deposit details...", key="_ret_dep_note", height=80)

        if st.button(
            "\U0001f4b0 Record Deposit", type="primary", key="_ret_dep_btn", use_container_width=True,
        ):
            if _dep_amount > 0:
                billing.add_retainer_deposit(
                    _ret_case_id, _dep_amount, _dep_date.strftime("%Y-%m-%d"), _dep_note.strip(),
                )
                st.success(f"\u2705 Deposit of ${_dep_amount:,.2f} recorded!")
                st.rerun()
            else:
                st.warning("Amount must be greater than $0.")

        # Draw form
        st.markdown("---")
        st.markdown("### \U0001f4c9 Record Draw / Application")
        _rw1, _rw2 = st.columns(2)
        with _rw1:
            _draw_amount = st.number_input(
                "Draw Amount ($)", min_value=0.0, value=0.0, step=50.0, key="_ret_draw_amount",
            )
            _draw_date = st.date_input("Date", value=datetime.now().date(), key="_ret_draw_date")
        with _rw2:
            _draw_note = st.text_area(
                "Note", placeholder="Services applied to retainer...", key="_ret_draw_note", height=80,
            )

        if st.button(
            "\U0001f4c9 Record Draw", key="_ret_draw_btn", use_container_width=True,
        ):
            if _draw_amount > 0:
                billing.add_retainer_draw(
                    _ret_case_id, _draw_amount, _draw_date.strftime("%Y-%m-%d"), _draw_note.strip(),
                )
                st.success(f"Draw of ${_draw_amount:,.2f} recorded!")
                st.rerun()
            else:
                st.warning("Amount must be greater than $0.")

        # History
        st.markdown("---")
        st.markdown("### \U0001f4cb Retainer History")
        if _ret_history:
            _running_bal = 0.0
            for _rh in _ret_history:
                _rh_type = _rh.get("type", "deposit")
                _rh_amt = _rh.get("amount", 0)
                if _rh_type == "deposit":
                    _running_bal += _rh_amt
                    _rh_icon = "\U0001f7e2"
                    _rh_sign = "+"
                else:
                    _running_bal -= _rh_amt
                    _rh_icon = "\U0001f534"
                    _rh_sign = "-"
                st.markdown(
                    f"{_rh_icon} **{_rh_sign}${_rh_amt:,.2f}** \u2014 "
                    f"{_rh.get('date', '')} \u2014 Bal: ${_running_bal:,.2f}  \n"
                    f"<small style='color:#888'>{_rh.get('note', '')}</small>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No retainer history. Record a deposit to get started.")

    # -- 4. Payments & Aging ---------------------------------------------------
    with tabs[3]:  # Payments & Aging
        st.markdown("## \U0001f4b3 Payments & Aging Report")
        _pa_case_id = st.session_state.current_case_id

        _pay_sub1, _pay_sub2 = st.tabs(["\U0001f4b3 Record Payment", "\U0001f4ca Aging Report"])

        with _pay_sub1:
            st.markdown("### Record Payment Against Invoice")
            _all_invs = billing.load_invoices()
            _case_invs = [i for i in _all_invs if i.get("case_id") == _pa_case_id]
            _unpaid_invs = [i for i in _case_invs if i.get("status") not in ("paid", "void")]

            if not _unpaid_invs:
                st.info("\u2705 No outstanding invoices for this case.")
            else:
                _inv_options = {
                    i["id"]: f"{i['id']} \u2014 ${i.get('total', 0):,.2f} ({i.get('status', 'draft')})"
                    for i in _unpaid_invs
                }
                _sel_inv_id = st.selectbox(
                    "Select Invoice",
                    list(_inv_options.keys()),
                    format_func=lambda x: _inv_options.get(x, x),
                    key="_pay_inv_select",
                )

                if _sel_inv_id:
                    _inv_bal = billing.get_invoice_balance(_sel_inv_id)
                    st.metric("Balance Due", f"${_inv_bal:,.2f}")

                    _pc1, _pc2 = st.columns(2)
                    with _pc1:
                        _pay_amt = st.number_input(
                            "Payment Amount ($)", min_value=0.0,
                            value=float(_inv_bal) if _inv_bal > 0 else 0.0,
                            step=50.0, key="_pay_amount",
                        )
                        _pay_date = st.date_input("Payment Date", value=datetime.now().date(), key="_pay_date")
                    with _pc2:
                        _pay_method = st.selectbox(
                            "Payment Method",
                            ["Check", "Wire Transfer", "Credit Card", "Cash", "ACH", "Other"],
                            key="_pay_method",
                        )
                        _pay_note = st.text_input("Note", placeholder="Check #, reference...", key="_pay_note")

                    if st.button(
                        "\U0001f4b3 Record Payment", type="primary", key="_pay_record_btn",
                        use_container_width=True,
                    ):
                        if _pay_amt > 0:
                            billing.record_payment(
                                _sel_inv_id, _pay_amt,
                                _pay_date.strftime("%Y-%m-%d"),
                                _pay_method, _pay_note.strip(),
                            )
                            st.success(f"\u2705 Payment of ${_pay_amt:,.2f} recorded!")
                            # Auto-mark as paid if balance reaches 0
                            _new_bal = billing.get_invoice_balance(_sel_inv_id)
                            if _new_bal <= 0:
                                billing.update_invoice_status(_sel_inv_id, "paid")
                                st.info("Invoice automatically marked as Paid (balance = $0).")
                            st.rerun()
                        else:
                            st.warning("Payment amount must be greater than $0.")

                    # Payment history for selected invoice
                    _pay_hist = billing.get_payment_history(_sel_inv_id)
                    if _pay_hist:
                        st.markdown("---")
                        st.markdown("### Payment History")
                        for _ph in _pay_hist:
                            st.markdown(
                                f"\u2705 **${_ph.get('amount', 0):,.2f}** \u2014 "
                                f"{_ph.get('date', '')} \u2014 {_ph.get('method', '')}  \n"
                                f"<small style='color:#888'>{_ph.get('note', '')}</small>",
                                unsafe_allow_html=True,
                            )

        with _pay_sub2:
            st.markdown("### Aging Report")
            st.caption("Outstanding invoices grouped by age.")

            _aging = billing.get_aging_report(_pa_case_id)

            # Summary metrics
            _ag1, _ag2, _ag3, _ag4 = st.columns(4)
            _ag1.metric("Current (0-30d)", f"${_aging.get('current', 0):,.2f}")
            _ag2.metric("31-60 Days", f"${_aging.get('31_60', 0):,.2f}")
            _ag3.metric("61-90 Days", f"${_aging.get('61_90', 0):,.2f}")
            _ag4.metric("90+ Days", f"${_aging.get('90_plus', 0):,.2f}")

            _total_outstanding = sum([
                _aging.get("current", 0),
                _aging.get("31_60", 0),
                _aging.get("61_90", 0),
                _aging.get("90_plus", 0),
            ])
            st.markdown(f"**Total Outstanding: ${_total_outstanding:,.2f}**")

            if _aging.get("90_plus", 0) > 0:
                st.error("\U0001f6a8 You have invoices over 90 days past due!")
            elif _aging.get("61_90", 0) > 0:
                st.warning("\u26a0\ufe0f Some invoices are 61-90 days past due.")

            # Detail by bucket
            _inv_details = _aging.get("invoices", [])
            if _inv_details:
                st.markdown("---")
                for _inv in _inv_details:
                    _days = _inv.get("days_outstanding", 0)
                    _color = (
                        "\U0001f534" if _days > 90
                        else "\U0001f7e0" if _days > 60
                        else "\U0001f7e1" if _days > 30
                        else "\U0001f7e2"
                    )
                    st.markdown(
                        f"{_color} **{_inv.get('id', '')}** \u2014 "
                        f"${_inv.get('balance', 0):,.2f} outstanding \u2014 "
                        f"{_days} days \u2014 {_inv.get('status', 'draft')}"
                    )
            else:
                st.success("\u2705 No outstanding invoices!")

    # -- 5. Invoices -----------------------------------------------------------
    with tabs[4]:  # Invoices (was tabs[2])
        st.markdown("## \U0001f4c4 Invoices")
        _inv_case_id = st.session_state.current_case_id

        _inv_sub1, _inv_sub2 = st.tabs(["\U0001f4c4 Invoice List", "\u2795 Create Invoice"])

        with _inv_sub2:
            st.markdown("### Create New Invoice")
            st.caption("Pull unbilled time entries and expenses into a new invoice.")

            _unbilled_time = billing.get_unbilled_time(_inv_case_id)
            _unbilled_exp = billing.get_unbilled_expenses(_inv_case_id)

            if not _unbilled_time and not _unbilled_exp:
                st.info("\u2705 No unbilled items for this case. All time entries and expenses have been invoiced.")
            else:
                # Show unbilled time entries
                if _unbilled_time:
                    st.markdown("#### \u23f1\ufe0f Unbilled Time Entries")
                    _selected_time_ids = []
                    for _ut in _unbilled_time:
                        _ut_total = _ut.get("duration_hours", 0) * _ut.get("rate", 0)
                        _checked = st.checkbox(
                            f"{_ut.get('date', '')} — {_ut.get('duration_hours', 0):.2f}h \u00d7 "
                            f"${_ut.get('rate', 0):,.0f} = **${_ut_total:,.2f}** — {_ut.get('description', '')[:60]}",
                            value=True,
                            key=f"_inv_te_{_ut.get('id')}"
                        )
                        if _checked:
                            _selected_time_ids.append(_ut.get("id"))
                    _time_subtotal = sum(
                        t.get("duration_hours", 0) * t.get("rate", 0)
                        for t in _unbilled_time if t.get("id") in _selected_time_ids
                    )
                    st.markdown(f"**Selected Fees:** ${_time_subtotal:,.2f}")
                else:
                    _selected_time_ids = []
                    _time_subtotal = 0

                st.markdown("---")

                # Show unbilled expenses
                if _unbilled_exp:
                    st.markdown("#### \U0001f4b5 Unbilled Expenses")
                    _selected_exp_ids = []
                    for _ue in _unbilled_exp:
                        _checked = st.checkbox(
                            f"{_ue.get('date', '')} — ${_ue.get('amount', 0):,.2f} — "
                            f"{_ue.get('category', '')} — {_ue.get('description', '')[:60]}",
                            value=True,
                            key=f"_inv_ex_{_ue.get('id')}"
                        )
                        if _checked:
                            _selected_exp_ids.append(_ue.get("id"))
                    _exp_subtotal = sum(
                        e.get("amount", 0)
                        for e in _unbilled_exp if e.get("id") in _selected_exp_ids
                    )
                    st.markdown(f"**Selected Expenses:** ${_exp_subtotal:,.2f}")
                else:
                    _selected_exp_ids = []
                    _exp_subtotal = 0

                st.markdown("---")

                # Invoice total
                _inv_total = _time_subtotal + _exp_subtotal
                st.markdown(f"### \U0001f4b0 Invoice Total: ${_inv_total:,.2f}")

                _inv_notes = st.text_area("Invoice Notes", value=billing.load_billing_settings().get("invoice_notes", ""), key="_inv_notes")

                _case_name = case_mgr.get_case_name(_inv_case_id) if _inv_case_id else ""
                _client_nm = ""
                if "agent_results" in st.session_state and st.session_state.agent_results:
                    _client_nm = st.session_state.agent_results.get("client_name", "")

                if st.button("\U0001f4c4 Generate Invoice", type="primary", key="_inv_create", use_container_width=True):
                    if _selected_time_ids or _selected_exp_ids:
                        _new_inv = billing.create_invoice(
                            case_id=_inv_case_id,
                            time_entry_ids=_selected_time_ids,
                            expense_ids=_selected_exp_ids,
                            notes=_inv_notes,
                            case_name=_case_name,
                            client_name=_client_nm,
                        )
                        st.success(f"\u2705 Invoice **{_new_inv['id']}** created for ${_new_inv['total']:,.2f}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.warning("Select at least one item to invoice.")

        with _inv_sub1:
            st.markdown("### Invoice History")

            _all_invoices = billing.load_invoices()
            _case_invoices = [i for i in _all_invoices if i.get("case_id") == _inv_case_id]

            _show_all = st.checkbox("Show invoices from all cases", value=False, key="_inv_show_all")
            _display_invoices = _all_invoices if _show_all else _case_invoices

            if _display_invoices:
                # Status summary
                _status_counts = {}
                for _inv in _display_invoices:
                    _s = _inv.get("status", "draft")
                    _status_counts[_s] = _status_counts.get(_s, 0) + 1

                _status_cols = st.columns(len(_status_counts))
                _status_colors = {"draft": "\U0001f535", "sent": "\U0001f4e4", "paid": "\u2705", "overdue": "\U0001f534", "void": "\u26ab"}
                for _si, (_status, _count) in enumerate(_status_counts.items()):
                    with _status_cols[_si]:
                        st.metric(f"{_status_colors.get(_status, '\u26aa')} {_status.title()}", _count)

                st.markdown("---")

                for _inv in _display_invoices:
                    _inv_status = _inv.get("status", "draft")
                    _status_badge = {
                        "draft": "\U0001f535 Draft",
                        "sent": "\U0001f4e4 Sent",
                        "paid": "\u2705 Paid",
                        "overdue": "\U0001f534 Overdue",
                        "void": "\u26ab Void",
                    }.get(_inv_status, _inv_status)

                    with st.expander(
                        f"{_status_badge} | {_inv.get('id', '')} | {_inv.get('date_created', '')} | "
                        f"${_inv.get('total', 0):,.2f} | {_inv.get('case_name', _inv.get('case_id', ''))}",
                        expanded=False
                    ):
                        _ic1, _ic2, _ic3 = st.columns(3)
                        _ic1.markdown(f"**Invoice:** {_inv.get('id')}")
                        _ic2.markdown(f"**Created:** {_inv.get('date_created')}")
                        _ic3.markdown(f"**Due:** {_inv.get('due_date')}")

                        st.markdown(f"**Case:** {_inv.get('case_name', _inv.get('case_id', ''))}")
                        if _inv.get("client_name"):
                            st.markdown(f"**Client:** {_inv.get('client_name')}")

                        _id1, _id2, _id3 = st.columns(3)
                        _id1.metric("Fees", f"${_inv.get('subtotal_fees', 0):,.2f}")
                        _id2.metric("Expenses", f"${_inv.get('subtotal_expenses', 0):,.2f}")
                        _id3.metric("Total", f"${_inv.get('total', 0):,.2f}")

                        if _inv.get("total_hours"):
                            st.caption(f"Total Hours: {_inv.get('total_hours', 0):.2f}")
                        if _inv.get("notes"):
                            st.caption(f"Notes: {_inv.get('notes')}")

                        # Status actions
                        if _inv_status not in ("paid", "void"):
                            _act1, _act2, _act3 = st.columns(3)
                            with _act1:
                                if _inv_status == "draft" and st.button("\U0001f4e4 Mark Sent", key=f"_inv_send_{_inv.get('id')}"):
                                    billing.update_invoice_status(_inv.get("id"), "sent")
                                    st.success("Marked as Sent!")
                                    st.rerun()
                            with _act2:
                                if _inv_status in ("sent", "overdue") and st.button("\u2705 Mark Paid", key=f"_inv_paid_{_inv.get('id')}"):
                                    billing.update_invoice_status(_inv.get("id"), "paid")
                                    st.success("Marked as Paid!")
                                    st.rerun()
                            with _act3:
                                if st.button("\u26ab Void", key=f"_inv_void_{_inv.get('id')}"):
                                    billing.void_invoice(_inv.get("id"))
                                    st.warning("Invoice voided. Items are now unbilled again.")
                                    st.rerun()

                        # -- Export / Email buttons --
                        st.markdown("---")
                        _exp1, _exp2 = st.columns(2)
                        with _exp1:
                            _pdf_buf = billing.generate_invoice_pdf(_inv.get("id", ""))
                            if _pdf_buf:
                                st.download_button(
                                    "\U0001f4e5 Download PDF",
                                    data=_pdf_buf,
                                    file_name=f"{_inv.get('id', 'invoice')}.pdf",
                                    mime="application/pdf",
                                    key=f"_inv_dl_{_inv.get('id')}",
                                    use_container_width=True,
                                )
                        with _exp2:
                            with st.popover("\U0001f4e7 Email Invoice", use_container_width=True):
                                _em_addr = st.text_input(
                                    "Recipient Email",
                                    placeholder="client@example.com",
                                    key=f"_inv_email_addr_{_inv.get('id')}",
                                )
                                if st.button("Send", key=f"_inv_email_send_{_inv.get('id')}", type="primary", use_container_width=True):
                                    if _em_addr:
                                        _result = billing.email_invoice(_inv.get("id", ""), _em_addr)
                                        if _result.get("ok"):
                                            st.success(_result["message"])
                                        else:
                                            st.error(_result["message"])
                                    else:
                                        st.warning("Enter a recipient email address.")
            else:
                st.info("No invoices yet. Create one from unbilled time and expenses.")

    # -- 6. Billing Settings ---------------------------------------------------
    with tabs[5]:  # Billing Settings (was tabs[3])
        st.markdown("## \u2699\ufe0f Billing Settings")
        st.caption("Configure your firm's billing defaults.")

        _bs = billing.load_billing_settings()

        st.markdown("### \U0001f3e2 Firm Information")
        _bs_firm = st.text_input("Firm Name", value=_bs.get("firm_name", ""), key="_bs_firm")
        _bs_addr = st.text_area("Firm Address", value=_bs.get("firm_address", ""), key="_bs_addr", height=80)
        _bs1, _bs2 = st.columns(2)
        with _bs1:
            _bs_phone = st.text_input("Phone", value=_bs.get("firm_phone", ""), key="_bs_phone")
        with _bs2:
            _bs_email = st.text_input("Email", value=_bs.get("firm_email", ""), key="_bs_email")

        st.markdown("---")
        st.markdown("### \U0001f4b0 Rate & Terms")
        _br1, _br2, _br3 = st.columns(3)
        with _br1:
            _bs_rate = st.number_input("Default Hourly Rate ($)", min_value=0.0, value=float(_bs.get("default_rate", 350.0)), step=25.0, key="_bs_rate")
        with _br2:
            _bs_terms = st.number_input("Payment Terms (days)", min_value=1, value=int(_bs.get("payment_terms_days", 30)), step=1, key="_bs_terms")
        with _br3:
            _bs_tax = st.number_input("Tax Rate (%)", min_value=0.0, max_value=100.0, value=float(_bs.get("tax_rate", 0.0)), step=0.5, key="_bs_tax")

        _bs_notes = st.text_area("Default Invoice Notes", value=_bs.get("invoice_notes", ""), key="_bs_notes", height=80)

        st.markdown("---")
        st.markdown("### \U0001f4e7 Email (SMTP) Settings")
        st.caption("Configure SMTP to send invoice PDFs directly from the app.")
        _smtp1, _smtp2 = st.columns(2)
        with _smtp1:
            _bs_smtp_host = st.text_input("SMTP Host", value=_bs.get("smtp_host", ""), key="_bs_smtp_host", placeholder="smtp.gmail.com")
        with _smtp2:
            _bs_smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=int(_bs.get("smtp_port", 587)), key="_bs_smtp_port")
        _smtp3, _smtp4 = st.columns(2)
        with _smtp3:
            _bs_smtp_user = st.text_input("SMTP Username", value=_bs.get("smtp_user", ""), key="_bs_smtp_user")
        with _smtp4:
            _bs_smtp_pass = st.text_input("SMTP Password", value=_bs.get("smtp_password", ""), key="_bs_smtp_pass", type="password")
        _bs_from_email = st.text_input("From Email", value=_bs.get("from_email", ""), key="_bs_from_email", placeholder="billing@firm.com")

        st.markdown("---")
        st.markdown("### \U0001f4ca Billing Status")
        st.caption(f"Next invoice number: **TLO-B{_bs.get('next_invoice_seq', 1):04d}**")

        if st.button("\U0001f4be Save Settings", type="primary", key="_bs_save", use_container_width=True):
            _updated = {
                "firm_name": _bs_firm,
                "firm_address": _bs_addr,
                "firm_phone": _bs_phone,
                "firm_email": _bs_email,
                "default_rate": _bs_rate,
                "payment_terms_days": int(_bs_terms),
                "tax_rate": _bs_tax,
                "invoice_notes": _bs_notes,
                "smtp_host": _bs_smtp_host,
                "smtp_port": int(_bs_smtp_port),
                "smtp_user": _bs_smtp_user,
                "smtp_password": _bs_smtp_pass,
                "from_email": _bs_from_email,
                "next_invoice_seq": _bs.get("next_invoice_seq", 1),
            }
            billing.save_billing_settings(_updated)
            st.success("\u2705 Billing settings saved!")
            st.rerun()

        # ---- API Usage History ----
        st.markdown("---")
        st.markdown("### 🤖 AI API Usage History")
        st.caption("Actual token usage and costs from AI analysis runs.")

        _prep_id = ctx.get("prep_id") or st.session_state.get("current_prep_id")
        if _prep_id:
            _cost_history = case_mgr.get_cost_history(case_id, _prep_id)
            if _cost_history:
                _total_cost = 0.0
                _total_in = 0
                _total_out = 0

                for _ch in reversed(_cost_history):
                    _ch_action = _ch.get("action", "Analysis")
                    _ch_model = _ch.get("model", "unknown")
                    _ch_cost = _ch.get("cost", 0)
                    _ch_time = _ch.get("timestamp", "")[:16]
                    _ch_in = _ch.get("input_tokens", 0)
                    _ch_out = _ch.get("output_tokens", 0)
                    _ch_total = _ch.get("total_tokens", _ch.get("tokens", 0))
                    _ch_nodes = _ch.get("nodes_completed", "")
                    _ch_calls = _ch.get("api_calls", "")

                    _total_cost += _ch_cost
                    _total_in += _ch_in
                    _total_out += _ch_out

                    with st.expander(
                        f"{'📊' if _ch_in else '📋'} {_ch_action} — **${_ch_cost:.4f}** — {_ch_time}",
                        expanded=False,
                    ):
                        _uc1, _uc2, _uc3, _uc4 = st.columns(4)
                        _uc1.metric("Input Tokens", f"{_ch_in:,}" if _ch_in else "—")
                        _uc2.metric("Output Tokens", f"{_ch_out:,}" if _ch_out else "—")
                        _uc3.metric("Total Tokens", f"{_ch_total:,}" if _ch_total else "—")
                        _uc4.metric("Cost", f"${_ch_cost:.4f}")
                        st.caption(
                            f"Model: {_ch_model}"
                            + (f" · {_ch_nodes} nodes" if _ch_nodes else "")
                            + (f" · {_ch_calls} API calls" if _ch_calls else "")
                        )
                        if _ch_in:
                            st.caption("✅ Actual token counts from API")
                        else:
                            st.caption("📋 Estimated token counts")

                # Summary
                st.markdown(
                    f"**Total API Cost (this prep):** ${_total_cost:.4f}"
                    + (f" · {_total_in:,} input + {_total_out:,} output tokens" if _total_in else "")
                )
            else:
                st.info("No analysis cost data yet. Run an analysis to see API usage here.")
        else:
            st.info("Select a case preparation to see API usage history.")
