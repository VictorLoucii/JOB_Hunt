"""
Tests for server.models — Pydantic schema validation.

Covers valid inputs, boundary conditions, and validation error cases
for all models in the pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from server.models import (
    DBRecord,
    DraftResult,
    DraftStatus,
    EmailDraft,
    ExtractedEmail,
    WebhookPayload,
)


# ──────────────────────────────────────────────
# WebhookPayload
# ──────────────────────────────────────────────


class TestWebhookPayload:
    """Tests for WebhookPayload validation."""

    def test_valid_payload(self) -> None:
        """Standard valid payload should pass."""
        payload = WebhookPayload(
            selected_text="Hiring ML interns! Email: test@acme.ai",
            page_url="https://www.linkedin.com/posts/1234",
        )
        assert payload.selected_text == "Hiring ML interns! Email: test@acme.ai"
        assert payload.page_url == "https://www.linkedin.com/posts/1234"
        assert payload.timestamp  # Auto-generated

    def test_valid_payload_without_www(self) -> None:
        """LinkedIn URL without www should also pass."""
        payload = WebhookPayload(
            selected_text="Some text",
            page_url="https://linkedin.com/posts/5678",
        )
        assert payload.page_url == "https://linkedin.com/posts/5678"

    def test_custom_timestamp(self) -> None:
        """Explicit timestamp should be preserved."""
        ts = "2026-06-01T12:00:00Z"
        payload = WebhookPayload(
            selected_text="Test",
            page_url="https://www.linkedin.com/posts/1",
            timestamp=ts,
        )
        assert payload.timestamp == ts

    def test_empty_selected_text_rejected(self) -> None:
        """Empty selected_text should fail validation."""
        with pytest.raises(ValidationError, match="must not be empty"):
            WebhookPayload(
                selected_text="",
                page_url="https://www.linkedin.com/posts/1",
            )

    def test_whitespace_only_selected_text_rejected(self) -> None:
        """Whitespace-only selected_text should fail validation."""
        with pytest.raises(ValidationError, match="must not be empty"):
            WebhookPayload(
                selected_text="   \n\t  ",
                page_url="https://www.linkedin.com/posts/1",
            )

    def test_non_linkedin_url_rejected(self) -> None:
        """Non-LinkedIn URL should fail validation."""
        with pytest.raises(ValidationError, match="must start with"):
            WebhookPayload(
                selected_text="Some text",
                page_url="https://twitter.com/posts/1",
            )

    def test_http_linkedin_url_rejected(self) -> None:
        """HTTP (not HTTPS) LinkedIn URL should fail validation."""
        with pytest.raises(ValidationError, match="must start with"):
            WebhookPayload(
                selected_text="Some text",
                page_url="http://www.linkedin.com/posts/1",
            )


# ──────────────────────────────────────────────
# ExtractedEmail
# ──────────────────────────────────────────────


class TestExtractedEmail:
    """Tests for ExtractedEmail validation."""

    def test_valid_email(self) -> None:
        """Valid email with metadata should pass."""
        result = ExtractedEmail(email="test@acme.ai", source="regex", confidence=1.0)
        assert result.email == "test@acme.ai"
        assert result.source == "regex"
        assert result.confidence == 1.0

    def test_none_email(self) -> None:
        """None email (manual fallback) should pass."""
        result = ExtractedEmail(email=None, source="manual", confidence=0.0)
        assert result.email is None

    def test_invalid_email_format_rejected(self) -> None:
        """Invalid email format should fail validation."""
        with pytest.raises(ValidationError, match="Invalid email format"):
            ExtractedEmail(email="not-an-email", source="regex", confidence=1.0)

    def test_confidence_below_zero_rejected(self) -> None:
        """Confidence below 0.0 should fail."""
        with pytest.raises(ValidationError, match="must be between"):
            ExtractedEmail(email=None, source="manual", confidence=-0.1)

    def test_confidence_above_one_rejected(self) -> None:
        """Confidence above 1.0 should fail."""
        with pytest.raises(ValidationError, match="must be between"):
            ExtractedEmail(email=None, source="manual", confidence=1.1)

    def test_confidence_boundary_values(self) -> None:
        """Boundary values (0.0 and 1.0) should pass."""
        low = ExtractedEmail(email=None, source="manual", confidence=0.0)
        high = ExtractedEmail(email="a@b.co", source="regex", confidence=1.0)
        assert low.confidence == 0.0
        assert high.confidence == 1.0


# ──────────────────────────────────────────────
# EmailDraft
# ──────────────────────────────────────────────


class TestEmailDraft:
    """Tests for EmailDraft validation."""

    def test_valid_draft(self) -> None:
        """Standard valid draft should pass."""
        draft = EmailDraft(
            to_email="hire@company.com",
            subject="ML Internship Application",
            body="Dear Hiring Manager, ...",
        )
        assert draft.to_email == "hire@company.com"

    def test_invalid_to_email_rejected(self) -> None:
        """Invalid to_email should fail."""
        with pytest.raises(ValidationError, match="Invalid email format"):
            EmailDraft(
                to_email="not-valid",
                subject="Test",
                body="Test body",
            )

    def test_empty_subject_rejected(self) -> None:
        """Empty subject should fail."""
        with pytest.raises(ValidationError, match="must not be empty"):
            EmailDraft(
                to_email="a@b.com",
                subject="",
                body="Test body",
            )

    def test_empty_body_rejected(self) -> None:
        """Empty body should fail."""
        with pytest.raises(ValidationError, match="must not be empty"):
            EmailDraft(
                to_email="a@b.com",
                subject="Test",
                body="   ",
            )


# ──────────────────────────────────────────────
# DraftResult
# ──────────────────────────────────────────────


class TestDraftResult:
    """Tests for DraftResult composition."""

    def test_valid_draft_result(self) -> None:
        """Full DraftResult with all fields should pass."""
        result = DraftResult(
            draft=EmailDraft(
                to_email="a@b.com", subject="Test", body="Hello"
            ),
            post_text="We're hiring!",
            page_url="https://www.linkedin.com/posts/1",
            resume_path="/path/to/resume.pdf",
            extracted_email=ExtractedEmail(
                email="a@b.com", source="regex", confidence=1.0
            ),
        )
        assert result.draft.to_email == "a@b.com"
        assert result.resume_path == "/path/to/resume.pdf"
        assert isinstance(result.created_at, datetime)

    def test_draft_result_without_resume(self) -> None:
        """DraftResult without resume path should default to None."""
        result = DraftResult(
            draft=EmailDraft(
                to_email="a@b.com", subject="Test", body="Hello"
            ),
            post_text="We're hiring!",
            page_url="https://www.linkedin.com/posts/1",
            extracted_email=ExtractedEmail(
                email="a@b.com", source="regex", confidence=1.0
            ),
        )
        assert result.resume_path is None


# ──────────────────────────────────────────────
# DraftStatus & DBRecord
# ──────────────────────────────────────────────


class TestDraftStatus:
    """Tests for DraftStatus enum."""

    def test_enum_values(self) -> None:
        """All expected statuses should exist."""
        assert DraftStatus.DRAFTED == "drafted"
        assert DraftStatus.APPROVED == "approved"
        assert DraftStatus.SKIPPED == "skipped"
        assert DraftStatus.REGENERATED == "regenerated"

    def test_string_serialization(self) -> None:
        """DraftStatus (StrEnum) should serialize directly to its value string."""
        assert str(DraftStatus.APPROVED) == "approved"
        assert DraftStatus.APPROVED.value == "approved"


class TestDBRecord:
    """Tests for DBRecord validation."""

    def test_valid_record(self) -> None:
        """Full valid DBRecord should pass."""
        now = datetime.now(timezone.utc)
        record = DBRecord(
            id=1,
            page_url="https://www.linkedin.com/posts/1",
            author_email="hire@co.com",
            subject="ML Intern",
            status=DraftStatus.DRAFTED,
            created_at=now,
        )
        assert record.id == 1
        assert record.updated_at is None

    def test_record_without_id(self) -> None:
        """DBRecord without id (before insert) should default to None."""
        now = datetime.now(timezone.utc)
        record = DBRecord(
            page_url="https://www.linkedin.com/posts/1",
            author_email="hire@co.com",
            subject="ML Intern",
            status=DraftStatus.APPROVED,
            created_at=now,
        )
        assert record.id is None
