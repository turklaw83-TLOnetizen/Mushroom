# ---- Document Annotations -------------------------------------------------
# CRUD for document annotations (notes/highlights) attached to specific
# pages and text excerpts within case documents.

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")

ANNOTATION_COLORS = ["yellow", "green", "blue", "red", "purple"]


def _annotations_path(data_dir: str, case_id: str, filename: str) -> str:
    """Return path to annotation file for a specific document."""
    safe_name = hashlib.md5(filename.encode()).hexdigest()
    ann_dir = os.path.join(data_dir, "cases", case_id, "annotations")
    os.makedirs(ann_dir, exist_ok=True)
    return os.path.join(ann_dir, f"{safe_name}.json")


def add_annotation(
    data_dir: str,
    case_id: str,
    filename: str,
    page: int,
    text: str = "",
    note: str = "",
    color: str = "yellow",
    user_id: str = "",
    user_name: str = "",
) -> str:
    """Create an annotation on a document page. Returns annotation ID."""
    ann_id = uuid.uuid4().hex[:8]
    entry = {
        "id": ann_id,
        "page": page,
        "text": text,
        "note": note,
        "color": color if color in ANNOTATION_COLORS else "yellow",
        "user_id": user_id,
        "user_name": user_name,
        "created_at": datetime.now().isoformat(),
    }

    path = _annotations_path(data_dir, case_id, filename)
    annotations = _load_raw(path)
    annotations.insert(0, entry)
    _save_raw(path, annotations)

    logger.info(
        "Annotation added: %s on %s page %d (case %s)",
        ann_id, filename, page, case_id,
    )
    return ann_id


def load_annotations(
    data_dir: str,
    case_id: str,
    filename: str,
    page: Optional[int] = None,
) -> List[Dict]:
    """Load annotations for a document, optionally filtered by page."""
    path = _annotations_path(data_dir, case_id, filename)
    annotations = _load_raw(path)
    if page is not None:
        annotations = [a for a in annotations if a.get("page") == page]
    return annotations


def count_annotations_by_page(
    data_dir: str,
    case_id: str,
    filename: str,
) -> Dict[int, int]:
    """Return {page_number: annotation_count} for a document."""
    path = _annotations_path(data_dir, case_id, filename)
    annotations = _load_raw(path)
    counts: Dict[int, int] = {}
    for a in annotations:
        pg = a.get("page", 0)
        counts[pg] = counts.get(pg, 0) + 1
    return counts


def delete_annotation(
    data_dir: str,
    case_id: str,
    filename: str,
    annotation_id: str,
) -> bool:
    """Delete an annotation by ID. Returns True if found and deleted."""
    path = _annotations_path(data_dir, case_id, filename)
    annotations = _load_raw(path)
    before = len(annotations)
    annotations = [a for a in annotations if a.get("id") != annotation_id]
    if len(annotations) < before:
        _save_raw(path, annotations)
        return True
    return False


def update_annotation(
    data_dir: str,
    case_id: str,
    filename: str,
    annotation_id: str,
    updates: Dict,
) -> bool:
    """Update annotation fields (note, color, text). Returns True if found."""
    path = _annotations_path(data_dir, case_id, filename)
    annotations = _load_raw(path)
    for a in annotations:
        if a.get("id") == annotation_id:
            for k, v in updates.items():
                if k in ("note", "color", "text"):
                    a[k] = v
            _save_raw(path, annotations)
            return True
    return False


def _load_raw(path: str) -> List[Dict]:
    """Load annotation list from JSON file."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _save_raw(path: str, data: List[Dict]) -> None:
    """Save annotation list to JSON file atomically."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception as exc:
        logger.warning("Error saving annotations: %s", exc)
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
