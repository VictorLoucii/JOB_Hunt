"""
JobHunt — Webhook Router

Receives data from the Tampermonkey script and orchestrates the
entire end-to-end extraction, drafting, and HITL review pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from server.config import Settings, get_user_profile
from server.dependencies import get_db, get_gmail_client, get_llm_client, get_settings
from server.models import DraftResult, DraftStatus, WebhookPayload
from server.services.db import Database
from server.services.email_extractor import extract_email
from server.services.gmail_client import GmailClient
from server.services.hitl import display_draft_success_log, display_eligibility_rejection_log
from server.services.llm_client import LLMClient
from server.utils.resume import find_latest_resume

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def handle_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    llm_client: LLMClient = Depends(get_llm_client),  # noqa: B008
    gmail_client: GmailClient = Depends(get_gmail_client),  # noqa: B008
    db: Database = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> JSONResponse:
    """
    Handle incoming LinkedIn post from the browser.

    1. Check for duplicates.
    2. Extract email.
    3. Generate draft.
    4. Pass to HITL for review.
    5. Save to database and Gmail.
    """
    start_time = time.perf_counter()
    # 1. Deduplication Check
    if db.is_duplicate(content_hash=payload.content_hash):
        logger.info("Skipping duplicate post (hash match)")
        return JSONResponse(
            status_code=200, content={"status": "skipped", "reason": "duplicate_post"}
        )

    # 1.5. Eligibility Screening
    user_profile = get_user_profile()
    try:
        eligibility = await llm_client.evaluate_eligibility(
            post_text=payload.selected_text,
            constraints=user_profile.constraints,
        )
    except Exception as e:
        logger.error("Failed to evaluate eligibility: %s", e)
        raise HTTPException(status_code=500, detail="Failed to evaluate eligibility") from e

    if not eligibility.is_eligible:
        display_eligibility_rejection_log(payload.selected_text, eligibility)
        db.insert_record(
            page_url=payload.page_url,
            author_email="",
            subject="[Rejected] Eligibility Screening",
            status=DraftStatus.SKIPPED,
            content_hash=payload.content_hash,
        )
        return JSONResponse(status_code=200, content={"status": "skipped", "reason": "ineligible"})

    # 2. Email Extraction
    extracted_email = await extract_email(payload.selected_text, llm_client)

    if not extracted_email.email:
        # Just use an empty string, the user will fill it in Gmail.
        extracted_email.email = ""

    # Check if we've already emailed this person.
    if db.is_duplicate(author_email=extracted_email.email):
        logger.info("Skipping duplicate recipient: %s", extracted_email.email)
        return JSONResponse(
            status_code=200, content={"status": "skipped", "reason": "duplicate_recipient"}
        )

    # 3. Kick off Draft Generation and Gmail upload in the background
    resume_dir = user_profile.resume_dir or settings.resume_dir
    resume_path = find_latest_resume(resume_dir)
    resume_path_str = str(resume_path) if resume_path else None

    # We add the background task to handle LLM drafting and Gmail API
    background_tasks.add_task(
        process_draft_background,
        post_text=payload.selected_text,
        page_url=payload.page_url,
        content_hash=payload.content_hash,
        extracted_email=extracted_email,
        resume_path_str=resume_path_str,
        resume_path=resume_path,
        llm_client=llm_client,
        gmail_client=gmail_client,
        db=db,
        start_time=start_time,
    )

    # Return immediately so the browser UI isn't blocked
    return JSONResponse(status_code=202, content={"status": "approved"})


async def process_draft_background(
    post_text: str,
    page_url: str,
    content_hash: str,
    extracted_email: Any,
    resume_path_str: str | None,
    resume_path: Any | None,
    llm_client: LLMClient,
    gmail_client: GmailClient,
    db: Database,
    start_time: float,
) -> None:
    """Background task to generate draft and send to Gmail."""
    try:
        draft = await llm_client.draft_email(post_text)
        draft.to_email = extracted_email.email or ""

        draft_result = DraftResult(
            draft=draft,
            post_text=post_text,
            page_url=page_url,
            content_hash=content_hash,
            resume_path=resume_path_str,
            extracted_email=extracted_email,
        )

        logger.info("Drafting to Gmail directly...")
        # `create_draft` blocks, so run it in a thread
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

        elapsed_time = time.perf_counter() - start_time
        logger.info("\033[1;32m⏱️  [TIMER] Completed drafted email in %.2fs\033[0m", elapsed_time)
        display_draft_success_log(draft_result, elapsed_time)

    except Exception as e:
        logger.error("Failed to process background draft: %s", e)
