"""
Bates Stamping & Exhibit Numbering Utility

Provides a BatesStamper class to assign sequential Bates numbers
and exhibit labels to case files, with persistent state tracking.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BatesStamper:
    """
    Manages Bates numbering and exhibit assignment for case files.

    Numbering format: PREFIX-000001, PREFIX-000002, ...
    Exhibit format:   Exhibit A, Exhibit B, ... Exhibit Z, Exhibit AA, ...

    State is persisted per-case in a bates_registry.json file.
    """

    def __init__(self, case_dir: str, prefix: str = "DEF"):
        self.case_dir = case_dir
        self.prefix = prefix
        self.registry_path = os.path.join(case_dir, "bates_registry.json")
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict:
        """Load existing Bates registry or create empty one."""
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "prefix": self.prefix,
            "next_number": 1,
            "next_exhibit": 1,
            "files": {},
            "created_at": datetime.now().isoformat(),
        }

    def _save_registry(self):
        """Persist registry to disk."""
        self.registry["updated_at"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

    @staticmethod
    def _number_to_exhibit(n: int) -> str:
        """Convert 1-based index to exhibit letter: 1=A, 26=Z, 27=AA, etc."""
        result = ""
        while n > 0:
            n -= 1
            result = chr(65 + (n % 26)) + result
            n //= 26
        return result

    def assign_bates(self, filename: str, page_count: int = 1) -> Dict:
        """
        Assign Bates numbers to a file.

        Args:
            filename: Name of the file (basename)
            page_count: Number of pages in the document

        Returns:
            Dict with bates_start, bates_end, exhibit, range_str
        """
        # Check if already assigned
        if filename in self.registry["files"]:
            return self.registry["files"][filename]

        start = self.registry["next_number"]
        end = start + page_count - 1
        exhibit_num = self.registry["next_exhibit"]
        exhibit_label = f"Exhibit {self._number_to_exhibit(exhibit_num)}"

        entry = {
            "bates_start": f"{self.prefix}-{start:06d}",
            "bates_end": f"{self.prefix}-{end:06d}",
            "range_str": f"{self.prefix}-{start:06d} — {self.prefix}-{end:06d}",
            "exhibit": exhibit_label,
            "exhibit_number": exhibit_num,
            "page_count": page_count,
            "assigned_at": datetime.now().isoformat(),
        }

        self.registry["files"][filename] = entry
        self.registry["next_number"] = end + 1
        self.registry["next_exhibit"] = exhibit_num + 1
        self._save_registry()

        return entry

    def get_assignment(self, filename: str) -> Optional[Dict]:
        """Get existing Bates assignment for a file, or None."""
        return self.registry["files"].get(filename)

    def get_all_assignments(self) -> Dict[str, Dict]:
        """Return all file->Bates assignments."""
        return self.registry.get("files", {})

    def remove_assignment(self, filename: str) -> bool:
        """Remove a Bates assignment (does NOT renumber others)."""
        if filename in self.registry["files"]:
            del self.registry["files"][filename]
            self._save_registry()
            return True
        return False

    def set_prefix(self, new_prefix: str):
        """Update the Bates prefix for future assignments."""
        self.prefix = new_prefix
        self.registry["prefix"] = new_prefix
        self._save_registry()

    def reassign_all(self, filenames: List[str], page_counts: Dict[str, int]) -> Dict[str, Dict]:
        """
        Clear all assignments and reassign in the given order.
        Useful when user reorders or adds files.

        Args:
            filenames: Ordered list of filenames
            page_counts: {filename: page_count} mapping

        Returns:
            New complete assignments dict
        """
        self.registry["files"] = {}
        self.registry["next_number"] = 1
        self.registry["next_exhibit"] = 1

        results = {}
        for fn in filenames:
            pc = page_counts.get(fn, 1)
            results[fn] = self.assign_bates(fn, pc)

        return results

    def get_exhibit_index(self) -> str:
        """
        Generate a formatted exhibit index for court filings.

        Returns:
            Markdown-formatted exhibit index
        """
        files = self.registry.get("files", {})
        if not files:
            return "*No exhibits assigned yet.*"

        lines = ["| Exhibit | Bates Range | Document | Pages |",
                 "|---------|-------------|----------|-------|"]

        # Sort by exhibit number
        sorted_files = sorted(files.items(), key=lambda x: x[1].get("exhibit_number", 0))

        for filename, info in sorted_files:
            lines.append(
                f"| {info['exhibit']} | {info['range_str']} | {filename} | {info['page_count']} |"
            )

        total_pages = sum(info["page_count"] for info in files.values())
        lines.append(f"\n**Total: {len(files)} exhibits, {total_pages} pages**")

        return "\n".join(lines)
