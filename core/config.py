# ---- Shared Configuration ------------------------------------------------
# Single source of truth for load_config() and CONFIG.
# All core modules import from here instead of defining their own copy.
#
# Uses Pydantic for validation; supports MUSHROOM_ env-var overrides.
# CONFIG exposes a dict-compatible interface so existing call-sites
# like  CONFIG.get("llm", {}).get("default_provider", "xai")  keep working.

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Resolve config.yaml relative to the project root (parent of core/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


# ---- Pydantic Models ---------------------------------------------------

class XAIConfig(BaseModel):
    """xAI / Grok provider settings."""
    model: str = "grok-4"
    temperature: float = 0.3
    max_tokens: int = 4096


class AnthropicConfig(BaseModel):
    """Anthropic / Claude provider settings."""
    model: str = "claude-4-6-opus-20260205"
    temperature: float = 0.3
    max_tokens: int = 4096


class OpenAIConfig(BaseModel):
    """OpenAI provider settings (e.g. Whisper for transcription)."""
    model: str = "whisper-1"


class LLMConfig(BaseModel):
    """Top-level LLM configuration."""
    default_provider: str = "anthropic"
    fallback_provider: Optional[str] = "xai"
    xai: XAIConfig = Field(default_factory=XAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)


class StorageConfig(BaseModel):
    """Storage paths."""
    vector_db_path: str = "./chroma_db"
    upload_dir: str = "./uploads"
    data_dir: str = "data"


class PrivacyConfig(BaseModel):
    """Privacy controls."""
    allow_external_api: bool = True


class ApiKeysConfig(BaseModel):
    """Optional in-config API keys (env vars preferred)."""
    xai: Optional[str] = None
    anthropic: Optional[str] = None
    google: Optional[str] = None


class AppConfig(BaseModel):
    """Root application configuration.

    Validated at import time so bad config fails fast.
    Exposes ``get()`` / ``__getitem__`` / ``__contains__`` so existing
    code that treats CONFIG as a plain dict keeps working.
    """
    app_name: str = "Legal Prep Agent"
    version: str = "0.1.0"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    api_keys: ApiKeysConfig = Field(default_factory=ApiKeysConfig)

    model_config = {"extra": "allow"}

    # -- Dict-compatible interface ----------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Mimic ``dict.get()`` for backward compatibility.

        Returns the sub-model as a plain dict when the attribute is a
        Pydantic model, so chained ``.get()`` calls keep working:

            CONFIG.get("llm", {}).get("default_provider", "xai")
        """
        try:
            value = getattr(self, key)
        except AttributeError:
            return default
        if isinstance(value, BaseModel):
            return value.model_dump()
        return value

    def __getitem__(self, key: str) -> Any:
        try:
            value = getattr(self, key)
        except AttributeError:
            raise KeyError(key)
        if isinstance(value, BaseModel):
            return value.model_dump()
        return value

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


# ---- Env-Var Override Helpers -------------------------------------------

_ENV_PREFIX = "MUSHROOM_"


def _apply_env_overrides(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Apply MUSHROOM_* environment variable overrides.

    Supports nested keys separated by ``_`` after the prefix:
        MUSHROOM_LLM_DEFAULT_PROVIDER=xai  ->  raw["llm"]["default_provider"] = "xai"
        MUSHROOM_STORAGE_DATA_DIR=/data     ->  raw["storage"]["data_dir"] = "/data"
        MUSHROOM_PRIVACY_ALLOW_EXTERNAL_API=false -> raw["privacy"]["allow_external_api"] = False
    """
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue
        parts = env_key[len(_ENV_PREFIX):].lower().split("_", 1)
        if len(parts) < 2:
            # Top-level scalar: MUSHROOM_APP_NAME etc.
            raw[parts[0]] = _coerce(env_val)
            continue

        section, rest = parts
        raw.setdefault(section, {})
        if isinstance(raw[section], dict):
            # For deeper nesting, split on remaining underscores
            subparts = rest.split("_", 1)
            if len(subparts) == 2 and subparts[0] in ("xai", "anthropic", "openai"):
                # Three-level: MUSHROOM_LLM_XAI_MODEL
                raw[section].setdefault(subparts[0], {})
                if isinstance(raw[section][subparts[0]], dict):
                    raw[section][subparts[0]][subparts[1]] = _coerce(env_val)
                else:
                    raw[section][subparts[0]] = _coerce(env_val)
            else:
                raw[section][rest] = _coerce(env_val)
    return raw


def _coerce(value: str) -> Any:
    """Best-effort type coercion for env-var strings."""
    lower = value.lower()
    if lower in ("true", "1", "yes"):
        return True
    if lower in ("false", "0", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# ---- Loader -------------------------------------------------------------

def load_config() -> AppConfig:
    """Load config from YAML, apply env-var overrides, validate with Pydantic."""
    raw: Dict[str, Any] = {}
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        logger.warning("config.yaml not found at %s - using defaults", _CONFIG_PATH)

    raw = _apply_env_overrides(raw)

    try:
        return AppConfig(**raw)
    except Exception:
        logger.exception("Config validation failed — falling back to defaults")
        return AppConfig()


CONFIG: AppConfig = load_config()
