"""Tests for file security modules (Phase 24)."""
import pytest
import tempfile
from pathlib import Path


class TestFileScanner:
    def test_import(self):
        from core.file_scanner import FileScanner
        assert FileScanner is not None

    def test_blocked_extensions(self):
        from core.file_scanner import FileScanner
        scanner = FileScanner()
        # Common dangerous extensions should be blocked
        assert not scanner.is_safe_file_type("malware.exe")
        assert not scanner.is_safe_file_type("script.bat")
        assert not scanner.is_safe_file_type("payload.dll")

    def test_allowed_extensions(self):
        from core.file_scanner import FileScanner
        scanner = FileScanner()
        assert scanner.is_safe_file_type("document.pdf")
        assert scanner.is_safe_file_type("image.jpg")
        assert scanner.is_safe_file_type("report.docx")


class TestDocumentWatermark:
    def test_import(self):
        from core.document_watermark import Watermarker
        assert Watermarker is not None

    def test_create_watermark_text(self):
        from core.document_watermark import Watermarker
        wm = Watermarker()
        text = wm.create_watermark_text(
            case_id="case-123",
            user_name="John Doe",
        )
        assert "case-123" in text.lower() or "Case" in text
        assert "John Doe" in text


class TestDLPRules:
    def test_import(self):
        from core.dlp_rules import DLPEngine
        assert DLPEngine is not None

    def test_engine_init(self, tmp_path):
        from core.dlp_rules import DLPEngine
        engine = DLPEngine(str(tmp_path))
        assert engine is not None

    def test_no_rules_allows_all(self, tmp_path):
        from core.dlp_rules import DLPEngine
        engine = DLPEngine(str(tmp_path))
        result = engine.check_download(
            case_id="case-1",
            file_name="test.pdf",
            user_id="user-1",
            user_role="admin",
        )
        assert result["allowed"] is True


class TestScanBytes:
    """Tests for the scan_bytes() in-memory scanner (api/file_scanner.py)."""

    def test_blocks_exe_extension(self):
        from api.file_scanner import scan_bytes
        # Even benign content should be blocked if the extension is .exe
        result = scan_bytes(b"harmless content", "malware.exe")
        assert not result.clean
        assert ".exe" in result.reason.lower() or "blocked" in result.reason.lower()

    def test_blocks_mz_magic_bytes_with_pdf_extension(self):
        from api.file_scanner import scan_bytes
        # MZ magic bytes (Windows PE) disguised as a .pdf
        pe_header = b"MZ" + b"\x00" * 100
        result = scan_bytes(pe_header, "report.pdf")
        assert not result.clean
        assert "executable" in result.reason.lower() or "blocked" in result.reason.lower()

    def test_allows_clean_pdf(self):
        from api.file_scanner import scan_bytes
        # Real PDF magic: %PDF-
        pdf_content = b"%PDF-1.4 some pdf content here"
        result = scan_bytes(pdf_content, "document.pdf")
        assert result.clean
        assert result.sha256  # SHA256 hash should be present

    def test_allows_clean_docx(self):
        from api.file_scanner import scan_bytes
        # DOCX files are ZIP archives starting with PK magic bytes
        docx_content = b"PK\x03\x04" + b"\x00" * 100
        result = scan_bytes(docx_content, "report.docx")
        assert result.clean
        assert result.sha256

    def test_returns_sha256_hash(self):
        from api.file_scanner import scan_bytes
        import hashlib
        content = b"test file content for hash verification"
        result = scan_bytes(content, "test.txt")
        assert result.clean
        expected_hash = hashlib.sha256(content).hexdigest()
        assert result.sha256 == expected_hash

    def test_blocks_elf_magic_bytes(self):
        from api.file_scanner import scan_bytes
        # ELF binary disguised as .txt
        elf_content = b"\x7fELF" + b"\x00" * 100
        result = scan_bytes(elf_content, "readme.txt")
        assert not result.clean
        assert "executable" in result.reason.lower() or "blocked" in result.reason.lower()

    def test_blocks_bat_extension(self):
        from api.file_scanner import scan_bytes
        result = scan_bytes(b"echo hello", "script.bat")
        assert not result.clean

    def test_blocks_ps1_extension(self):
        from api.file_scanner import scan_bytes
        result = scan_bytes(b"Get-Process", "script.ps1")
        assert not result.clean


class TestEncryptionManager:
    def test_import(self):
        from core.encryption_manager import EncryptionManager
        assert EncryptionManager is not None

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        try:
            from core.encryption_manager import EncryptionManager
            mgr = EncryptionManager("test-password-for-testing")

            # Create a test file
            test_file = tmp_path / "test.txt"
            test_file.write_text("Hello, World! This is a test file for encryption.")

            # Encrypt
            encrypted = mgr.encrypt_file(str(test_file))
            assert encrypted != str(test_file) or Path(encrypted).read_bytes() != b"Hello, World!"

            # Decrypt
            decrypted = mgr.decrypt_file(encrypted)
            content = Path(decrypted).read_text()
            assert "Hello, World!" in content
        except ImportError:
            pytest.skip("cryptography package not installed")
