"""
JobHunt — LLM Client (OpenRouter / DeepSeek)

Async HTTP client for the OpenRouter API. Handles two types of calls:
  1. Email drafting — Full prompt with post text + user profile → structured EmailDraft
  2. Email extraction — Lightweight prompt to find obfuscated emails
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx

from server.config import PROJECT_ROOT, Settings, UserConstraints, UserProfile
from server.models import EligibilityResult, EmailDraft

logger = logging.getLogger(__name__)

# OpenRouter API base URL.
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Lightweight prompt for email extraction (not the full drafting prompt).
_EMAIL_EXTRACTION_PROMPT = """Extract the email address from this text.
Return ONLY the email address, nothing else.
If no email is found, return "NONE".

Text: {text}"""

_ELIGIBILITY_PROMPT = """Evaluate if candidate is eligible based on their strict constraints.
You MUST output JSON matching EXACTLY this schema:
{{
  "hard_requirements_found": ["list of strict dealbreakers"],
  "soft_requirements_found": ["list of preferred qualifications"],
  "candidate_matches_hard_requirements": true/false,
  "reasoning": "short explanation based only on hard requirements",
  "is_eligible": true/false
}}

Rules:
1. Bias Towards Action: If a qualification is listed as 'preferred', 'bonus', or
   'nice to have', it MUST be ignored for eligibility purposes.
2. Benefit of the Doubt: If it is ambiguous whether a requirement is strict or
   preferred, default to marking the candidate as is_eligible: True.
3. Strict Matching: Only reject (is_eligible: False) if the post explicitly uses
   exclusionary language (e.g., "Must have", "Required", "Strictly on-site") that
   conflicts with the user's constraints.
4. Education Status: Consider the candidate's Graduation Date relative to the Current Date. If the current date is the same month/year or later, the candidate HAS ALREADY graduated and possesses the degree. Also, if a role accepts "Pursuing or recently completed", then either students or recent grads are eligible.
5. Remote Geopolitics: If a role is "Remote" but explicitly restricted to a country outside of India or the US (e.g., "Remote (Pakistan)", "Remote - UK only"), you MUST reject it (is_eligible: False) unless that specific country is in the Allowed Locations list.
6. Job Post Validation: If the text provided is just an informational article, thought-leadership post, or discussion (NOT a job or internship listing), you MUST reject it (is_eligible: False).
7. Excluded Roles: Reject any role that is primarily focused on the Excluded Role Types (e.g., Sales, Marketing, Outreach), even if it has 'AI' in the title.
8. Paid-Only Filter: Reject any role that explicitly states compensation is 100% commission or performance-based.

Candidate Constraints:
Allowed Locations: {locations}
Max Experience Required: {max_exp} years
Graduation Date: {grad_date}
Degree: {degree}
Excluded Role Types: {excluded_roles}

Current Date:
{current_date}

Job Post:
{post_text}"""


class LLMError(Exception):
    """Raised when LLM API call fails or returns unparseable response."""


class LLMClient:
    """Async client for OpenRouter API (DeepSeek model)."""

    def __init__(self, settings: Settings, user_profile: UserProfile) -> None:
        """
        Initialize with settings and user profile.

        Creates an httpx.AsyncClient with connection pooling, authorization,
        and required OpenRouter headers. Loads the system prompt once.
        """
        self._settings = settings
        self._user_profile = user_profile

        self._client = httpx.AsyncClient(
            base_url=_OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "JobHunt",
            },
            timeout=30.0,
        )

        # Load the system prompt once at init.
        prompt_path = PROJECT_ROOT / "prompts" / "email_draft.txt"
        self._system_prompt = self._load_prompt(prompt_path)
        logger.info("LLMClient initialized with model: %s", user_profile.llm_model)

    @staticmethod
    def _load_prompt(path: Path) -> str:
        """Load a prompt template from disk."""
        if not path.exists():
            raise LLMError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    async def draft_email(self, post_text: str) -> EmailDraft:
        """
        Generate a personalized email draft from a LinkedIn post.

        Steps:
          1. Construct user message with post_text + user_profile context
          2. POST to /chat/completions with json_object response format
          3. Parse response → validate with EmailDraft model

        Args:
            post_text: The raw LinkedIn post text.

        Returns:
            Validated EmailDraft.

        Raises:
            LLMError: If the API call fails or response can't be parsed.
        """
        profile_context = self._user_profile.to_prompt_context()
        user_message = (
            f"## LinkedIn Post\n{post_text}\n\n"
            f"## My Profile\n{profile_context}"
        )

        payload = {
            "model": self._user_profile.llm_model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self._user_profile.llm_temperature,
            "max_tokens": self._user_profile.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }

        raw_content = await self._call_api(payload)

        # Parse and validate.
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", e, raw_content)
            raise LLMError(f"Invalid JSON from LLM: {e}") from e

        try:
            draft = EmailDraft.model_validate(parsed)
        except Exception as e:
            logger.error(
                "Pydantic validation failed for LLM response: %s\nParsed: %s", e, parsed
            )
            raise LLMError(f"LLM response failed validation: {e}") from e

        logger.info("Email draft generated — subject: %s", draft.subject)
        return draft

    async def evaluate_eligibility(
        self, post_text: str, constraints: UserConstraints
    ) -> EligibilityResult:
        """
        Evaluate if a LinkedIn post meets the user's hard constraints.

        Args:
            post_text: The raw LinkedIn post text.
            constraints: The user's hard constraints.

        Returns:
            Validated EligibilityResult.

        Raises:
            LLMError: If the API call fails or response can't be parsed.
        """
        locs = constraints.allowed_locations
        locations_str = ", ".join(locs) if locs else "Any"
        excluded = constraints.excluded_role_types
        excluded_roles_str = ", ".join(excluded) if excluded else "None"
        current_date_str = datetime.now(UTC).strftime("%B %Y")
        
        prompt = _ELIGIBILITY_PROMPT.format(
            locations=locations_str,
            max_exp=constraints.max_experience_required_years,
            grad_date=constraints.grad_date,
            degree=constraints.degree,
            excluded_roles=excluded_roles_str,
            current_date=current_date_str,
            post_text=post_text,
        )

        payload = {
            "model": self._user_profile.llm_model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,  # Deterministic for screening
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }

        raw_content = await self._call_api(payload)

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", e, raw_content)
            raise LLMError(f"Invalid JSON from LLM: {e}") from e

        try:
            result = EligibilityResult.model_validate(parsed)
        except Exception as e:
            logger.error(
                "Pydantic validation failed for LLM response: %s\nParsed: %s", e, parsed
            )
            raise LLMError(f"LLM response failed validation: {e}") from e

        logger.info("Eligibility evaluated — eligible: %s", result.is_eligible)
        return result

    async def extract_email(self, text: str) -> str | None:
        """
        Lightweight call to extract an email from text.

        Uses a simple prompt (not the full drafting prompt).

        Args:
            text: The text to search for an email address.

        Returns:
            The email string, or None if not found.

        Raises:
            LLMError: If the API call fails.
        """
        prompt = _EMAIL_EXTRACTION_PROMPT.format(text=text)

        payload = {
            "model": self._user_profile.llm_model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,  # Deterministic for extraction.
            "max_tokens": 100,  # Short response expected.
        }

        raw_content = await self._call_api(payload)
        result = raw_content.strip()

        if result.upper() == "NONE" or not result:
            logger.info("LLM extraction returned no email")
            return None

        logger.info("LLM extracted email: %s", result)
        return result

    async def _call_api(self, payload: dict) -> str:
        """
        Make a POST request to the OpenRouter chat completions endpoint.

        Args:
            payload: The JSON request body.

        Returns:
            The raw content string from the LLM response.

        Raises:
            LLMError: On network errors, non-200 status, or missing content.
        """
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as e:
            logger.error("LLM API request timed out: %s", e)
            raise LLMError("LLM API request timed out") from e
        except httpx.HTTPError as e:
            logger.error("LLM API network error: %s", e)
            raise LLMError(f"LLM API network error: {e}") from e

        if response.status_code != 200:
            logger.error(
                "LLM API returned status %d: %s", response.status_code, response.text
            )
            raise LLMError(
                f"LLM API returned status {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error("Failed to extract content from LLM response: %s", e)
            raise LLMError(f"Unexpected LLM response structure: {e}") from e

        return content

    async def close(self) -> None:
        """Close the httpx client. Call during app shutdown."""
        await self._client.aclose()
        logger.info("LLMClient closed")
