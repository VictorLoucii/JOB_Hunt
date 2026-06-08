"""
Tests for server.services.email_extractor — Regex extraction patterns.

Tests the two-stage extraction pipeline: regex (standard + obfuscated)
and LLM fallback behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.services.email_extractor import (
    _extract_email_regex,
    _normalize_obfuscated,
    extract_email,
)


# ──────────────────────────────────────────────
# Regex extraction — standard patterns
# ──────────────────────────────────────────────


class TestExtractEmailRegex:
    """Tests for the regex extraction function."""

    def test_standard_email(self) -> None:
        """Standard email in text should be extracted."""
        result = _extract_email_regex("Send resume to hiring@acme.ai for review")
        assert result == "hiring@acme.ai"

    def test_email_with_plus(self) -> None:
        """Email with + addressing should be extracted."""
        result = _extract_email_regex("Contact john+intern@company.com")
        assert result == "john+intern@company.com"

    def test_email_with_dots(self) -> None:
        """Email with dots in username should be extracted."""
        result = _extract_email_regex("Reach out to first.last@domain.co.uk")
        assert result == "first.last@domain.co.uk"

    def test_no_email_returns_none(self) -> None:
        """Text without email should return None."""
        result = _extract_email_regex("No email here, just a regular LinkedIn post")
        assert result is None

    def test_multiple_emails_returns_first(self) -> None:
        """When multiple emails exist, return the first one."""
        result = _extract_email_regex("primary@a.com or backup@b.com")
        assert result == "primary@a.com"


# ──────────────────────────────────────────────
# Regex extraction — obfuscated patterns
# ──────────────────────────────────────────────


class TestObfuscatedEmail:
    """Tests for obfuscated email normalization and extraction."""

    def test_bracket_at_dot(self) -> None:
        """[at] and [dot] should be normalized."""
        result = _extract_email_regex("john [at] acme [dot] com")
        assert result == "john@acme.com"

    def test_paren_at_dot(self) -> None:
        """(at) and (dot) should be normalized."""
        result = _extract_email_regex("john (at) acme (dot) com")
        assert result == "john@acme.com"

    def test_curly_at_dot(self) -> None:
        """{at} and {dot} should be normalized."""
        result = _extract_email_regex("john {at} acme {dot} com")
        assert result == "john@acme.com"

    def test_spaced_at_dot(self) -> None:
        """' at ' and ' dot ' (with spaces) should be normalized."""
        result = _extract_email_regex("john at acme dot com")
        assert result == "john@acme.com"

    def test_mixed_obfuscation(self) -> None:
        """Mixed obfuscation patterns should be handled."""
        result = _extract_email_regex("jane [at] startup (dot) io")
        assert result == "jane@startup.io"


class TestNormalizeObfuscated:
    """Tests for the normalization helper."""

    def test_normalize_brackets(self) -> None:
        """Bracket obfuscation should be replaced."""
        result = _normalize_obfuscated("user [at] domain [dot] com")
        assert "@" in result
        assert "." in result

    def test_normalize_preserves_standard(self) -> None:
        """Standard email should not be mangled by normalization."""
        text = "Contact user@domain.com for info"
        result = _normalize_obfuscated(text)
        assert "user@domain.com" in result


# ──────────────────────────────────────────────
# Full pipeline (extract_email async)
# ──────────────────────────────────────────────


class TestExtractEmailPipeline:
    """Tests for the full extract_email async pipeline."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client for testing."""
        client = MagicMock()
        client.extract_email = AsyncMock(return_value=None)
        return client

    async def test_regex_hit_skips_llm(self, mock_llm_client: MagicMock) -> None:
        """When regex finds an email, LLM should not be called."""
        result = await extract_email("Send resume to test@example.com", mock_llm_client)
        assert result.email == "test@example.com"
        assert result.source == "regex"
        assert result.confidence == 1.0
        mock_llm_client.extract_email.assert_not_called()

    async def test_llm_fallback_on_regex_miss(self, mock_llm_client: MagicMock) -> None:
        """When regex misses, LLM should be called."""
        mock_llm_client.extract_email = AsyncMock(return_value="found@llm.com")
        result = await extract_email("Creative email format here", mock_llm_client)
        assert result.email == "found@llm.com"
        assert result.source == "llm"
        assert result.confidence == 0.8

    async def test_manual_fallback_when_both_fail(
        self, mock_llm_client: MagicMock
    ) -> None:
        """When both regex and LLM fail, return manual fallback."""
        mock_llm_client.extract_email = AsyncMock(return_value=None)
        result = await extract_email("No email in this text at all", mock_llm_client)
        assert result.email is None
        assert result.source == "manual"
        assert result.confidence == 0.0

    async def test_invalid_llm_email_falls_to_manual(
        self, mock_llm_client: MagicMock
    ) -> None:
        """When LLM returns invalid email, fall through to manual."""
        mock_llm_client.extract_email = AsyncMock(return_value="not-an-email")
        result = await extract_email("Some text here", mock_llm_client)
        assert result.email is None
        assert result.source == "manual"

    async def test_llm_error_falls_to_manual(
        self, mock_llm_client: MagicMock
    ) -> None:
        """When LLM call raises an exception, fall through to manual."""
        mock_llm_client.extract_email = AsyncMock(side_effect=Exception("API down"))
        result = await extract_email("Some text here", mock_llm_client)
        assert result.email is None
        assert result.source == "manual"

    async def test_obfuscated_email_found_by_regex(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Obfuscated email should be caught by regex, no LLM needed."""
        result = await extract_email(
            "Drop resume at john [at] acme [dot] com", mock_llm_client
        )
        assert result.email == "john@acme.com"
        assert result.source == "regex"
        mock_llm_client.extract_email.assert_not_called()
