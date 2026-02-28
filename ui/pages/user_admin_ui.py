"""User Admin UI module — ported from legacy ui_modules/user_admin_ui.py."""
import logging
import streamlit as st

from core.user_profiles import UserManager, ROLES, ROLE_LABELS

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, results, **ctx):
    """Render the User Admin panel."""
    tabs = ctx.get("tabs", [])
    user_mgr = UserManager()

    # Access check -- only admins
    current_user = st.session_state.get("current_user")
    if not current_user or current_user.get("role") != "admin":
        st.warning("\u26a0\ufe0f You must be an **admin** to access User Management.")
        return

    # tabs from router.py are already st.tabs() objects (DeltaGenerators)
    tab_objs = tabs if tabs else [st.container()]

    # ================================================================
    #  TAB 1 -- Team Roster
    # ================================================================
    with tab_objs[0]:
        st.markdown("### \U0001f465 Team Roster")
        users = user_mgr.list_users(include_inactive=True)
        stats = user_mgr.get_team_stats()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", stats["total"])
        c2.metric("Admins", stats["admins"])
        c3.metric("Attorneys", stats["attorneys"])
        c4.metric("Paralegals", stats["paralegals"])
        st.divider()

        for u in users:
            is_active = u.get("active", True)
            role_label = ROLE_LABELS.get(u.get("role", ""), u.get("role", ""))
            status_dot = "\U0001f7e2" if is_active else "\U0001f534"
            initials = u.get("initials", "?")
            name = u.get("name", "Unknown")
            uid = u["id"]

            with st.expander(f"{status_dot} **{initials}** \u2014 {name}  \u00b7  {role_label}", expanded=False):
                col_info, col_actions = st.columns([2, 1])

                with col_info:
                    st.caption(f"**ID:** `{uid}`")
                    st.caption(f"**Email:** {u.get('email', '\u2014') or '\u2014'}")
                    g_email = u.get("google_email", "") or ""
                    st.caption(f"**Google Account:** {g_email if g_email else '\u2014 not linked'}")
                    login = u.get("last_login")
                    st.caption(f"**Last Login:** {login[:16] if login else 'Never'}")
                    assigned = u.get("assigned_cases", [])
                    if assigned:
                        case_names = []
                        for cid in assigned:
                            cname = case_mgr.get_case_name(cid)
                            case_names.append(cname)
                        st.caption(f"**Assigned Cases ({len(assigned)}):** {', '.join(case_names)}")
                    else:
                        st.caption("**Assigned Cases:** None")

                with col_actions:
                    # Role change
                    new_role = st.selectbox(
                        "Role",
                        ROLES,
                        index=ROLES.index(u.get("role", "attorney")),
                        key=f"_role_{uid}"
                    )
                    if new_role != u.get("role"):
                        if st.button("Update Role", key=f"_uprole_{uid}"):
                            user_mgr.update_user(uid, {"role": new_role})
                            st.success(f"Role updated to {ROLE_LABELS.get(new_role, new_role)}")
                            st.rerun()

                    # PIN management
                    has_pin = bool(u.get("pin_hash", ""))
                    if has_pin:
                        if st.button("\U0001f513 Remove PIN", key=f"_rmpin_{uid}"):
                            user_mgr.update_user(uid, {"pin": ""})
                            st.success("PIN removed")
                            st.rerun()
                    else:
                        new_pin = st.text_input("Set PIN", type="password", max_chars=6, key=f"_newpin_{uid}")
                        if new_pin and st.button("Set PIN", key=f"_setpin_{uid}"):
                            user_mgr.update_user(uid, {"pin": new_pin})
                            st.success("PIN set")
                            st.rerun()

                    # Google email linking
                    cur_google = u.get("google_email", "") or ""
                    new_google = st.text_input(
                        "Google Email",
                        value=cur_google,
                        key=f"_gemail_{uid}",
                        placeholder="user@gmail.com"
                    )
                    if new_google.strip() != cur_google:
                        if st.button("\U0001f517 Link Google", key=f"_linkgoogle_{uid}"):
                            user_mgr.link_google_account(uid, new_google.strip())
                            st.success(f"Google account linked: {new_google.strip()}")
                            st.rerun()

                    # Activate / Deactivate
                    if is_active:
                        if st.button("\U0001f6ab Deactivate", key=f"_deact_{uid}", type="secondary"):
                            user_mgr.deactivate_user(uid)
                            st.warning(f"{name} deactivated")
                            st.rerun()
                    else:
                        if st.button("\u2705 Reactivate", key=f"_react_{uid}", type="primary"):
                            user_mgr.reactivate_user(uid)
                            st.success(f"{name} reactivated")
                            st.rerun()

    # ================================================================
    #  TAB 2 -- Add New User
    # ================================================================
    if len(tab_objs) > 1:
        with tab_objs[1]:
            st.markdown("### \u2795 Add New Team Member")
            with st.form("add_user_form"):
                new_name = st.text_input("Full Name *")
                new_initials = st.text_input("Initials (auto-generated if empty)")
                new_email = st.text_input("Email")
                new_google_email = st.text_input("Google Email (for Google Sign-In)", placeholder="user@gmail.com")
                new_role = st.selectbox("Role", ROLES, index=1)  # Default: attorney
                new_pin = st.text_input("PIN (optional)", type="password", max_chars=6)
                submitted = st.form_submit_button("Create User", type="primary", use_container_width=True)
                if submitted:
                    if not new_name.strip():
                        st.error("Name is required")
                    else:
                        profile = user_mgr.create_user(
                            name=new_name.strip(),
                            role=new_role,
                            initials=new_initials.strip() or "",
                            email=new_email.strip(),
                            pin=new_pin,
                            google_email=new_google_email.strip(),
                        )
                        st.success(f"\u2705 Created **{profile['name']}** ({ROLE_LABELS.get(new_role, new_role)})")
                        st.rerun()

    # ================================================================
    #  TAB 3 -- Case Assignments
    # ================================================================
    if len(tab_objs) > 2:
        with tab_objs[2]:
            st.markdown("### \U0001f4cb Case Assignments")
            st.caption("Manage which team members can access each case. Admins always see all cases.")

            all_cases = case_mgr.list_cases()
            active_users = user_mgr.list_users()
            non_admin_users = [u for u in active_users if u.get("role") != "admin"]

            if not all_cases:
                st.info("No cases exist yet. Create a case first.")
            elif not non_admin_users:
                st.info("All active users are admins \u2014 they can already see all cases.")
            else:
                for case in all_cases:
                    cid = case["id"]
                    cname = case.get("name", cid)
                    ctype_icon = {"criminal": "\U0001f512", "criminal-juvenile": "\U0001f512", "civil-plaintiff": "\u2696\ufe0f", "civil-defendant": "\U0001f6e1\ufe0f", "civil-juvenile": "\u2696\ufe0f"}.get(case.get("case_type", ""), "\U0001f4c1")

                    with st.expander(f"{ctype_icon} **{cname}**", expanded=False):
                        # Show current assignees
                        assigned_users = user_mgr.get_users_for_case(cid)
                        assigned_names = [f"{u.get('initials', '')} ({u.get('name', '')})" for u in assigned_users]
                        st.caption(f"Currently assigned: {', '.join(assigned_names) if assigned_names else 'None'}")

                        # Multi-select for assignment
                        user_options = {u["id"]: f"{u.get('initials', '')} \u2014 {u.get('name', '')}" for u in non_admin_users}
                        currently_assigned = [u["id"] for u in non_admin_users if cid in u.get("assigned_cases", [])]

                        selected = st.multiselect(
                            "Assign team members",
                            options=list(user_options.keys()),
                            default=currently_assigned,
                            format_func=lambda x: user_options.get(x, x),
                            key=f"_assign_{cid}"
                        )

                        if st.button("Save Assignments", key=f"_save_assign_{cid}"):
                            # Add new assignments
                            for uid in selected:
                                if uid not in currently_assigned:
                                    user_mgr.assign_case(uid, cid)
                            # Remove old assignments
                            for uid in currently_assigned:
                                if uid not in selected:
                                    user_mgr.unassign_case(uid, cid)
                            st.success(f"Assignments updated for **{cname}**")
                            st.rerun()
