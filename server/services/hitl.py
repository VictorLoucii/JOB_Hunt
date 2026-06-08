"""
JobHunt — Human-in-the-Loop (HITL) Service

Rich terminal UI for reviewing, editing, and approving email drafts.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from server.models import DraftResult

logger = logging.getLogger(__name__)
console = Console()


def prompt_for_email(page_url: str) -> str:
    """
    Prompt the user to manually enter an email address if extraction failed.
    
    Args:
        page_url: The LinkedIn post URL for context.
        
    Returns:
        The manually entered email address.
    """
    console.print()
    console.print(
        Panel(
            f"[bold yellow]⚠️ No email address could be extracted automatically.[/bold yellow]\n\n"
            f"[dim]Post URL: {page_url}[/dim]\n"
            f"Please check the post in your browser and enter the recipient's email.",
            title="Manual Email Entry Required",
            border_style="yellow",
        )
    )

    email = ""
    while not email:
        email = Prompt.ask("[bold green]Recipient Email[/bold green]").strip()
        if not email:
            console.print("[red]Email cannot be empty. Please try again.[/red]")

    return email


def present_hitl_review(result: DraftResult) -> str:
    """
    Display the drafted email and prompt the user for action.
    
    Args:
        result: The DraftResult containing the post, draft, and metadata.
        
    Returns:
        A string representing the user's choice: 'A', 'E', 'R', or 'S'.
    """
    console.clear()

    # 1. LinkedIn Post Panel
    post_preview = result.post_text
    if len(post_preview) > 300:
        post_preview = post_preview[:300] + "..."

    console.print(
        Panel(
            f"[blue]URL:[/blue] {result.page_url}\n\n[italic]\"{post_preview}\"[/italic]",
            title="📋 LINKEDIN POST",
            border_style="blue",
        )
    )

    # 2. Email Draft Panel
    draft_content = Text()
    draft_content.append("To: ", style="bold green")
    draft_content.append(f"{result.draft.to_email}\n")
    draft_content.append("Subject: ", style="bold green")
    draft_content.append(f"{result.draft.subject}\n\n")
    draft_content.append(result.draft.body)

    console.print(
        Panel(
            draft_content,
            title="✉️  DRAFTED EMAIL",
            border_style="green",
        )
    )

    # 3. Metadata Panel
    resume_text = (
        Path(result.resume_path).name if result.resume_path else "None"
    )
    metadata_content = (
        f"📎 [bold]Resume:[/bold] {resume_text}\n"
        f"📊 [bold]Email source:[/bold] {result.extracted_email.source} "
        f"(confidence: {result.extracted_email.confidence:.1f})"
    )

    console.print(
        Panel(
            metadata_content,
            border_style="dim",
        )
    )

    # 4. Action Prompt
    choices = ["A", "E", "R", "S"]
    choice_text = "[A]pprove  [E]dit  [R]egenerate  [S]kip"

    action = Prompt.ask(
        f"\n{choice_text}",
        choices=[c.lower() for c in choices] + choices,
        show_choices=False,
    ).upper()

    if action == "E":
        _handle_edit(result)

    return action


def _handle_edit(result: DraftResult) -> None:
    """
    Open the draft in the system editor and parse it back upon save.
    Mutates the result in place.
    """
    editor = os.environ.get("EDITOR", "nano")

    # Create the initial content for the editor.
    content = (
        f"To: {result.draft.to_email}\n"
        f"Subject: {result.draft.subject}\n"
        f"---\n"
        f"{result.draft.body}"
    )

    # Write to temp file.
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tf:
        tf.write(content)
        tf.flush()
        tmp_path = tf.name

    try:
        # Open editor.
        subprocess.run([editor, tmp_path], check=True)

        # Read the file back.
        with open(tmp_path, encoding="utf-8") as f:
            edited_content = f.read()

        _parse_edited_content(result, edited_content)
        logger.info("Draft successfully updated from editor.")

    except subprocess.CalledProcessError as e:
        logger.error("Editor process failed: %s", e)
        console.print(f"[red]Failed to open editor: {e}[/red]")
    except Exception as e:
        logger.error("Failed to parse edited draft: %s", e)
        console.print(f"[red]Failed to parse edited draft: {e}[/red]")
        Prompt.ask("Press Enter to continue")
    finally:
        # Cleanup temp file.
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _parse_edited_content(result: DraftResult, content: str) -> None:
    """
    Parse the content returned from the text editor back into the DraftResult.
    Expected format:
    To: <email>
    Subject: <subject>
    ---
    <body>
    """
    lines = content.splitlines()

    to_email = result.draft.to_email
    subject = result.draft.subject
    body_lines = []

    in_body = False

    for line in lines:
        if in_body:
            body_lines.append(line)
        elif line.startswith("To:"):
            to_email = line[3:].strip()
        elif line.startswith("Subject:"):
            subject = line[8:].strip()
        elif line.startswith("---"):
            in_body = True

    result.draft.to_email = to_email
    result.draft.subject = subject
    result.draft.body = "\n".join(body_lines).strip()
