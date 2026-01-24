"""Email and attachment database operations."""

import polars as pl

from arbie.services.db.base import query

EMAILS_TABLE = "emails"
ATTACHMENTS_TABLE = "attachments"


# === Email Operations ===


def get_emails_by_session(session_id: str) -> list[dict]:
    """Get all emails for a session."""
    return query(EMAILS_TABLE, pl.col("session_id") == session_id)


# === Attachment Operations ===


def get_attachments_by_email(email_id: str) -> list[dict]:
    """Get all attachments for an email."""
    return query(ATTACHMENTS_TABLE, pl.col("email_id") == email_id)
