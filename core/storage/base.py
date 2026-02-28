# ---- StorageBackend ABC ---------------------------------------------------
# Abstract base class defining all persistence operations.
# Concrete implementations (JSONStorageBackend, future SQL, S3, etc.)
# must implement every method.

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StorageBackend(abc.ABC):
    """
    Abstract interface for all case data persistence.

    Every method that touches the filesystem (or database, or cloud) lives
    here.  ``CaseManager`` delegates to whichever backend is configured,
    keeping business logic and I/O cleanly separated.
    """

    # ---- Case CRUD -------------------------------------------------------

    @abc.abstractmethod
    def list_cases(self, include_archived: bool = False) -> List[Dict]:
        """Return metadata dicts for all cases."""

    @abc.abstractmethod
    def get_case_metadata(self, case_id: str) -> Dict:
        """Return the config.json contents for a single case."""

    @abc.abstractmethod
    def create_case(self, case_id: str, metadata: Dict) -> None:
        """Create the directory structure and write initial config.json."""

    @abc.abstractmethod
    def update_case_metadata(self, case_id: str, metadata: Dict) -> None:
        """Overwrite config.json for the given case."""

    @abc.abstractmethod
    def delete_case(self, case_id: str) -> None:
        """Permanently remove a case directory."""

    @abc.abstractmethod
    def case_exists(self, case_id: str) -> bool:
        """Return True if the case directory and config.json exist."""

    # ---- File / Document Management --------------------------------------

    @abc.abstractmethod
    def save_file(self, case_id: str, filename: str, data: bytes) -> str:
        """Save an uploaded document to the case's source_docs/. Return full path."""

    @abc.abstractmethod
    def get_case_files(self, case_id: str) -> List[str]:
        """Return list of filenames in source_docs/."""

    @abc.abstractmethod
    def delete_file(self, case_id: str, filename: str) -> bool:
        """Remove a file from source_docs/. Return True on success."""

    @abc.abstractmethod
    def get_file_path(self, case_id: str, filename: str) -> str:
        """Return the absolute path to a source_docs file."""

    # ---- State Persistence (Legacy root-level) ---------------------------

    @abc.abstractmethod
    def save_state(self, case_id: str, state: Dict) -> None:
        """Save the root-level state.json (legacy, pre-preparations)."""

    @abc.abstractmethod
    def load_state(self, case_id: str) -> Optional[Dict]:
        """Load the root-level state.json. Return None if missing."""

    # ---- Preparation Management ------------------------------------------

    @abc.abstractmethod
    def list_preparations(self, case_id: str) -> List[Dict]:
        """Return the preparations index list."""

    @abc.abstractmethod
    def save_preparations_index(self, case_id: str, preps: List[Dict]) -> None:
        """Overwrite the preparations.json index file."""

    @abc.abstractmethod
    def create_preparation_dir(self, case_id: str, prep_id: str) -> None:
        """Create the directory for a new preparation."""

    @abc.abstractmethod
    def delete_preparation_dir(self, case_id: str, prep_id: str) -> None:
        """Remove a preparation directory and its contents."""

    @abc.abstractmethod
    def save_prep_state(self, case_id: str, prep_id: str, state: Dict) -> None:
        """Save the state.json for a preparation."""

    @abc.abstractmethod
    def load_prep_state(self, case_id: str, prep_id: str) -> Optional[Dict]:
        """Load the state.json for a preparation. Return None if missing."""

    # ---- Generic JSON I/O ------------------------------------------------

    @abc.abstractmethod
    def load_json(self, case_id: str, filename: str, default: Any = None) -> Any:
        """Load a JSON file from the case root. Return *default* if missing."""

    @abc.abstractmethod
    def save_json(self, case_id: str, filename: str, data: Any) -> None:
        """Save a JSON file to the case root."""

    @abc.abstractmethod
    def load_prep_json(self, case_id: str, prep_id: str, filename: str, default: Any = None) -> Any:
        """Load a JSON file from a preparation directory."""

    @abc.abstractmethod
    def save_prep_json(self, case_id: str, prep_id: str, filename: str, data: Any) -> None:
        """Save a JSON file to a preparation directory."""

    # ---- Text Files (notes) ----------------------------------------------

    @abc.abstractmethod
    def load_text(self, case_id: str, filename: str, default: str = "") -> str:
        """Load a text file from the case root."""

    @abc.abstractmethod
    def save_text(self, case_id: str, filename: str, text: str) -> None:
        """Save a text file to the case root."""

    @abc.abstractmethod
    def load_prep_text(self, case_id: str, prep_id: str, filename: str, default: str = "") -> str:
        """Load a text file from a preparation directory."""

    @abc.abstractmethod
    def save_prep_text(self, case_id: str, prep_id: str, filename: str, text: str) -> None:
        """Save a text file to a preparation directory."""

    # ---- Module Notes (per-module text within a prep) --------------------

    @abc.abstractmethod
    def load_module_notes(self, case_id: str, prep_id: str, module_name: str) -> str:
        """Load notes for a specific module within a preparation."""

    @abc.abstractmethod
    def save_module_notes(self, case_id: str, prep_id: str, module_name: str, text: str) -> None:
        """Save notes for a specific module within a preparation."""

    # ---- Snapshots -------------------------------------------------------

    @abc.abstractmethod
    def save_snapshot(self, case_id: str, prep_id: str, snapshot_id: str,
                      state: Dict, metadata: Dict) -> None:
        """Save a state snapshot with metadata."""

    @abc.abstractmethod
    def list_snapshots(self, case_id: str, prep_id: str) -> List[Dict]:
        """List all snapshot metadata dicts for a preparation."""

    @abc.abstractmethod
    def load_snapshot(self, case_id: str, prep_id: str, snapshot_id: str) -> Optional[Dict]:
        """Load a snapshot's state dict."""

    # ---- Activity Log ----------------------------------------------------

    @abc.abstractmethod
    def append_activity(self, case_id: str, entry: Dict) -> None:
        """Append an entry to the case activity log."""

    @abc.abstractmethod
    def get_activity_log(self, case_id: str, limit: int = 50) -> List[Dict]:
        """Return the most recent *limit* activity entries."""

    # ---- File Tags & Ordering --------------------------------------------

    @abc.abstractmethod
    def get_file_tags(self, case_id: str) -> Dict[str, List[str]]:
        """Return {filename: [tags]} map."""

    @abc.abstractmethod
    def save_file_tags(self, case_id: str, tags: Dict[str, List[str]]) -> None:
        """Save the full file tags map."""

    @abc.abstractmethod
    def get_file_order(self, case_id: str) -> List[str]:
        """Return the user-defined file ordering."""

    @abc.abstractmethod
    def save_file_order(self, case_id: str, order: List[str]) -> None:
        """Save the user-defined file ordering."""

    # ---- Clone / Copy Operations -----------------------------------------

    @abc.abstractmethod
    def clone_case(self, source_id: str, target_id: str) -> None:
        """Deep-copy a case directory to a new case_id."""

    @abc.abstractmethod
    def clone_preparation(self, case_id: str, source_prep_id: str,
                          target_prep_id: str) -> None:
        """Deep-copy a preparation directory within a case."""

    # ---- Prospective Clients (cross-case data) ---------------------------

    @abc.abstractmethod
    def load_prospective_clients(self) -> List[Dict]:
        """Load the global prospective clients list."""

    @abc.abstractmethod
    def save_prospective_clients(self, clients: List[Dict]) -> None:
        """Save the global prospective clients list."""

    # ---- Purge (Lifecycle) ------------------------------------------------

    @abc.abstractmethod
    def purge_source_docs(self, case_id: str) -> int:
        """Delete all files in source_docs/. Return count of files deleted."""

    # ---- Global JSON (cross-case data) -----------------------------------

    @abc.abstractmethod
    def load_global_json(self, filename: str, default: Any = None) -> Any:
        """Load a JSON file from the global data directory (not per-case)."""

    @abc.abstractmethod
    def save_global_json(self, filename: str, data: Any) -> None:
        """Save a JSON file to the global data directory."""

    # ---- Document Fingerprinting -----------------------------------------

    @abc.abstractmethod
    def compute_docs_fingerprint(self, case_id: str) -> str:
        """Return a hash representing the current source_docs contents."""

    @abc.abstractmethod
    def compute_per_file_fingerprint(self, case_id: str) -> Dict[str, str]:
        """Return {filename: hash} for each file in source_docs."""
