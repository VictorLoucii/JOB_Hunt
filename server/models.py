"""
JobHunt — Pydantic Models

Central schema definitions for all data boundaries in the pipeline.
Every external input/output is validated through these models.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Simple email regex used across multiple models for validation.
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class WebhookPayload(BaseModel):
    """Incoming data from the Tampermonkey script."""

    selected_text: str = Field(..., description="Text the user highlighted on LinkedIn")
    page_url: str = Field(..., description="LinkedIn post URL")
    content_hash: str = Field(..., description="SHA-256 hash of the selected text")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 timestamp from the browser",
    )

    @field_validator("selected_text")
    @classmethod
    def selected_text_not_empty(cls, v: str) -> str:
        """Ensure selected_text is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("selected_text must not be empty or whitespace-only")
        return v

    @field_validator("page_url")
    @classmethod
    def validate_linkedin_url(cls, v: str) -> str:
        """Ensure page_url is a LinkedIn URL."""
        if not v.startswith(("https://www.linkedin.com/", "https://linkedin.com/")):
            raise ValueError(
                "page_url must start with 'https://www.linkedin.com/' or 'https://linkedin.com/'"
            )
        return v


class ExtractedEmail(BaseModel):
    """Result of the email extraction pipeline."""

    email: str | None = Field(default=None, description="Extracted email, or None if not found")
    source: str = Field(..., description="How it was found: 'regex', 'llm', or 'manual'")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        """If email is provided, it must match a basic email pattern."""
        if v is not None and not EMAIL_REGEX.match(v):
            raise ValueError(f"Invalid email format: {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Confidence must be between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


class EligibilityResult(BaseModel):
    """Result of the LLM eligibility screening."""

    hard_requirements_found: list[str] = Field(
        ...,
        description="Strict dealbreakers mentioned in the post (e.g., 'Must have 5 years experience', 'Requires US Citizenship').",
    )
    soft_requirements_found: list[str] = Field(
        ...,
        description="Nice-to-haves or preferred qualifications (e.g., 'Master's preferred', 'Bonus points for AWS').",
    )
    candidate_matches_hard_requirements: bool = Field(
        ...,
        description="True if the candidate meets ALL hard requirements.",
    )
    reasoning: str = Field(
        ...,
        description="Short explanation of why the candidate is or isn't eligible based ONLY on hard requirements.",
    )
    is_eligible: bool = Field(
        ...,
        description="Final decision. True if eligible, False if disqualified.",
    )


class EmailDraft(BaseModel):
    """LLM-generated email draft (matches the JSON schema in email_draft.txt)."""

    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Full email body text")

    @field_validator("to_email", mode="before")
    @classmethod
    def validate_to_email(cls, v: Any) -> str:
        """Ensure to_email is a string. The webhook overrides this anyway."""
        if v is None:
            return ""
        if not isinstance(v, str):
            v = str(v)

        v_stripped = v.strip()
        # Just return the string. If it's totally invalid, the webhook overrides it
        # with the extracted/manual email before sending to Gmail.
        if not v_stripped or v_stripped.startswith("[") or EMAIL_REGEX.match(v_stripped):
            return v_stripped

        # If the LLM hallucinated some random text (like "extracted email from post"),
        # just return an empty string to avoid crashing.
        return ""

    @field_validator("subject")
    @classmethod
    def subject_not_empty(cls, v: str) -> str:
        """Subject must not be empty."""
        if not v.strip():
            raise ValueError("subject must not be empty")
        return v

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        """Body must not be empty."""
        if not v.strip():
            raise ValueError("body must not be empty")
        return v


class DraftResult(BaseModel):
    """Combined result object passed to the HITL review step and stored in the database."""

    draft: EmailDraft = Field(..., description="The generated email draft")
    post_text: str = Field(..., description="Original LinkedIn post text")
    page_url: str = Field(..., description="Original LinkedIn post URL")
    content_hash: str = Field(..., description="SHA-256 hash of the selected text")
    resume_path: str | None = Field(
        default=None, description="Path to attached resume, or None"
    )
    extracted_email: ExtractedEmail = Field(..., description="Email extraction details")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this result was generated",
    )


class DraftStatus(StrEnum):
    """Status of a draft in the database."""

    DRAFTED = "drafted"
    APPROVED = "approved"
    SKIPPED = "skipped"
    REGENERATED = "regenerated"


class DBRecord(BaseModel):
    """A row in the SQLite tracking table."""

    id: int | None = Field(default=None, description="Auto-incremented primary key")
    page_url: str = Field(..., description="LinkedIn post URL")
    author_email: str = Field(..., description="Email address from the post")
    subject: str = Field(..., description="Email subject line")
    status: DraftStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="When the record was created")
    updated_at: datetime | None = Field(
        default=None, description="When the record was last modified"
    )
