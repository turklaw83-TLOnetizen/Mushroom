# ---- Tests for Encrypted Storage Backend ------------------------------------
# Covers key derivation, salt management, encryption markers, passphrase
# verification, EncryptedStorageBackend CRUD, plaintext fallback, and the
# one-time encrypt_existing_data migration utility.

import json
import os
from pathlib import Path

import pytest

from core.storage.encrypted_backend import (
    EncryptedStorageBackend,
    derive_encryption_key,
    enable_encryption_marker,
    encrypt_existing_data,
    get_or_create_salt,
    is_encryption_enabled,
    verify_passphrase,
    write_verification_token,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASSPHRASE = "test-passphrase-42"
ALT_PASSPHRASE = "different-passphrase-99"
MAGIC_BYTES = b"TLO_ALLRISE_ENCRYPTION_VERIFIED"


def _make_key(data_dir: str, passphrase: str = PASSPHRASE) -> bytes:
    """Derive an encryption key using the salt in *data_dir*."""
    salt = get_or_create_salt(data_dir)
    return derive_encryption_key(passphrase, salt)


# ---------------------------------------------------------------------------
# derive_encryption_key
# ---------------------------------------------------------------------------


class TestDeriveEncryptionKey:
    """Tests for PBKDF2 key derivation."""

    def test_consistent_output_same_inputs(self):
        """Same passphrase + salt must always produce the same key."""
        salt = os.urandom(16)
        key1 = derive_encryption_key(PASSPHRASE, salt)
        key2 = derive_encryption_key(PASSPHRASE, salt)
        assert key1 == key2

    def test_different_passphrase_produces_different_key(self):
        """Different passphrases must yield different keys."""
        salt = os.urandom(16)
        key1 = derive_encryption_key(PASSPHRASE, salt)
        key2 = derive_encryption_key(ALT_PASSPHRASE, salt)
        assert key1 != key2

    def test_different_salt_produces_different_key(self):
        """Different salts must yield different keys."""
        salt_a = os.urandom(16)
        salt_b = os.urandom(16)
        key1 = derive_encryption_key(PASSPHRASE, salt_a)
        key2 = derive_encryption_key(PASSPHRASE, salt_b)
        assert key1 != key2

    def test_key_is_url_safe_base64(self):
        """Returned key must be 44-byte URL-safe base64 (Fernet-compatible)."""
        import base64

        salt = os.urandom(16)
        key = derive_encryption_key(PASSPHRASE, salt)
        # Fernet keys are 32 bytes -> 44 chars in urlsafe base64 (with padding)
        assert len(key) == 44
        # Must round-trip through urlsafe b64 without error
        raw = base64.urlsafe_b64decode(key)
        assert len(raw) == 32


# ---------------------------------------------------------------------------
# get_or_create_salt
# ---------------------------------------------------------------------------


class TestGetOrCreateSalt:
    """Tests for salt file management."""

    def test_creates_new_salt_file(self, tmp_path):
        """When no salt file exists, one is created."""
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        salt = get_or_create_salt(data_dir)
        assert (Path(data_dir) / ".encryption_salt").exists()
        assert isinstance(salt, bytes)

    def test_returns_existing_salt(self, tmp_path):
        """Calling twice returns the same salt bytes."""
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        salt1 = get_or_create_salt(data_dir)
        salt2 = get_or_create_salt(data_dir)
        assert salt1 == salt2

    def test_salt_is_16_bytes(self, tmp_path):
        """Salt must be exactly 16 bytes."""
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        salt = get_or_create_salt(data_dir)
        assert len(salt) == 16


# ---------------------------------------------------------------------------
# is_encryption_enabled / enable_encryption_marker
# ---------------------------------------------------------------------------


class TestEncryptionMarker:
    """Tests for the .encrypted marker file."""

    def test_returns_false_when_no_marker(self, tmp_path):
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        assert is_encryption_enabled(data_dir) is False

    def test_returns_true_after_enable(self, tmp_path):
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        enable_encryption_marker(data_dir)
        assert is_encryption_enabled(data_dir) is True

    def test_enable_creates_marker_file(self, tmp_path):
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        enable_encryption_marker(data_dir)
        marker = Path(data_dir) / ".encrypted"
        assert marker.exists()
        assert marker.read_text(encoding="utf-8") == "AES-256-Fernet"


# ---------------------------------------------------------------------------
# write_verification_token / verify_passphrase
# ---------------------------------------------------------------------------


class TestPassphraseVerification:
    """Tests for the passphrase verification roundtrip."""

    def test_roundtrip_succeeds(self, tmp_path):
        """write_verification_token followed by verify_passphrase with same passphrase."""
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        write_verification_token(data_dir, PASSPHRASE)
        assert verify_passphrase(data_dir, PASSPHRASE) is True

    def test_wrong_passphrase_fails(self, tmp_path):
        """verify_passphrase must return False for wrong passphrase."""
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        write_verification_token(data_dir, PASSPHRASE)
        assert verify_passphrase(data_dir, ALT_PASSPHRASE) is False

    def test_first_time_returns_true(self, tmp_path):
        """When no .encryption_test file exists, verify_passphrase returns True."""
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        assert verify_passphrase(data_dir, PASSPHRASE) is True

    def test_verification_uses_magic_bytes(self, tmp_path):
        """The decrypted test value must be the exact magic bytes constant."""
        from cryptography.fernet import Fernet

        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        write_verification_token(data_dir, PASSPHRASE)

        # Manually decrypt and check the magic bytes
        salt = get_or_create_salt(data_dir)
        key = derive_encryption_key(PASSPHRASE, salt)
        fernet = Fernet(key)
        test_path = Path(data_dir) / ".encryption_test"
        decrypted = fernet.decrypt(test_path.read_bytes())
        assert decrypted == MAGIC_BYTES


# ---------------------------------------------------------------------------
# EncryptedStorageBackend — CRUD
# ---------------------------------------------------------------------------


@pytest.fixture
def enc_storage(tmp_path):
    """Provide an EncryptedStorageBackend backed by a temp directory."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir)
    key = _make_key(data_dir)
    return EncryptedStorageBackend(data_dir, key)


@pytest.fixture
def enc_case(enc_storage):
    """Create a case in the encrypted backend and return (backend, case_id)."""
    case_id = "enc_test__001"
    metadata = {
        "id": case_id,
        "name": "Encrypted Test Case",
        "status": "active",
        "case_type": "criminal",
    }
    enc_storage.create_case(case_id, metadata)
    return enc_storage, case_id


class TestEncryptedBackendCRUD:
    """Basic case management through the encrypted backend."""

    def test_create_and_list_cases(self, enc_case):
        backend, case_id = enc_case
        cases = backend.list_cases()
        assert len(cases) == 1
        assert cases[0]["id"] == case_id

    def test_get_case_metadata(self, enc_case):
        backend, case_id = enc_case
        meta = backend.get_case_metadata(case_id)
        assert meta["name"] == "Encrypted Test Case"
        assert meta["status"] == "active"

    def test_case_exists(self, enc_case):
        backend, case_id = enc_case
        assert backend.case_exists(case_id) is True
        assert backend.case_exists("nonexistent_case") is False

    def test_config_json_is_encrypted_on_disk(self, enc_case):
        """The raw config.json on disk should NOT be valid plaintext JSON."""
        backend, case_id = enc_case
        config_path = backend._case_dir(case_id) / "config.json"
        raw = config_path.read_bytes()
        # Encrypted data will fail to parse as JSON
        with pytest.raises((json.JSONDecodeError, UnicodeDecodeError)):
            json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# EncryptedStorageBackend — file I/O
# ---------------------------------------------------------------------------


class TestEncryptedBackendFileIO:
    """Tests for save_file / read_file_bytes roundtrip."""

    def test_save_and_read_file_roundtrip(self, enc_case):
        backend, case_id = enc_case
        original = b"Hello, encrypted world! \xde\xad\xbe\xef"
        backend.save_file(case_id, "test.bin", original)
        recovered = backend.read_file_bytes(case_id, "test.bin")
        assert recovered == original

    def test_saved_file_is_encrypted_on_disk(self, enc_case):
        backend, case_id = enc_case
        original = b"plaintext content here"
        backend.save_file(case_id, "doc.txt", original)
        raw_on_disk = (backend._source_docs_dir(case_id) / "doc.txt").read_bytes()
        assert raw_on_disk != original

    def test_read_nonexistent_file_returns_empty(self, enc_case):
        backend, case_id = enc_case
        assert backend.read_file_bytes(case_id, "missing.pdf") == b""

    def test_read_file_bytes_falls_back_to_raw_for_unencrypted(self, enc_case):
        """If a file was written in plaintext (pre-encryption), read_file_bytes
        should fall back to returning the raw bytes."""
        backend, case_id = enc_case
        docs_dir = backend._source_docs_dir(case_id)
        docs_dir.mkdir(parents=True, exist_ok=True)
        plaintext = b"I was never encrypted"
        (docs_dir / "legacy.txt").write_bytes(plaintext)
        assert backend.read_file_bytes(case_id, "legacy.txt") == plaintext

    def test_get_case_files_lists_saved_files(self, enc_case):
        backend, case_id = enc_case
        backend.save_file(case_id, "alpha.pdf", b"aaa")
        backend.save_file(case_id, "beta.docx", b"bbb")
        files = backend.get_case_files(case_id)
        names = [Path(f).name for f in files]
        assert "alpha.pdf" in names
        assert "beta.docx" in names


# ---------------------------------------------------------------------------
# EncryptedStorageBackend — _write_json / _read_json
# ---------------------------------------------------------------------------


class TestEncryptedBackendJSON:
    """Tests for low-level JSON encryption/decryption."""

    def test_write_read_json_roundtrip(self, enc_storage, tmp_path):
        data = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
        target = Path(enc_storage.data_dir) / "test_data.json"
        enc_storage._write_json(target, data)
        recovered = enc_storage._read_json(target)
        assert recovered == data

    def test_read_json_returns_default_for_missing_file(self, enc_storage):
        missing = Path(enc_storage.data_dir) / "nonexistent.json"
        assert enc_storage._read_json(missing, default={"fallback": True}) == {"fallback": True}

    def test_read_json_falls_back_to_plaintext(self, enc_storage, tmp_path):
        """If a JSON file was written in plaintext (pre-encryption migration),
        _read_json should decode it without decryption."""
        target = Path(enc_storage.data_dir) / "legacy.json"
        plain_data = {"legacy": True, "count": 42}
        target.write_text(json.dumps(plain_data), encoding="utf-8")
        recovered = enc_storage._read_json(target)
        assert recovered == plain_data

    def test_written_json_is_encrypted_on_disk(self, enc_storage):
        data = {"secret": "classified"}
        target = Path(enc_storage.data_dir) / "secret.json"
        enc_storage._write_json(target, data)
        raw = target.read_bytes()
        # Should not be valid JSON in plaintext
        with pytest.raises((json.JSONDecodeError, UnicodeDecodeError)):
            json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# EncryptedStorageBackend — _write_text / _read_text
# ---------------------------------------------------------------------------


class TestEncryptedBackendText:
    """Tests for low-level text encryption/decryption."""

    def test_write_read_text_roundtrip(self, enc_storage):
        target = Path(enc_storage.data_dir) / "notes.txt"
        text = "These are confidential notes.\nLine 2."
        enc_storage._write_text(target, text)
        recovered = enc_storage._read_text(target)
        assert recovered == text

    def test_read_text_falls_back_to_plaintext(self, enc_storage):
        target = Path(enc_storage.data_dir) / "old_notes.txt"
        plain = "Legacy unencrypted notes"
        target.write_text(plain, encoding="utf-8")
        assert enc_storage._read_text(target) == plain

    def test_read_text_returns_default_for_missing(self, enc_storage):
        missing = Path(enc_storage.data_dir) / "gone.txt"
        assert enc_storage._read_text(missing, default="N/A") == "N/A"


# ---------------------------------------------------------------------------
# encrypt_existing_data — migration utility
# ---------------------------------------------------------------------------


class TestEncryptExistingData:
    """Tests for the one-time plaintext-to-encrypted migration."""

    def _setup_data_dir(self, tmp_path):
        """Create a data directory with some plaintext files."""
        data_dir = tmp_path / "migration_data"
        data_dir.mkdir()
        sub = data_dir / "cases" / "case_001"
        sub.mkdir(parents=True)
        # Plaintext JSON
        (sub / "config.json").write_text(
            json.dumps({"name": "Test"}), encoding="utf-8"
        )
        # Plaintext binary
        (sub / "document.pdf").write_bytes(b"%PDF-1.4 fake content")
        # A text file
        (data_dir / "global_config.txt").write_text("setting=on", encoding="utf-8")
        return str(data_dir)

    def test_encrypts_plaintext_files(self, tmp_path):
        data_dir = self._setup_data_dir(tmp_path)
        key = _make_key(data_dir)
        stats = encrypt_existing_data(data_dir, key)
        assert stats["files_encrypted"] == 3
        assert stats["errors"] == 0

        # Verify files are now encrypted (not readable as plaintext JSON)
        config_path = Path(data_dir) / "cases" / "case_001" / "config.json"
        raw = config_path.read_bytes()
        with pytest.raises((json.JSONDecodeError, UnicodeDecodeError)):
            json.loads(raw.decode("utf-8"))

    def test_skips_already_encrypted_files(self, tmp_path):
        from cryptography.fernet import Fernet

        data_dir = self._setup_data_dir(tmp_path)
        key = _make_key(data_dir)
        fernet = Fernet(key)

        # Pre-encrypt one file
        config_path = Path(data_dir) / "cases" / "case_001" / "config.json"
        plaintext = config_path.read_bytes()
        config_path.write_bytes(fernet.encrypt(plaintext))

        stats = encrypt_existing_data(data_dir, key)
        # 1 skipped (already encrypted), 2 newly encrypted
        assert stats["files_skipped"] == 1
        assert stats["files_encrypted"] == 2

    def test_skips_special_files(self, tmp_path):
        data_dir = tmp_path / "skip_data"
        data_dir.mkdir()
        # Create special files that should be skipped
        (data_dir / ".encryption_salt").write_bytes(os.urandom(16))
        (data_dir / ".encrypted").write_text("AES-256-Fernet", encoding="utf-8")
        (data_dir / ".encryption_test").write_bytes(b"test")
        (data_dir / ".gitkeep").write_text("", encoding="utf-8")
        (data_dir / ".gitignore").write_text("*.pyc", encoding="utf-8")
        # One normal file
        (data_dir / "data.json").write_text('{"a":1}', encoding="utf-8")

        key = _make_key(str(data_dir))
        stats = encrypt_existing_data(str(data_dir), key)
        # Only the normal file should be encrypted
        assert stats["files_encrypted"] == 1
        assert stats["files_skipped"] == 0

    def test_calls_progress_callback(self, tmp_path):
        data_dir = self._setup_data_dir(tmp_path)
        key = _make_key(data_dir)

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        encrypt_existing_data(data_dir, key, progress_callback=on_progress)
        # Should have received at least one callback
        assert len(progress_calls) > 0
        # Last call should report completion (current == total)
        last_current, last_total = progress_calls[-1]
        assert last_current == last_total

    def test_returns_correct_stats_shape(self, tmp_path):
        data_dir = tmp_path / "empty_data"
        data_dir.mkdir()
        key = _make_key(str(data_dir))
        stats = encrypt_existing_data(str(data_dir), key)
        assert set(stats.keys()) == {"files_encrypted", "files_skipped", "errors"}
        assert all(isinstance(v, int) for v in stats.values())
