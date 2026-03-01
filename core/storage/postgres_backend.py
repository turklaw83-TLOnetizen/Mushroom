# ---- PostgreSQL Storage Backend -------------------------------------------
# Implements StorageBackend ABC using PostgreSQL via SQLAlchemy 2.0.
#
# Design:
#   - Uses SYNCHRONOUS SQLAlchemy sessions because CaseManager and all
#     background workers (bg_analysis, ingestion, OCR) call storage methods
#     synchronously from daemon threads.
#   - Binary files (source_docs, OCR cache) remain on disk.
#   - Structured data (cases, preps, activity, notes, etc.) lives in Postgres.
#   - JSONB columns for flexible dict data (case metadata, prep state).

import hashlib
import json
import zlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, select, delete, update, func, text
from sqlalchemy.orm import Session, sessionmaker

from core.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class PostgresStorageBackend(StorageBackend):
    """
    PostgreSQL-backed storage implementing the full StorageBackend ABC.

    Binary files stay on the filesystem (source_docs/, ocr_cache/).
    All structured/metadata goes into PostgreSQL via SQLAlchemy.
    """

    def __init__(self, database_url: str, data_dir: str):
        """
        Args:
            database_url: Synchronous PostgreSQL URL, e.g.
                          postgresql://user:pass@host:5432/mushroom_cloud
            data_dir: Filesystem path for binary file storage (source_docs, etc.)
        """
        # Convert async URL to sync if needed
        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=3,   # Fix #4: keep total connections low for Neon
        )
        self._SessionFactory = sessionmaker(self._engine, expire_on_commit=False)

        self.data_dir = Path(data_dir)
        self.cases_dir = self.data_dir / "cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def _session(self) -> Session:
        return self._SessionFactory()

    def _source_docs_dir(self, case_id: str) -> Path:
        d = self.cases_dir / case_id / "source_docs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _advisory_lock(self, session: Session, case_id: str, resource: str = "") -> None:
        """Acquire a PostgreSQL advisory lock scoped to (case_id, resource).

        Uses pg_advisory_xact_lock which is automatically released at
        transaction end. The lock key is a deterministic int64 derived
        from a hash of the case_id + resource string.

        This prevents concurrent writes from clobbering each other
        when two background workers update the same prep state.
        """
        key = zlib.crc32(f"{case_id}:{resource}".encode()) & 0x7FFFFFFF
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    # ---- Case CRUD -------------------------------------------------------

    def list_cases(self, include_archived: bool = False) -> List[Dict]:
        from api.models import Case
        with self._session() as session:
            q = select(Case)
            if not include_archived:
                q = q.where(Case.phase != "archived")
            q = q.order_by(Case.name)
            rows = session.execute(q).scalars().all()
            return [r.to_metadata_dict() for r in rows]

    def get_case_metadata(self, case_id: str) -> Dict:
        from api.models import Case
        with self._session() as session:
            row = session.get(Case, case_id)
            if row:
                return row.to_metadata_dict()
            return {}

    def create_case(self, case_id: str, metadata: Dict) -> None:
        from api.models import Case
        metadata["id"] = case_id
        case = Case.from_metadata_dict(metadata)
        # Ensure source_docs dir exists on disk
        self._source_docs_dir(case_id)
        with self._session() as session:
            session.add(case)
            session.commit()

    def update_case_metadata(self, case_id: str, metadata: Dict) -> None:
        from api.models import Case
        known_cols = {
            "name", "description", "case_type", "case_category",
            "case_subcategory", "client_name", "jurisdiction", "phase",
            "sub_phase", "status", "pinned", "assigned_to",
        }
        with self._session() as session:
            self._advisory_lock(session, case_id, "case_meta")
            row = session.get(Case, case_id)
            if not row:
                return
            for k, v in metadata.items():
                if k in known_cols and hasattr(row, k):
                    setattr(row, k, v)
            # Handle special fields
            if "purged" in metadata:
                row.purged = metadata["purged"]
            if "purged_at" in metadata:
                row.purged_at = metadata.get("purged_at")
            if "purged_file_count" in metadata:
                row.purged_file_count = metadata.get("purged_file_count", 0)
            if "closed_at" in metadata:
                row.closed_at = metadata.get("closed_at")
            # Anything else goes into metadata_extra
            extra = row.metadata_extra or {}
            skip_keys = known_cols | {
                "id", "created_at", "last_updated", "purged", "purged_at",
                "purged_file_count", "closed_at",
            }
            for k, v in metadata.items():
                if k not in skip_keys:
                    extra[k] = v
            row.metadata_extra = extra
            row.last_updated = datetime.now(timezone.utc)
            session.commit()

    def delete_case(self, case_id: str) -> None:
        from api.models import Case
        with self._session() as session:
            row = session.get(Case, case_id)
            if row:
                session.delete(row)
                session.commit()
        # Also remove files from disk
        case_dir = self.cases_dir / case_id
        if case_dir.exists():
            shutil.rmtree(case_dir)

    def case_exists(self, case_id: str) -> bool:
        from api.models import Case
        with self._session() as session:
            return session.get(Case, case_id) is not None

    # ---- File / Document Management --------------------------------------
    # Files stay on disk — metadata tracked in DB.

    def save_file(self, case_id: str, filename: str, data: bytes) -> str:
        from api.models import FileMetadata
        docs_dir = self._source_docs_dir(case_id)
        path = (docs_dir / filename).resolve()
        if not str(path).startswith(str(docs_dir.resolve())):
            raise ValueError(f"Path traversal rejected: {filename}")
        path.write_bytes(data)

        # Upsert file metadata
        with self._session() as session:
            existing = session.execute(
                select(FileMetadata).where(
                    FileMetadata.case_id == case_id,
                    FileMetadata.filename == filename,
                )
            ).scalar_one_or_none()
            if existing:
                existing.disk_path = str(path)
                existing.file_size = len(data)
            else:
                session.add(FileMetadata(
                    case_id=case_id,
                    filename=filename,
                    disk_path=str(path),
                    file_size=len(data),
                ))
            session.commit()
        return str(path)

    def record_file_metadata(self, case_id: str, filename: str,
                             disk_path: str, file_size: int = 0) -> None:
        """Record file metadata in DB WITHOUT writing to disk.

        Used by the migration script to register existing files that
        are already on disk without overwriting them.
        """
        from api.models import FileMetadata
        with self._session() as session:
            existing = session.execute(
                select(FileMetadata).where(
                    FileMetadata.case_id == case_id,
                    FileMetadata.filename == filename,
                )
            ).scalar_one_or_none()
            if existing:
                existing.disk_path = disk_path
                existing.file_size = file_size
            else:
                session.add(FileMetadata(
                    case_id=case_id,
                    filename=filename,
                    disk_path=disk_path,
                    file_size=file_size,
                ))
            session.commit()

    def get_case_files(self, case_id: str) -> List[str]:
        """Return full paths to all source document files (from disk)."""
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return []
        return sorted(
            str(f) for f in docs_dir.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )

    def delete_file(self, case_id: str, filename: str) -> bool:
        from api.models import FileMetadata
        docs_dir = self._source_docs_dir(case_id)
        path = (docs_dir / filename).resolve()
        if not str(path).startswith(str(docs_dir.resolve())):
            raise ValueError(f"Path traversal rejected: {filename}")

        deleted = False
        if path.exists():
            path.unlink()
            deleted = True

        # Remove from DB
        with self._session() as session:
            session.execute(
                delete(FileMetadata).where(
                    FileMetadata.case_id == case_id,
                    FileMetadata.filename == filename,
                )
            )
            session.commit()
        return deleted

    def get_file_path(self, case_id: str, filename: str) -> str:
        return str(self._source_docs_dir(case_id) / filename)

    def purge_source_docs(self, case_id: str) -> int:
        from api.models import FileMetadata
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return 0
        count = 0
        for f in docs_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                f.unlink()
                count += 1
        # Remove all file metadata from DB
        with self._session() as session:
            session.execute(
                delete(FileMetadata).where(FileMetadata.case_id == case_id)
            )
            session.commit()
        return count

    # ---- State Persistence (Legacy) --------------------------------------

    def save_state(self, case_id: str, state: Dict) -> None:
        self._save_case_json(case_id, "_legacy_state.json", state)

    def load_state(self, case_id: str) -> Optional[Dict]:
        data = self._load_case_json(case_id, "_legacy_state.json")
        return data if isinstance(data, dict) else None

    # ---- Preparation Management ------------------------------------------

    def list_preparations(self, case_id: str) -> List[Dict]:
        from api.models import Preparation
        with self._session() as session:
            rows = session.execute(
                select(Preparation)
                .where(Preparation.case_id == case_id)
                .order_by(Preparation.created_at)
            ).scalars().all()
            return [r.to_index_dict() for r in rows]

    def save_preparations_index(self, case_id: str, preps: List[Dict]) -> None:
        from api.models import Preparation
        with self._session() as session:
            self._advisory_lock(session, case_id, "preps_index")
            # Get existing preps
            existing = {
                r.id: r for r in session.execute(
                    select(Preparation).where(Preparation.case_id == case_id)
                ).scalars().all()
            }
            incoming_ids = set()
            for p in preps:
                pid = p.get("id", "")
                incoming_ids.add(pid)
                if pid in existing:
                    # Update
                    row = existing[pid]
                    row.name = p.get("name", row.name)
                    row.prep_type = p.get("type", row.prep_type)
                    if p.get("last_updated"):
                        try:
                            row.last_updated = datetime.fromisoformat(p["last_updated"])
                        except (ValueError, TypeError):
                            pass
                else:
                    # Insert
                    created_at = None
                    if p.get("created_at"):
                        try:
                            created_at = datetime.fromisoformat(p["created_at"])
                        except (ValueError, TypeError):
                            pass
                    session.add(Preparation(
                        id=pid,
                        case_id=case_id,
                        name=p.get("name", ""),
                        prep_type=p.get("type", "trial"),
                        created_at=created_at or datetime.now(timezone.utc),
                    ))
            # Delete preps not in the incoming list
            for pid, row in existing.items():
                if pid not in incoming_ids:
                    session.delete(row)
            session.commit()

    def create_preparation_dir(self, case_id: str, prep_id: str) -> None:
        # No-op for Postgres — prep created via save_preparations_index
        pass

    def delete_preparation_dir(self, case_id: str, prep_id: str) -> None:
        from api.models import Preparation, Snapshot, ModuleNote, PrepJsonData, PrepTextData
        with self._session() as session:
            # Delete related records
            for model in [Snapshot, ModuleNote, PrepJsonData, PrepTextData]:
                session.execute(
                    delete(model).where(
                        model.case_id == case_id,
                        model.prep_id == prep_id,
                    )
                )
            # Delete the prep itself
            session.execute(
                delete(Preparation).where(
                    Preparation.id == prep_id,
                    Preparation.case_id == case_id,
                )
            )
            session.commit()

    def save_prep_state(self, case_id: str, prep_id: str, state: Dict) -> None:
        from api.models import Preparation
        with self._session() as session:
            self._advisory_lock(session, case_id, f"prep_state:{prep_id}")
            row = session.execute(
                select(Preparation).where(
                    Preparation.id == prep_id,
                    Preparation.case_id == case_id,
                )
            ).scalar_one_or_none()
            if row:
                row.state = state
                row.last_updated = datetime.now(timezone.utc)
                session.commit()

    def load_prep_state(self, case_id: str, prep_id: str) -> Optional[Dict]:
        from api.models import Preparation
        with self._session() as session:
            row = session.execute(
                select(Preparation).where(
                    Preparation.id == prep_id,
                    Preparation.case_id == case_id,
                )
            ).scalar_one_or_none()
            if row and isinstance(row.state, dict):
                return row.state
            return None

    # ---- Generic JSON I/O ------------------------------------------------

    def load_json(self, case_id: str, filename: str, default: Any = None) -> Any:
        return self._load_case_json(case_id, filename, default)

    def save_json(self, case_id: str, filename: str, data: Any) -> None:
        self._save_case_json(case_id, filename, data)

    def load_prep_json(self, case_id: str, prep_id: str, filename: str, default: Any = None) -> Any:
        from api.models import PrepJsonData
        with self._session() as session:
            row = session.execute(
                select(PrepJsonData).where(
                    PrepJsonData.case_id == case_id,
                    PrepJsonData.prep_id == prep_id,
                    PrepJsonData.filename == filename,
                )
            ).scalar_one_or_none()
            if row and row.data is not None:
                return row.data
            return default

    def save_prep_json(self, case_id: str, prep_id: str, filename: str, data: Any) -> None:
        from api.models import PrepJsonData
        with self._session() as session:
            row = session.execute(
                select(PrepJsonData).where(
                    PrepJsonData.case_id == case_id,
                    PrepJsonData.prep_id == prep_id,
                    PrepJsonData.filename == filename,
                )
            ).scalar_one_or_none()
            if row:
                row.data = data
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(PrepJsonData(
                    case_id=case_id,
                    prep_id=prep_id,
                    filename=filename,
                    data=data,
                ))
            session.commit()

    # ---- Text Files ------------------------------------------------------

    def load_text(self, case_id: str, filename: str, default: str = "") -> str:
        from api.models import CaseTextData
        with self._session() as session:
            row = session.execute(
                select(CaseTextData).where(
                    CaseTextData.case_id == case_id,
                    CaseTextData.filename == filename,
                )
            ).scalar_one_or_none()
            if row and row.content is not None:
                return row.content
            return default

    def save_text(self, case_id: str, filename: str, text: str) -> None:
        from api.models import CaseTextData
        with self._session() as session:
            row = session.execute(
                select(CaseTextData).where(
                    CaseTextData.case_id == case_id,
                    CaseTextData.filename == filename,
                )
            ).scalar_one_or_none()
            if row:
                row.content = text
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(CaseTextData(
                    case_id=case_id, filename=filename, content=text,
                ))
            session.commit()

    def load_prep_text(self, case_id: str, prep_id: str, filename: str, default: str = "") -> str:
        from api.models import PrepTextData
        with self._session() as session:
            row = session.execute(
                select(PrepTextData).where(
                    PrepTextData.case_id == case_id,
                    PrepTextData.prep_id == prep_id,
                    PrepTextData.filename == filename,
                )
            ).scalar_one_or_none()
            if row and row.content is not None:
                return row.content
            return default

    def save_prep_text(self, case_id: str, prep_id: str, filename: str, text: str) -> None:
        from api.models import PrepTextData
        with self._session() as session:
            row = session.execute(
                select(PrepTextData).where(
                    PrepTextData.case_id == case_id,
                    PrepTextData.prep_id == prep_id,
                    PrepTextData.filename == filename,
                )
            ).scalar_one_or_none()
            if row:
                row.content = text
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(PrepTextData(
                    case_id=case_id, prep_id=prep_id,
                    filename=filename, content=text,
                ))
            session.commit()

    # ---- Module Notes ----------------------------------------------------

    def load_module_notes(self, case_id: str, prep_id: str, module_name: str) -> str:
        from api.models import ModuleNote
        with self._session() as session:
            row = session.execute(
                select(ModuleNote).where(
                    ModuleNote.case_id == case_id,
                    ModuleNote.prep_id == prep_id,
                    ModuleNote.module_name == module_name,
                )
            ).scalar_one_or_none()
            return row.content if row and row.content else ""

    def save_module_notes(self, case_id: str, prep_id: str, module_name: str, text: str) -> None:
        from api.models import ModuleNote
        with self._session() as session:
            row = session.execute(
                select(ModuleNote).where(
                    ModuleNote.case_id == case_id,
                    ModuleNote.prep_id == prep_id,
                    ModuleNote.module_name == module_name,
                )
            ).scalar_one_or_none()
            if row:
                row.content = text
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(ModuleNote(
                    case_id=case_id, prep_id=prep_id,
                    module_name=module_name, content=text,
                ))
            session.commit()

    # ---- Snapshots -------------------------------------------------------

    def save_snapshot(self, case_id: str, prep_id: str, snapshot_id: str,
                      state: Dict, metadata: Dict) -> None:
        from api.models import Snapshot
        with self._session() as session:
            session.add(Snapshot(
                id=snapshot_id,
                case_id=case_id,
                prep_id=prep_id,
                state=state,
                snapshot_metadata=metadata,
            ))
            session.commit()

    def list_snapshots(self, case_id: str, prep_id: str) -> List[Dict]:
        from api.models import Snapshot
        with self._session() as session:
            rows = session.execute(
                select(Snapshot)
                .where(Snapshot.case_id == case_id, Snapshot.prep_id == prep_id)
                .order_by(Snapshot.created_at)
            ).scalars().all()
            results = []
            for r in rows:
                meta = dict(r.snapshot_metadata) if r.snapshot_metadata else {}
                meta.setdefault("id", r.id)
                results.append(meta)
            return results

    def load_snapshot(self, case_id: str, prep_id: str, snapshot_id: str) -> Optional[Dict]:
        from api.models import Snapshot
        with self._session() as session:
            row = session.get(Snapshot, snapshot_id)
            if row and isinstance(row.state, dict):
                return row.state
            return None

    # ---- Activity Log ----------------------------------------------------

    def append_activity(self, case_id: str, entry: Dict) -> None:
        from api.models import ActivityLog
        with self._session() as session:
            session.add(ActivityLog(
                case_id=case_id,
                action=entry.get("action", ""),
                description=entry.get("description", ""),
                user_id=entry.get("user_id", ""),
                timestamp=datetime.now(timezone.utc),
            ))
            # Cap at 2000 per case
            count = session.execute(
                select(func.count(ActivityLog.id)).where(ActivityLog.case_id == case_id)
            ).scalar_one()
            if count > 2000:
                # Delete oldest entries beyond 2000
                oldest = session.execute(
                    select(ActivityLog.id)
                    .where(ActivityLog.case_id == case_id)
                    .order_by(ActivityLog.timestamp.desc())
                    .offset(2000)
                ).scalars().all()
                if oldest:
                    session.execute(
                        delete(ActivityLog).where(ActivityLog.id.in_(oldest))
                    )
            session.commit()

    def get_activity_log(self, case_id: str, limit: int = 50) -> List[Dict]:
        from api.models import ActivityLog
        with self._session() as session:
            rows = session.execute(
                select(ActivityLog)
                .where(ActivityLog.case_id == case_id)
                .order_by(ActivityLog.timestamp.desc())
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "action": r.action,
                    "description": r.description or "",
                    "user_id": r.user_id or "",
                    "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                }
                for r in rows
            ]

    # ---- File Tags & Ordering --------------------------------------------

    def get_file_tags(self, case_id: str) -> Dict[str, List[str]]:
        data = self._load_case_json(case_id, "_file_tags", {})
        return data if isinstance(data, dict) else {}

    def save_file_tags(self, case_id: str, tags: Dict[str, List[str]]) -> None:
        self._save_case_json(case_id, "_file_tags", tags)

    def get_file_order(self, case_id: str) -> List[str]:
        data = self._load_case_json(case_id, "_file_order", [])
        return data if isinstance(data, list) else []

    def save_file_order(self, case_id: str, order: List[str]) -> None:
        self._save_case_json(case_id, "_file_order", order)

    # ---- Clone / Copy Operations -----------------------------------------

    def clone_case(self, source_id: str, target_id: str) -> None:
        from api.models import (
            Case, Preparation, Snapshot, ActivityLog, FileMetadata,
            ModuleNote, CaseJsonData, CaseTextData, PrepJsonData, PrepTextData,
        )
        with self._session() as session:
            src = session.get(Case, source_id)
            if not src:
                raise FileNotFoundError(f"Source case {source_id} not found")
            if session.get(Case, target_id):
                raise FileExistsError(f"Target case {target_id} already exists")

            # Clone case metadata
            d = src.to_metadata_dict()
            d["id"] = target_id
            new_case = Case.from_metadata_dict(d)
            session.add(new_case)
            session.flush()

            # Clone preparations
            for prep in session.execute(
                select(Preparation).where(Preparation.case_id == source_id)
            ).scalars().all():
                session.add(Preparation(
                    id=prep.id,
                    case_id=target_id,
                    name=prep.name,
                    prep_type=prep.prep_type,
                    state=prep.state,
                    created_at=prep.created_at,
                ))

            # Clone case JSON data
            for row in session.execute(
                select(CaseJsonData).where(CaseJsonData.case_id == source_id)
            ).scalars().all():
                session.add(CaseJsonData(
                    case_id=target_id, filename=row.filename, data=row.data,
                ))

            # Clone case text data
            for row in session.execute(
                select(CaseTextData).where(CaseTextData.case_id == source_id)
            ).scalars().all():
                session.add(CaseTextData(
                    case_id=target_id, filename=row.filename, content=row.content,
                ))

            session.commit()

        # Clone files on disk
        src_dir = self.cases_dir / source_id / "source_docs"
        dst_dir = self.cases_dir / target_id / "source_docs"
        if src_dir.exists():
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)

    def clone_preparation(self, case_id: str, source_prep_id: str,
                          target_prep_id: str) -> None:
        from api.models import (
            Preparation, Snapshot, ModuleNote, PrepJsonData, PrepTextData,
        )
        with self._session() as session:
            src = session.execute(
                select(Preparation).where(
                    Preparation.id == source_prep_id,
                    Preparation.case_id == case_id,
                )
            ).scalar_one_or_none()
            if not src:
                raise FileNotFoundError(f"Source prep {source_prep_id} not found")

            # Clone the prep
            session.add(Preparation(
                id=target_prep_id,
                case_id=case_id,
                name=src.name,
                prep_type=src.prep_type,
                state=src.state,
            ))

            # Clone prep JSON data
            for row in session.execute(
                select(PrepJsonData).where(
                    PrepJsonData.case_id == case_id,
                    PrepJsonData.prep_id == source_prep_id,
                )
            ).scalars().all():
                session.add(PrepJsonData(
                    case_id=case_id, prep_id=target_prep_id,
                    filename=row.filename, data=row.data,
                ))

            # Clone prep text data
            for row in session.execute(
                select(PrepTextData).where(
                    PrepTextData.case_id == case_id,
                    PrepTextData.prep_id == source_prep_id,
                )
            ).scalars().all():
                session.add(PrepTextData(
                    case_id=case_id, prep_id=target_prep_id,
                    filename=row.filename, content=row.content,
                ))

            # Clone module notes
            for row in session.execute(
                select(ModuleNote).where(
                    ModuleNote.case_id == case_id,
                    ModuleNote.prep_id == source_prep_id,
                )
            ).scalars().all():
                session.add(ModuleNote(
                    case_id=case_id, prep_id=target_prep_id,
                    module_name=row.module_name, content=row.content,
                ))

            # Clone snapshots
            import uuid
            for row in session.execute(
                select(Snapshot).where(
                    Snapshot.case_id == case_id,
                    Snapshot.prep_id == source_prep_id,
                )
            ).scalars().all():
                session.add(Snapshot(
                    id=uuid.uuid4().hex[:12],
                    case_id=case_id, prep_id=target_prep_id,
                    state=row.state, snapshot_metadata=row.snapshot_metadata,
                ))

            session.commit()

    # ---- Prospective Clients (cross-case data) ---------------------------

    def load_prospective_clients(self) -> List[Dict]:
        from api.models import Client
        with self._session() as session:
            rows = session.execute(
                select(Client).where(Client.client_type == "prospective")
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.client_type,
                    "contact_info": r.contact_info or {},
                    "notes": r.notes or "",
                    **(r.intake_data or {}),
                }
                for r in rows
            ]

    def save_prospective_clients(self, clients: List[Dict]) -> None:
        from api.models import Client
        with self._session() as session:
            # Delete existing prospective clients
            session.execute(
                delete(Client).where(Client.client_type == "prospective")
            )
            for c in clients:
                session.add(Client(
                    id=c.get("id", ""),
                    name=c.get("name", "Unknown"),
                    client_type="prospective",
                    contact_info=c.get("contact_info", {}),
                    notes=c.get("notes", ""),
                ))
            session.commit()

    # ---- Global JSON (cross-case data) -----------------------------------

    def load_global_json(self, filename: str, default: Any = None) -> Any:
        from api.models import GlobalSetting
        with self._session() as session:
            row = session.get(GlobalSetting, filename)
            if row and row.value is not None:
                return row.value
            return default

    def save_global_json(self, filename: str, data: Any) -> None:
        from api.models import GlobalSetting
        with self._session() as session:
            row = session.get(GlobalSetting, filename)
            if row:
                row.value = data
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(GlobalSetting(key=filename, value=data))
            session.commit()

    # ---- Document Fingerprinting -----------------------------------------
    # These always scan the actual files on disk for accuracy.

    def compute_docs_fingerprint(self, case_id: str) -> str:
        docs_dir = self._source_docs_dir(case_id)
        if not docs_dir.exists():
            return ""
        entries = []
        for f in sorted(docs_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                entries.append(f"{f.name}:{f.stat().st_size}")
        return hashlib.sha256("|".join(entries).encode()).hexdigest()

    def compute_per_file_fingerprint(self, case_id: str) -> Dict[str, str]:
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

    # ---- Internal Helpers ------------------------------------------------

    def _load_case_json(self, case_id: str, filename: str, default: Any = None) -> Any:
        from api.models import CaseJsonData
        with self._session() as session:
            row = session.execute(
                select(CaseJsonData).where(
                    CaseJsonData.case_id == case_id,
                    CaseJsonData.filename == filename,
                )
            ).scalar_one_or_none()
            if row and row.data is not None:
                return row.data
            return default

    def _save_case_json(self, case_id: str, filename: str, data: Any) -> None:
        from api.models import CaseJsonData
        with self._session() as session:
            row = session.execute(
                select(CaseJsonData).where(
                    CaseJsonData.case_id == case_id,
                    CaseJsonData.filename == filename,
                )
            ).scalar_one_or_none()
            if row:
                row.data = data
                row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(CaseJsonData(
                    case_id=case_id, filename=filename, data=data,
                ))
            session.commit()
