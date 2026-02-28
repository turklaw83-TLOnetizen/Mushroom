# ---- Encrypted Storage Backend -----------------------------------------------
# AES-256 encryption proxy wrapping JSONStorageBackend.
# Intercepts low-level I/O methods to encrypt/decrypt all data at rest.
#
# Usage:
#   key = derive_encryption_key(passphrase, salt)
#   backend = EncryptedStorageBackend(data_dir, key)
#
# All JSON, text, and binary files are encrypted transparently.
# Directory structure and filenames remain in plaintext for navigation.

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.storage.json_backend import JSONStorageBackend

logger = logging.getLogger(__name__)

# ---- Key Derivation --------------------------------------------------------

_SALT_FILE = ".encryption_salt"
_MARKER_FILE = ".encrypted"


def derive_encryption_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet-compatible key from passphrase + salt using PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    raw_key = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def get_or_create_salt(data_dir: str) -> bytes:
    """Load existing salt or generate a new 16-byte random salt."""
    salt_path = Path(data_dir) / _SALT_FILE
    if salt_path.exists():
        return salt_path.read_bytes()
    salt = os.urandom(16)
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt_path.write_bytes(salt)
    return salt


def is_encryption_enabled(data_dir: str) -> bool:
    """Check if the data directory has encryption enabled."""
    return (Path(data_dir) / _MARKER_FILE).exists()


def enable_encryption_marker(data_dir: str) -> None:
    """Write the .encrypted marker file."""
    marker = Path(data_dir) / _MARKER_FILE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("AES-256-Fernet", encoding="utf-8")


def verify_passphrase(data_dir: str, passphrase: str) -> bool:
    """Verify a passphrase by attempting to decrypt a known test value."""
    from cryptography.fernet import Fernet, InvalidToken

    test_path = Path(data_dir) / ".encryption_test"
    if not test_path.exists():
        return True  # No test file yet -- first-time setup
    salt = get_or_create_salt(data_dir)
    key = derive_encryption_key(passphrase, salt)
    fernet = Fernet(key)
    try:
        result = fernet.decrypt(test_path.read_bytes())
        return result == b"TLO_ALLRISE_ENCRYPTION_VERIFIED"
    except (InvalidToken, Exception):
        return False


def write_verification_token(data_dir: str, passphrase: str) -> None:
    """Write an encrypted test value used for passphrase verification."""
    from cryptography.fernet import Fernet

    salt = get_or_create_salt(data_dir)
    key = derive_encryption_key(passphrase, salt)
    fernet = Fernet(key)
    test_path = Path(data_dir) / ".encryption_test"
    encrypted = fernet.encrypt(b"TLO_ALLRISE_ENCRYPTION_VERIFIED")
    test_path.write_bytes(encrypted)


# ---- Encrypted Backend Class ------------------------------------------------

class EncryptedStorageBackend(JSONStorageBackend):
    """
    Transparent encryption proxy over JSONStorageBackend.

    All file I/O is intercepted: writes encrypt, reads decrypt.
    Directory structure and filenames remain in plaintext.
    """

    def __init__(self, data_dir: str, encryption_key: bytes):
        super().__init__(data_dir)
        from cryptography.fernet import Fernet
        self._fernet = Fernet(encryption_key)

    # ---- Encrypted Low-Level I/O -------------------------------------------

    def _read_json(self, path: Path, default: Any = None) -> Any:
        """Read + decrypt a JSON file. Falls back to plaintext for unencrypted files."""
        if not path.exists():
            return default
        try:
            raw_bytes = path.read_bytes()
            # Try decrypting first (encrypted data)
            try:
                decrypted = self._fernet.decrypt(raw_bytes)
                return json.loads(decrypted.decode("utf-8"))
            except Exception:
                # Fall back to plaintext (pre-encryption data)
                return json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return default

    def _write_json(self, path: Path, data: Any) -> None:
        """Serialize JSON + encrypt + write."""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            json_bytes = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode("utf-8")
            encrypted = self._fernet.encrypt(json_bytes)
            path.write_bytes(encrypted)
        except OSError:
            logger.exception("Failed to write %s", path)
            raise

    def _read_text(self, path: Path, default: str = "") -> str:
        """Read + decrypt a text file. Falls back to plaintext for unencrypted files."""
        if not path.exists():
            return default
        try:
            raw_bytes = path.read_bytes()
            try:
                decrypted = self._fernet.decrypt(raw_bytes)
                return decrypted.decode("utf-8")
            except Exception:
                # Fall back to plaintext
                return raw_bytes.decode("utf-8")
        except OSError:
            return default

    def _write_text(self, path: Path, text: str) -> None:
        """Encrypt + write a text file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self._fernet.encrypt(text.encode("utf-8"))
        path.write_bytes(encrypted)

    def save_file(self, case_id: str, filename: str, data: bytes) -> str:
        """Encrypt + save a binary file (uploaded documents)."""
        docs_dir = self._source_docs_dir(case_id)
        docs_dir.mkdir(parents=True, exist_ok=True)
        path = docs_dir / filename
        encrypted = self._fernet.encrypt(data)
        path.write_bytes(encrypted)
        return str(path)

    def get_case_files(self, case_id: str) -> List[str]:
        """Return full paths to all source document files for a case.
        Same as parent -- filenames are not encrypted."""
        return super().get_case_files(case_id)

    # ---- Decrypted File Reading (for processing) ----------------------------

    def read_file_bytes(self, case_id: str, filename: str) -> bytes:
        """Read and decrypt a source document file. Returns raw bytes."""
        path = self._source_docs_dir(case_id) / filename
        if not path.exists():
            return b""
        raw = path.read_bytes()
        try:
            return self._fernet.decrypt(raw)
        except Exception:
            # Fall back to raw bytes (pre-encryption file)
            return raw


# ---- Migration Utility ------------------------------------------------------

def encrypt_existing_data(data_dir: str, encryption_key: bytes,
                          progress_callback=None) -> Dict[str, int]:
    """
    One-time migration: encrypt all existing plaintext files in data_dir.

    Returns stats dict: {"files_encrypted": N, "files_skipped": M, "errors": E}
    """
    from cryptography.fernet import Fernet, InvalidToken

    fernet = Fernet(encryption_key)
    stats = {"files_encrypted": 0, "files_skipped": 0, "errors": 0}

    data_path = Path(data_dir)
    # Skip these special files
    skip_names = {_SALT_FILE, _MARKER_FILE, ".encryption_test", ".gitkeep", ".gitignore"}

    all_files = [
        f for f in data_path.rglob("*")
        if f.is_file() and f.name not in skip_names
        and not any(p.name == "__pycache__" for p in f.parents)
    ]

    total = len(all_files)
    for i, fpath in enumerate(all_files):
        try:
            raw = fpath.read_bytes()

            # Check if already encrypted (try decrypting)
            try:
                fernet.decrypt(raw)
                stats["files_skipped"] += 1
                continue  # Already encrypted
            except (InvalidToken, Exception):
                pass  # Not encrypted -- proceed

            # Encrypt and write back
            encrypted = fernet.encrypt(raw)
            fpath.write_bytes(encrypted)
            stats["files_encrypted"] += 1

        except Exception as exc:
            logger.warning("Failed to encrypt %s: %s", fpath, exc)
            stats["errors"] += 1

        if progress_callback and (i % 10 == 0 or i == total - 1):
            progress_callback(i + 1, total)

    return stats
