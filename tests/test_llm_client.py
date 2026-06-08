"""
Tests for server.services.llm_client — LLM API integration.

Tests the LLMClient using mocked HTTP responses to avoid real API calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from server.models import EmailDraft
from server.services.llm_client import LLMClient, LLMError


@pytest.fixture
def llm_client(mock_settings, mock_user_profile):
    with patch.object(LLMClient, '_load_prompt', return_value="dummy system prompt"):
        client = LLMClient(mock_settings, mock_user_profile)
        yield client

class TestLLMClient:
    """Tests for LLMClient API."""

    @pytest.mark.asyncio
    async def test_draft_email_success(self, llm_client):
        """Mock a valid 200 response with JSON → assert EmailDraft returned correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "to_email": "test@example.com",
                            "subject": "ML Internship Application",
                            "body": "Dear Hiring Manager, I'm interested..."
                        })
                    }
                }
            ]
        }

        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            draft = await llm_client.draft_email("post text")

            assert isinstance(draft, EmailDraft)
            assert draft.to_email == "test@example.com"
            assert draft.subject == "ML Internship Application"

    @pytest.mark.asyncio
    async def test_draft_email_invalid_json(self, llm_client):
        """Mock response with invalid JSON → assert LLMError raised."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "not-valid-json"
                    }
                }
            ]
        }

        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(LLMError, match="Invalid JSON from LLM"):
                await llm_client.draft_email("post text")

    @pytest.mark.asyncio
    async def test_draft_email_api_error(self, llm_client):
        """Mock a 500 response → assert LLMError raised."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(LLMError, match="LLM API returned status 500"):
                await llm_client.draft_email("post text")

    @pytest.mark.asyncio
    async def test_draft_email_timeout(self, llm_client):
        """Mock httpx.TimeoutException → assert LLMError raised."""
        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")
            with pytest.raises(LLMError, match="LLM API request timed out"):
                await llm_client.draft_email("post text")

    @pytest.mark.asyncio
    async def test_draft_email_pydantic_validation_error(self, llm_client):
        """Mock JSON with missing fields → assert LLMError raised."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "to_email": "test@example.com",
                            # missing subject and body
                        })
                    }
                }
            ]
        }

        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(LLMError, match="LLM response failed validation"):
                await llm_client.draft_email("post text")

    @pytest.mark.asyncio
    async def test_extract_email_success(self, llm_client):
        """Mock response with 'test@acme.com' → assert email returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "test@acme.com"
                    }
                }
            ]
        }

        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            email = await llm_client.extract_email("some post text")
            assert email == "test@acme.com"

    @pytest.mark.asyncio
    async def test_extract_email_none(self, llm_client):
        """Mock response with 'NONE' → assert None returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "NONE"
                    }
                }
            ]
        }

        with patch.object(llm_client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            email = await llm_client.extract_email("some post text")
            assert email is None

    @pytest.mark.asyncio
    async def test_close_closes_client(self, llm_client):
        """Assert aclose() is called on the httpx client."""
        with patch.object(llm_client._client, 'aclose', new_callable=AsyncMock) as mock_aclose:
            await llm_client.close()
            mock_aclose.assert_called_once()
