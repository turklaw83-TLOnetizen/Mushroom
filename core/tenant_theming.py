"""Tenant theming — white-label branding configuration."""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


@dataclass
class TenantTheme:
    logo_url: str = ""
    primary_color: str = "#6366f1"
    secondary_color: str = "#8b5cf6"
    accent_color: str = "#f59e0b"
    font_family: str = "Inter, system-ui, sans-serif"
    firm_name: str = "Project Mushroom Cloud"
    tagline: str = "Legal Intelligence Suite"
    favicon_url: str = ""
    sidebar_bg: str = "#1e1b4b"
    header_bg: str = "#ffffff"


def get_theme(tenant_id: str, data_dir: Optional[Path] = None) -> TenantTheme:
    base = (data_dir or DATA_DIR) / "tenants" / tenant_id
    f = base / "theme.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return TenantTheme(**{k: v for k, v in data.items() if hasattr(TenantTheme, k)})
        except Exception as e:
            logger.warning("Failed to load theme for %s: %s", tenant_id, e)
    return TenantTheme()


def apply_theme(tenant_id: str, theme: TenantTheme, data_dir: Optional[Path] = None):
    base = (data_dir or DATA_DIR) / "tenants" / tenant_id
    base.mkdir(parents=True, exist_ok=True)
    f = base / "theme.json"
    f.write_text(json.dumps(asdict(theme), indent=2), encoding="utf-8")


def get_theme_css_vars(theme: TenantTheme) -> dict[str, str]:
    """Convert theme to CSS custom properties."""
    return {
        "--primary": theme.primary_color,
        "--secondary": theme.secondary_color,
        "--accent": theme.accent_color,
        "--font-family": theme.font_family,
        "--sidebar-bg": theme.sidebar_bg,
        "--header-bg": theme.header_bg,
    }
