"""Encryption manager — encrypt/decrypt files at rest with AES-256-GCM."""

import hashlib
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# IMPORTANT: Do NOT change these magic bytes — backward compat with encrypted_backend.py
MAGIC_BYTES = b"TLO_ALLRISE_ENCRYPTION_VERIFIED"


def _derive_key(passphrase: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """Derive AES-256 key from passphrase using PBKDF2."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 100000, dklen=32)
    return key, salt


class EncryptionManager:
    """Manage file encryption at rest."""

    def __init__(self, passphrase: Optional[str] = None):
        self.passphrase = passphrase or os.getenv("ENCRYPTION_KEY", "")

    def encrypt_file(self, file_path: str) -> bool:
        """Encrypt a file in place. Returns True on success."""
        if not self.passphrase:
            logger.warning("No ENCRYPTION_KEY set — skipping encryption")
            return False

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            data = Path(file_path).read_bytes()

            # Already encrypted?
            if data[:len(MAGIC_BYTES)] == MAGIC_BYTES:
                return True

            key, salt = _derive_key(self.passphrase)
            nonce = secrets.token_bytes(12)
            aesgcm = AESGCM(key)
            encrypted = aesgcm.encrypt(nonce, data, None)

            # Format: MAGIC + salt(16) + nonce(12) + ciphertext
            output = MAGIC_BYTES + salt + nonce + encrypted
            Path(file_path).write_bytes(output)
            return True

        except ImportError:
            logger.error("cryptography package not installed")
            return False
        except Exception as e:
            logger.error("Encryption failed for %s: %s", file_path, e)
            return False

    def decrypt_file(self, file_path: str) -> Optional[bytes]:
        """Decrypt a file and return plaintext bytes."""
        if not self.passphrase:
            return Path(file_path).read_bytes()

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            data = Path(file_path).read_bytes()
            magic_len = len(MAGIC_BYTES)

            # Not encrypted
            if data[:magic_len] != MAGIC_BYTES:
                return data

            salt = data[magic_len : magic_len + 16]
            nonce = data[magic_len + 16 : magic_len + 28]
            ciphertext = data[magic_len + 28 :]

            key, _ = _derive_key(self.passphrase, salt)
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)

        except Exception as e:
            logger.error("Decryption failed for %s: %s", file_path, e)
            return None

    def verify_encryption(self, file_path: str) -> bool:
        """Check if a file is encrypted."""
        try:
            data = Path(file_path).read_bytes(len(MAGIC_BYTES) + 1)
            return data[:len(MAGIC_BYTES)] == MAGIC_BYTES
        except Exception:
            return False

    def get_encryption_status(self, directory: str) -> dict:
        """Report encryption status for all files in a directory."""
        total = 0
        encrypted = 0
        unencrypted = []

        for f in Path(directory).rglob("*"):
            if f.is_file():
                total += 1
                if self.verify_encryption(str(f)):
                    encrypted += 1
                else:
                    unencrypted.append(str(f.name))

        return {
            "total_files": total,
            "encrypted": encrypted,
            "unencrypted": total - encrypted,
            "coverage_pct": round(encrypted / max(total, 1) * 100, 1),
            "unencrypted_files": unencrypted[:20],
        }

    def rotate_key(self, new_passphrase: str, directory: str) -> dict:
        """Re-encrypt all files with a new key."""
        results = {"success": 0, "failed": 0, "skipped": 0}
        new_mgr = EncryptionManager(new_passphrase)

        for f in Path(directory).rglob("*"):
            if not f.is_file():
                continue
            try:
                plaintext = self.decrypt_file(str(f))
                if plaintext is None:
                    results["failed"] += 1
                    continue
                f.write_bytes(plaintext)  # Write decrypted
                if new_mgr.encrypt_file(str(f)):
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error("Key rotation failed for %s: %s", f, e)
                results["failed"] += 1

        return results
