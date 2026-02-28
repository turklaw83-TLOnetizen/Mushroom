"""E-Signature UI module — ported from legacy ui_modules/esign_ui.py."""
import logging
import os
import streamlit as st
from datetime import datetime

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, results, **ctx):
    """Render all tabs for the E-Signature nav group."""
    tabs = ctx.get("tabs", [])

    # Lazy imports for graceful degradation
    try:
        from core.esign import ESignManager, sdk_available, api_key_configured, status_badge
    except ImportError:
        st.error("\u26a0\ufe0f E-Signature module not found. Ensure `core/esign.py` is in the project.")
        return

    DATA_DIR = os.path.join("data", "cases")
    case_dir = os.path.join(DATA_DIR, case_id)

    # ====================================================================
    #  TAB 0 -- Send for Signature
    # ====================================================================
    with tabs[0]:
        st.markdown("## \U0001f4e8 Send for Signature")

        # -- Config check --
        _sdk_ok = sdk_available()
        _key_ok = api_key_configured()

        if not _sdk_ok or not _key_ok:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1e1e2e 0%, #2d1b69 100%);
                        border-radius: 12px; padding: 24px; margin-bottom: 16px;
                        border: 1px solid rgba(255,255,255,0.1);">
                <h3 style="margin: 0 0 12px 0;">\u2699\ufe0f Setup Required</h3>
                <p style="opacity: 0.8; margin: 0 0 16px 0;">
                    E-Signature integration needs a quick one-time setup:
                </p>
            """, unsafe_allow_html=True)

            if not _sdk_ok:
                st.markdown("""
                <div style="background: rgba(255,255,255,0.05); border-radius: 8px;
                            padding: 12px 16px; margin-bottom: 8px;">
                    <b>1. Install the SDK</b><br>
                    <code style="background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px;">
                        pip install dropbox-sign
                    </code>
                </div>
                """, unsafe_allow_html=True)

            if not _key_ok:
                st.markdown("""
                <div style="background: rgba(255,255,255,0.05); border-radius: 8px;
                            padding: 12px 16px; margin-bottom: 8px;">
                    <b>2. Add your API key</b><br>
                    Add to your <code>.env</code> file:<br>
                    <code style="background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px;">
                        DROPBOX_SIGN_API_KEY=your_api_key_here
                    </code><br>
                    <span style="opacity: 0.6; font-size: 12px;">
                        Get a free test key at
                        <a href="https://app.hellosign.com/api" target="_blank">app.hellosign.com/api</a>
                    </span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        # -- Document picker --
        st.markdown("### \U0001f4c4 Select Document")
        _case_files = case_mgr.get_case_files(case_id) or []
        _signable_exts = {".pdf", ".docx"}
        _signable_files = [
            f for f in _case_files
            if os.path.splitext(f)[1].lower() in _signable_exts
        ]

        if not _signable_files:
            st.info("\U0001f4c2 No PDF or DOCX files in this case. Upload documents first.")
        else:
            _file_names = [os.path.basename(f) for f in _signable_files]
            _selected_idx = st.selectbox(
                "Choose a document to send for signature",
                range(len(_file_names)),
                format_func=lambda i: f"\U0001f4c4 {_file_names[i]}",
                key="esign_file_picker",
            )
            _selected_file = _signable_files[_selected_idx]

            # File info card
            try:
                _fsize = os.path.getsize(_selected_file)
                _size_str = f"{_fsize / (1024*1024):.1f} MB" if _fsize > 1024*1024 else f"{_fsize / 1024:.0f} KB"
            except OSError:
                _size_str = "unknown size"

            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.03); border-radius: 8px;
                        padding: 12px 16px; border: 1px solid rgba(255,255,255,0.08);
                        margin: 8px 0 16px 0; font-size: 13px;">
                \U0001f4ce <b>{_file_names[_selected_idx]}</b> &nbsp;\u00b7&nbsp; {_size_str}
            </div>
            """, unsafe_allow_html=True)

            # -- Signers --
            st.markdown("### \U0001f465 Signers")

            # Dynamic signer count
            _num_signers = st.number_input(
                "Number of signers", min_value=1, max_value=10, value=1,
                key="esign_num_signers",
            )

            _signers = []
            for _si in range(int(_num_signers)):
                _sc1, _sc2 = st.columns(2)
                with _sc1:
                    _sname = st.text_input(
                        f"Name", key=f"esign_signer_name_{_si}",
                        placeholder=f"Signer {_si+1} full name",
                    )
                with _sc2:
                    _semail = st.text_input(
                        f"Email", key=f"esign_signer_email_{_si}",
                        placeholder=f"signer{_si+1}@example.com",
                    )
                if _sname and _semail:
                    _signers.append({
                        "name": _sname,
                        "email_address": _semail,
                        "order": _si,
                    })

            # -- Message --
            st.markdown("### \U0001f4ac Message to Signers")
            _title = st.text_input(
                "Title", value=_file_names[_selected_idx],
                key="esign_title",
            )
            _subject = st.text_input(
                "Email subject",
                value=f"Signature requested: {_file_names[_selected_idx]}",
                key="esign_subject",
            )
            _message = st.text_area(
                "Message",
                value="Please review and sign the attached document at your earliest convenience.",
                key="esign_message",
                height=80,
            )

            # -- Test mode toggle --
            _test_mode = st.checkbox(
                "\U0001f9ea Test mode (free, watermarked \u2014 no real signatures)",
                value=True,
                key="esign_test_mode",
            )

            # -- Send button --
            st.divider()
            _can_send = (
                _sdk_ok and _key_ok
                and len(_signers) > 0
                and all(s.get("email_address") for s in _signers)
            )

            _send_col1, _send_col2 = st.columns([3, 1])
            with _send_col1:
                if not _can_send:
                    if not _sdk_ok or not _key_ok:
                        st.caption("\u2699\ufe0f Complete the setup above to enable sending.")
                    elif len(_signers) == 0:
                        st.caption("\U0001f446 Add at least one signer with name and email.")

            with _send_col2:
                if st.button(
                    "\U0001f4e8 Send for Signature",
                    disabled=not _can_send,
                    use_container_width=True,
                    type="primary",
                    key="esign_send_btn",
                ):
                    mgr = ESignManager(case_dir)
                    with st.spinner("Sending signature request..."):
                        result = mgr.send_request(
                            file_path=_selected_file,
                            signers=_signers,
                            title=_title,
                            subject=_subject,
                            message=_message,
                            test_mode=_test_mode,
                        )

                    if result.get("status") == "sent":
                        st.toast("\u2705 Signature request sent successfully!", icon="\U0001f4e8")
                        st.balloons()
                    elif result.get("status") == "not_configured":
                        st.warning("\u2699\ufe0f Request saved locally but not sent \u2014 API not configured.")
                    else:
                        st.error(f"\u26a0\ufe0f Error: {result.get('error', 'Unknown error')}")

    # ====================================================================
    #  TAB 1 -- Request Tracker
    # ====================================================================
    with tabs[1]:
        st.markdown("## \U0001f4ca Signature Request Tracker")

        mgr = ESignManager(case_dir)
        _requests = mgr.list_requests()

        if not _requests:
            st.markdown("""
            <div style="text-align: center; padding: 48px 24px; opacity: 0.5;">
                <div style="font-size: 48px;">\u270d\ufe0f</div>
                <p style="margin-top: 12px;">No signature requests yet.<br>
                Send a document from the <b>\U0001f4e8 Send</b> tab to get started.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Refresh statuses button
            _rc1, _rc2 = st.columns([3, 1])
            with _rc2:
                if st.button("\U0001f504 Refresh All", key="esign_refresh_all"):
                    with st.spinner("Checking statuses..."):
                        mgr.refresh_all_statuses()
                    st.rerun()

            with _rc1:
                _active = mgr.get_active_count()
                st.caption(f"\U0001f4ca {len(_requests)} total request{'s' if len(_requests) != 1 else ''} \u00b7 {_active} active")

            # Request cards
            for _ri, _req in enumerate(_requests):
                _badge = status_badge(_req.get("status", "unknown"))
                _created = _req.get("created_at", "")
                try:
                    _created_dt = datetime.fromisoformat(_created)
                    _created_str = _created_dt.strftime("%b %d, %Y at %I:%M %p")
                except Exception:
                    _created_str = _created

                _signer_names = ", ".join(
                    s.get("name", "Unknown") for s in _req.get("signers", [])
                )

                # Card styling based on status
                _status = _req.get("status", "")
                if _status == "signed":
                    _border_color = "rgba(76, 175, 80, 0.4)"
                    _bg = "rgba(76, 175, 80, 0.05)"
                elif _status in ("sent", "viewed"):
                    _border_color = "rgba(33, 150, 243, 0.4)"
                    _bg = "rgba(33, 150, 243, 0.05)"
                elif _status in ("error", "declined"):
                    _border_color = "rgba(244, 67, 54, 0.4)"
                    _bg = "rgba(244, 67, 54, 0.05)"
                elif _status == "cancelled":
                    _border_color = "rgba(158, 158, 158, 0.4)"
                    _bg = "rgba(158, 158, 158, 0.05)"
                else:
                    _border_color = "rgba(255, 255, 255, 0.1)"
                    _bg = "rgba(255, 255, 255, 0.03)"

                st.markdown(f"""
                <div style="background: {_bg}; border: 1px solid {_border_color};
                            border-radius: 10px; padding: 16px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <b style="font-size: 15px;">\U0001f4c4 {_req.get('filename', 'Document')}</b>
                        <span style="font-size: 14px;">{_badge}</span>
                    </div>
                    <div style="font-size: 12px; opacity: 0.7;">
                        \U0001f465 {_signer_names} &nbsp;\u00b7&nbsp; \U0001f550 {_created_str}
                        {' &nbsp;\u00b7&nbsp; \U0001f9ea Test mode' if _req.get('test_mode') else ''}
                    </div>
                    {f'<div style="font-size: 12px; color: #f44336; margin-top: 4px;">\u26a0\ufe0f {_req.get("error", "")}</div>' if _req.get("error") and _status == "error" else ''}
                </div>
                """, unsafe_allow_html=True)

                # Action buttons
                _ac1, _ac2, _ac3 = st.columns(3)

                with _ac1:
                    if _status in ("sent", "viewed", "pending") and st.button(
                        "\U0001f504 Refresh", key=f"esign_refresh_{_ri}",
                    ):
                        mgr.get_request_status(_req["local_id"])
                        st.rerun()

                with _ac2:
                    if _status == "signed" and st.button(
                        "\U0001f4e5 Download Signed", key=f"esign_download_{_ri}",
                    ):
                        with st.spinner("Downloading signed copy..."):
                            path = mgr.download_signed(_req["local_id"])
                        if path:
                            st.toast(f"\u2705 Saved: {os.path.basename(path)}", icon="\U0001f4e5")
                        else:
                            st.warning("\u26a0\ufe0f Could not download signed file.")

                with _ac3:
                    if _status in ("sent", "viewed", "pending") and st.button(
                        "\U0001f6ab Cancel", key=f"esign_cancel_{_ri}",
                        type="secondary",
                    ):
                        mgr.cancel_request(_req["local_id"])
                        st.toast("\U0001f6ab Request cancelled.", icon="\U0001f6ab")
                        st.rerun()

    # ====================================================================
    #  TAB 2 -- E-Sign Settings
    # ====================================================================
    with tabs[2]:
        st.markdown("## \u2699\ufe0f E-Signature Settings")

        # Status dashboard
        _sdk_ok = sdk_available()
        _key_ok = api_key_configured()

        st.markdown("### \U0001f50c Integration Status")
        _s1, _s2 = st.columns(2)
        with _s1:
            if _sdk_ok:
                st.success("\u2705 **Dropbox Sign SDK** installed")
            else:
                st.error("\u274c **Dropbox Sign SDK** not installed")
                st.code("pip install dropbox-sign", language="bash")

        with _s2:
            if _key_ok:
                st.success("\u2705 **API Key** configured")
            else:
                st.error("\u274c **API Key** not configured")
                st.caption("Add `DROPBOX_SIGN_API_KEY=...` to your `.env` file")

        st.divider()

        # API key info
        st.markdown("### \U0001f511 API Key Setup")
        st.markdown("""
        <div style="background: rgba(255,255,255,0.03); border-radius: 10px;
                    padding: 16px; border: 1px solid rgba(255,255,255,0.08);">
            <p style="margin: 0 0 8px 0;"><b>How to get your Dropbox Sign API key:</b></p>
            <ol style="margin: 0; padding-left: 20px; opacity: 0.8; line-height: 1.8;">
                <li>Go to <a href="https://app.hellosign.com/api" target="_blank">app.hellosign.com/api</a></li>
                <li>Sign in or create a free account</li>
                <li>Navigate to <b>API</b> &rarr; <b>Settings</b></li>
                <li>Copy your API key</li>
                <li>Add it to your <code>.env</code> file as: <code>DROPBOX_SIGN_API_KEY=your_key</code></li>
                <li>Restart the app</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Stats
        st.markdown("### \U0001f4ca Case Statistics")
        mgr = ESignManager(case_dir)
        _all = mgr.list_requests()
        _by_status = {}
        for _r in _all:
            _s = _r.get("status", "unknown")
            _by_status[_s] = _by_status.get(_s, 0) + 1

        if _by_status:
            _stat_cols = st.columns(min(len(_by_status), 4))
            for _ci, (_stat, _count) in enumerate(_by_status.items()):
                with _stat_cols[_ci % len(_stat_cols)]:
                    _badge = status_badge(_stat)
                    st.metric(_badge, _count)
        else:
            st.caption("No signature requests for this case yet.")

        st.divider()

        st.markdown("""
        <div style="font-size: 12px; opacity: 0.5; text-align: center; padding: 12px;">
            Powered by <a href="https://www.hellosign.com" target="_blank">Dropbox Sign</a>
            &nbsp;\u00b7&nbsp; Test mode requests are free and watermarked
        </div>
        """, unsafe_allow_html=True)
