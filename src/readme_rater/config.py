# readme_rater/config.py
"""Handles loading and validation of application settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class LLMSettings(BaseModel):
    """Configuration for the LLM client."""

    api_key: Optional[str] = Field(None, description="API key for the LLM service.")
    model: str = Field(
        "openai/gpt-4o", description="The model identifier to use for the API call."
    )
    base_url: str = Field(
        "https://openrouter.ai/api/v1",
        description="The base URL for the OpenAI-compatible API.",
    )


class AppSettings(BaseSettings):
    """Main application settings model."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        toml_file=os.environ.get("README_RATER_CONFIG", ".config/settings.toml"),
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)  # type: ignore[arg-type]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define the priority of configuration sources."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


def get_project_root() -> Path:
    """Gets the project root directory."""
    return Path(__file__).parent.parent.parent.parent


def get_cache_dir() -> Path:
    """Gets the cache directory path, creating it if it doesn't exist."""
    cache_path = get_project_root() / ".cache"
    cache_path.mkdir(exist_ok=True)
    return cache_path


# Load settings once and reuse
settings = AppSettings()

# Fallback for API key if not in settings or .env
if not settings.llm.api_key:
    settings.llm.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get(
        "OPENAI_API_KEY"
    )
