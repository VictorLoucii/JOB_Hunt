"""
JobHunt — Shared Test Fixtures

Provides reusable fixtures for the test suite:
- Mock settings (no real .env needed)
- Mock LLM responses
- In-memory SQLite database
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_settings() -> MagicMock:
    """
    Create a mock Settings object for tests that don't need real env vars.

    Returns:
        MagicMock with common settings attributes pre-configured.
    """
    settings = MagicMock()
    settings.server_host = "127.0.0.1"
    settings.server_port = 8000
    settings.log_level = "DEBUG"
    settings.openrouter_api_key = "sk-or-v1-test-key"
    settings.gmail_credentials_path = Path("/tmp/test_credentials.json")
    settings.gmail_token_path = Path("/tmp/test_token.json")
    settings.resume_dir = Path("/tmp/test_resumes")
    return settings


@pytest.fixture
def sample_linkedin_post() -> str:
    """Sample LinkedIn post text for testing."""
    return (
        "🚀 We're hiring AI/ML Interns for Summer 2026!\n\n"
        "Location: Bangalore\n"
        "Duration: 3 months (paid)\n"
        "Team: Applied AI\n\n"
        "Looking for candidates with experience in Python, ML, and LLMs.\n"
        "Send your resume to hiring@acme.ai\n\n"
        "#hiring #internship #AI #ML"
    )


@pytest.fixture
def sample_post_with_obfuscated_email() -> str:
    """Sample post with obfuscated email for extraction tests."""
    return (
        "Hiring ML interns! Paid, Bangalore based.\n"
        "Interested? Drop your resume at john [at] acme [dot] com\n"
        "or DM me."
    )


@pytest.fixture
def mock_user_profile() -> MagicMock:
    """
    Create a mock UserProfile object for tests.
    """
    profile = MagicMock()
    profile.llm_model = "deepseek/deepseek-chat"
    profile.llm_temperature = 0.7
    profile.llm_max_tokens = 1024
    profile.to_prompt_context.return_value = "Name: Test User\nSkills: Python"
    return profile
