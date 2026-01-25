"""Email and Attachment models."""

from datetime import datetime

from pydantic import Field

from arbie.models.base import BaseEntity
from arbie.models.enums import AttachmentStatus, EmailDirection, EmailType


class Email(BaseEntity):
    """Represents an email in the conversation."""

    session_id: str = Field(..., description="FK to Session")
    direction: EmailDirection = Field(...)
    email_type: EmailType = Field(...)
    message_id: str = Field(..., description="Email Message-ID header")
    in_reply_to: str | None = Field(default=None, description="For threading")
    from_address: str = Field(...)
    to_addresses: list[str] = Field(default_factory=list)
    cc_addresses: list[str] = Field(default_factory=list)
    subject: str = Field(...)
    body_text: str | None = Field(default=None)
    body_html: str | None = Field(default=None)
    sent_at: datetime | None = Field(default=None)
    received_at: datetime | None = Field(default=None)
    processed_at: datetime | None = Field(default=None)


class Attachment(BaseEntity):
    """Files attached to emails."""

    email_id: str = Field(..., description="FK to Email")
    filename: str = Field(...)
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(...)
    storage_path: str = Field(..., description="Path in file storage")
    checksum: str = Field(..., description="SHA-256 for integrity")
    status: AttachmentStatus = Field(default=AttachmentStatus.NOT_ANALYZED)
    extracted_text: str | None = Field(default=None)
    extracted_metadata: list[str] = Field(default_factory=list, description="IDs of attachments extracted from this file")
    uploaded_at: datetime = Field(...)
    processed_at: datetime | None = Field(default=None)
