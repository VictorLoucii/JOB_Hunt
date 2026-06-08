"""
Tests for server.services.gmail_client — Gmail API integration.

Tests the GmailClient using mocked Google API calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from server.models import EmailDraft
from server.services.gmail_client import GmailClient, GmailError


@pytest.fixture
def gmail_client(mock_settings):
    client = GmailClient(mock_settings)
    # Mock the authenticated service
    mock_service = MagicMock()
    mock_service.users().drafts().create().execute.return_value = {
        "id": "draft-123"
    }
    client._service = mock_service
    return client

def test_create_draft_without_attachment(gmail_client):
    draft = EmailDraft(to_email="a@b.com", subject="Test", body="Hello")
    result = gmail_client.create_draft(draft)
    assert result == "draft-123"

def test_create_draft_with_attachment(gmail_client, tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 test content")
    draft = EmailDraft(to_email="a@b.com", subject="Test", body="Hello")
    result = gmail_client.create_draft(draft, resume_path=resume)
    assert result == "draft-123"

def test_create_draft_returns_draft_id(gmail_client):
    draft = EmailDraft(to_email="a@b.com", subject="Test", body="Hello")
    result = gmail_client.create_draft(draft)
    assert result == "draft-123"

def test_create_draft_api_error(gmail_client):
    gmail_client._service.users().drafts().create().execute.side_effect = Exception("API error")
    draft = EmailDraft(to_email="a@b.com", subject="Test", body="Hello")
    with pytest.raises(GmailError, match="Failed to create Gmail draft: API error"):
        gmail_client.create_draft(draft)

def test_authenticate_with_existing_valid_token(mock_settings):
    with patch("server.services.gmail_client.Credentials.from_authorized_user_file") as mock_from_file, \
         patch("server.services.gmail_client.build") as mock_build, \
         patch.object(Path, "exists", return_value=True):

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_file.return_value = mock_creds

        client = GmailClient(mock_settings)
        client.authenticate()

        mock_from_file.assert_called_once_with(
            str(mock_settings.gmail_token_path),
            ["https://www.googleapis.com/auth/gmail.compose"]
        )
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)

def test_authenticate_creates_service(mock_settings):
    with patch("server.services.gmail_client.Credentials.from_authorized_user_file") as mock_from_file, \
         patch("server.services.gmail_client.build") as mock_build, \
         patch.object(Path, "exists", return_value=True):

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_file.return_value = mock_creds
        mock_build.return_value = "mocked_service"

        client = GmailClient(mock_settings)
        client.authenticate()

        assert client._service == "mocked_service"
