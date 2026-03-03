"""SSO configuration — per-tenant SAML/OIDC settings."""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


@dataclass
class SSOConfig:
    provider: str = ""  # "saml" or "oidc"
    enabled: bool = False
    metadata_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    issuer: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    attribute_mapping: dict = None

    def __post_init__(self):
        if self.attribute_mapping is None:
            self.attribute_mapping = {
                "email": "email",
                "name": "name",
                "role": "role",
            }


def get_sso_config(tenant_id: str, data_dir: Optional[Path] = None) -> SSOConfig:
    base = (data_dir or DATA_DIR) / "tenants" / tenant_id
    f = base / "sso_config.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return SSOConfig(**{k: v for k, v in data.items() if hasattr(SSOConfig, k)})
        except Exception:
            pass
    return SSOConfig()


def save_sso_config(tenant_id: str, config: SSOConfig, data_dir: Optional[Path] = None):
    base = (data_dir or DATA_DIR) / "tenants" / tenant_id
    base.mkdir(parents=True, exist_ok=True)
    f = base / "sso_config.json"
    f.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
