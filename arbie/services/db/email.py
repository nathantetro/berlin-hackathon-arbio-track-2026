"""Email and attachment database operations."""

import hashlib

import polars as pl

from arbie.models.base import utc_now
from arbie.models.email import Attachment
from arbie.models.enums import AttachmentStatus
from arbie.services.db.base import insert, query

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


def get_attachments_by_session(session_id: str) -> list[dict]:
    """Get all attachments for a session.

    Finds all emails for the session, then retrieves all attachments
    for those emails.

    Args:
        session_id: Session ID to get attachments for.

    Returns:
        List of attachment dicts with storage_path for each.
    """
    # Get all emails for this session
    emails = get_emails_by_session(session_id)
    if not emails:
        return []

    # Get all attachments for each email
    attachments = []
    for email in emails:
        email_attachments = get_attachments_by_email(email["id"])
        attachments.extend(email_attachments)

    return attachments


def update_attachment_after_extraction(
    storage_path: str,
    extracted_text: str,
    extracted_metadata: list[str] | None = None,
) -> bool:
    """Update attachment fields after extraction processing.

    Args:
        storage_path: Virtual path of the attachment (e.g., /attachments/doc.pdf).
        extracted_text: The extracted text content to store.
        extracted_metadata: List of attachment IDs extracted from this file (e.g., images from PDF).

    Returns:
        True if attachment was found and updated, False otherwise.
    """
    attachments = query(ATTACHMENTS_TABLE, pl.col("storage_path") == storage_path)
    if not attachments:
        return False

    attachment = attachments[0]
    attachment["extracted_text"] = extracted_text
    if extracted_metadata is not None:
        attachment["extracted_metadata"] = extracted_metadata
    attachment["status"] = AttachmentStatus.PROCESSED.value
    attachment["processed_at"] = utc_now()
    attachment["updated_at"] = utc_now()
    insert(ATTACHMENTS_TABLE, attachment)
    return True


def update_attachment_room_name(storage_path: str, room_name: str) -> bool:
    """Update attachment with its classified room name.

    Args:
        storage_path: Virtual path of the attachment (e.g., /attachements/photo.png).
        room_name: Room identifier from classification (e.g., "bedroom1").

    Returns:
        True if attachment was found and updated, False otherwise.
    """
    attachments = query(ATTACHMENTS_TABLE, pl.col("storage_path") == storage_path)
    if not attachments:
        return False

    attachment = attachments[0]
    attachment["room_name"] = room_name
    attachment["updated_at"] = utc_now()
    insert(ATTACHMENTS_TABLE, attachment)
    return True
