# ── Cloud Backup Integration ──────────────────────────────────────────
# Provides programmatic backup/restore for AllRise Beta case data.
# Supports two targets:
#   1. Dropbox (via local sync folder — Dropbox desktop app handles upload)
#   2. Backblaze B2 (via b2sdk)
#
# This module is used by:
#   - The deploy/backup.sh script (full system backups)
#   - The app itself (on-demand case exports, pre-purge safety copies)

import hashlib
import io
import json
import logging
import os
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Dropbox Sync Backup ──────────────────────────────────────────────
# Uses local Dropbox folder. Dropbox desktop app handles cloud upload.

class DropboxSyncBackup:
    """Backup to Dropbox via local sync folder.

    The Dropbox desktop app must be installed and the sync folder accessible.
    This class simply copies files into the Dropbox folder structure and
    relies on the desktop app for actual cloud synchronization.
    """

    def __init__(self, dropbox_dir: str = ""):
        """
        Args:
            dropbox_dir: Path to Dropbox sync folder. If empty, attempts
                         to auto-detect from common locations.
        """
        if dropbox_dir:
            self.dropbox_dir = Path(dropbox_dir)
        else:
            self.dropbox_dir = self._detect_dropbox_folder()
        self.backup_dir = self.dropbox_dir / "AllRise-Beta-Backups"

    @staticmethod
    def _detect_dropbox_folder() -> Path:
        """Auto-detect the Dropbox sync folder."""
        home = Path.home()
        candidates = [
            home / "Dropbox",
            home / "Dropbox (Personal)",
            home / "Dropbox (Business)",
            Path("D:/Dropbox"),
            Path("E:/Dropbox"),
        ]
        # Check Dropbox info file
        info_file = home / ".dropbox" / "info.json"
        if info_file.exists():
            try:
                info = json.loads(info_file.read_text())
                for key in ("personal", "business"):
                    if key in info and "path" in info[key]:
                        return Path(info[key]["path"])
            except (json.JSONDecodeError, KeyError):
                pass

        for c in candidates:
            if c.is_dir():
                return c

        return home / "Dropbox"  # Fallback

    @property
    def is_available(self) -> bool:
        """Check if Dropbox folder exists and is accessible."""
        return self.dropbox_dir.is_dir()

    def backup_case(self, data_dir: str, case_id: str) -> Optional[str]:
        """Backup a single case's data to Dropbox.

        Args:
            data_dir: The TLO data directory (parent of cases/)
            case_id: The case ID to backup

        Returns:
            Path to the backup directory, or None on failure.
        """
        case_dir = Path(data_dir) / "cases" / case_id
        if not case_dir.is_dir():
            logger.warning("Case directory not found: %s", case_dir)
            return None

        dest = self.backup_dir / "cases" / case_id
        try:
            dest.mkdir(parents=True, exist_ok=True)
            # Sync case directory
            _sync_directory(case_dir, dest)
            logger.info("Backed up case %s to Dropbox: %s", case_id, dest)
            return str(dest)
        except Exception as e:
            logger.error("Failed to backup case %s to Dropbox: %s", case_id, e)
            return None

    def backup_case_archive(self, data_dir: str, case_id: str) -> Optional[str]:
        """Create a compressed archive of a case before purging.

        This is called before purge_source_docs to ensure files are backed up.

        Returns:
            Path to the .tar.gz archive, or None on failure.
        """
        case_dir = Path(data_dir) / "cases" / case_id
        if not case_dir.is_dir():
            return None

        archives_dir = self.backup_dir / "archives"
        archives_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{case_id}_{timestamp}.tar.gz"
        archive_path = archives_dir / archive_name

        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(str(case_dir), arcname=case_id)
            logger.info("Created pre-purge archive: %s", archive_path)
            return str(archive_path)
        except Exception as e:
            logger.error("Failed to create case archive: %s", e)
            return None

    def backup_full(self, data_dir: str) -> Optional[str]:
        """Full backup of the entire data directory.

        Returns:
            Path to the backup archive, or None on failure.
        """
        data_path = Path(data_dir)
        if not data_path.is_dir():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"tlo-backup-{timestamp}.tar.gz"
        archive_path = self.backup_dir / archive_name

        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(str(data_path), arcname="data")
            logger.info("Created full backup: %s", archive_path)

            # Also sync latest state for quick file-level access
            latest_dir = self.backup_dir / "latest"
            latest_dir.mkdir(parents=True, exist_ok=True)
            _sync_directory(data_path, latest_dir,
                           exclude={".pyc", "__pycache__", ".DS_Store"})

            return str(archive_path)
        except Exception as e:
            logger.error("Full backup failed: %s", e)
            return None

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backup archives."""
        results = []
        if not self.backup_dir.exists():
            return results

        for f in sorted(self.backup_dir.glob("tlo-backup-*.tar.gz"), reverse=True):
            results.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })

        archives_dir = self.backup_dir / "archives"
        if archives_dir.is_dir():
            for f in sorted(archives_dir.glob("*.tar.gz"), reverse=True):
                results.append({
                    "filename": f.name,
                    "path": str(f),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                    "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "type": "case_archive",
                })

        return results

    def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """Remove backups older than retention_days. Returns count deleted."""
        if not self.backup_dir.exists():
            return 0

        cutoff = datetime.now().timestamp() - (retention_days * 86400)
        deleted = 0

        for f in self.backup_dir.glob("tlo-backup-*.tar.gz"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
                logger.info("Deleted old backup: %s", f.name)

        return deleted


# ── Backblaze B2 Backup ──────────────────────────────────────────────
# Uses b2sdk for direct API uploads. Optional — only used if credentials
# are configured.

class B2Backup:
    """Backup to Backblaze B2 cloud storage.

    Requires b2sdk: pip install b2sdk
    Configure via environment variables:
        B2_APPLICATION_KEY_ID
        B2_APPLICATION_KEY
        B2_BUCKET_NAME
    """

    def __init__(self,
                 key_id: str = "",
                 app_key: str = "",
                 bucket_name: str = ""):
        self.key_id = key_id or os.environ.get("B2_APPLICATION_KEY_ID", "")
        self.app_key = app_key or os.environ.get("B2_APPLICATION_KEY", "")
        self.bucket_name = bucket_name or os.environ.get("B2_BUCKET_NAME",
                                                          "tlo-allrise-backups")
        self._bucket = None
        self._api = None

    @property
    def is_available(self) -> bool:
        """Check if B2 credentials are configured."""
        return bool(self.key_id and self.app_key)

    def _connect(self):
        """Lazy-connect to B2 API."""
        if self._api is not None:
            return

        try:
            from b2sdk.v2 import InMemoryAccountInfo, B2Api
        except ImportError:
            raise ImportError(
                "b2sdk is required for Backblaze B2 backup. "
                "Install it with: pip install b2sdk"
            )

        info = InMemoryAccountInfo()
        self._api = B2Api(info)
        self._api.authorize_account("production", self.key_id, self.app_key)
        self._bucket = self._api.get_bucket_by_name(self.bucket_name)

    def upload_file(self, local_path: str, remote_name: str = "") -> Optional[str]:
        """Upload a single file to B2.

        Args:
            local_path: Path to local file
            remote_name: B2 key name (default: backups/{filename})

        Returns:
            B2 file ID, or None on failure.
        """
        if not self.is_available:
            logger.warning("B2 credentials not configured")
            return None

        try:
            self._connect()
            local = Path(local_path)
            if not remote_name:
                remote_name = f"backups/{local.name}"

            file_info = self._bucket.upload_local_file(
                local_file=str(local),
                file_name=remote_name,
            )
            logger.info("Uploaded to B2: %s -> %s", local.name, remote_name)
            return file_info.id_
        except Exception as e:
            logger.error("B2 upload failed: %s", e)
            return None

    def upload_bytes(self, data: bytes, remote_name: str) -> Optional[str]:
        """Upload bytes directly to B2.

        Args:
            data: Raw bytes to upload
            remote_name: B2 key name

        Returns:
            B2 file ID, or None on failure.
        """
        if not self.is_available:
            return None

        try:
            self._connect()
            file_info = self._bucket.upload_bytes(
                data_bytes=data,
                file_name=remote_name,
            )
            logger.info("Uploaded bytes to B2: %s (%d bytes)",
                        remote_name, len(data))
            return file_info.id_
        except Exception as e:
            logger.error("B2 upload failed: %s", e)
            return None

    def backup_case_archive(self, archive_path: str) -> Optional[str]:
        """Upload a case archive to B2.

        Args:
            archive_path: Path to local .tar.gz file

        Returns:
            B2 file ID, or None on failure.
        """
        name = Path(archive_path).name
        return self.upload_file(archive_path, f"archives/{name}")

    def backup_full(self, data_dir: str) -> Optional[str]:
        """Create and upload a full data backup to B2.

        Args:
            data_dir: Path to the TLO data directory

        Returns:
            B2 file ID, or None on failure.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_name = f"backups/tlo-backup-{timestamp}.tar.gz"

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(data_dir, arcname="data")
            return self.upload_file(tmp_path, remote_name)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups in B2."""
        if not self.is_available:
            return []

        try:
            self._connect()
            results = []
            for file_version, _ in self._bucket.ls_folder("backups/"):
                results.append({
                    "filename": file_version.file_name,
                    "size_mb": round(file_version.size / (1024 * 1024), 1),
                    "uploaded": datetime.fromtimestamp(
                        file_version.upload_timestamp / 1000
                    ).isoformat(),
                    "file_id": file_version.id_,
                })
            return sorted(results, key=lambda x: x["uploaded"], reverse=True)
        except Exception as e:
            logger.error("Failed to list B2 backups: %s", e)
            return []


# ── Unified Backup Manager ───────────────────────────────────────────

class BackupManager:
    """High-level backup manager that coordinates Dropbox and B2.

    Usage:
        bm = BackupManager(data_dir="/opt/tlo-allrise/data")
        bm.backup_before_purge(case_id)  # Called before purging source docs
        bm.run_full_backup()             # Daily scheduled backup
    """

    def __init__(self, data_dir: str, dropbox_dir: str = "",
                 b2_key_id: str = "", b2_app_key: str = "",
                 b2_bucket: str = ""):
        self.data_dir = data_dir
        self.dropbox = DropboxSyncBackup(dropbox_dir)
        self.b2 = B2Backup(b2_key_id, b2_app_key, b2_bucket)

    def backup_before_purge(self, case_id: str) -> Dict[str, Optional[str]]:
        """Create safety backups of a case before purging source documents.

        Should be called before CaseManager.purge_source_docs().

        Returns:
            {"dropbox": path_or_None, "b2": file_id_or_None}
        """
        result: Dict[str, Optional[str]] = {"dropbox": None, "b2": None}

        # Dropbox archive (fast, local)
        if self.dropbox.is_available:
            archive = self.dropbox.backup_case_archive(self.data_dir, case_id)
            result["dropbox"] = archive

            # Also upload to B2 if available
            if archive and self.b2.is_available:
                b2_id = self.b2.backup_case_archive(archive)
                result["b2"] = b2_id
        elif self.b2.is_available:
            # No Dropbox — create temp archive and upload to B2 directly
            case_dir = Path(self.data_dir) / "cases" / case_id
            if case_dir.is_dir():
                with tempfile.NamedTemporaryFile(
                    suffix=".tar.gz", delete=False
                ) as tmp:
                    tmp_path = tmp.name
                try:
                    with tarfile.open(tmp_path, "w:gz") as tar:
                        tar.add(str(case_dir), arcname=case_id)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    b2_id = self.b2.upload_file(
                        tmp_path, f"archives/{case_id}_{ts}.tar.gz"
                    )
                    result["b2"] = b2_id
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        return result

    def run_full_backup(self) -> Dict[str, Optional[str]]:
        """Run a full backup to all configured targets.

        Returns:
            {"dropbox": path_or_None, "b2": file_id_or_None}
        """
        result: Dict[str, Optional[str]] = {"dropbox": None, "b2": None}

        if self.dropbox.is_available:
            result["dropbox"] = self.dropbox.backup_full(self.data_dir)

        if self.b2.is_available:
            result["b2"] = self.b2.backup_full(self.data_dir)

        return result

    def get_backup_status(self) -> Dict[str, Any]:
        """Return status of backup targets."""
        return {
            "dropbox": {
                "available": self.dropbox.is_available,
                "path": str(self.dropbox.backup_dir),
                "backups": (
                    self.dropbox.list_backups()
                    if self.dropbox.is_available else []
                ),
            },
            "b2": {
                "available": self.b2.is_available,
                "bucket": self.b2.bucket_name,
            },
        }


# ── Helpers ───────────────────────────────────────────────────────────

def _sync_directory(src: Path, dest: Path,
                    exclude: Optional[set] = None) -> int:
    """Sync files from src to dest. Returns count of files copied."""
    exclude = exclude or set()
    count = 0
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        if any(ex in str(item) for ex in exclude):
            continue

        rel = item.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)

        # Only copy if source is newer or different size
        if target.exists():
            if (item.stat().st_mtime <= target.stat().st_mtime
                    and item.stat().st_size == target.stat().st_size):
                continue

        shutil.copy2(item, target)
        count += 1

    return count
