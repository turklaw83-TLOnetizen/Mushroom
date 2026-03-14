# ---- JSON File-System Storage Backend -------------------------------------
# Implements StorageBackend ABC using the exact same directory layout as the
# original case_manager.py so existing case data loads without migration.
#
# Directory layout per case:
#   data/cases/{case_id}/
#       config.json
#       state.json              (legacy root-level state)
#       directives.json
#       source_docs/            (uploaded documents)
#       preparations/
#           preparations.json   (index)
#           {prep_id}/
#               state.json
#               cost_history.json
#               notes.txt
#               chat_history.json
#               evidence_tags.json
#               annotations.json
#               witness_prep.json
#               deadlines.json
#               checklist.json
#               snapshots/{snapshot_id}/ (state.json + metadata.json)
#               module_notes/{module_name}.txt
#       journal.json
#       contact_log.json
#       manual_entities.json
#       ocr_reviews.json
#       file_tags.json
#       custom_file_tags.json
#       file_order.json
#       activity_log.json
#       notes.txt / case_notes.txt
#       fee_agreement.json
#       litigation_holds.json
#       supervision_log.json
#       trust_ledger.json

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class JSONStorageBackend(StorageBackend):
    """
    File-system storage backend using JSON files.
    Maintains exact backward compatibility with the original case_manager.py layout.
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.cases_dir = self.data_dir / "cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    # ---- Helpers ---------------------------------------------------------

    def _case_dir(self, case_id: str) -> Path:
        return self.cases_dir / case_id

    def _source_docs_dir(self, case_id: str) -> Path:
        return self._case_dir(case_id) / "source_docs"

    def _preps_dir(self, case_id: str) -> Path:
        return self._case_dir(case_id) / "preparations"

    def _prep_dir(self, case_id: str, prep_id: str) -> Path:
        return self._preps_dir(case_id) / prep_id

    def _read_json(self, path: Path, default: Any = None) -> Any:
        """Read a JSON file with UTF-8 encoding. Return *default* on any error."""
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return default

    def _write_json(self, path: Path, data: Any) -> None:
        """Atomically write JSON with UTF-8 encoding and pretty-print.

        Uses tmp file + os.replace to prevent truncated/corrupt files on crash
        or concurrent access from multiple case threads.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            os.replace(str(tmp_path), str(path))
        except OSError:
            logger.exception("Failed to write %s", path)
            # Clean up tmp file on failure
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    def _read_text(self, path: Path, default: str = "") -> str:
        if not path.exists():
            return default
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return default

    def _write_text(self, path: Path, text: str) -> None:
        """Atomically write a text file (tmp + os.replace)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp_path.write_text(text, encoding="utf-8")
            os.replace(str(tmp_path), str(path))
        except OSError:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    # ---- Case CRUD -------------------------------------------------------

    def list_cases(self, include_archived: bool = False) -> List[Dict]:
        cases = []
        if not self.cases_dir.exists():
            return cases
        for d in sorted(self.cases_dir.iterdir()):
            if not d.is_dir():
                continue
            cfg = self._read_json(d / "config.json", {})
            if not cfg:
                continue
            # Phase-aware filtering (backward compatible)
            _phase = cfg.get("phase") or cfg.get("status", "active")
            if not include_archived and _phase == "archived":
                continue
            cfg.setdefault("id", d.name)
            cases.append(cfg)
        return cases

    def get_case_metadata(self, case_id: str) -> Dict:
        return self._read_json(self._case_dir(case_id) / "config.json", {})

    def create_case(self, case_id: str, metadata: Dict) -> None:
        case_dir = self._case_dir(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "source_docs").mkdir(exist_ok=True)
        preps_dir = case_dir / "preparations"
        preps_dir.mkdir(exist_ok=True)
        self._write_json(case_dir / "config.json", metadata)
        # Initialize empty preparations index
        if not (preps_dir / "preparations.json").exists():
            self._write_json(preps_dir / "preparations.json", [])

    def update_case_metadata(self, case_id: str, metadata: Dict) -> None:
        self._write_json(self._case_dir(case_id) / "config.json", metadata)

    def delete_case(self, case_id: str) -> None:
        case_dir = self._case_dir(case_id)
        if case_dir.exists():
            shutil.rmtree(case_dir)

    def case_exists(self, case_id: str) -> bool:
        return (self._case_dir(case_id) / "config.json").exists()

    # ---- File / Document Management --------------------------------------

    def save_file(self, case_id: str, filename: str, data: bytes) -> str:
        docs_dir = self._source_docs_dir(case_id)
        docs_dir.mkdir(parents=True, exist_ok=True)
        path = (docs_dir / filename).resolve()
        if not str(path).startswith(str(docs_dir.resolve())):
            raise ValueError(f"Path traversal rejected: {filename}")
        path.write_bytes(data)
        return str(path)

    def get_case_files(self, case_id: str) -> List[str]:
        """Return full paths to all source document files for a case."""
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return []
        return sorted(
            str(f) for f in docs_dir.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )

    def delete_file(self, case_id: str, filename: str) -> bool:
        docs_dir = self._source_docs_dir(case_id)
        path = (docs_dir / filename).resolve()
        if not str(path).startswith(str(docs_dir.resolve())):
            raise ValueError(f"Path traversal rejected: {filename}")
        if path.exists():
            path.unlink()
            return True
        return False

    def get_file_path(self, case_id: str, filename: str) -> str:
        docs_dir = self._source_docs_dir(case_id)
        path = (docs_dir / filename).resolve()
        if not str(path).startswith(str(docs_dir.resolve())):
            raise ValueError(f"Path traversal rejected: {filename}")
        return str(path)

    def purge_source_docs(self, case_id: str) -> int:
        """Delete all files in source_docs/. Return count of files deleted."""
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return 0
        count = 0
        for f in docs_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                f.unlink()
                count += 1
        return count

    # ---- State Persistence (Legacy) --------------------------------------

    def save_state(self, case_id: str, state: Dict) -> None:
        self._write_json(self._case_dir(case_id) / "state.json", state)

    def load_state(self, case_id: str) -> Optional[Dict]:
        data = self._read_json(self._case_dir(case_id) / "state.json")
        return data if isinstance(data, dict) else None

    # ---- Preparation Management ------------------------------------------

    def list_preparations(self, case_id: str) -> List[Dict]:
        path = self._preps_dir(case_id) / "preparations.json"
        data = self._read_json(path, [])
        return data if isinstance(data, list) else []

    def save_preparations_index(self, case_id: str, preps: List[Dict]) -> None:
        self._write_json(self._preps_dir(case_id) / "preparations.json", preps)

    def create_preparation_dir(self, case_id: str, prep_id: str) -> None:
        prep_dir = self._prep_dir(case_id, prep_id)
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "snapshots").mkdir(exist_ok=True)
        (prep_dir / "module_notes").mkdir(exist_ok=True)

    def delete_preparation_dir(self, case_id: str, prep_id: str) -> None:
        prep_dir = self._prep_dir(case_id, prep_id)
        if prep_dir.exists():
            shutil.rmtree(prep_dir)

    def save_prep_state(self, case_id: str, prep_id: str, state: Dict) -> None:
        self._write_json(self._prep_dir(case_id, prep_id) / "state.json", state)

    def load_prep_state(self, case_id: str, prep_id: str) -> Optional[Dict]:
        data = self._read_json(self._prep_dir(case_id, prep_id) / "state.json")
        return data if isinstance(data, dict) else None

    # ---- Generic JSON I/O ------------------------------------------------

    def load_json(self, case_id: str, filename: str, default: Any = None) -> Any:
        return self._read_json(self._case_dir(case_id) / filename, default)

    def save_json(self, case_id: str, filename: str, data: Any) -> None:
        self._write_json(self._case_dir(case_id) / filename, data)

    def load_prep_json(self, case_id: str, prep_id: str, filename: str, default: Any = None) -> Any:
        return self._read_json(self._prep_dir(case_id, prep_id) / filename, default)

    def save_prep_json(self, case_id: str, prep_id: str, filename: str, data: Any) -> None:
        self._write_json(self._prep_dir(case_id, prep_id) / filename, data)

    # ---- Text Files ------------------------------------------------------

    def load_text(self, case_id: str, filename: str, default: str = "") -> str:
        return self._read_text(self._case_dir(case_id) / filename, default)

    def save_text(self, case_id: str, filename: str, text: str) -> None:
        self._write_text(self._case_dir(case_id) / filename, text)

    def load_prep_text(self, case_id: str, prep_id: str, filename: str, default: str = "") -> str:
        return self._read_text(self._prep_dir(case_id, prep_id) / filename, default)

    def save_prep_text(self, case_id: str, prep_id: str, filename: str, text: str) -> None:
        self._write_text(self._prep_dir(case_id, prep_id) / filename, text)

    # ---- Module Notes ----------------------------------------------------

    def load_module_notes(self, case_id: str, prep_id: str, module_name: str) -> str:
        path = self._prep_dir(case_id, prep_id) / "module_notes" / f"{module_name}.txt"
        return self._read_text(path)

    def save_module_notes(self, case_id: str, prep_id: str, module_name: str, text: str) -> None:
        path = self._prep_dir(case_id, prep_id) / "module_notes" / f"{module_name}.txt"
        self._write_text(path, text)

    # ---- Snapshots -------------------------------------------------------

    def save_snapshot(self, case_id: str, prep_id: str, snapshot_id: str,
                      state: Dict, metadata: Dict) -> None:
        snap_dir = self._prep_dir(case_id, prep_id) / "snapshots" / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(snap_dir / "state.json", state)
        self._write_json(snap_dir / "metadata.json", metadata)

    def list_snapshots(self, case_id: str, prep_id: str) -> List[Dict]:
        snaps_dir = self._prep_dir(case_id, prep_id) / "snapshots"
        if not snaps_dir.exists():
            return []
        results = []
        for d in sorted(snaps_dir.iterdir()):
            if d.is_dir():
                meta = self._read_json(d / "metadata.json", {})
                meta.setdefault("id", d.name)
                results.append(meta)
        return results

    def load_snapshot(self, case_id: str, prep_id: str, snapshot_id: str) -> Optional[Dict]:
        path = self._prep_dir(case_id, prep_id) / "snapshots" / snapshot_id / "state.json"
        data = self._read_json(path)
        return data if isinstance(data, dict) else None

    # ---- Activity Log ----------------------------------------------------

    def append_activity(self, case_id: str, entry: Dict) -> None:
        path = self._case_dir(case_id) / "activity_log.json"
        log = self._read_json(path, [])
        if not isinstance(log, list):
            log = []
        log.insert(0, entry)  # newest first
        # Cap at 2000 entries
        if len(log) > 2000:
            log = log[:2000]
        self._write_json(path, log)

    def get_activity_log(self, case_id: str, limit: int = 50) -> List[Dict]:
        log = self._read_json(self._case_dir(case_id) / "activity_log.json", [])
        if not isinstance(log, list):
            return []
        return log[:limit]

    # ---- File Tags & Ordering --------------------------------------------

    def get_file_tags(self, case_id: str) -> Dict[str, List[str]]:
        data = self._read_json(self._case_dir(case_id) / "file_tags.json", {})
        return data if isinstance(data, dict) else {}

    def save_file_tags(self, case_id: str, tags: Dict[str, List[str]]) -> None:
        self._write_json(self._case_dir(case_id) / "file_tags.json", tags)

    def get_file_order(self, case_id: str) -> List[str]:
        data = self._read_json(self._case_dir(case_id) / "file_order.json", [])
        return data if isinstance(data, list) else []

    def save_file_order(self, case_id: str, order: List[str]) -> None:
        self._write_json(self._case_dir(case_id) / "file_order.json", order)

    # ---- Clone / Copy Operations -----------------------------------------

    def clone_case(self, source_id: str, target_id: str) -> None:
        src = self._case_dir(source_id)
        dst = self._case_dir(target_id)
        if dst.exists():
            raise FileExistsError(f"Target case {target_id} already exists")
        shutil.copytree(src, dst)

    def clone_preparation(self, case_id: str, source_prep_id: str,
                          target_prep_id: str) -> None:
        src = self._prep_dir(case_id, source_prep_id)
        dst = self._prep_dir(case_id, target_prep_id)
        if dst.exists():
            raise FileExistsError(f"Target preparation {target_prep_id} already exists")
        shutil.copytree(src, dst)

    # ---- Prospective Clients ---------------------------------------------

    def load_prospective_clients(self) -> List[Dict]:
        path = self.data_dir / "prospective_clients.json"
        data = self._read_json(path, [])
        return data if isinstance(data, list) else []

    def save_prospective_clients(self, clients: List[Dict]) -> None:
        self._write_json(self.data_dir / "prospective_clients.json", clients)

    # ---- Global JSON (cross-case data) -----------------------------------

    def load_global_json(self, filename: str, default: Any = None) -> Any:
        return self._read_json(self.data_dir / filename, default)

    def save_global_json(self, filename: str, data: Any) -> None:
        self._write_json(self.data_dir / filename, data)

    # ---- Document Fingerprinting -----------------------------------------

    def compute_docs_fingerprint(self, case_id: str) -> str:
        """SHA-256 hash of sorted (filename, size) tuples for change detection."""
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return ""
        entries = []
        for f in sorted(docs_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                entries.append(f"{f.name}:{f.stat().st_size}")
        return hashlib.sha256("|".join(entries).encode()).hexdigest()

    def compute_per_file_fingerprint(self, case_id: str) -> Dict[str, str]:
        """Return {filename: sha256_of_contents} for each source doc."""
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return {}
        result: Dict[str, str] = {}
        for f in sorted(docs_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for block in iter(lambda: fh.read(8192), b""):
                        h.update(block)
                result[f.name] = h.hexdigest()
        return result
