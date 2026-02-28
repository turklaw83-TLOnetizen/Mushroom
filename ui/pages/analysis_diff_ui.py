"""
analysis_diff_ui.py -- Analysis Version Comparison UI
Side-by-side or unified diff view comparing analysis snapshots.
"""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(case_id=None, case_mgr=None, prep_id=None, **kwargs):
    """Render the analysis diff viewer."""
    from core.analysis_diff import (
        diff_analysis_states, generate_diff_summary, KEY_LABELS,
        count_new_citations,
    )

    if not case_id or not prep_id:
        st.info("Select a case and preparation to compare versions.")
        return

    st.markdown("### \U0001f50d Analysis Version Comparison")

    # Load snapshots
    snapshots = case_mgr.list_snapshots(case_id, prep_id)
    if not snapshots:
        st.info("No snapshots available. Snapshots are created before each analysis run.")
        return

    snap_options = {s["id"]: s.get("label", s["id"]) for s in snapshots}
    snap_ids = list(snap_options.keys())

    # Snapshot selectors
    _sel1, _sel2 = st.columns(2)
    with _sel1:
        _snap_a = st.selectbox(
            "Version A (older)",
            snap_ids,
            format_func=lambda x: snap_options.get(x, x),
            key="_diff_snap_a",
        )
    with _sel2:
        _snap_b_options = ["Current"] + snap_ids
        _snap_b = st.selectbox(
            "Version B (newer)",
            _snap_b_options,
            format_func=lambda x: "Current State" if x == "Current" else snap_options.get(x, x),
            key="_diff_snap_b",
        )

    if not st.button("\U0001f50d Compare", type="primary"):
        return

    # Load states
    state_a = case_mgr.load_snapshot(case_id, prep_id, _snap_a)
    if _snap_b == "Current":
        state_b = st.session_state.get("agent_results") or {}
        label_b = "Current State"
    else:
        state_b = case_mgr.load_snapshot(case_id, prep_id, _snap_b)
        label_b = snap_options.get(_snap_b, _snap_b)

    if not state_a:
        st.error("Could not load Version A snapshot.")
        return
    if not state_b:
        st.error("Could not load Version B state.")
        return

    # Compute diff
    changes = diff_analysis_states(state_a, state_b)
    summary = generate_diff_summary(changes)

    # Summary header
    st.divider()
    _s1, _s2, _s3, _s4 = st.columns(4)
    _s1.metric("Modules Changed", summary["total_changes"])
    _s2.metric("Added", len(summary["added"]))
    _s3.metric("Modified", len(summary["modified"]))
    _s4.metric("Removed", len(summary["removed"]))

    # Citation changes
    try:
        cites_added, cites_removed = count_new_citations(state_a, state_b)
        _c1, _c2 = st.columns(2)
        _c1.metric("Citations Added", f"+{cites_added}")
        _c2.metric("Citations Removed", f"-{cites_removed}")
    except Exception:
        pass

    st.divider()

    if not changes:
        st.success("No differences found between the two versions.")
        return

    # Display changes per module
    for key, change in changes.items():
        label = KEY_LABELS.get(key, key.replace("_", " ").title())
        status = change["status"]

        if status == "added":
            with st.expander(f"\U0001f7e2 **{label}** -- Added (+{change['new_len']} chars)", expanded=False):
                new_str = _format_value(change["new"])
                st.text(new_str[:3000])
                if len(new_str) > 3000:
                    st.caption(f"(Showing first 3,000 of {len(new_str):,} characters)")

        elif status == "removed":
            with st.expander(f"\U0001f534 **{label}** -- Removed (-{change['old_len']} chars)", expanded=False):
                old_str = _format_value(change["old"])
                st.text(old_str[:3000])

        elif status == "modified":
            delta = change["delta"]
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            with st.expander(
                f"\U0001f7e1 **{label}** -- Modified ({delta_str} chars)",
                expanded=False,
            ):
                # Show unified diff
                diff_lines = change.get("diff_lines", [])
                if diff_lines:
                    _colored_lines = []
                    for line in diff_lines[:200]:
                        if line.startswith("+") and not line.startswith("+++"):
                            _colored_lines.append(f"🟢 {line}")
                        elif line.startswith("-") and not line.startswith("---"):
                            _colored_lines.append(f"🔴 {line}")
                        else:
                            _colored_lines.append(f"   {line}")
                    st.code("\n".join(_colored_lines), language="diff")
                    if len(diff_lines) > 200:
                        st.caption(f"(Showing first 200 of {len(diff_lines)} diff lines)")
                else:
                    st.caption("Content changed but detailed diff not available.")


def _format_value(value):
    """Format a value for display."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        import json
        return json.dumps(value, indent=2, default=str)[:5000]
    if isinstance(value, dict):
        import json
        return json.dumps(value, indent=2, default=str)[:5000]
    return str(value)
