"""
JobHunt — Webhook Router

Receives data from the Tampermonkey script and orchestrates the
entire end-to-end extraction, drafting, and HITL review pipeline.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from server.config import Settings
from server.dependencies import get_db, get_gmail_client, get_llm_client, get_settings
from server.models import DraftResult, DraftStatus, WebhookPayload
from server.services.db import Database
from server.services.email_extractor import extract_email
from server.services.gmail_client import GmailClient
from server.services.hitl import display_draft_success_log
from server.services.llm_client import LLMClient
from server.utils.resume import find_latest_resume

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def handle_webhook(
    payload: WebhookPayload,
    llm_client: LLMClient = Depends(get_llm_client),  # noqa: B008
    gmail_client: GmailClient = Depends(get_gmail_client),  # noqa: B008
    db: Database = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, str]:
    """
    Handle incoming LinkedIn post from the browser.
    
    1. Check for duplicates.
    2. Extract email.
    3. Generate draft.
    4. Pass to HITL for review.
    5. Save to database and Gmail.
    """
    # 1. Deduplication Check
    if db.is_duplicate(content_hash=payload.content_hash):
        logger.info("Skipping duplicate post (hash match)")
        return {"status": "skipped", "reason": "duplicate_post"}

    # 2. Email Extraction
    extracted_email = await extract_email(payload.selected_text, llm_client)

    if not extracted_email.email:
        # Just use an empty string, the user will fill it in Gmail.
        extracted_email.email = ""

    # Check if we've already emailed this person.
    if db.is_duplicate(author_email=extracted_email.email):
        logger.info("Skipping duplicate recipient: %s", extracted_email.email)
        return {"status": "skipped", "reason": "duplicate_recipient"}

    # 3. Generate Draft
    try:
        draft = await llm_client.draft_email(payload.selected_text)
    except Exception as e:
        logger.error("Failed to generate draft: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate draft") from e

    # Override the "To" email with the extracted one.
    draft.to_email = extracted_email.email

    # 4. Find Resume
    resume_path = find_latest_resume(settings.resume_dir)
    resume_path_str = str(resume_path) if resume_path else None

    # Construct the result object.
    draft_result = DraftResult(
        draft=draft,
        post_text=payload.selected_text,
        page_url=payload.page_url,
        content_hash=payload.content_hash,
        resume_path=resume_path_str,
        extracted_email=extracted_email,
    )

    # 5. Draft directly to Gmail (Asynchronous workflow)
    logger.info("Drafting to Gmail directly...")
    try:
        # `create_draft` blocks, so run it in a thread if it's slow.
        # To be safe and compliant with Code Quality rules, we use to_thread.
        await asyncio.to_thread(
            gmail_client.create_draft,
            draft_result.draft,
            resume_path,
        )
        db.insert_record(
            page_url=draft_result.page_url,
            author_email=draft_result.draft.to_email,
            subject=draft_result.draft.subject,
            status=DraftStatus.DRAFTED,
            content_hash=draft_result.content_hash,
        )
        
        # Display the success log to the terminal
        display_draft_success_log(draft_result)
        
        return {"status": "approved"}
    except Exception as e:
        logger.error("Failed to create Gmail draft: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create Gmail draft") from e
