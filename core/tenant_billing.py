"""Tenant billing & quota enforcement."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

PLAN_LIMITS = {
    "starter": {"max_users": 5, "max_cases": 50, "max_storage_gb": 10.0, "max_tokens_month": 100_000},
    "professional": {"max_users": 25, "max_cases": 500, "max_storage_gb": 100.0, "max_tokens_month": 1_000_000},
    "enterprise": {"max_users": 999999, "max_cases": 999999, "max_storage_gb": 1000.0, "max_tokens_month": 10_000_000},
}


class TenantBilling:
    """Track and enforce per-tenant resource usage."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.base = (data_dir or DATA_DIR) / "tenants"
        self.base.mkdir(parents=True, exist_ok=True)

    def _usage_file(self, tenant_id: str) -> Path:
        return self.base / tenant_id / "usage.json"

    def _load_usage(self, tenant_id: str) -> dict:
        f = self._usage_file(tenant_id)
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"cases": 0, "users": 0, "storage_bytes": 0, "tokens_month": 0}

    def _save_usage(self, tenant_id: str, usage: dict):
        f = self._usage_file(tenant_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(usage), encoding="utf-8")

    def get_usage(self, tenant_id: str) -> dict:
        return self._load_usage(tenant_id)

    def check_quota(self, tenant_id: str, resource: str, plan: str = "starter") -> dict:
        """Check if tenant can use more of a resource."""
        usage = self._load_usage(tenant_id)
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])

        checks = {
            "cases": ("cases", "max_cases"),
            "users": ("users", "max_users"),
            "storage": ("storage_bytes", "max_storage_gb"),
            "tokens": ("tokens_month", "max_tokens_month"),
        }

        if resource not in checks:
            return {"allowed": True, "reason": "Unknown resource"}

        usage_key, limit_key = checks[resource]
        current = usage.get(usage_key, 0)
        limit = limits[limit_key]

        if resource == "storage":
            current_gb = current / (1024 ** 3)
            allowed = current_gb < limit
            return {"allowed": allowed, "current": round(current_gb, 2), "limit": limit, "unit": "GB"}

        allowed = current < limit
        return {"allowed": allowed, "current": current, "limit": limit}

    def record_usage(self, tenant_id: str, resource: str, amount: int = 1):
        usage = self._load_usage(tenant_id)
        mapping = {"cases": "cases", "users": "users", "tokens": "tokens_month", "storage": "storage_bytes"}
        key = mapping.get(resource, resource)
        usage[key] = usage.get(key, 0) + amount
        self._save_usage(tenant_id, usage)

    def get_billing_summary(self, tenant_id: str, plan: str = "starter") -> dict:
        usage = self._load_usage(tenant_id)
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
        return {
            "plan": plan,
            "usage": usage,
            "limits": limits,
            "cases_pct": round(usage.get("cases", 0) / max(limits["max_cases"], 1) * 100, 1),
            "users_pct": round(usage.get("users", 0) / max(limits["max_users"], 1) * 100, 1),
            "storage_pct": round(usage.get("storage_bytes", 0) / (limits["max_storage_gb"] * 1024**3) * 100, 1),
            "tokens_pct": round(usage.get("tokens_month", 0) / max(limits["max_tokens_month"], 1) * 100, 1),
        }
