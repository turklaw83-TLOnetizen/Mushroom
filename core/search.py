# ---- Global Search --------------------------------------------------------
# Cross-entity search across cases, clients, tasks, and activity logs.

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")


def global_search(query: str, case_mgr, data_dir: str = "") -> Dict[str, list]:
    """
    Search across cases, clients, and tasks.

    Returns:
        {"cases": [...], "clients": [...], "tasks": [...]}
    """
    if not query or len(query) < 2:
        return {"cases": [], "clients": [], "tasks": []}

    q = query.lower().strip()
    _dir = data_dir or _DATA_DIR
    results = {"cases": [], "clients": [], "tasks": []}

    # ---- Cases ----
    try:
        all_cases = case_mgr.list_cases(include_archived=True)
        for c in all_cases:
            searchable = " ".join([
                c.get("name", ""),
                c.get("description", ""),
                c.get("client_name", ""),
                c.get("id", ""),
                c.get("case_type", ""),
                c.get("jurisdiction", ""),
            ]).lower()
            if q in searchable:
                results["cases"].append({
                    "id": c["id"],
                    "name": c.get("name", c["id"]),
                    "client_name": c.get("client_name", ""),
                    "status": c.get("status", "active"),
                    "match_type": "case",
                })
    except Exception as exc:
        logger.debug("Case search error: %s", exc)

    # ---- Clients ----
    try:
        from core.crm import search_clients
        client_hits = search_clients(q)
        for cl in client_hits[:20]:
            results["clients"].append({
                "id": cl.get("id", ""),
                "name": cl.get("name", ""),
                "email": cl.get("email", ""),
                "phone": cl.get("phone", ""),
                "status": cl.get("intake_status", ""),
                "linked_cases": cl.get("linked_case_ids", []),
                "match_type": "client",
            })
    except Exception as exc:
        logger.debug("Client search error: %s", exc)

    # ---- Tasks (across all cases) ----
    try:
        from core.tasks import load_tasks
        all_cases_for_tasks = case_mgr.list_cases(include_archived=False)
        for c in all_cases_for_tasks[:50]:  # Cap to avoid slowness
            cid = c["id"]
            tasks = load_tasks(_dir, cid)
            for t in tasks:
                searchable = " ".join([
                    t.get("title", ""),
                    t.get("description", ""),
                    t.get("category", ""),
                ]).lower()
                if q in searchable:
                    results["tasks"].append({
                        "id": t.get("id", ""),
                        "title": t.get("title", ""),
                        "case_id": cid,
                        "case_name": c.get("name", cid),
                        "status": t.get("status", ""),
                        "priority": t.get("priority", ""),
                        "match_type": "task",
                    })
    except Exception as exc:
        logger.debug("Task search error: %s", exc)

    return results


def search_in_case(query: str, case_id: str, case_mgr, data_dir: str = "") -> Dict[str, list]:
    """Search within a specific case: tasks, activity, analysis results."""
    if not query or len(query) < 2:
        return {"tasks": [], "activity": []}

    q = query.lower().strip()
    _dir = data_dir or _DATA_DIR
    results = {"tasks": [], "activity": []}

    # Tasks
    try:
        from core.tasks import load_tasks
        tasks = load_tasks(_dir, case_id)
        for t in tasks:
            searchable = f"{t.get('title', '')} {t.get('description', '')}".lower()
            if q in searchable:
                results["tasks"].append(t)
    except Exception:
        pass

    # Activity
    try:
        entries = case_mgr.get_activity_log(case_id, limit=500)
        for e in entries:
            searchable = f"{e.get('action', '')} {e.get('detail', '')}".lower()
            if q in searchable:
                results["activity"].append(e)
                if len(results["activity"]) >= 20:
                    break
    except Exception:
        pass

    return results
