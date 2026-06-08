"""
JobHunt — Email Extraction Service

Two-stage pipeline for extracting email addresses from LinkedIn post text:
  1. Regex scan (fast, free) — handles standard and common obfuscation patterns
  2. LLM fallback (cheap) — catches creative obfuscation the regex misses
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from server.models import ExtractedEmail

if TYPE_CHECKING:
    from server.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Standard email regex pattern.
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Obfuscation replacements applied before regex matching.
_OBFUSCATION_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", re.IGNORECASE), "@"),
    (re.compile(r"\s+at\s+", re.IGNORECASE), "@"),
    (re.compile(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", re.IGNORECASE), "."),
    (re.compile(r"\s+dot\s+", re.IGNORECASE), "."),
]


def _normalize_obfuscated(text: str) -> str:
    """
    Normalize common email obfuscation patterns in text.

    Handles patterns like:
      - user [at] domain [dot] com
      - user (at) domain (dot) com
      - user {at} domain {dot} com
      - user at domain dot com
    """
    normalized = text
    for pattern, replacement in _OBFUSCATION_MAP:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _extract_email_regex(text: str) -> str | None:
    """
    Try to extract an email using regex patterns.

    Runs regex on both the original text and a version with
    normalized obfuscation patterns. Returns the first valid
    email found, or None.
    """
    # Try original text first.
    match = _EMAIL_PATTERN.search(text)
    if match:
        logger.debug("Email found via regex (original text): %s", match.group())
        return match.group()

    # Try normalized text (de-obfuscated).
    normalized = _normalize_obfuscated(text)
    match = _EMAIL_PATTERN.search(normalized)
    if match:
        logger.debug("Email found via regex (normalized text): %s", match.group())
        return match.group()

    return None


async def extract_email(text: str, llm_client: LLMClient) -> ExtractedEmail:
    """
    Extract email from LinkedIn post text.

    Pipeline:
      1. Regex scan → if found, return with confidence=1.0, source="regex"
      2. LLM extraction → if found, return with confidence=0.8, source="llm"
      3. Return None email with confidence=0.0, source="manual"

    Args:
        text: The LinkedIn post text to extract an email from.
        llm_client: LLM client instance for the fallback extraction.

    Returns:
        ExtractedEmail with the result and metadata.
    """
    # Stage 1: Regex extraction (fast, free).
    regex_result = _extract_email_regex(text)
    if regex_result:
        logger.info("Email extracted via regex: %s", regex_result)
        return ExtractedEmail(email=regex_result, source="regex", confidence=1.0)

    # Stage 2: LLM extraction (handles creative obfuscation).
    logger.info("Regex failed — falling back to LLM extraction")
    try:
        llm_result = await llm_client.extract_email(text)
        if llm_result:
            # Validate the LLM result with regex before accepting.
            if _EMAIL_PATTERN.match(llm_result):
                logger.info("Email extracted via LLM: %s", llm_result)
                return ExtractedEmail(email=llm_result, source="llm", confidence=0.8)
            logger.warning("LLM returned invalid email format: %s", llm_result)
    except Exception as e:
        logger.error("LLM email extraction failed: %s", e)

    # Stage 3: No email found — will need manual input at HITL step.
    logger.info("No email found — manual input required")
    return ExtractedEmail(email=None, source="manual", confidence=0.0)
