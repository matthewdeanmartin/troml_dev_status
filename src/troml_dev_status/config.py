# troml_dev_status/config.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field

# Use tomllib for Python 3.11+, fallback to tomli
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]

# --- Default Values ---
DEFAULT_MODE = "application"
DEFAULT_USE_AI = False


class Config(BaseModel):
    """Holds the application configuration."""

    mode: Literal["application", "library"] = Field(default="application")
    use_ai: bool = Field(default=DEFAULT_USE_AI)


def _load_pyproject_toml(repo_path: Path) -> Dict[str, Any] | None:
    """Loads the pyproject.toml file."""
    toml_path = repo_path / "pyproject.toml"
    if not toml_path.is_file():
        return None
    try:
        with toml_path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError:
        return None


# Global config cache to avoid re-reading the file multiple times
_config_cache: Dict[Path, Config] = {}


def load_config(repo_path: Path) -> Config:
    """
    Loads configuration from [tool.troml-dev-status] in pyproject.toml.
    Returns a Config object with defaults if the section is missing or invalid.
    Results are cached per repo_path.
    """
    repo_path = repo_path.resolve()
    if repo_path in _config_cache:
        return _config_cache[repo_path]

    data = _load_pyproject_toml(repo_path)
    tool_config = {}
    if data:
        tool_config = data.get("tool", {}).get("troml-dev-status", {})

    # Pydantic will handle defaults and validation
    config = Config.model_validate(tool_config)
    _config_cache[repo_path] = config
    return config


def set_config_for_testing(repo_path: Path, config: Config):
    """
    Allows overriding the configuration for a given path during tests.
    """
    _config_cache[repo_path.resolve()] = config


def clear_config_cache():
    """Clears the configuration cache. Useful for test isolation."""
    _config_cache.clear()
