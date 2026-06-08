"""
JobHunt — SQLite Database Service

Local SQLite database to prevent duplicate outreach and provide an audit trail.
Zero cost, zero setup — just a file.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from server.config import PROJECT_ROOT
from server.models import DBRecord, DraftStatus

logger = logging.getLogger(__name__)

# Default database path.
_DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "jobhunt.db"

# Table creation SQL.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS drafts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url    TEXT NOT NULL,
    author_email TEXT NOT NULL,
    subject     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'drafted',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_page_url ON drafts(page_url);",
    "CREATE INDEX IF NOT EXISTS idx_author_email ON drafts(author_email);",
]


class Database:
    """SQLite database for dedup and tracking of email drafts."""

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite file. Defaults to data/jobhunt.db.

        Creates the database file and tables if they don't exist.
        """
        self._db_path = db_path or _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,  # FastAPI is multi-threaded.
        )
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        logger.info("Database initialized at %s", self._db_path)

    def _init_tables(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._conn:
            self._conn.execute(_CREATE_TABLE_SQL)
            for index_sql in _CREATE_INDEXES_SQL:
                self._conn.execute(index_sql)

    def is_duplicate(
        self, page_url: str | None = None, author_email: str | None = None
    ) -> bool:
        """
        Check if we've already processed this post or emailed this person.

        Returns True if either:
          - A record with this page_url exists (any status)
          - A record with this author_email exists with status 'approved'

        Args:
            page_url: The LinkedIn post URL to check.
            author_email: The recipient email to check.

        Returns:
            True if this is a duplicate, False otherwise.
        """
        # Check 1: Same post URL (any status — even "skipped" means we saw it).
        if page_url:
            cursor = self._conn.execute(
                "SELECT 1 FROM drafts WHERE page_url = ? LIMIT 1",
                (page_url,),
            )
            if cursor.fetchone():
                logger.info("Duplicate detected — same post URL: %s", page_url)
                return True

        # Check 2: Same email, but only if we already approved/sent to them.
        if author_email:
            cursor = self._conn.execute(
                "SELECT 1 FROM drafts WHERE author_email = ? AND status = 'approved' LIMIT 1",
                (author_email,),
            )
            if cursor.fetchone():
                logger.info("Duplicate detected — already emailed: %s", author_email)
                return True

        return False

    def insert_record(
        self,
        page_url: str,
        author_email: str,
        subject: str,
        status: DraftStatus,
    ) -> int:
        """
        Insert a new tracking record.

        Args:
            page_url: The LinkedIn post URL.
            author_email: The recipient email address.
            subject: The email subject line.
            status: The initial status of the draft.

        Returns:
            The row ID of the inserted record.
        """
        now = datetime.now(UTC).isoformat()
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO drafts (page_url, author_email, subject, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (page_url, author_email, subject, status.value, now),
            )
            row_id = cursor.lastrowid
            logger.info(
                "Inserted record #%d — %s → %s [%s]",
                row_id,
                author_email,
                subject,
                status.value,
            )
            return row_id  # type: ignore[return-value]

    def update_status(self, record_id: int, status: DraftStatus) -> None:
        """
        Update the status of an existing record.

        Args:
            record_id: The row ID to update.
            status: The new status.
        """
        now = datetime.now(UTC).isoformat()
        with self._conn:
            self._conn.execute(
                "UPDATE drafts SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, record_id),
            )
            logger.info("Updated record #%d → status=%s", record_id, status.value)

    def get_history(self, limit: int = 50) -> list[DBRecord]:
        """
        Return the most recent records, newest first.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of DBRecord objects.
        """
        cursor = self._conn.execute(
            "SELECT id, page_url, author_email, subject, status, created_at, updated_at "
            "FROM drafts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        records = []
        for row in rows:
            records.append(
                DBRecord(
                    id=row["id"],
                    page_url=row["page_url"],
                    author_email=row["author_email"],
                    subject=row["subject"],
                    status=DraftStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=(
                        datetime.fromisoformat(row["updated_at"])
                        if row["updated_at"]
                        else None
                    ),
                )
            )
        return records

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("Database connection closed")
