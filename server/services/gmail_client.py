"""
JobHunt — Gmail API Client

Creates Gmail drafts with optional resume attachments using Google's
official API client library with OAuth2 authentication.
"""

from __future__ import annotations

import base64
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from server.config import Settings
from server.models import EmailDraft

logger = logging.getLogger(__name__)

# Minimal scope — compose only (create drafts + send). No read access.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailError(Exception):
    """Raised when Gmail API operations fail."""


class GmailClient:
    """Gmail API client for creating drafts with resume attachments."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize Gmail client.

        Stores settings but does NOT authenticate immediately.
        Authentication happens lazily on first API call or explicitly
        via authenticate().
        """
        self._settings = settings
        self._service: Any = None
        self._creds: Credentials | None = None
        logger.info("GmailClient initialized (not yet authenticated)")

    @property
    def is_authenticated(self) -> bool:
        """Check if the Gmail service has been authenticated."""
        return self._service is not None

    def authenticate(self) -> None:
        """
        Run the OAuth2 flow.

        Flow:
          1. Check if token.json exists and is valid → use it
          2. If token exists but expired → refresh it
          3. If no token → open browser for OAuth consent, save token.json

        This is a BLOCKING call (may open browser on first run).
        Should be called during server startup or first use.

        Raises:
            GmailError: If authentication fails.
        """
        creds: Credentials | None = None
        token_path = self._settings.gmail_token_path
        creds_path = self._settings.gmail_credentials_path

        try:
            # 1. Try loading existing token.
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                logger.info("Loaded existing token from %s", token_path)

            # 2. Refresh or re-authenticate.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired token")
                    creds.refresh(Request())
                else:
                    if not creds_path.exists():
                        raise GmailError(
                            f"Gmail credentials file not found: {creds_path}. "
                            "Download it from Google Cloud Console."
                        )
                    logger.info("Starting OAuth flow — a browser window will open")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # 3. Save token for next time.
                token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
                logger.info("Saved token to %s", token_path)

            self._creds = creds
            self._service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail API authenticated successfully")

        except GmailError:
            raise
        except Exception as e:
            logger.error("Gmail authentication failed: %s", e)
            raise GmailError(f"Gmail authentication failed: {e}") from e

    def _ensure_authenticated(self) -> None:
        """Ensure the service is authenticated before making API calls."""
        if not self.is_authenticated:
            raise GmailError(
                "Gmail client is not authenticated. Call authenticate() first."
            )

    def create_draft(
        self, draft: EmailDraft, resume_path: Path | None = None
    ) -> str:
        """
        Create a Gmail draft with optional resume attachment.

        Args:
            draft: The EmailDraft with to_email, subject, body.
            resume_path: Path to resume PDF, or None for no attachment.

        Returns:
            Draft ID string from Gmail API.

        Raises:
            GmailError: If draft creation fails.
        """
        self._ensure_authenticated()

        # Create a fresh service instance to avoid thread-safety issues
        # and stale httplib2 connections (Broken pipe) after long idle times.
        service = build("gmail", "v1", credentials=self._creds)

        try:
            if resume_path and resume_path.exists():
                raw_message = self._build_message_with_attachment(draft, resume_path)
                logger.info("Creating draft with resume attachment: %s", resume_path.name)
            else:
                raw_message = self._build_plain_message(draft)
                if resume_path:
                    logger.warning(
                        "Resume path provided but file not found: %s", resume_path
                    )
                logger.info("Creating draft without attachment")

            body = {"message": {"raw": raw_message}}
            result = (
                service.users()
                .drafts()
                .create(userId="me", body=body)
                .execute()
            )

            draft_id = result["id"]
            logger.info("Gmail draft created — ID: %s", draft_id)
            return draft_id

        except GmailError:
            raise
        except Exception as e:
            logger.error("Failed to create Gmail draft: %s", e)
            raise GmailError(f"Failed to create Gmail draft: {e}") from e

    @staticmethod
    def _build_plain_message(draft: EmailDraft) -> str:
        """Build an HTML MIME message and return base64url-encoded raw string."""
        html_body = draft.body.replace("\n", "<br>")
        message = MIMEText(html_body, "html")
        message["to"] = draft.to_email
        message["subject"] = draft.subject
        return base64.urlsafe_b64encode(message.as_bytes()).decode()

    @staticmethod
    def _build_message_with_attachment(
        draft: EmailDraft, resume_path: Path
    ) -> str:
        """
        Build a multipart MIME message with PDF attachment.

        Returns base64url-encoded raw string.
        """
        message = MIMEMultipart()
        message["to"] = draft.to_email
        message["subject"] = draft.subject

        html_body = draft.body.replace("\n", "<br>")
        message.attach(MIMEText(html_body, "html"))

        # Attach the resume PDF.
        with open(resume_path, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="pdf")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=resume_path.name,
            )
            message.attach(attachment)

        return base64.urlsafe_b64encode(message.as_bytes()).decode()
