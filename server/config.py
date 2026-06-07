"""
JobHunt — Configuration Loader

Single source of truth for all application settings.
Loads from .env (secrets) and config.yaml (user profile), validates with Pydantic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Project root = parent of server/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables (.env file).
    
    Usage:
        settings = Settings()
        print(settings.openrouter_api_key)
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Server ----
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    log_level: str = "INFO"

    # ---- OpenRouter (LLM) ----
    openrouter_api_key: str = Field(..., description="OpenRouter API key for DeepSeek")

    # ---- Gmail OAuth ----
    gmail_credentials_path: Path = Field(
        default=PROJECT_ROOT / "credentials" / "credentials.json",
        description="Path to Gmail OAuth client credentials",
    )
    gmail_token_path: Path = Field(
        default=PROJECT_ROOT / "credentials" / "token.json",
        description="Path to store Gmail OAuth token",
    )

    # ---- Resume ----
    resume_dir: Path = Field(
        default=Path.home() / "Documents" / "resumes",
        description="Directory containing resume PDF(s)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log_level '{v}'. Must be one of: {valid_levels}")
        return upper

    @field_validator("resume_dir", mode="before")
    @classmethod
    def expand_resume_dir(cls, v: Any) -> Path:
        """Expand ~ in resume directory path."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v


class UserProfile:
    """
    User profile loaded from config.yaml.
    
    Contains non-secret user information used for LLM prompt context.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or (PROJECT_ROOT / "config.yaml")
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load and parse config.yaml."""
        if not self._config_path.exists():
            logger.warning("config.yaml not found at %s — using defaults", self._config_path)
            self._data = {}
            return

        with open(self._config_path, encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        logger.info("Loaded user profile from %s", self._config_path)

    @property
    def name(self) -> str:
        return self._data.get("user", {}).get("name", "")

    @property
    def university(self) -> str:
        return self._data.get("user", {}).get("university", "")

    @property
    def major(self) -> str:
        return self._data.get("user", {}).get("major", "")

    @property
    def graduation(self) -> str:
        return self._data.get("user", {}).get("graduation", "")

    @property
    def skills(self) -> list[str]:
        return self._data.get("user", {}).get("skills", [])

    @property
    def linkedin(self) -> str:
        return self._data.get("user", {}).get("linkedin", "")

    @property
    def portfolio(self) -> str:
        return self._data.get("user", {}).get("portfolio", "")

    @property
    def llm_model(self) -> str:
        return self._data.get("llm", {}).get("model", "deepseek/deepseek-chat")

    @property
    def llm_temperature(self) -> float:
        return self._data.get("llm", {}).get("temperature", 0.7)

    @property
    def llm_max_tokens(self) -> int:
        return self._data.get("llm", {}).get("max_tokens", 1024)

    def to_prompt_context(self) -> str:
        """
        Format user profile as a string for LLM prompt injection.
        
        Returns:
            Formatted string with user details for email personalization.
        """
        skills_str = ", ".join(self.skills) if self.skills else "Not specified"
        return (
            f"Name: {self.name}\n"
            f"University: {self.university}\n"
            f"Major: {self.major}\n"
            f"Expected Graduation: {self.graduation}\n"
            f"Skills: {skills_str}\n"
            f"LinkedIn: {self.linkedin}\n"
            f"Portfolio: {self.portfolio}"
        )


def get_settings() -> Settings:
    """Create and return validated Settings instance."""
    return Settings()


def get_user_profile() -> UserProfile:
    """Create and return UserProfile instance."""
    return UserProfile()
