"""Deposition annotator — timestamp-linked annotations for transcripts."""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ANNOTATION_TYPES = {"note", "objection", "key_testimony", "impeachment", "exhibit_reference"}
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


class DepositionAnnotator:
    """Manage annotations for deposition transcripts."""

    def __init__(self, case_id: str, job_id: str, data_dir: Optional[Path] = None):
        self.case_id = case_id
        self.job_id = job_id
        self.base = (data_dir or DATA_DIR) / "cases" / case_id / "depositions" / job_id
        self.base.mkdir(parents=True, exist_ok=True)
        self._file = self.base / "annotations.json"

    def _load(self) -> list[dict]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self, annotations: list[dict]):
        self._file.write_text(json.dumps(annotations, default=str), encoding="utf-8")

    def create_annotation(
        self,
        timestamp: float,
        text: str,
        annotation_type: str = "note",
        user_id: str = "",
        evidence_id: Optional[str] = None,
    ) -> dict:
        annotation = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": timestamp,
            "text": text,
            "type": annotation_type if annotation_type in ANNOTATION_TYPES else "note",
            "user_id": user_id,
            "evidence_id": evidence_id,
            "created_at": __import__("time").time(),
        }
        items = self._load()
        items.append(annotation)
        items.sort(key=lambda a: a["timestamp"])
        self._save(items)
        return annotation

    def get_annotations(self, annotation_type: Optional[str] = None) -> list[dict]:
        items = self._load()
        if annotation_type:
            items = [a for a in items if a.get("type") == annotation_type]
        return items

    def delete_annotation(self, annotation_id: str) -> bool:
        items = self._load()
        before = len(items)
        items = [a for a in items if a["id"] != annotation_id]
        if len(items) < before:
            self._save(items)
            return True
        return False

    def link_to_evidence(self, annotation_id: str, evidence_id: str) -> bool:
        items = self._load()
        for a in items:
            if a["id"] == annotation_id:
                a["evidence_id"] = evidence_id
                self._save(items)
                return True
        return False
