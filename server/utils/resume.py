"""
JobHunt — Resume File Discovery & Validation

Finds the most recently modified PDF in the configured resume directory.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_latest_resume(resume_dir: Path) -> Path | None:
    """
    Find the most recently modified PDF in the resume directory.

    Args:
        resume_dir: Directory to search for PDF files.

    Returns:
        Path to the newest PDF, or None if no PDFs found.
    """
    if not resume_dir.exists():
        logger.warning("Resume directory does not exist: %s", resume_dir)
        return None
        
    try:
        all_files = list(resume_dir.iterdir())
        logger.info("Debug: All files in %s: %s", resume_dir, all_files)
    except Exception as e:
        logger.error("Debug: Failed to list directory %s: %s", resume_dir, e)

    pdfs = sorted(
        [p for p in resume_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not pdfs:
        logger.warning("No PDF files found in: %s", resume_dir)
        return None

    logger.info("Found resume: %s", pdfs[0].name)
    return pdfs[0]
