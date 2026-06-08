"""
Tests for server.routers.webhook — webhook endpoint integration tests.

Uses FastAPI TestClient with mocked dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server.dependencies import get_db, get_gmail_client, get_llm_client, get_settings
from server.main import app
from server.models import DraftStatus, EmailDraft
from server.services.db import Database


@pytest.fixture
def mock_db():
    db = Database(db_path=Path(":memory:"))
    return db

@pytest.fixture
def client(mock_db, mock_settings):
    mock_llm = MagicMock()
    mock_gmail = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_llm_client] = lambda: mock_llm
    app.dependency_overrides[get_gmail_client] = lambda: mock_gmail

    with TestClient(app) as c:
        yield c, mock_llm, mock_gmail, mock_db

    app.dependency_overrides.clear()

def test_webhook_duplicate_post(client):
    c, mock_llm, mock_gmail, mock_db = client
    # Pre-insert a record
    mock_db.insert_record(
        page_url="https://www.linkedin.com/posts/123",
        author_email="test@co.com",
        subject="Test",
        status=DraftStatus.DRAFTED,
    )
    response = c.post("/webhook", json={
        "selected_text": "Some text",
        "page_url": "https://www.linkedin.com/posts/123",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    assert response.json()["reason"] == "duplicate_post"

def test_webhook_invalid_payload_empty_text(client):
    c, _, _, _ = client
    response = c.post("/webhook", json={
        "selected_text": "",
        "page_url": "https://www.linkedin.com/posts/123",
    })
    assert response.status_code == 422

def test_webhook_invalid_payload_non_linkedin_url(client):
    c, _, _, _ = client
    response = c.post("/webhook", json={
        "selected_text": "Some text",
        "page_url": "https://twitter.com/posts/123",
    })
    assert response.status_code == 422

@patch("server.routers.webhook.present_hitl_review", return_value="A")
@patch("server.routers.webhook.prompt_for_email", return_value="test@example.com")
def test_webhook_valid_payload_pipeline_fires(mock_prompt, mock_hitl, client):
    c, mock_llm, mock_gmail, mock_db = client

    # Setup mocks
    mock_llm.extract_email = AsyncMock(return_value="test@example.com")
    mock_llm.draft_email = AsyncMock(return_value=EmailDraft(
        to_email="test@example.com", subject="Test", body="Body"
    ))
    mock_gmail.create_draft = MagicMock(return_value="draft-123")

    response = c.post("/webhook", json={
        "selected_text": "Hiring! email is test@example.com",
        "page_url": "https://www.linkedin.com/posts/456",
    })

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
