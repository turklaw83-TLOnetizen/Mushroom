# ---- Shared Configuration ------------------------------------------------
# Single source of truth for load_config() and CONFIG.
# All core modules import from here instead of defining their own copy.

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Resolve config.yaml relative to the project root (parent of core/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    """Load application config from config.yaml (if it exists)."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    logger.warning("config.yaml not found at %s - using empty config", _CONFIG_PATH)
    return {}


CONFIG: dict = load_config()
