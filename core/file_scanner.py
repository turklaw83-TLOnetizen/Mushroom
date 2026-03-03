"""File scanner — malware scanning with ClamAV and extension checks."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".scr",
    ".msi", ".com", ".pif", ".hta", ".cpl", ".reg", ".inf", ".ws",
}

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".rtf", ".odt", ".ods", ".odp",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg",
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm", ".avi",
    ".zip", ".tar", ".gz", ".7z",
    ".json", ".xml", ".html", ".md",
}


@dataclass
class ScanResult:
    clean: bool
    threats: list[str]
    scan_time_ms: float = 0
    scanner: str = "extension_check"


class FileScanner:
    """Scan files for malware and unsafe extensions."""

    def __init__(self):
        self._clamd = None
        self._init_clamav()

    def _init_clamav(self):
        try:
            import pyclamd
            self._clamd = pyclamd.ClamdUnixSocket()
            if not self._clamd.ping():
                self._clamd = pyclamd.ClamdNetworkSocket()
                if not self._clamd.ping():
                    self._clamd = None
                    logger.warning("ClamAV not available — using extension-only scanning")
            else:
                logger.info("ClamAV connected")
        except (ImportError, Exception) as e:
            self._clamd = None
            logger.warning("ClamAV not available (%s) — using extension-only scanning", e)

    def is_safe_file_type(self, filename: str) -> bool:
        ext = Path(filename).suffix.lower()
        if ext in BLOCKED_EXTENSIONS:
            return False
        return True

    def scan_file(self, file_path: str) -> ScanResult:
        import time
        start = time.time()
        path = Path(file_path)
        threats = []

        # Extension check
        if not self.is_safe_file_type(path.name):
            return ScanResult(
                clean=False,
                threats=[f"Blocked file extension: {path.suffix}"],
                scan_time_ms=round((time.time() - start) * 1000, 1),
                scanner="extension_check",
            )

        # ClamAV scan
        if self._clamd and path.exists():
            try:
                result = self._clamd.scan_file(str(path))
                if result:
                    for fpath, (status, virus_name) in result.items():
                        if status == "FOUND":
                            threats.append(f"Malware detected: {virus_name}")
                return ScanResult(
                    clean=len(threats) == 0,
                    threats=threats,
                    scan_time_ms=round((time.time() - start) * 1000, 1),
                    scanner="clamav",
                )
            except Exception as e:
                logger.error("ClamAV scan failed: %s", e)

        # Fallback: extension-only check passed
        return ScanResult(
            clean=True,
            threats=[],
            scan_time_ms=round((time.time() - start) * 1000, 1),
            scanner="extension_check",
        )

    def scan_directory(self, dir_path: str) -> dict[str, ScanResult]:
        results = {}
        for f in Path(dir_path).rglob("*"):
            if f.is_file():
                results[str(f)] = self.scan_file(str(f))
        return results


# Singleton
_scanner: Optional[FileScanner] = None


def get_scanner() -> FileScanner:
    global _scanner
    if _scanner is None:
        _scanner = FileScanner()
    return _scanner
