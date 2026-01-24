"""Email and attachment database operations."""

import polars as pl

from arbie.services.db.base import query

EMAILS_TABLE = "emails"
ATTACHMENTS_TABLE = "attachments"


# === Email Operations ===


def get_emails_by_session(session_id: str) -> list[dict]:
    """Get all emails for a session."""
    return query(EMAILS_TABLE, pl.col("session_id") == session_id)


def get_emails_by_session_chronological(session_id: str) -> list[dict]:
    """Get all emails for a session, sorted chronologically (oldest first).

    Uses received_at for inbound emails and sent_at for outbound emails,
    falling back to created_at if neither is available.
    """
    emails = query(EMAILS_TABLE, pl.col("session_id") == session_id)

    def get_timestamp(email: dict) -> str:
        """Get the best timestamp for sorting."""
        return (
            email.get("received_at")
            or email.get("sent_at")
            or email.get("created_at")
            or ""
        )

    return sorted(emails, key=get_timestamp)


# === Attachment Operations ===


def get_attachments_by_email(email_id: str) -> list[dict]:
    """Get all attachments for an email."""
    return query(ATTACHMENTS_TABLE, pl.col("email_id") == email_id)
