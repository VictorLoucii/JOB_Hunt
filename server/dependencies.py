"""
JobHunt — FastAPI Dependencies

Provides singletons for routers to inject from app.state.
"""

from __future__ import annotations

from typing import cast

from fastapi import HTTPException, Request

from server.config import Settings, UserProfile
from server.config import get_user_profile as load_user_profile
from server.services.db import Database
from server.services.gmail_client import GmailClient
from server.services.llm_client import LLMClient


def get_settings(request: Request) -> Settings:
    """Get the loaded Settings object."""
    return cast(Settings, request.app.state.settings)


def get_llm_client(request: Request) -> LLMClient:
    """Get the LLMClient instance."""
    return cast(LLMClient, request.app.state.llm_client)


def get_gmail_client(request: Request) -> GmailClient:
    """Get the GmailClient instance."""
    return cast(GmailClient, request.app.state.gmail_client)


def get_user_profile() -> UserProfile:
    """
    Load the UserProfile from config.yaml on each request.

    Edits to the constraints and the resume dir apply without a restart. The
    LLMClient keeps the profile it got at startup for everything else.

    Raises:
        HTTPException: 500 when config.yaml fails validation; the server log names the field.
    """
    try:
        return load_user_profile()
    except ValueError as e:
        raise HTTPException(status_code=500, detail="Invalid config.yaml; see server log") from e


def get_db(request: Request) -> Database:
    """Get the Database instance."""
    return cast(Database, request.app.state.db)
