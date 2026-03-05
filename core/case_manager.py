# ---- Case Manager ---------------------------------------------------------
# Refactored from the original 104KB case_manager.py.
# Business logic lives here; all I/O delegated to StorageBackend.
# Every method mirrors the original API so callers don't need to change.

import hashlib
import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.append_only import APPEND_ONLY_KEYS, merge_append_only
from core.config import CONFIG
from core.storage.base import StorageBackend

logger = logging.getLogger(__name__)

# Preparation types
PREP_TYPES = {"trial", "prelim_hearing", "motion_hearing"}

# Master case phases
PHASES = ("active", "closed", "archived")

# Map phase → legacy status for backward compat
_PHASE_TO_STATUS = {"active": "active", "closed": "active", "archived": "archived"}

# Default sub-phases per case type (customizable via phase_config.json)
DEFAULT_PHASE_CONFIG = {
    "criminal": [
        "Intake", "Arraignment / Bond", "Discovery", "Pre-Trial Motions",
        "Plea Negotiation", "Trial Prep", "Trial", "Sentencing", "Appeal",
    ],
    "criminal-juvenile": [
        "Intake", "Detention Hearing", "Discovery",
        "Pre-Adjudication Motions", "Diversion / Plea",
        "Adjudication", "Disposition", "Post-Disposition",
    ],
    "civil-plaintiff": [
        "Intake", "Pre-Litigation / Demand", "Filing / Pleadings",
        "Discovery", "Mediation / ADR", "Pre-Trial Motions",
        "Trial Prep", "Trial", "Post-Trial / Collection",
    ],
    "civil-defendant": [
        "Intake", "Answer / Responsive Pleadings", "Discovery",
        "Mediation / ADR", "Pre-Trial Motions", "Trial Prep",
        "Trial", "Post-Trial",
    ],
    "civil-juvenile": [
        "Intake", "Petition Filed", "Discovery / Investigation",
        "Mediation", "Hearing Prep", "Hearing", "Post-Hearing",
    ],
}

# Days a case can remain in "closed" before auto-archiving
CLOSED_AUTO_ARCHIVE_DAYS = 21


def _now_iso() -> str:
    return datetime.now().isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _sanitize_case_id(name: str) -> str:
    """Convert a case name into a filesystem-safe ID."""
    sanitized = re.sub(r"[^\w\s-]", "", name).strip()
    sanitized = re.sub(r"[\s]+", "_", sanitized)
    # Append short hash to avoid collisions
    suffix = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"{sanitized}__{suffix}" if sanitized else f"case__{suffix}"


# ---- State Serialization -------------------------------------------------
# LangChain Document objects need special handling for JSON persistence.

def _serialize_state(state: Dict) -> Dict:
    """Convert LangChain Document objects to serializable dicts."""
    out = {}
    for k, v in state.items():
        if k == "raw_documents" and isinstance(v, list):
            serialized = []
            for doc in v:
                if hasattr(doc, "page_content"):
                    serialized.append({
                        "page_content": doc.page_content,
                        "metadata": doc.metadata if hasattr(doc, "metadata") else {},
                    })
                else:
                    serialized.append(doc)
            out[k] = serialized
        else:
            out[k] = v
    return out


def _deserialize_state(state: Dict) -> Dict:
    """Reconstitute LangChain Document objects from serialized dicts."""
    if "raw_documents" in state and isinstance(state["raw_documents"], list):
        restored = []
        for item in state["raw_documents"]:
            if isinstance(item, dict) and "page_content" in item:
                try:
                    from langchain_core.documents import Document
                    restored.append(Document(
                        page_content=item["page_content"],
                        metadata=item.get("metadata", {}),
                    ))
                except ImportError:
                    restored.append(item)
            else:
                restored.append(item)
        state["raw_documents"] = restored
    return state


class CaseManager:
    """
    High-level case management API.

    All file I/O is delegated to self.storage (a StorageBackend instance).
    Business logic (validation, ID generation, merging) lives here.
    """

    # Class-level constants
    PREP_TYPE_LABELS = {
        "trial": "\u2694\ufe0f Trial",
        "prelim_hearing": "\U0001f4cb Preliminary Hearing",
        "motion_hearing": "\U0001f4dd Motion Hearing",
    }

    CONTACT_TYPES = [
        "Phone Call", "In-Person", "Zoom/Video", "Email",
        "Text/Message", "Court Appearance", "Other",
    ]

    FILE_TAG_CATEGORIES = [
        "Police Report", "Witness Statement", "Medical Records",
        "Financial Records", "Photos/Video", "Court Filing",
        "Expert Report", "Correspondence", "Contract/Agreement",
        "Deposition", "Discovery", "Other",
    ]

    # Per-case locks to prevent concurrent writes to the same case from
    # background threads (analysis, ingestion, OCR) and UI reruns.
    _case_locks: Dict[str, threading.Lock] = {}
    _case_locks_guard = threading.Lock()

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def _get_case_lock(self, case_id: str) -> threading.Lock:
        """Return a per-case lock, creating it on first use."""
        with CaseManager._case_locks_guard:
            if case_id not in CaseManager._case_locks:
                CaseManager._case_locks[case_id] = threading.Lock()
            return CaseManager._case_locks[case_id]

    # ==== Case CRUD =======================================================

    def list_cases(self, include_archived: bool = False) -> List[Dict]:
        return self.storage.list_cases(include_archived=include_archived)

    def list_cases_for_user(self, user_allowed_ids: List[str],
                            include_archived: bool = False) -> List[Dict]:
        """Return cases filtered by user's allowed case IDs."""
        all_cases = self.list_cases(include_archived=include_archived)
        if not user_allowed_ids:
            return all_cases  # empty list means "all" access
        allowed = set(user_allowed_ids)
        return [c for c in all_cases if c.get("id") in allowed]

    def get_case_name(self, case_id: str) -> str:
        meta = self.storage.get_case_metadata(case_id)
        return meta.get("name", case_id)

    def get_case_metadata(self, case_id: str) -> Dict:
        return self.storage.get_case_metadata(case_id)

    def create_case(
        self,
        case_name: str,
        description: str = "",
        case_category: str = "",
        case_subcategory: str = "",
        case_type: str = "criminal",
        assigned_to: Optional[List[str]] = None,
        client_name: str = "",
        jurisdiction: str = "",
        docket_number: str = "",
        charges: str = "",
        court_name: str = "",
        date_of_incident: str = "",
        opposing_counsel: str = "",
        jurisdiction_type: str = "",
        county: str = "",
        district: str = "",
    ) -> str:
        """Create a new case. Returns the case_id."""
        case_id = _sanitize_case_id(case_name)
        now = _now_iso()
        metadata = {
            "id": case_id,
            "name": case_name,
            "description": description,
            "status": "active",
            "case_type": case_type,
            "case_category": case_category,
            "case_subcategory": case_subcategory,
            "client_name": client_name,
            "jurisdiction": jurisdiction,
            "assigned_to": assigned_to or [],
            "docket_number": docket_number,
            "charges": charges,
            "court_name": court_name,
            "date_of_incident": date_of_incident,
            "opposing_counsel": opposing_counsel,
            "jurisdiction_type": jurisdiction_type,
            "county": county,
            "district": district,
            "created_at": now,
            "last_updated": now,
        }
        self.storage.create_case(case_id, metadata)
        self.log_activity(case_id, "case_created", f"Case '{case_name}' created")
        return case_id

    def delete_case(self, case_id: str) -> None:
        self.storage.delete_case(case_id)

    def rename_case(self, case_id: str, new_name: str) -> str:
        """Rename a case. Returns the new case_id."""
        new_id = _sanitize_case_id(new_name)
        if new_id == case_id:
            # Just update the display name
            meta = self.storage.get_case_metadata(case_id)
            meta["name"] = new_name
            meta["last_updated"] = _now_iso()
            self.storage.update_case_metadata(case_id, meta)
            return case_id

        # Clone to new ID, delete old
        self.storage.clone_case(case_id, new_id)
        meta = self.storage.get_case_metadata(new_id)
        meta["id"] = new_id
        meta["name"] = new_name
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(new_id, meta)
        self.storage.delete_case(case_id)
        return new_id

    def archive_case(self, case_id: str) -> None:
        """Legacy-compatible: set phase to archived."""
        self.set_phase(case_id, "archived")

    def unarchive_case(self, case_id: str) -> None:
        """Legacy-compatible: set phase back to active."""
        self.set_phase(case_id, "active")

    def clone_case(self, case_id: str, new_name: str) -> str:
        """Deep copy a case. Returns the new case_id."""
        new_id = _sanitize_case_id(new_name)
        self.storage.clone_case(case_id, new_id)
        meta = self.storage.get_case_metadata(new_id)
        meta["id"] = new_id
        meta["name"] = new_name
        meta["created_at"] = _now_iso()
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(new_id, meta)
        return new_id

    def update_status(self, case_id: str, new_status: str) -> None:
        """Legacy-compatible status update. Prefer set_phase() for new code."""
        meta = self.storage.get_case_metadata(case_id)
        meta["status"] = new_status
        # Sync phase field
        if new_status == "archived":
            meta["phase"] = "archived"
        elif new_status == "active":
            meta["phase"] = "active"
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)

    def get_status(self, case_id: str) -> str:
        """Legacy-compatible: return status derived from phase if available."""
        meta = self.storage.get_case_metadata(case_id)
        phase = meta.get("phase")
        if phase:
            return _PHASE_TO_STATUS.get(phase, "active")
        return meta.get("status", "active")

    # ==== Case Phase Management ============================================

    @staticmethod
    def _migrate_phase(meta: dict) -> dict:
        """Enrich metadata with phase field if missing (lazy on-read migration)."""
        if not meta.get("phase"):
            meta["phase"] = meta.get("status", "active")
        if not meta.get("sub_phase"):
            meta["sub_phase"] = ""
        return meta

    def get_phase(self, case_id: str) -> tuple:
        """Return (phase, sub_phase) for a case."""
        meta = self.storage.get_case_metadata(case_id)
        meta = self._migrate_phase(meta)
        return meta.get("phase", "active"), meta.get("sub_phase", "")

    def set_phase(self, case_id: str, phase: str, sub_phase: str = "") -> None:
        """Set master phase (active/closed/archived) and optional sub-phase."""
        if phase not in PHASES:
            raise ValueError(f"Invalid phase: {phase}")
        meta = self.storage.get_case_metadata(case_id)
        old_phase = meta.get("phase", meta.get("status", "active"))
        meta["phase"] = phase
        meta["status"] = _PHASE_TO_STATUS.get(phase, "active")  # backward compat
        if phase == "active":
            meta["sub_phase"] = sub_phase
        elif phase == "closed":
            meta["sub_phase"] = ""
            meta["closed_at"] = _now_iso()  # Start the 21-day auto-archive clock
        else:
            meta["sub_phase"] = ""
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)
        desc = f"Phase changed: {old_phase} → {phase}"
        if sub_phase:
            desc += f" ({sub_phase})"
        self.log_activity(case_id, "phase_changed", desc)

    def set_sub_phase(self, case_id: str, sub_phase: str) -> None:
        """Change sub-phase within Active phase."""
        meta = self.storage.get_case_metadata(case_id)
        meta = self._migrate_phase(meta)
        if meta.get("phase") != "active":
            return  # Sub-phases only for active cases
        old = meta.get("sub_phase", "")
        meta["sub_phase"] = sub_phase
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)
        if old != sub_phase:
            self.log_activity(case_id, "sub_phase_changed",
                              f"Sub-phase: {old or '(none)'} → {sub_phase}")

    def purge_source_docs(self, case_id: str) -> int:
        """Delete source documents from an archived case. Returns file count."""
        with self._get_case_lock(case_id):
            meta = self.storage.get_case_metadata(case_id)
            meta = self._migrate_phase(meta)
            if meta.get("phase") != "archived":
                raise ValueError("Can only purge files from archived cases")
            count = self.storage.purge_source_docs(case_id)
            meta["purged"] = True
            meta["purged_at"] = _now_iso()
            meta["purged_file_count"] = count
            meta["last_updated"] = _now_iso()
            self.storage.update_case_metadata(case_id, meta)
        self.log_activity(case_id, "files_purged",
                          f"Purged {count} source document(s) from archived case")
        return count

    def check_auto_archive_closed_cases(self) -> List[str]:
        """Auto-archive cases that have been 'closed' longer than CLOSED_AUTO_ARCHIVE_DAYS.
        Returns list of case_ids that were auto-archived."""
        archived = []
        all_cases = self.storage.list_cases(include_archived=False)
        for c in all_cases:
            c = self._migrate_phase(c)
            if c.get("phase") != "closed":
                continue
            closed_at = c.get("closed_at", "")
            if not closed_at:
                continue
            try:
                age = (datetime.now() - datetime.fromisoformat(closed_at)).days
            except (ValueError, TypeError):
                continue
            if age >= CLOSED_AUTO_ARCHIVE_DAYS:
                cid = c.get("id", "")
                if cid:
                    self.set_phase(cid, "archived")
                    self.log_activity(cid, "auto_archived",
                                      f"Auto-archived after {age} days in Closed phase")
                    archived.append(cid)
        return archived

    # ==== Phase Configuration ==============================================

    def get_phase_config(self) -> dict:
        """Load customizable phase sub-phases. Returns defaults if not configured."""
        config = self.storage.load_global_json("phase_config.json")
        if not config or not isinstance(config, dict):
            return {k: list(v) for k, v in DEFAULT_PHASE_CONFIG.items()}
        # Merge defaults for any missing or malformed case types
        for ct, phases in DEFAULT_PHASE_CONFIG.items():
            if ct not in config or not isinstance(config[ct], list):
                config[ct] = list(phases)
        return config

    def save_phase_config(self, config: dict) -> None:
        """Save customized phase configuration."""
        self.storage.save_global_json("phase_config.json", config)

    def get_sub_phases_for_case(self, case_id: str) -> list:
        """Return the sub-phase list for a case's type."""
        meta = self.storage.get_case_metadata(case_id)
        case_type = meta.get("case_type", "criminal")
        config = self.get_phase_config()
        return config.get(case_type, config.get("criminal", []))

    # ==== Pinned / Favorite Cases ==========================================

    def pin_case(self, case_id: str) -> None:
        meta = self.storage.get_case_metadata(case_id)
        meta["pinned"] = True
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)

    def unpin_case(self, case_id: str) -> None:
        meta = self.storage.get_case_metadata(case_id)
        meta["pinned"] = False
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)

    def is_pinned(self, case_id: str) -> bool:
        return self.storage.get_case_metadata(case_id).get("pinned", False)

    # ==== Case Type & Client ==============================================

    def get_case_type(self, case_id: str) -> str:
        return self.storage.get_case_metadata(case_id).get("case_type", "criminal")

    def update_case_type(self, case_id: str, case_type: str) -> None:
        meta = self.storage.get_case_metadata(case_id)
        meta["case_type"] = case_type
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)

    def get_client_name(self, case_id: str) -> str:
        return self.storage.get_case_metadata(case_id).get("client_name", "")

    def update_client_name(self, case_id: str, client_name: str) -> None:
        meta = self.storage.get_case_metadata(case_id)
        meta["client_name"] = client_name
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)

    # ==== Assigned Staff ==================================================

    def get_assigned_staff(self, case_id: str) -> List[str]:
        """Return list of user IDs assigned to this case."""
        return self.storage.get_case_metadata(case_id).get("assigned_to", [])

    def set_assigned_staff(self, case_id: str, user_ids: List[str]) -> None:
        """Replace the full assigned-staff list for this case."""
        meta = self.storage.get_case_metadata(case_id)
        meta["assigned_to"] = user_ids
        meta["last_updated"] = _now_iso()
        self.storage.update_case_metadata(case_id, meta)

    def add_assigned_staff(self, case_id: str, user_id: str) -> None:
        """Add a staff member to this case (no-op if already assigned)."""
        meta = self.storage.get_case_metadata(case_id)
        assigned = meta.get("assigned_to", [])
        if user_id not in assigned:
            assigned.append(user_id)
            meta["assigned_to"] = assigned
            meta["last_updated"] = _now_iso()
            self.storage.update_case_metadata(case_id, meta)

    def remove_assigned_staff(self, case_id: str, user_id: str) -> None:
        """Remove a staff member from this case."""
        meta = self.storage.get_case_metadata(case_id)
        assigned = meta.get("assigned_to", [])
        if user_id in assigned:
            assigned.remove(user_id)
            meta["assigned_to"] = assigned
            meta["last_updated"] = _now_iso()
            self.storage.update_case_metadata(case_id, meta)

    # ==== Directives ======================================================

    def load_directives(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "directives.json", [])

    def save_directive(self, case_id: str, text: str,
                       category: str = "instruction") -> str:
        directives = self.load_directives(case_id)
        directive_id = _new_id()
        directives.append({
            "id": directive_id,
            "text": text,
            "category": category,
            "created_at": _now_iso(),
        })
        self.storage.save_json(case_id, "directives.json", directives)
        self.log_activity(case_id, "directive_added", f"[{category}] {text[:60]}")
        return directive_id

    def update_directive(self, case_id: str, directive_id: str, new_text: str) -> None:
        directives = self.load_directives(case_id)
        for d in directives:
            if d.get("id") == directive_id:
                d["text"] = new_text
                break
        self.storage.save_json(case_id, "directives.json", directives)

    def delete_directive(self, case_id: str, directive_id: str) -> None:
        directives = self.load_directives(case_id)
        directives = [d for d in directives if d.get("id") != directive_id]
        self.storage.save_json(case_id, "directives.json", directives)

    # ==== Files / Documents ===============================================

    def save_file(self, case_id: str, file_obj, filename: str) -> str:
        """Save an uploaded file. *file_obj* must have .read() or be bytes."""
        if hasattr(file_obj, "read"):
            data = file_obj.read()
        elif isinstance(file_obj, bytes):
            data = file_obj
        else:
            data = bytes(file_obj)
        with self._get_case_lock(case_id):
            path = self.storage.save_file(case_id, filename, data)
        self.log_activity(case_id, "file_uploaded", filename)
        return path

    def get_case_files(self, case_id: str) -> List[str]:
        return self.storage.get_case_files(case_id)

    def delete_file(self, case_id: str, filename: str) -> bool:
        result = self.storage.delete_file(case_id, filename)
        if result:
            self.log_activity(case_id, "file_deleted", filename)
        return result

    def get_file_path(self, case_id: str, filename: str) -> str:
        return self.storage.get_file_path(case_id, filename)

    def get_ordered_files(self, case_id: str) -> List[str]:
        """Return full file paths in user-defined order, with unordered files appended."""
        order = self.storage.get_file_order(case_id)  # basenames
        all_paths = self.get_case_files(case_id)  # full paths
        # Build basename → full path map
        path_map = {os.path.basename(p): p for p in all_paths}
        ordered = [path_map[name] for name in order if name in path_map]
        ordered_set = set(ordered)
        remaining = sorted(p for p in all_paths if p not in ordered_set)
        return ordered + remaining

    def save_file_order(self, case_id: str, order: List[str]) -> None:
        self.storage.save_file_order(case_id, order)

    # Alias used by UI
    set_file_order = save_file_order

    # ==== State (Legacy root-level) =======================================

    def save_state(self, case_id: str, state: Dict) -> None:
        self.storage.save_state(case_id, _serialize_state(state))

    def load_state(self, case_id: str) -> Optional[Dict]:
        data = self.storage.load_state(case_id)
        if data:
            return _deserialize_state(data)
        return None

    # ==== Preparation Management ==========================================

    def create_preparation(self, case_id: str, prep_type: str,
                           name: str = "") -> str:
        """Create a new preparation within a case. Returns prep_id."""
        if prep_type not in PREP_TYPES:
            prep_type = "trial"

        prep_id = _new_id()
        now = _now_iso()
        with self._get_case_lock(case_id):
            preps = self.storage.list_preparations(case_id)
            preps.append({
                "id": prep_id,
                "type": prep_type,
                "name": name,
                "created_at": now,
                "last_updated": now,
            })
            self.storage.save_preparations_index(case_id, preps)
            self.storage.create_preparation_dir(case_id, prep_id)
        self.log_activity(case_id, "prep_created", f"{prep_type}: {name or prep_id}")
        return prep_id

    def list_preparations(self, case_id: str) -> List[Dict]:
        return self.storage.list_preparations(case_id)

    def get_preparation(self, case_id: str, prep_id: str) -> Optional[Dict]:
        preps = self.list_preparations(case_id)
        for p in preps:
            if p.get("id") == prep_id:
                return p
        return None

    def delete_preparation(self, case_id: str, prep_id: str) -> None:
        with self._get_case_lock(case_id):
            preps = self.list_preparations(case_id)
            preps = [p for p in preps if p.get("id") != prep_id]
            self.storage.save_preparations_index(case_id, preps)
            self.storage.delete_preparation_dir(case_id, prep_id)

    def rename_preparation(self, case_id: str, prep_id: str, new_name: str) -> None:
        with self._get_case_lock(case_id):
            preps = self.list_preparations(case_id)
            for p in preps:
                if p.get("id") == prep_id:
                    p["name"] = new_name
                    p["last_updated"] = _now_iso()
                    break
            self.storage.save_preparations_index(case_id, preps)

    def clone_preparation(self, case_id: str, source_prep_id: str,
                          new_name: str = "") -> str:
        """Deep copy a preparation. Returns the new prep_id."""
        new_prep_id = _new_id()
        with self._get_case_lock(case_id):
            source_prep = self.get_preparation(case_id, source_prep_id)
            source_type = source_prep.get("type", "trial") if source_prep else "trial"
            self.storage.clone_preparation(case_id, source_prep_id, new_prep_id)
            preps = self.list_preparations(case_id)
            now = _now_iso()
            preps.append({
                "id": new_prep_id,
                "type": source_type,
                "name": new_name or f"Copy of {source_prep_id}",
                "created_at": now,
                "last_updated": now,
            })
            self.storage.save_preparations_index(case_id, preps)
        return new_prep_id

    def has_preparations(self, case_id: str) -> bool:
        return len(self.list_preparations(case_id)) > 0

    def is_legacy_case(self, case_id: str) -> bool:
        """Check if case uses legacy root-level state (no preparations)."""
        return not self.has_preparations(case_id) and self.storage.load_state(case_id) is not None

    def migrate_legacy_case(self, case_id: str) -> Optional[str]:
        """
        Migrate a legacy case to the preparations system.
        Creates a 'trial' preparation from the root state.json.
        Returns the new prep_id, or None if nothing to migrate.
        """
        old_state = self.load_state(case_id)
        if not old_state:
            return None
        prep_id = self.create_preparation(case_id, "trial", "Trial Preparation (Migrated)")
        self.save_prep_state(case_id, prep_id, old_state)
        self.log_activity(case_id, "legacy_migrated", f"Migrated to prep {prep_id}")
        return prep_id

    # ==== Preparation State ===============================================

    def save_prep_state(self, case_id: str, prep_id: str, state: Dict) -> None:
        with self._get_case_lock(case_id):
            serialized = _serialize_state(state)
            self.storage.save_prep_state(case_id, prep_id, serialized)
            # Update last_updated timestamp in prep index
            preps = self.list_preparations(case_id)
            for p in preps:
                if p.get("id") == prep_id:
                    p["last_updated"] = _now_iso()
                    break
            self.storage.save_preparations_index(case_id, preps)

    def load_prep_state(self, case_id: str, prep_id: str) -> Optional[Dict]:
        data = self.storage.load_prep_state(case_id, prep_id)
        if data:
            return _deserialize_state(data)
        return None

    def merge_append_only(self, case_id: str, prep_id: str,
                          new_state: Dict) -> Dict:
        """Merge new analysis results using append-only semantics, then save.

        NOTE: save_prep_state acquires the per-case lock internally, so we do NOT
        lock here to avoid deadlock.
        """
        existing = self.load_prep_state(case_id, prep_id) or {}
        merged = merge_append_only(existing, new_state)
        self.save_prep_state(case_id, prep_id, merged)
        return merged

    def import_from_prep(self, case_id: str, source_prep_id: str,
                         target_prep_id: str, keys: List[str]) -> Dict[str, int]:
        """Import selected data keys from one preparation to another."""
        source = self.load_prep_state(case_id, source_prep_id) or {}
        target = self.load_prep_state(case_id, target_prep_id) or {}
        counts: Dict[str, int] = {}
        for key in keys:
            val = source.get(key)
            if val:
                target[key] = val
                counts[key] = len(val) if isinstance(val, list) else 1
        self.save_prep_state(case_id, target_prep_id, target)
        return counts

    # ==== Notes ===========================================================

    def save_notes(self, case_id: str, prep_id: str, text: str) -> None:
        self.storage.save_prep_text(case_id, prep_id, "notes.txt", text)

    def load_notes(self, case_id: str, prep_id: str) -> str:
        return self.storage.load_prep_text(case_id, prep_id, "notes.txt")

    def save_case_notes(self, case_id: str, text: str) -> None:
        self.storage.save_text(case_id, "case_notes.txt", text)

    def load_case_notes(self, case_id: str) -> str:
        return self.storage.load_text(case_id, "case_notes.txt")

    def save_module_notes(self, case_id: str, prep_id: str,
                          module_name: str, text: str) -> None:
        self.storage.save_module_notes(case_id, prep_id, module_name, text)

    def load_module_notes(self, case_id: str, prep_id: str,
                          module_name: str) -> str:
        return self.storage.load_module_notes(case_id, prep_id, module_name)

    # ==== Chat History ====================================================

    def save_chat_history(self, case_id: str, prep_id: str,
                          messages: List[Dict]) -> None:
        self.storage.save_prep_json(case_id, prep_id, "chat_history.json", messages)

    def load_chat_history(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "chat_history.json", [])

    def clear_chat_history(self, case_id: str, prep_id: str) -> None:
        self.storage.save_prep_json(case_id, prep_id, "chat_history.json", [])

    # ==== Evidence Tags & Annotations =====================================

    def save_evidence_tags(self, case_id: str, prep_id: str,
                           tags: List[Dict]) -> None:
        self.storage.save_prep_json(case_id, prep_id, "evidence_tags.json", tags)

    def load_evidence_tags(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "evidence_tags.json", [])

    def save_annotations(self, case_id: str, prep_id: str,
                         annotations: List[Dict]) -> None:
        self.storage.save_prep_json(case_id, prep_id, "annotations.json", annotations)

    def load_annotations(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "annotations.json", [])

    # ==== Witness Preparation =============================================

    def save_witness_prep(self, case_id: str, prep_id: str,
                          data: List[Dict]) -> None:
        self.storage.save_prep_json(case_id, prep_id, "witness_prep.json", data)

    def load_witness_prep(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "witness_prep.json", [])

    # ==== Mock Examination Sessions =======================================

    def save_mock_exam_sessions(self, case_id: str, prep_id: str,
                                 sessions: List[Dict]) -> None:
        self.storage.save_prep_json(case_id, prep_id, "mock_exam_sessions.json", sessions)

    def load_mock_exam_sessions(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "mock_exam_sessions.json", [])

    def save_mock_exam_data(self, case_id: str, prep_id: str,
                             session_id: str, data: Dict) -> None:
        self.storage.save_prep_json(case_id, prep_id, f"mock_exam_{session_id}.json", data)

    def load_mock_exam_data(self, case_id: str, prep_id: str,
                             session_id: str) -> Optional[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, f"mock_exam_{session_id}.json", None)

    # ==== Journal =========================================================

    def load_journal(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "journal.json", [])

    def add_journal_entry(self, case_id: str, text: str,
                          category: str = "General") -> str:
        journal = self.load_journal(case_id)
        entry_id = _new_id()
        journal.insert(0, {
            "id": entry_id,
            "text": text,
            "category": category,
            "timestamp": _now_iso(),
        })
        self.storage.save_json(case_id, "journal.json", journal)
        return entry_id

    def delete_journal_entry(self, case_id: str, entry_id: str) -> None:
        journal = self.load_journal(case_id)
        journal = [e for e in journal if e.get("id") != entry_id]
        self.storage.save_json(case_id, "journal.json", journal)

    # ==== Contact Log =====================================================

    def load_contact_log(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "contact_log.json", [])

    def add_contact_log_entry(self, case_id: str, contact_type: str,
                              person: str, subject: str = "",
                              notes: str = "", contact_date: str = "",
                              contact_time: str = "",
                              duration_mins: int = 0) -> str:
        log = self.load_contact_log(case_id)
        entry_id = _new_id()
        log.insert(0, {
            "id": entry_id,
            "contact_type": contact_type,
            "person": person,
            "subject": subject,
            "notes": notes,
            "contact_date": contact_date or _now_iso()[:10],
            "contact_time": contact_time,
            "duration_mins": duration_mins,
            "created_at": _now_iso(),
        })
        self.storage.save_json(case_id, "contact_log.json", log)
        self.log_activity(case_id, "contact_logged", f"{contact_type} with {person}")
        return entry_id

    def update_contact_log_entry(self, case_id: str, entry_id: str,
                                 updates: Dict) -> None:
        log = self.load_contact_log(case_id)
        for entry in log:
            if entry.get("id") == entry_id:
                entry.update(updates)
                break
        self.storage.save_json(case_id, "contact_log.json", log)

    def delete_contact_log_entry(self, case_id: str, entry_id: str) -> None:
        log = self.load_contact_log(case_id)
        log = [e for e in log if e.get("id") != entry_id]
        self.storage.save_json(case_id, "contact_log.json", log)

    # ==== Deadlines =======================================================

    def load_deadlines(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "deadlines.json", [])

    def save_deadline(self, case_id: str, prep_id: str,
                      deadline: Dict) -> str:
        deadlines = self.load_deadlines(case_id, prep_id)
        if "id" not in deadline:
            deadline["id"] = _new_id()
        if "created_at" not in deadline:
            deadline["created_at"] = _now_iso()
        # Upsert
        updated = False
        for i, d in enumerate(deadlines):
            if d.get("id") == deadline["id"]:
                deadlines[i] = deadline
                updated = True
                break
        if not updated:
            deadlines.append(deadline)
        self.storage.save_prep_json(case_id, prep_id, "deadlines.json", deadlines)
        return deadline["id"]

    def delete_deadline(self, case_id: str, prep_id: str,
                        deadline_id: str) -> None:
        deadlines = self.load_deadlines(case_id, prep_id)
        deadlines = [d for d in deadlines if d.get("id") != deadline_id]
        self.storage.save_prep_json(case_id, prep_id, "deadlines.json", deadlines)

    def dismiss_reminder(self, case_id: str, prep_id: str,
                         deadline_id: str, reminder_day: int) -> None:
        deadlines = self.load_deadlines(case_id, prep_id)
        for d in deadlines:
            if d.get("id") == deadline_id:
                dismissed = d.get("dismissed_reminders", [])
                if reminder_day not in dismissed:
                    dismissed.append(reminder_day)
                d["dismissed_reminders"] = dismissed
                break
        self.storage.save_prep_json(case_id, prep_id, "deadlines.json", deadlines)

    def get_all_deadlines(self) -> List[Dict]:
        """Return all deadlines across all cases and preparations."""
        all_deadlines: List[Dict] = []
        for case in self.list_cases(include_archived=False):
            case_id = case.get("id", "")
            for prep in self.list_preparations(case_id):
                prep_id = prep.get("id", "")
                for d in self.load_deadlines(case_id, prep_id):
                    d["_case_id"] = case_id
                    d["_prep_id"] = prep_id
                    d["_case_name"] = case.get("name", case_id)
                    all_deadlines.append(d)
        return all_deadlines

    def get_active_reminders(self) -> List[Dict]:
        """Return deadlines with active (undismissed) reminders due today or past."""
        from datetime import date as _date
        today = _date.today()
        active = []
        for d in self.get_all_deadlines():
            try:
                deadline_date = _date.fromisoformat(d.get("date", ""))
            except (ValueError, TypeError):
                continue
            days_until = (deadline_date - today).days
            reminder_days = d.get("reminder_days", [7, 3, 1, 0])
            dismissed = set(d.get("dismissed_reminders", []))
            for rd in reminder_days:
                if days_until <= rd and rd not in dismissed:
                    active.append(d)
                    break
        return active

    # ==== Cost Tracking ===================================================

    def log_cost(self, case_id: str, prep_id: str, entry: Dict) -> None:
        history = self.get_cost_history(case_id, prep_id)
        if "timestamp" not in entry:
            entry["timestamp"] = _now_iso()
        history.append(entry)
        self.storage.save_prep_json(case_id, prep_id, "cost_history.json", history)

    def get_cost_history(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "cost_history.json", [])

    # ==== OCR Reviews =====================================================

    def save_ocr_reviews(self, case_id: str, reviews: list) -> None:
        self.storage.save_json(case_id, "ocr_reviews.json", reviews)

    def load_ocr_reviews(self, case_id: str) -> list:
        return self.storage.load_json(case_id, "ocr_reviews.json", [])

    def get_pending_ocr_reviews(self, case_id: str) -> list:
        return [r for r in self.load_ocr_reviews(case_id)
                if r.get("status") == "pending"]

    def resolve_ocr_review(self, case_id: str, review_id: str,
                           resolution: str, replacement_text: str = "") -> None:
        reviews = self.load_ocr_reviews(case_id)
        for r in reviews:
            if r.get("id") == review_id:
                r["status"] = resolution
                if replacement_text:
                    r["replacement_text"] = replacement_text
                break
        self.save_ocr_reviews(case_id, reviews)

    def clear_ocr_reviews(self, case_id: str) -> None:
        self.storage.save_json(case_id, "ocr_reviews.json", [])

    # ==== Snapshots =======================================================

    def save_snapshot(self, case_id: str, prep_id: str,
                      label: str = "") -> str:
        """Save a state checkpoint. Returns snapshot_id."""
        state = self.load_prep_state(case_id, prep_id)
        if not state:
            return ""
        snapshot_id = _new_id()
        metadata = {
            "id": snapshot_id,
            "label": label or f"Snapshot {_now_iso()[:16]}",
            "created_at": _now_iso(),
        }
        self.storage.save_snapshot(case_id, prep_id, snapshot_id,
                                   _serialize_state(state), metadata)
        self.log_activity(case_id, "snapshot_saved", label or snapshot_id)
        return snapshot_id

    def list_snapshots(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.list_snapshots(case_id, prep_id)

    def restore_snapshot(self, case_id: str, prep_id: str,
                         snapshot_id: str) -> Optional[Dict]:
        """Restore a snapshot. Returns the restored state or None."""
        state = self.storage.load_snapshot(case_id, prep_id, snapshot_id)
        if state:
            state = _deserialize_state(state)
            self.save_prep_state(case_id, prep_id, state)
            self.log_activity(case_id, "snapshot_restored", snapshot_id)
        return state

    # ==== File Tags =======================================================

    def get_file_tags(self, case_id: str, filename: str) -> List[str]:
        all_tags = self.storage.get_file_tags(case_id)
        return all_tags.get(filename, [])

    def set_file_tags(self, case_id: str, filename: str,
                      tags: List[str]) -> None:
        all_tags = self.storage.get_file_tags(case_id)
        all_tags[filename] = tags
        self.storage.save_file_tags(case_id, all_tags)

    def get_all_file_tags(self, case_id: str) -> Dict[str, List[str]]:
        return self.storage.get_file_tags(case_id)

    def get_custom_file_tag_categories(self, case_id: str) -> List[str]:
        """Return user-defined file tag categories for a case."""
        return self.storage.load_json(case_id, "custom_file_tags.json", [])

    def add_custom_file_tag_category(self, case_id: str, category: str) -> bool:
        """Add a custom file tag category. Returns False if duplicate."""
        category = category.strip()
        if not category:
            return False
        builtin_lower = {c.lower() for c in self.FILE_TAG_CATEGORIES}
        if category.lower() in builtin_lower:
            return False
        existing = self.get_custom_file_tag_categories(case_id)
        if category.lower() in {c.lower() for c in existing}:
            return False
        existing.append(category)
        self.storage.save_json(case_id, "custom_file_tags.json", existing)
        return True

    # ==== Relevance Scores ================================================

    def load_relevance_scores(self, case_id: str, prep_id: str) -> Dict[str, dict]:
        """Load file relevance scores for a prep. Returns empty dict if none."""
        return self.storage.load_prep_json(
            case_id, prep_id, "file_relevance.json", {},
        )

    def save_relevance_scores(self, case_id: str, prep_id: str,
                              scores: Dict[str, dict]) -> None:
        """Save file relevance scores for a prep."""
        self.storage.save_prep_json(
            case_id, prep_id, "file_relevance.json", scores,
        )

    # ==== Checklist =======================================================

    CHECKLIST_TEMPLATES = {
        "Trial Prep": [
            {"text": "Review all discovery documents", "category": "Documents", "priority": "high"},
            {"text": "Prepare witness list", "category": "Witnesses", "priority": "high"},
            {"text": "Draft opening statement", "category": "Statements", "priority": "high"},
            {"text": "Draft closing argument outline", "category": "Statements", "priority": "medium"},
            {"text": "Prepare exhibit list and organize exhibits", "category": "Exhibits", "priority": "high"},
            {"text": "File motions in limine", "category": "Motions", "priority": "high"},
            {"text": "Prepare voir dire questions", "category": "Jury", "priority": "medium"},
            {"text": "Review and challenge jury instructions", "category": "Jury", "priority": "medium"},
            {"text": "Prepare cross-examination outlines", "category": "Witnesses", "priority": "high"},
            {"text": "Prepare direct examination outlines", "category": "Witnesses", "priority": "high"},
            {"text": "Review prior testimony / depositions", "category": "Documents", "priority": "medium"},
            {"text": "Confirm client availability and prepare client", "category": "Client", "priority": "high"},
        ],
        "Motion Hearing": [
            {"text": "Draft motion brief", "category": "Motions", "priority": "high"},
            {"text": "Research supporting case law", "category": "Research", "priority": "high"},
            {"text": "Prepare oral argument outline", "category": "Statements", "priority": "medium"},
            {"text": "Anticipate opposing arguments", "category": "Strategy", "priority": "medium"},
            {"text": "Organize supporting exhibits", "category": "Exhibits", "priority": "medium"},
            {"text": "File and serve motion", "category": "Motions", "priority": "high"},
        ],
        "Client Intake": [
            {"text": "Initial client interview", "category": "Client", "priority": "high"},
            {"text": "Obtain signed retainer agreement", "category": "Admin", "priority": "high"},
            {"text": "Collect all relevant documents from client", "category": "Documents", "priority": "high"},
            {"text": "Request police reports / incident reports", "category": "Documents", "priority": "high"},
            {"text": "Photograph any physical evidence", "category": "Evidence", "priority": "medium"},
            {"text": "Identify potential witnesses", "category": "Witnesses", "priority": "medium"},
            {"text": "Set up case file and calendar deadlines", "category": "Admin", "priority": "high"},
        ],
    }

    def load_checklist_template(self, case_id: str, prep_id: str,
                                template_name: str) -> None:
        template = self.CHECKLIST_TEMPLATES.get(template_name, [])
        checklist = self.load_checklist(case_id, prep_id)
        for tmpl_item in template:
            item = {
                "id": _new_id(),
                "text": tmpl_item["text"],
                "checked": False,
                "category": tmpl_item.get("category", "General"),
                "priority": tmpl_item.get("priority", "medium"),
                "created_at": _now_iso(),
            }
            checklist.append(item)
        self.save_checklist(case_id, prep_id, checklist)

    def load_checklist(self, case_id: str, prep_id: str) -> List[Dict]:
        return self.storage.load_prep_json(case_id, prep_id, "checklist.json", [])

    def save_checklist(self, case_id: str, prep_id: str,
                       checklist: List[Dict]) -> None:
        self.storage.save_prep_json(case_id, prep_id, "checklist.json", checklist)

    def add_checklist_item(self, case_id: str, prep_id: str, text: str,
                           category: str = "General",
                           priority: str = "medium") -> Dict:
        checklist = self.load_checklist(case_id, prep_id)
        item = {
            "id": _new_id(),
            "text": text,
            "category": category,
            "priority": priority,
            "checked": False,
            "created_at": _now_iso(),
        }
        checklist.append(item)
        self.save_checklist(case_id, prep_id, checklist)
        return item

    def toggle_checklist_item(self, case_id: str, prep_id: str,
                              item_id: str, checked: bool) -> None:
        checklist = self.load_checklist(case_id, prep_id)
        for item in checklist:
            if item.get("id") == item_id:
                item["checked"] = checked
                break
        self.save_checklist(case_id, prep_id, checklist)

    def delete_checklist_item(self, case_id: str, prep_id: str,
                              item_id: str) -> None:
        checklist = self.load_checklist(case_id, prep_id)
        checklist = [c for c in checklist if c.get("id") != item_id]
        self.save_checklist(case_id, prep_id, checklist)

    # ==== Entities ========================================================

    def load_manual_entities(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "manual_entities.json", [])

    def save_manual_entity(self, case_id: str, name: str,
                           entity_type: str = "PERSON",
                           role: str = "", notes: str = "") -> str:
        entities = self.load_manual_entities(case_id)
        entity_id = _new_id()
        entities.append({
            "id": entity_id,
            "name": name,
            "type": entity_type,
            "role": role,
            "notes": notes,
            "created_at": _now_iso(),
        })
        self.storage.save_json(case_id, "manual_entities.json", entities)
        return entity_id

    def delete_manual_entity(self, case_id: str, entity_id: str) -> None:
        entities = self.load_manual_entities(case_id)
        entities = [e for e in entities if e.get("id") != entity_id]
        self.storage.save_json(case_id, "manual_entities.json", entities)

    def load_all_entities(self, include_analysis: bool = True) -> Dict[str, List[Dict]]:
        """Return all entities across all cases: {case_id: [entities]}.

        When include_analysis=True (default), also loads analysis-derived
        entities and witnesses from preparation states for conflict checking.
        """
        result: Dict[str, List[Dict]] = {}
        for case in self.list_cases():
            case_id = case.get("id", "")
            ents = list(self.load_manual_entities(case_id))

            if include_analysis:
                # Load analysis-derived entities from all preparations
                try:
                    for prep in self.list_preparations(case_id):
                        state = self.load_prep_state(case_id, prep["id"])
                        if not state:
                            continue
                        # Extracted entities
                        for ent in state.get("entities", []):
                            if isinstance(ent, dict) and ent.get("name"):
                                ents.append({
                                    "name": ent["name"],
                                    "role": ent.get("type", "entity"),
                                    "source": "analysis",
                                })
                        # Witnesses
                        for w in state.get("witnesses", []):
                            wname = w.get("name", "") if isinstance(w, dict) else str(w)
                            if wname.strip():
                                ents.append({
                                    "name": wname.strip(),
                                    "role": "witness",
                                    "source": "analysis",
                                })
                        # Cross/direct examination plans
                        for plan_key in ("cross_examination_plan", "direct_examination_plan"):
                            for item in state.get(plan_key, []):
                                if isinstance(item, dict):
                                    wn = item.get("witness_name", "") or item.get("name", "")
                                    if wn.strip():
                                        ents.append({
                                            "name": wn.strip(),
                                            "role": "witness",
                                            "source": plan_key,
                                        })
                except Exception as e:
                    logger.debug("Error loading analysis entities for %s: %s", case_id, e)

            if ents:
                result[case_id] = ents
        return result

    # ==== Major Document Drafts ==========================================

    def save_major_draft(self, case_id: str, draft: dict) -> str:
        """Save or update a major document draft. Returns draft_id."""
        import uuid as _uuid
        draft_id = draft.get("id") or str(_uuid.uuid4())[:8]
        draft["id"] = draft_id
        draft["updated_at"] = _now_iso()
        if "created_at" not in draft:
            draft["created_at"] = _now_iso()
        with self._get_case_lock(case_id):
            # Save full draft to individual file
            self.storage.save_json(case_id, f"major_drafts/{draft_id}.json", draft)
            # Update index
            index = self.storage.load_json(case_id, "major_drafts_index.json", [])
            if not isinstance(index, list):
                index = []
            # Remove old entry if updating
            index = [e for e in index if e.get("id") != draft_id]
            index.insert(0, {
                "id": draft_id,
                "doc_type": draft.get("doc_type", ""),
                "doc_subtype": draft.get("doc_subtype", ""),
                "title": draft.get("title", ""),
                "status": draft.get("status", "in_progress"),
                "created_at": draft.get("created_at", ""),
                "updated_at": draft.get("updated_at", ""),
                "section_count": len(draft.get("sections", [])),
                "outline_count": len(draft.get("outline", [])),
            })
            self.storage.save_json(case_id, "major_drafts_index.json", index)
        return draft_id

    def load_major_drafts(self, case_id: str) -> list:
        """List all major drafts for a case (index only)."""
        index = self.storage.load_json(case_id, "major_drafts_index.json", [])
        return index if isinstance(index, list) else []

    def load_major_draft(self, case_id: str, draft_id: str) -> Optional[Dict]:
        """Load a single complete draft with all sections."""
        return self.storage.load_json(case_id, f"major_drafts/{draft_id}.json")

    def delete_major_draft(self, case_id: str, draft_id: str) -> bool:
        """Delete a draft by ID. Updates index first, then removes file."""
        try:
            # Update index BEFORE deleting file (safer on failure)
            index = self.storage.load_json(case_id, "major_drafts_index.json", [])
            if isinstance(index, list):
                index = [e for e in index if e.get("id") != draft_id]
                self.storage.save_json(case_id, "major_drafts_index.json", index)
            # Remove draft file via storage API (not direct filesystem access)
            draft_filename = f"major_drafts/{draft_id}.json"
            try:
                self.storage.save_json(case_id, draft_filename, None)
            except Exception:
                pass  # File may already be gone
            # Try to remove the actual file using storage's path helper
            try:
                draft_path = Path(self.storage.get_file_path(case_id, "")).parent / "major_drafts" / f"{draft_id}.json"
                if draft_path.exists():
                    draft_path.unlink()
            except Exception:
                pass  # Best-effort cleanup
            return True
        except Exception as e:
            logger.error("Failed to delete major draft %s/%s: %s", case_id, draft_id, e)
            return False

    def update_major_draft(self, case_id: str, draft_id: str, updates: dict) -> bool:
        """Partial update of a draft (merges updates into existing)."""
        draft = self.load_major_draft(case_id, draft_id)
        if not draft:
            return False
        draft.update(updates)
        draft["updated_at"] = _now_iso()
        self.save_major_draft(case_id, draft)
        return True

    # ==== Activity Log ====================================================

    def log_activity(self, case_id: str, action: str,
                     detail: str = "", user_id: str = "",
                     user_name: str = "", category: str = "",
                     metadata: dict = None) -> None:
        """Log an activity entry with optional user attribution and metadata."""
        entry = {
            "action": action,
            "detail": detail,
            "timestamp": _now_iso(),
        }
        if user_id:
            entry["user_id"] = user_id
        if user_name:
            entry["user_name"] = user_name
        if category:
            entry["category"] = category
        if metadata:
            entry["metadata"] = metadata
        self.storage.append_activity(case_id, entry)

    def get_activity_log(self, case_id: str, limit: int = 50) -> List[Dict]:
        return self.storage.get_activity_log(case_id, limit=limit)

    # ==== Prospective Clients =============================================

    def load_prospective_clients(self) -> List[Dict]:
        return self.storage.load_prospective_clients()

    def save_prospective_client(self, name: str, contact_date: str = "",
                                phone: str = "", email: str = "",
                                notes: str = "", source: str = "",
                                status: str = "New") -> str:
        clients = self.load_prospective_clients()
        client_id = _new_id()
        clients.append({
            "id": client_id,
            "name": name,
            "contact_date": contact_date or _now_iso()[:10],
            "phone": phone,
            "email": email,
            "notes": notes,
            "source": source,
            "status": status,
            "created_at": _now_iso(),
        })
        self.storage.save_prospective_clients(clients)
        return client_id

    def update_prospective_client(self, client_id: str,
                                  updates: Dict) -> None:
        clients = self.load_prospective_clients()
        for c in clients:
            if c.get("id") == client_id:
                c.update(updates)
                break
        self.storage.save_prospective_clients(clients)

    def delete_prospective_client(self, client_id: str) -> None:
        clients = self.load_prospective_clients()
        clients = [c for c in clients if c.get("id") != client_id]
        self.storage.save_prospective_clients(clients)

    # ==== Financial Management ============================================

    def load_trust_ledger(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "trust_ledger.json", [])

    def add_trust_entry(self, case_id: str, entry_type: str,
                        amount: float, description: str = "",
                        reference: str = "") -> str:
        ledger = self.load_trust_ledger(case_id)
        entry_id = _new_id()
        ledger.append({
            "id": entry_id,
            "type": entry_type,
            "amount": amount,
            "description": description,
            "reference": reference,
            "date": _now_iso()[:10],
            "created_at": _now_iso(),
        })
        self.storage.save_json(case_id, "trust_ledger.json", ledger)
        return entry_id

    def delete_trust_entry(self, case_id: str, entry_id: str) -> None:
        ledger = self.load_trust_ledger(case_id)
        ledger = [e for e in ledger if e.get("id") != entry_id]
        self.storage.save_json(case_id, "trust_ledger.json", ledger)

    def load_fee_agreement(self, case_id: str) -> Dict:
        return self.storage.load_json(case_id, "fee_agreement.json", {})

    def save_fee_agreement(self, case_id: str, agreement: Dict) -> None:
        self.storage.save_json(case_id, "fee_agreement.json", agreement)

    # ==== Litigation Holds ================================================

    def load_litigation_holds(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "litigation_holds.json", [])

    def add_litigation_hold(self, case_id: str, custodian: str,
                            description: str = "", scope: str = "",
                            issued_date: str = "") -> str:
        holds = self.load_litigation_holds(case_id)
        hold_id = _new_id()
        holds.append({
            "id": hold_id,
            "custodian": custodian,
            "description": description,
            "scope": scope,
            "issued_date": issued_date or _now_iso()[:10],
            "status": "active",
            "created_at": _now_iso(),
        })
        self.storage.save_json(case_id, "litigation_holds.json", holds)
        return hold_id

    def update_litigation_hold(self, case_id: str, hold_id: str,
                               updates: Dict) -> None:
        holds = self.load_litigation_holds(case_id)
        for h in holds:
            if h.get("id") == hold_id:
                h.update(updates)
                break
        self.storage.save_json(case_id, "litigation_holds.json", holds)

    def delete_litigation_hold(self, case_id: str, hold_id: str) -> None:
        holds = self.load_litigation_holds(case_id)
        holds = [h for h in holds if h.get("id") != hold_id]
        self.storage.save_json(case_id, "litigation_holds.json", holds)

    # ==== Supervision Log =================================================

    def load_supervision_log(self, case_id: str) -> List[Dict]:
        return self.storage.load_json(case_id, "supervision_log.json", [])

    def add_supervision_entry(self, case_id: str, delegatee: str,
                              task: str, deadline: str = "",
                              notes: str = "") -> str:
        log = self.load_supervision_log(case_id)
        entry_id = _new_id()
        log.append({
            "id": entry_id,
            "delegatee": delegatee,
            "task": task,
            "deadline": deadline,
            "notes": notes,
            "status": "assigned",
            "created_at": _now_iso(),
        })
        self.storage.save_json(case_id, "supervision_log.json", log)
        return entry_id

    def update_supervision_entry(self, case_id: str, entry_id: str,
                                 updates: Dict) -> None:
        log = self.load_supervision_log(case_id)
        for e in log:
            if e.get("id") == entry_id:
                e.update(updates)
                break
        self.storage.save_json(case_id, "supervision_log.json", log)

    def delete_supervision_entry(self, case_id: str, entry_id: str) -> None:
        log = self.load_supervision_log(case_id)
        log = [e for e in log if e.get("id") != entry_id]
        self.storage.save_json(case_id, "supervision_log.json", log)

    # ==== Document Fingerprinting =========================================

    def compute_docs_fingerprint(self, case_id: str) -> str:
        return self.storage.compute_docs_fingerprint(case_id)

    def compute_per_file_fingerprint(self, case_id: str) -> Dict[str, str]:
        return self.storage.compute_per_file_fingerprint(case_id)

    @staticmethod
    def diff_file_fingerprints(saved: Dict[str, str],
                               current: Dict[str, str]) -> Dict:
        """Compare two fingerprint dicts and return added/removed/changed."""
        saved_set = set(saved.keys())
        current_set = set(current.keys())
        return {
            "added": sorted(current_set - saved_set),
            "removed": sorted(saved_set - current_set),
            "changed": sorted(
                f for f in saved_set & current_set
                if saved[f] != current[f]
            ),
        }
