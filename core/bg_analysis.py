"""
Background Analysis Worker
Runs case analysis in a daemon thread so the user can navigate to other cases.
Progress is communicated via a progress.json file on disk (not session_state).
"""
import atexit
import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.getcwd(), "data", "cases")

# Lock to serialize progress.json writes (main thread + updater thread)
_progress_lock = threading.Lock()

# -- Human-readable descriptions for each analysis node --
NODE_DESCRIPTIONS = {
    "analyzer": "Reading all documents and building a comprehensive case summary...",
    "strategist": "Developing defense strategy based on case facts and legal elements...",
    "elements_mapper": "Mapping each legal element to determine prosecution's burden of proof strength...",
    "investigation_planner": "Identifying unanswered questions and planning investigation tasks...",
    "consistency_checker": "Cross-referencing all evidence for contradictions, conflicts, and impeachment opportunities...",
    "legal_researcher": "Researching applicable statutes, defenses, and relevant case law...",
    "devils_advocate": "Simulating the prosecution's strongest arguments and counter-strategies...",
    "entity_extractor": "Extracting people, places, dates, organizations, and key facts from documents...",
    "cross_examiner": "Generating cross-examination questions for each opposing witness...",
    "direct_examiner": "Preparing direct-examination outlines for defense witnesses...",
    "timeline_generator": "Building a chronological timeline of all events from the evidence...",
    "foundations_agent": "Analyzing evidence admissibility and foundation requirements for each exhibit...",
    "voir_dire_agent": "Preparing jury selection questions tailored to the specific case issues...",
    "mock_jury": "Simulating jury deliberation, verdict predictions, and persuasion strategy...",
}

# -- Map node names to their primary result key(s) for cache checking --
NODE_RESULT_KEYS = {
    "analyzer": ["case_summary"],
    "strategist": ["strategy_notes", "witnesses"],
    "elements_mapper": ["legal_elements"],
    "investigation_planner": ["investigation_plan"],
    "consistency_checker": ["consistency_check"],
    "legal_researcher": ["research_summary", "legal_research_data"],
    "devils_advocate": ["devils_advocate_notes"],
    "entity_extractor": ["entities", "relationships"],
    "cross_examiner": ["cross_examination_plan"],
    "direct_examiner": ["direct_examination_plan"],
    "timeline_generator": ["timeline"],
    "foundations_agent": ["evidence_foundations"],
    "voir_dire_agent": ["voir_dire"],
    "mock_jury": ["mock_jury_feedback"],
}


def _progress_path(case_id: str, prep_id: str) -> str:
    return os.path.join(DATA_DIR, case_id, "preparations", prep_id, "progress.json")


def _write_progress(case_id: str, prep_id: str, progress: dict):
    """Write progress dict to disk atomically.

    Uses a lock to prevent the main analysis thread and the per-token
    updater thread from colliding on the same tmp file.
    """
    path = _progress_path(case_id, prep_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Thread-unique tmp name avoids file collision between writers
    tmp_path = f"{path}.{threading.get_ident()}.tmp"
    with _progress_lock:
        try:
            with open(tmp_path, "w") as f:
                json.dump(progress, f, indent=2)
            os.replace(tmp_path, path)
        except OSError:
            try:
                if os.path.exists(path):
                    os.remove(path)
                os.rename(tmp_path, path)
            except OSError as e:
                logger.warning("Progress write failed: %s", e)


def get_analysis_progress(case_id: str, prep_id: str) -> dict:
    """Read current analysis progress from disk. Returns empty dict if none.

    On Windows, os.replace() during atomic writes can briefly make the file
    unavailable.  Retry up to 3 times with a short sleep to handle this.

    Proactive stale detection: if status is 'running' but no update in 5 min,
    the thread is likely dead — auto-correct to 'error' so the UI doesn't hang.
    """
    path = _progress_path(case_id, prep_id)
    if not os.path.exists(path):
        return {}
    data = {}
    for _attempt in range(3):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            break
        except (json.JSONDecodeError, IOError, OSError):
            if _attempt < 2:
                time.sleep(0.05)  # 50ms backoff

    # Proactive stale detection
    if data.get("status") == "running":
        last_update = data.get("node_started_at") or data.get("started_at", "")
        if last_update:
            try:
                last_dt = datetime.fromisoformat(last_update)
                elapsed = (datetime.now() - last_dt).total_seconds()
                if elapsed > 300:  # 5 min — analysis nodes can take minutes for large LLM calls
                    logger.warning(
                        "Analysis progress stale for %s/%s (%ds). Marking as error.",
                        case_id, prep_id, int(elapsed),
                    )
                    data["status"] = "error"
                    data["error"] = (
                        f"Analysis appears stale (no update for {int(elapsed)}s). "
                        "Partial results were saved."
                    )
                    data["completed_at"] = datetime.now().isoformat()
                    _write_progress(case_id, prep_id, data)
            except (ValueError, TypeError):
                pass

    return data


def is_analysis_running(case_id: str, prep_id: str) -> bool:
    """Check if analysis is currently running for this prep.

    Also detects stale/crashed analyses: if status is 'running' but
    no update has occurred for >5 minutes, mark it as errored.
    """
    progress = get_analysis_progress(case_id, prep_id)
    if progress.get("status") != "running":
        return False

    # Stale crash detection: if last update was >5 min ago, thread likely died
    last_update = progress.get("node_started_at") or progress.get("started_at", "")
    if last_update:
        try:
            last_dt = datetime.fromisoformat(last_update)
            elapsed = (datetime.now() - last_dt).total_seconds()
            if elapsed > 300:  # 5 min — analysis nodes can take minutes for large LLM calls
                _write_progress(case_id, prep_id, {
                    "status": "error",
                    "error": f"Analysis appears to have crashed (no update for {int(elapsed)}s). Partial results were saved.",
                    "nodes_completed": progress.get("nodes_completed", 0),
                    "total_nodes": progress.get("total_nodes", 0),
                    "current_node": progress.get("current_node", ""),
                    "current_description": "Analysis crashed -- partial results saved",
                    "completed_nodes": progress.get("completed_nodes", []),
                    "started_at": progress.get("started_at", ""),
                    "completed_at": datetime.now().isoformat(),
                    "per_node_times": progress.get("per_node_times", {}),
                    "skipped_nodes": progress.get("skipped_nodes", []),
                    "est_tokens_so_far": progress.get("est_tokens_so_far", 0),
                    "stop_requested": False,
                })
                return False
        except (ValueError, TypeError):
            pass

    return True


def is_any_analysis_running(case_id: str) -> bool:
    """Check if ANY prep in this case has a running analysis."""
    preps_dir = os.path.join(DATA_DIR, case_id, "preparations")
    if not os.path.exists(preps_dir):
        return False
    try:
        preps_index = os.path.join(preps_dir, "preparations.json")
        if os.path.exists(preps_index):
            with open(preps_index, "r") as f:
                preps = json.load(f)
            for p in preps:
                if is_analysis_running(case_id, p["id"]):
                    return True
    except (json.JSONDecodeError, IOError, KeyError):
        pass
    return False


def stop_background_analysis(case_id: str, prep_id: str):
    """Request the background thread to stop by setting a flag in progress.json."""
    progress = get_analysis_progress(case_id, prep_id)
    if progress.get("status") == "running":
        progress["stop_requested"] = True
        _write_progress(case_id, prep_id, progress)


def clear_progress(case_id: str, prep_id: str):
    """Remove progress.json after results have been acknowledged."""
    path = _progress_path(case_id, prep_id)
    if os.path.exists(path):
        os.remove(path)


def _run_analysis_thread(
    case_id: str,
    prep_id: str,
    state: dict,
    active_modules: set | None,
    prep_type: str,
    model_provider: str,
    max_context_mode: bool,
):
    """
    The actual analysis work -- runs in a background thread.
    Enhanced with per-node timing, token counter, descriptions, smart caching,
    and per-token streaming progress for real-time UI feedback.
    """
    # Import here to avoid circular imports at module level
    from core.nodes.graph_builder import (
        build_graph, build_graph_selective, NODE_LABELS, get_node_count,
    )
    from core.state import set_stream_callback, clear_stream_callback
    from core.case_manager import CaseManager
    from core.storage.json_backend import JSONStorageBackend
    from pathlib import Path as _Path

    _data_dir = str(_Path(__file__).resolve().parent.parent / "data")
    case_mgr = CaseManager(JSONStorageBackend(_data_dir))

    # -- Per-token streaming infrastructure --
    _token_lock = threading.Lock()
    _token_count = [0]        # mutable counter for current node
    _token_buffer = []        # accumulated token strings for streaming text
    _node_start_time = [0.0]  # when current node started (time.monotonic())
    _updater_stop = threading.Event()

    def _on_token(token):
        """Callback invoked for each streamed token from the LLM."""
        with _token_lock:
            _token_buffer.append(token)
            _token_count[0] += 1

    def _progress_updater():
        """Daemon thread: writes per-token progress to disk every ~1s."""
        while not _updater_stop.is_set():
            try:
                progress = get_analysis_progress(case_id, prep_id)
                if not progress or progress.get("status") != "running":
                    break
                with _token_lock:
                    cur_tokens = _token_count[0]
                    # Keep last 8000 chars of streaming text for display
                    full_text = "".join(_token_buffer)
                    display_text = full_text[-8000:] if len(full_text) > 8000 else full_text

                elapsed = time.monotonic() - _node_start_time[0]
                rate = cur_tokens / elapsed if elapsed > 1 else 0
                # Heuristic: expect ~20% of input tokens as output per node
                expected = progress.get("node_expected_tokens", 2000)
                pct = min((cur_tokens / max(expected, 1)) * 100, 99.0)

                progress["node_tokens"] = cur_tokens
                progress["node_token_rate"] = round(rate, 1)
                progress["node_pct"] = round(pct, 2)
                progress["streamed_text"] = display_text
                progress["node_started_at"] = datetime.now().isoformat()
                _write_progress(case_id, prep_id, progress)
            except Exception as _upd_err:
                logger.warning("Progress updater failed to write token progress: %s", _upd_err)
            _updater_stop.wait(timeout=1.0)

    # Start the progress updater daemon
    _updater_thread = threading.Thread(target=_progress_updater, daemon=True)

    try:
        # Reset token usage accumulator for accurate cost tracking
        from core.llm import reset_usage_accumulator
        reset_usage_accumulator()

        # Build graph
        if active_modules and active_modules != set(NODE_LABELS.keys()):
            prep_graph, total_nodes = build_graph_selective(active_modules, prep_type)
        else:
            prep_graph = build_graph(prep_type)
            total_nodes = get_node_count(prep_type)

        started_at = datetime.now().isoformat()

        # -- Load attorney module notes for AI-aware re-analysis --
        # Module notes are stored separately from analysis results and persist
        # through re-analysis. They're injected into state so get_case_context()
        # can build the module_notes_block for LLM prompts.
        try:
            from core.module_definitions import MODULE_NAMES as _MODULE_NAMES
            _notes = {}
            for _mod in _MODULE_NAMES:
                _note = case_mgr.load_module_notes(case_id, prep_id, _mod)
                if _note and _note.strip():
                    _notes[_mod] = _note
            if _notes:
                state["_attorney_module_notes"] = _notes
                logger.info("Loaded %d attorney module notes for re-analysis", len(_notes))
        except Exception as _notes_err:
            logger.warning("Failed to load module notes: %s", _notes_err)

        # -- Smart caching: check existing results + fingerprint --
        existing_state = case_mgr.load_prep_state(case_id, prep_id) or {}
        current_fingerprint = case_mgr.compute_docs_fingerprint(case_id)
        saved_fingerprint = existing_state.get("_docs_fingerprint", "")
        docs_unchanged = (saved_fingerprint and current_fingerprint
                          and saved_fingerprint == current_fingerprint)

        # Estimate input tokens for expected-output heuristic
        docs = state.get("raw_documents", [])
        doc_tokens = sum(
            len(str(d.page_content if hasattr(d, 'page_content') else d)) // 4
            for d in docs
        )

        _write_progress(case_id, prep_id, {
            "status": "running",
            "nodes_completed": 0,
            "total_nodes": total_nodes,
            "current_node": "Starting...",
            "current_description": "Initializing analysis pipeline...",
            "started_at": started_at,
            "node_started_at": started_at,
            "est_tokens_so_far": 0,
            "per_node_times": {},
            "skipped_nodes": [],
            "completed_nodes": [],
            "stop_requested": False,
            "node_tokens": 0,
            "node_token_rate": 0,
            "node_pct": 0,
            "node_expected_tokens": max(500, int(doc_tokens * 0.20)),
            "streamed_text": "",
        })

        # Activate streaming callback and start updater
        set_stream_callback(_on_token)
        _updater_thread.start()

        # Stream through nodes
        results = state.copy()
        nodes_completed = 0
        completed_node_names = []
        per_node_times = {}
        skipped_nodes = []
        est_tokens_so_far = 0
        was_stopped = False
        _last_node_start = time.monotonic()  # Track when a node started processing
        _node_start_time[0] = _last_node_start

        for node_output in prep_graph.stream(state):
            # Check stop flag from disk
            progress = get_analysis_progress(case_id, prep_id)
            if progress.get("stop_requested"):
                was_stopped = True
                break

            for node_name, node_result in node_output.items():
                if node_name == "__end__":
                    continue

                # Record elapsed time for this node (time since last yield)
                node_elapsed = time.monotonic() - _last_node_start
                node_label = NODE_LABELS.get(node_name, node_name)
                node_desc = NODE_DESCRIPTIONS.get(node_name, f"Processing {node_label}...")

                # -- Smart caching check --
                # Core nodes (analyzer, strategist) always run -- everything depends on them.
                # For other nodes: if docs are unchanged AND result keys already have data, skip.
                result_keys = NODE_RESULT_KEYS.get(node_name, [])
                is_core = node_name in ("analyzer", "strategist")
                has_cached = (
                    not is_core
                    and docs_unchanged
                    and result_keys
                    and all(
                        existing_state.get(k) not in (None, "", [], {})
                        for k in result_keys
                    )
                )

                # For exam nodes, also check if witnesses changed
                if has_cached and node_name in ("cross_examiner", "direct_examiner"):
                    import hashlib
                    _wit_list = results.get("witnesses", [])
                    _wit_fp = hashlib.sha256(
                        json.dumps(sorted(
                            [w.get("name", "") + w.get("type", "") for w in _wit_list if isinstance(w, dict)]
                        )).encode()
                    ).hexdigest()[:16]
                    _saved_wit_fp = existing_state.get("_witnesses_fingerprint", "")
                    if _saved_wit_fp and _wit_fp != _saved_wit_fp:
                        has_cached = False  # Witnesses changed — regenerate exam

                if has_cached:
                    # Use cached results -- copy them into results dict
                    for k in result_keys:
                        node_result[k] = existing_state[k]
                    skipped_nodes.append(node_name)

                results.update(node_result)
                nodes_completed += 1
                completed_node_names.append(node_name)

                # Save witness fingerprint after strategist (for exam cache invalidation)
                if node_name == "strategist":
                    import hashlib
                    _wit_list = results.get("witnesses", [])
                    results["_witnesses_fingerprint"] = hashlib.sha256(
                        json.dumps(sorted(
                            [w.get("name", "") + w.get("type", "") for w in _wit_list if isinstance(w, dict)]
                        )).encode()
                    ).hexdigest()[:16]

                # Track timing for the node that just completed
                per_node_times[node_label] = round(node_elapsed, 1)

                # Track tokens (rough estimate from result content)
                for _val in node_result.values():
                    est_tokens_so_far += len(str(_val)) // 4

                # Per-module timestamp for smart re-analysis
                if "_module_timestamps" not in results:
                    results["_module_timestamps"] = {}
                results["_module_timestamps"][node_label] = datetime.now().isoformat()

                # Show the COMPLETED node status with its time, plus what's coming next
                _status_desc = f"{node_label} completed ({per_node_times[node_label]}s)"
                if has_cached:
                    _status_desc = f"{node_label} -- cached (documents unchanged)"

                # Reset per-token counters for the next node
                with _token_lock:
                    _token_count[0] = 0
                    _token_buffer.clear()
                _node_start_time[0] = time.monotonic()

                _write_progress(case_id, prep_id, {
                    "status": "running",
                    "nodes_completed": nodes_completed,
                    "total_nodes": total_nodes,
                    "current_node": node_label,
                    "current_description": _status_desc,
                    "completed_nodes": completed_node_names,
                    "started_at": started_at,
                    "node_started_at": datetime.now().isoformat(),
                    "est_tokens_so_far": est_tokens_so_far,
                    "per_node_times": per_node_times,
                    "skipped_nodes": skipped_nodes,
                    "stop_requested": False,
                    "node_tokens": 0,
                    "node_token_rate": 0,
                    "node_pct": 0,
                    "node_expected_tokens": max(500, int(doc_tokens * 0.20)),
                    "streamed_text": "",
                })

                # Save partial results after each node (checkpoint)
                try:
                    _partial = case_mgr.merge_append_only(case_id, prep_id, results)
                    _partial["_docs_fingerprint"] = case_mgr.compute_docs_fingerprint(case_id)
                    case_mgr.save_prep_state(case_id, prep_id, _partial)
                except Exception as _chk_err:
                    logger.warning(
                        "Checkpoint save failed after node %s: %s",
                        node_name, _chk_err,
                    )

                # Reset timer for NEXT node
                _last_node_start = time.monotonic()
                _node_start_time[0] = _last_node_start

        # -- Cleanup streaming infrastructure --
        clear_stream_callback()
        _updater_stop.set()

        # Save results -- merge with existing state (append-only protection)
        results = case_mgr.merge_append_only(case_id, prep_id, results)

        # Merge module timestamps so cached/skipped modules preserve their last-run time
        _merged_ts = existing_state.get("_module_timestamps", {}).copy()
        _merged_ts.update(results.get("_module_timestamps", {}))
        results["_module_timestamps"] = _merged_ts

        results["_docs_fingerprint"] = case_mgr.compute_docs_fingerprint(case_id)
        results["_last_per_node_times"] = per_node_times  # Historical times for ETA
        case_mgr.save_prep_state(case_id, prep_id, results)

        # Compute and save file relevance scores (zero LLM cost)
        try:
            from core.relevance import compute_relevance_scores, save_relevance_scores
            _rel_file_tags = case_mgr.get_all_file_tags(case_id)
            _rel_case_type = state.get("case_type", "criminal")
            _rel_scores = compute_relevance_scores(results, _rel_file_tags, _rel_case_type)
            if _rel_scores:
                save_relevance_scores(_data_dir, case_id, prep_id, _rel_scores)
                logger.info("Saved relevance scores for %d files", len(_rel_scores))
        except Exception as _rel_err:
            logger.warning("Relevance scoring failed: %s", _rel_err)

        # Log ACTUAL cost from API usage accumulator
        try:
            from core.llm import get_accumulated_usage
            from core.cost_tracker import estimate_cost as _calc_cost
            _actual_usage = get_accumulated_usage()
            _actual_in = _actual_usage.get("input_tokens", 0)
            _actual_out = _actual_usage.get("output_tokens", 0)
            _actual_cost = _calc_cost(_actual_in, _actual_out, model_provider)
            case_mgr.log_cost(case_id, prep_id, {
                "action": f"Full Analysis ({prep_type})",
                "input_tokens": _actual_in,
                "output_tokens": _actual_out,
                "total_tokens": _actual_in + _actual_out,
                "cost": round(_actual_cost, 4),
                "model": model_provider,
                "nodes_completed": nodes_completed,
                "nodes_skipped": len(skipped_nodes),
                "api_calls": _actual_usage.get("calls", 0),
            })
        except Exception as _cost_exc:
            logger.warning("Cost logging failed: %s", _cost_exc)
            # Fallback to estimate
            est_tokens = len(str(state.get("raw_documents", []))) // 4
            cost_per_1k = {"xai": 0.005, "anthropic": 0.003}.get(model_provider, 0.003)
            est_cost = (est_tokens / 1000) * cost_per_1k
            case_mgr.log_cost(case_id, prep_id, {
                "action": f"Full Analysis ({prep_type}) [estimated]",
                "tokens": est_tokens,
                "cost": round(est_cost, 4),
                "model": model_provider,
            })

        completed_at = datetime.now().isoformat()

        # Get actual cost data for final progress
        try:
            from core.llm import get_accumulated_usage
            from core.cost_tracker import estimate_cost as _calc_cost_final
            _final_usage = get_accumulated_usage()
            _final_cost = _calc_cost_final(
                _final_usage.get("input_tokens", 0),
                _final_usage.get("output_tokens", 0),
                model_provider,
            )
            _cost_data = {
                "actual_input_tokens": _final_usage.get("input_tokens", 0),
                "actual_output_tokens": _final_usage.get("output_tokens", 0),
                "actual_total_tokens": _final_usage.get("total_tokens", 0),
                "actual_cost": round(_final_cost, 4),
                "api_calls": _final_usage.get("calls", 0),
            }
        except Exception:
            _cost_data = {
                "est_tokens_so_far": est_tokens_so_far,
            }

        if was_stopped:
            _write_progress(case_id, prep_id, {
                "status": "stopped",
                "nodes_completed": nodes_completed,
                "total_nodes": total_nodes,
                "current_node": "Stopped by user",
                "current_description": "Analysis stopped by user. Partial results saved.",
                "completed_at": completed_at,
                "started_at": started_at,
                "per_node_times": per_node_times,
                "skipped_nodes": skipped_nodes,
                "completed_nodes": completed_node_names,
                **_cost_data,
            })
        else:
            _write_progress(case_id, prep_id, {
                "status": "complete",
                "nodes_completed": nodes_completed,
                "total_nodes": total_nodes,
                "current_node": "Complete",
                "current_description": "All analysis modules finished successfully.",
                "completed_at": completed_at,
                "started_at": started_at,
                "per_node_times": per_node_times,
                "skipped_nodes": skipped_nodes,
                "completed_nodes": completed_node_names,
                **_cost_data,
            })

    except Exception as e:
        # Cleanup streaming on error
        try:
            clear_stream_callback()
        except Exception as _cb_err:
            logger.debug("Failed to clear stream callback during error cleanup: %s", _cb_err)
        _updater_stop.set()

        # Save partial results on error so work isn't lost
        try:
            _partial = case_mgr.merge_append_only(case_id, prep_id, results)
            _partial["_docs_fingerprint"] = case_mgr.compute_docs_fingerprint(case_id)
            case_mgr.save_prep_state(case_id, prep_id, _partial)
        except Exception as _save_err:
            logger.warning("Failed to save partial results on error: %s", _save_err)

        _write_progress(case_id, prep_id, {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "nodes_completed": nodes_completed if 'nodes_completed' in dir() else 0,
            "completed_nodes": completed_node_names if 'completed_node_names' in dir() else [],
            "completed_at": datetime.now().isoformat(),
            "per_node_times": per_node_times if 'per_node_times' in dir() else {},
            "skipped_nodes": skipped_nodes if 'skipped_nodes' in dir() else [],
        })

        # Notify assigned users about the failure
        try:
            from api.notify import notify_analysis_failed
            notify_analysis_failed(case_id, prep_id, str(e))
        except Exception:
            pass  # best-effort


def start_background_analysis(
    case_id: str,
    prep_id: str,
    state: dict,
    active_modules: set | None,
    prep_type: str,
    model_provider: str,
    max_context_mode: bool = False,
):
    """
    Spawns a daemon thread that runs the analysis graph.
    Returns immediately so the UI can continue.
    """
    # Snapshot before analysis
    try:
        from core.case_manager import CaseManager
        from core.storage.json_backend import JSONStorageBackend
        _data_dir = str(Path(__file__).resolve().parent.parent / "data")
        _storage = JSONStorageBackend(_data_dir)
        case_mgr = CaseManager(_storage)
        case_mgr.save_snapshot(case_id, prep_id, label="Before background analysis")
    except Exception as _snap_err:
        logger.warning("Pre-analysis snapshot failed: %s", _snap_err)

    # -- Write initial progress.json BEFORE starting the thread --
    # This eliminates the race condition where st.rerun() fires before
    # the thread has a chance to write progress.json, causing
    # is_analysis_running() to return False and the progress UI to vanish.
    from core.nodes.graph_builder import NODE_LABELS, get_node_count
    if active_modules and active_modules != set(NODE_LABELS.keys()):
        total_nodes = len(active_modules)
    else:
        total_nodes = get_node_count(prep_type)

    started_at = datetime.now().isoformat()
    _write_progress(case_id, prep_id, {
        "status": "running",
        "nodes_completed": 0,
        "total_nodes": total_nodes,
        "current_node": "Starting...",
        "current_description": "Launching analysis pipeline...",
        "started_at": started_at,
        "node_started_at": started_at,
        "est_tokens_so_far": 0,
        "per_node_times": {},
        "skipped_nodes": [],
        "completed_nodes": [],
        "stop_requested": False,
        "node_tokens": 0,
        "node_token_rate": 0,
        "node_pct": 0,
        "node_expected_tokens": 2000,
        "streamed_text": "",
    })

    thread = threading.Thread(
        target=_run_analysis_thread,
        args=(case_id, prep_id, state, active_modules, prep_type, model_provider, max_context_mode),
        daemon=True,
        name=f"analysis-{case_id}-{prep_id}",
    )
    _active_analysis_threads[f"{case_id}:{prep_id}"] = thread
    thread.start()
    return thread


# --- Active Thread Tracking & Graceful Shutdown ---

_active_analysis_threads: dict = {}  # {"case_id:prep_id": threading.Thread}


def _cleanup_analysis_threads():
    """atexit handler: wait briefly for running analysis threads to checkpoint."""
    for key, thr in list(_active_analysis_threads.items()):
        if thr.is_alive():
            logger.info("Waiting for analysis thread %s to checkpoint...", key)
            thr.join(timeout=10)
            if thr.is_alive():
                logger.warning("Analysis thread %s still running at exit.", key)


atexit.register(_cleanup_analysis_threads)
