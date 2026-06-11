"""
JobHunt — Human-in-the-Loop (HITL) Service

Rich terminal UI for reviewing, editing, and approving email drafts.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from server.models import DraftResult, EligibilityResult

logger = logging.getLogger(__name__)
console = Console()


def display_eligibility_rejection_log(post_text: str, result: EligibilityResult) -> None:
    """
    Display a log when a post is rejected during the eligibility screening.
    
    Args:
        post_text: Original LinkedIn post text.
        result: The EligibilityResult containing the reasoning.
    """
    console.print()

    # Show a short preview of the post
    post_preview = post_text
    if len(post_preview) > 100:
        post_preview = post_preview[:100] + "..."

    logger.info("🔍 Analyzing post for eligibility: \"%s\"", post_preview)
    logger.info("❌ Post skipped. Eligibility criteria not met.")
    
    # We use rich to print the reason with the arrow as requested
    console.print(f"       [yellow]↳ Reason:[/yellow] {result.reasoning}")


def display_draft_success_log(result: DraftResult) -> None:
    """
    Display a read-only, non-blocking summary of the successfully drafted email.
    
    Args:
        result: The DraftResult containing the post, draft, and metadata.
    """
    console.print()  # Add some spacing

    # 1. LinkedIn Post Panel
    post_preview = result.post_text
    if len(post_preview) > 200:
        post_preview = post_preview[:200] + "..."

    console.print(
        Panel(
            f"[blue]URL:[/blue] {result.page_url}\n\n[italic]\"{post_preview}\"[/italic]",
            title="📋 LINKEDIN POST",
            border_style="blue",
        )
    )

    # 2. Email Draft Panel
    draft_content = Text()
    
    # Highlight if email is missing
    if not result.draft.to_email:
        draft_content.append("To: ", style="bold red")
        draft_content.append("[Needs Email] (Please add manually in Gmail)\n", style="bold red")
    else:
        draft_content.append("To: ", style="bold green")
        draft_content.append(f"{result.draft.to_email}\n")
        
    draft_content.append("Subject: ", style="bold green")
    draft_content.append(f"{result.draft.subject}\n\n")
    
    # Strip HTML tags for clean terminal viewing
    clean_body = result.draft.body.replace("<b>", "").replace("</b>", "")
    # Only show the first few lines of the body to keep the terminal clean
    body_lines = clean_body.splitlines()
    body_preview = "\n".join(body_lines[:5])
    if len(body_lines) > 5:
        body_preview += "\n\n[dim]...(draft truncated, view full in Gmail)[/dim]"
    
    draft_content.append(body_preview)

    console.print(
        Panel(
            draft_content,
            title="✉️  GMAIL DRAFT CREATED",
            border_style="green",
        )
    )

    # 3. Metadata Note
    resume_text = (
        Path(result.resume_path).name if result.resume_path else "None"
    )
    metadata_content = (
        f"📎 [bold]Attached Resume:[/bold] {resume_text}\n"
        f"✅ [bold]Status:[/bold] Ready for your review in Gmail Drafts."
    )

    console.print(
        Panel(
            metadata_content,
            border_style="dim",
        )
    )
