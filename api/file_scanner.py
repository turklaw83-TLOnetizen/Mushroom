# ---- Upload Content Scanner ----------------------------------------------
# Scans uploaded files for known malware signatures and suspicious content.

import hashlib
import logging
import os

logger = logging.getLogger(__name__)

# Magic bytes for known dangerous file types
BLOCKED_SIGNATURES = {
    b"MZ": "Windows executable (.exe/.dll)",
    b"\x7fELF": "Linux executable (ELF)",
    b"#!/": "Shell script",
    b"<?php": "PHP script",
    b"<% @": "ASP script",
}

# Blocked extensions
BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".scr",
    ".ps1", ".vbs", ".js", ".wsf", ".wsh",
    ".php", ".asp", ".aspx", ".jsp",
}

# Max file size for content scanning (files over this are hash-only)
SCAN_SIZE_LIMIT = 100 * 1024 * 1024  # 100MB


class ScanResult:
    def __init__(self, clean: bool, reason: str = "", sha256: str = ""):
        self.clean = clean
        self.reason = reason
        self.sha256 = sha256


def scan_file(filepath: str, filename: str) -> ScanResult:
    """
    Scan an uploaded file for malicious content.

    Returns ScanResult with clean=True if safe, clean=False if blocked.
    """
    # Check extension
    ext = os.path.splitext(filename)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        return ScanResult(False, f"Blocked file type: {ext}")

    # Calculate hash
    sha256 = hashlib.sha256()
    file_size = 0

    try:
        with open(filepath, "rb") as f:
            # Read first 8 bytes for magic number check
            header = f.read(8)
            sha256.update(header)
            file_size += len(header)

            # Check magic bytes
            for sig, desc in BLOCKED_SIGNATURES.items():
                if header.startswith(sig):
                    return ScanResult(False, f"Blocked content type: {desc}")

            # Continue hashing
            while chunk := f.read(8192):
                sha256.update(chunk)
                file_size += len(chunk)

    except Exception as e:
        logger.error("File scan failed for %s: %s", filename, e)
        return ScanResult(False, f"Scan error: {str(e)}")

    file_hash = sha256.hexdigest()
    logger.info("File scanned: %s (%d bytes, SHA256: %s)", filename, file_size, file_hash[:16])

    return ScanResult(True, sha256=file_hash)


def scan_bytes(data: bytes, filename: str) -> ScanResult:
    """
    Scan in-memory file bytes before writing to disk.

    Use this in upload endpoints to reject dangerous files before saving.
    """
    # Check extension
    ext = os.path.splitext(filename)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        return ScanResult(False, f"Blocked file type: {ext}")

    # Check magic bytes
    header = data[:8]
    for sig, desc in BLOCKED_SIGNATURES.items():
        if header.startswith(sig):
            return ScanResult(False, f"Blocked content type: {desc}")

    file_hash = hashlib.sha256(data).hexdigest()
    logger.info("Upload scanned: %s (%d bytes, SHA256: %s)", filename, len(data), file_hash[:16])
    return ScanResult(True, sha256=file_hash)


async def scan_upload(filepath: str, filename: str) -> ScanResult:
    """Async wrapper for file scanning."""
    return scan_file(filepath, filename)
