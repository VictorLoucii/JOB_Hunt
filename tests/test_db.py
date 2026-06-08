"""
Tests for server.services.db — SQLite operations.

Uses a temporary in-memory database for each test to ensure isolation.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from server.models import DraftStatus
from server.services.db import Database


@pytest.fixture
def db() -> Database:
    """Create a fresh in-memory database for each test."""
    return Database(db_path=Path(":memory:"))


@pytest.fixture
def db_on_disk() -> Database:
    """Create a database on disk for file-creation tests."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path=db_path)
        yield db  # type: ignore[misc]
        db.close()


# ──────────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────────


class TestDatabaseInit:
    """Tests for database initialization."""

    def test_creates_tables(self, db: Database) -> None:
        """Tables and indexes should be created on init."""
        cursor = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drafts'"
        )
        assert cursor.fetchone() is not None

    def test_creates_file_on_disk(self) -> None:
        """Database file should be created at the specified path."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            db = Database(db_path=db_path)
            assert db_path.exists()
            db.close()


# ──────────────────────────────────────────────
# Insert & Retrieve
# ──────────────────────────────────────────────


class TestInsertAndRetrieve:
    """Tests for inserting and retrieving records."""

    def test_insert_returns_row_id(self, db: Database) -> None:
        """Insert should return the new row's ID."""
        row_id = db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="test@acme.com",
            subject="ML Internship",
            status=DraftStatus.DRAFTED,
        )
        assert row_id == 1

    def test_insert_increments_id(self, db: Database) -> None:
        """Successive inserts should increment the row ID."""
        id1 = db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="a@a.com",
            subject="Test 1",
            status=DraftStatus.DRAFTED,
        )
        id2 = db.insert_record(
            page_url="https://www.linkedin.com/posts/2",
            author_email="b@b.com",
            subject="Test 2",
            status=DraftStatus.DRAFTED,
        )
        assert id2 == id1 + 1

    def test_get_history_returns_records(self, db: Database) -> None:
        """get_history should return inserted records."""
        db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="test@co.com",
            subject="Test Subject",
            status=DraftStatus.APPROVED,
        )
        history = db.get_history()
        assert len(history) == 1
        assert history[0].author_email == "test@co.com"
        assert history[0].status == DraftStatus.APPROVED

    def test_get_history_respects_limit(self, db: Database) -> None:
        """get_history should respect the limit parameter."""
        for i in range(10):
            db.insert_record(
                page_url=f"https://www.linkedin.com/posts/{i}",
                author_email=f"user{i}@co.com",
                subject=f"Test {i}",
                status=DraftStatus.DRAFTED,
            )
        history = db.get_history(limit=3)
        assert len(history) == 3

    def test_get_history_newest_first(self, db: Database) -> None:
        """get_history should return newest records first."""
        db.insert_record(
            page_url="https://www.linkedin.com/posts/old",
            author_email="old@co.com",
            subject="Old",
            status=DraftStatus.DRAFTED,
        )
        db.insert_record(
            page_url="https://www.linkedin.com/posts/new",
            author_email="new@co.com",
            subject="New",
            status=DraftStatus.DRAFTED,
        )
        history = db.get_history()
        assert history[0].subject == "New"


# ──────────────────────────────────────────────
# Dedup Logic
# ──────────────────────────────────────────────


class TestDedup:
    """Tests for deduplication logic."""

    def test_no_records_is_not_duplicate(self, db: Database) -> None:
        """Empty database should never flag duplicates."""
        assert db.is_duplicate(page_url="https://www.linkedin.com/posts/1") is False
        assert db.is_duplicate(author_email="test@co.com") is False

    def test_same_page_url_is_duplicate(self, db: Database) -> None:
        """Same page_url (any status) should be flagged as duplicate."""
        url = "https://www.linkedin.com/posts/123"
        db.insert_record(
            page_url=url,
            author_email="test@co.com",
            subject="Test",
            status=DraftStatus.SKIPPED,  # Even skipped counts.
        )
        assert db.is_duplicate(page_url=url) is True

    def test_different_page_url_is_not_duplicate(self, db: Database) -> None:
        """Different page_url should not be flagged."""
        db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="test@co.com",
            subject="Test",
            status=DraftStatus.DRAFTED,
        )
        assert db.is_duplicate(page_url="https://www.linkedin.com/posts/2") is False

    def test_approved_email_is_duplicate(self, db: Database) -> None:
        """Same email with 'approved' status should be flagged as duplicate."""
        db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="hire@co.com",
            subject="Test",
            status=DraftStatus.APPROVED,
        )
        assert db.is_duplicate(author_email="hire@co.com") is True

    def test_drafted_email_is_not_duplicate(self, db: Database) -> None:
        """Same email with 'drafted' status should NOT be flagged."""
        db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="hire@co.com",
            subject="Test",
            status=DraftStatus.DRAFTED,
        )
        assert db.is_duplicate(author_email="hire@co.com") is False

    def test_skipped_email_is_not_duplicate(self, db: Database) -> None:
        """Same email with 'skipped' status should NOT be flagged."""
        db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="hire@co.com",
            subject="Test",
            status=DraftStatus.SKIPPED,
        )
        assert db.is_duplicate(author_email="hire@co.com") is False

    def test_both_none_is_not_duplicate(self, db: Database) -> None:
        """No arguments should return False."""
        assert db.is_duplicate() is False


# ──────────────────────────────────────────────
# Status Update
# ──────────────────────────────────────────────


class TestUpdateStatus:
    """Tests for status update functionality."""

    def test_update_status(self, db: Database) -> None:
        """Updating status should be reflected in history."""
        row_id = db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="test@co.com",
            subject="Test",
            status=DraftStatus.DRAFTED,
        )
        db.update_status(row_id, DraftStatus.APPROVED)
        history = db.get_history()
        assert history[0].status == DraftStatus.APPROVED
        assert history[0].updated_at is not None

    def test_update_changes_dedup_behavior(self, db: Database) -> None:
        """Updating from 'drafted' to 'approved' should change dedup result."""
        row_id = db.insert_record(
            page_url="https://www.linkedin.com/posts/1",
            author_email="hire@co.com",
            subject="Test",
            status=DraftStatus.DRAFTED,
        )
        # Not a duplicate yet (drafted, not approved).
        assert db.is_duplicate(author_email="hire@co.com") is False
        # After approval, it becomes a duplicate.
        db.update_status(row_id, DraftStatus.APPROVED)
        assert db.is_duplicate(author_email="hire@co.com") is True
