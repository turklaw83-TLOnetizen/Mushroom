"""DLP (Data Loss Prevention) rules engine."""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


class DLPEngine:
    """Enforce data loss prevention rules."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.base = data_dir or DATA_DIR
        self._rules_file = self.base / "dlp_rules.json"
        self._audit_file = self.base / "dlp_audit.json"

    def _load_rules(self) -> list[dict]:
        if self._rules_file.exists():
            try:
                return json.loads(self._rules_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return self._default_rules()

    def _save_rules(self, rules: list[dict]):
        self._rules_file.parent.mkdir(parents=True, exist_ok=True)
        self._rules_file.write_text(json.dumps(rules, indent=2), encoding="utf-8")

    def _default_rules(self) -> list[dict]:
        return [
            {
                "id": "default_watermark",
                "name": "Require Watermark",
                "type": "require_watermark",
                "enabled": False,
                "description": "Apply watermark to all downloaded documents",
            },
            {
                "id": "default_bulk",
                "name": "Bulk Download Limit",
                "type": "restrict_bulk_download",
                "enabled": True,
                "max_per_hour": 50,
                "description": "Limit downloads to 50 per hour per user",
            },
            {
                "id": "default_role",
                "name": "Attorney-Only Downloads",
                "type": "restrict_by_role",
                "enabled": False,
                "allowed_roles": ["admin", "attorney"],
                "description": "Only attorneys and admins can download files",
            },
        ]

    def get_rules(self) -> list[dict]:
        return self._load_rules()

    def create_rule(self, rule: dict) -> dict:
        rules = self._load_rules()
        rule["id"] = uuid.uuid4().hex[:12]
        rules.append(rule)
        self._save_rules(rules)
        return rule

    def update_rule(self, rule_id: str, updates: dict) -> Optional[dict]:
        rules = self._load_rules()
        for r in rules:
            if r["id"] == rule_id:
                r.update(updates)
                self._save_rules(rules)
                return r
        return None

    def delete_rule(self, rule_id: str) -> bool:
        rules = self._load_rules()
        before = len(rules)
        rules = [r for r in rules if r["id"] != rule_id]
        if len(rules) < before:
            self._save_rules(rules)
            return True
        return False

    def check_download(self, user_id: str, user_role: str, filename: str) -> dict:
        """Check if a download is allowed. Returns {allowed, reason, require_watermark}."""
        rules = self._load_rules()
        result = {"allowed": True, "reason": "", "require_watermark": False}

        for rule in rules:
            if not rule.get("enabled"):
                continue

            if rule["type"] == "restrict_by_role":
                if user_role not in rule.get("allowed_roles", []):
                    result["allowed"] = False
                    result["reason"] = f"Role '{user_role}' not authorized for downloads"
                    self._log_audit(user_id, "download_blocked", filename, rule["name"])
                    return result

            elif rule["type"] == "require_watermark":
                result["require_watermark"] = True

            elif rule["type"] == "restrict_bulk_download":
                max_per_hour = rule.get("max_per_hour", 50)
                recent = self._count_recent_downloads(user_id, 3600)
                if recent >= max_per_hour:
                    result["allowed"] = False
                    result["reason"] = f"Download limit exceeded ({max_per_hour}/hour)"
                    self._log_audit(user_id, "bulk_download_blocked", filename, rule["name"])
                    return result

        self._log_audit(user_id, "download_allowed", filename)
        return result

    def check_export(self, user_id: str, user_role: str, case_id: str, export_type: str) -> dict:
        result = {"allowed": True, "reason": ""}
        rules = self._load_rules()
        for rule in rules:
            if not rule.get("enabled"):
                continue
            if rule["type"] == "restrict_by_role":
                if user_role not in rule.get("allowed_roles", []):
                    result["allowed"] = False
                    result["reason"] = f"Role '{user_role}' not authorized for exports"
                    return result
        return result

    def _log_audit(self, user_id: str, action: str, resource: str = "", rule_name: str = ""):
        try:
            entries = []
            if self._audit_file.exists():
                entries = json.loads(self._audit_file.read_text(encoding="utf-8"))
            entries.append({
                "user_id": user_id,
                "action": action,
                "resource": resource,
                "rule": rule_name,
                "timestamp": time.time(),
            })
            # Keep last 10000 entries
            entries = entries[-10000:]
            self._audit_file.parent.mkdir(parents=True, exist_ok=True)
            self._audit_file.write_text(json.dumps(entries), encoding="utf-8")
        except Exception as e:
            logger.error("DLP audit log failed: %s", e)

    def get_audit_log(self, limit: int = 100, user_id: Optional[str] = None) -> list[dict]:
        if not self._audit_file.exists():
            return []
        try:
            entries = json.loads(self._audit_file.read_text(encoding="utf-8"))
            if user_id:
                entries = [e for e in entries if e.get("user_id") == user_id]
            return entries[-limit:]
        except Exception:
            return []

    def _count_recent_downloads(self, user_id: str, window_seconds: int) -> int:
        cutoff = time.time() - window_seconds
        log = self.get_audit_log(limit=1000, user_id=user_id)
        return sum(1 for e in log if e.get("action") == "download_allowed" and e.get("timestamp", 0) > cutoff)
