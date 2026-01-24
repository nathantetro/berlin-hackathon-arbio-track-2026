"""Email communication tools for Arbie agent.

Provides tools to send and fetch emails through Resend API
and retrieve email history from the database.
"""

import os
from typing import Any, Literal

from agents import function_tool

from arbie.models.base import generate_id, utc_now
from arbie.models.email import Email
from arbie.models.enums import EmailDirection, EmailType
from arbie.services.db.base import insert, query
from arbie.services.db.email import get_emails_by_session
from arbie.services.resend_client import (
    EmailAttachment,
    get_resend_client,
)


# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for email tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


@function_tool
def send_email(
    to: Any,
    subject: str,
    body: str,
    attachments: Any = None,
    reply_to_message_id: str | None = None,
) -> dict:
    """
    Send an email to the property owner or other recipients.

    Use this to:
    - Request missing information from property owners
    - Send status updates
    - Ask clarifying questions
    - Provide onboarding instructions
    - Share generated documents

    The email is sent via Resend API with Arbio branding.

    Args:
        to: Recipient email address(es). Single string or list of strings.
        subject: Email subject line
        body: Email body (plain text or HTML)
        attachments: Optional list of file paths to attach (from /workspace/ or /outputs/)
        reply_to_message_id: Optional message ID to reply to (maintains thread)

    Returns:
        SendEmailResult dict with:
        - message_id: Unique message ID for tracking
        - status: "sent" or "queued"
        - recipients: List of recipients
        - timestamp: When the email was sent

    Example:
        send_email(
            to="owner@example.com",
            subject="Missing Information for Your Property",
            body="Hi! We need a few more details to complete your listing...",
            reply_to_message_id="previous-msg-123"
        )
    """
    import polars as pl

    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available. Cannot send email.",
        }

    # Normalize recipients
    recipients = [to] if isinstance(to, str) else list(to)

    # Determine if HTML or plain text
    is_html = "<" in body and ">" in body
    body_text = None if is_html else body
    body_html = body if is_html else None

    # Look up threading information if reply_to_message_id provided
    in_reply_to = None
    references = []

    if reply_to_message_id:
        # Find the email to get threading headers
        emails = query("emails", pl.col("message_id") == reply_to_message_id)
        if emails:
            in_reply_to = emails[0].get("message_id")
            # Build references chain
            if emails[0].get("in_reply_to"):
                references.append(emails[0]["in_reply_to"])
            references.append(reply_to_message_id)

    # Load attachments if provided
    email_attachments = []
    if attachments:
        from arbie.services.storage import get_storage_service

        storage = get_storage_service()
        att_list = attachments if isinstance(attachments, list) else [attachments]
        for att_path in att_list:
            try:
                # Read file from Azure Blob storage
                content = storage.read(att_path, session_id)
                filename = att_path.split("/")[-1]

                # Determine content type from extension
                ext = filename.lower().split(".")[-1] if "." in filename else ""
                content_types = {
                    "pdf": "application/pdf",
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "doc": "application/msword",
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "txt": "text/plain",
                }
                content_type = content_types.get(ext, "application/octet-stream")

                email_attachments.append(
                    EmailAttachment(
                        filename=filename,
                        content=content,
                        content_type=content_type,
                    )
                )
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed to load attachment {att_path}: {e}",
                }

    # Send the email
    try:
        client = get_resend_client()
        result = client.send_email_with_retry(
            to=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=email_attachments if email_attachments else None,
            in_reply_to=in_reply_to,
            references=references if references else None,
        )

        # Store the outbound email in the database
        now = utc_now()
        email = Email(
            session_id=session_id,
            direction=EmailDirection.OUTBOUND,
            email_type=EmailType.FOLLOW_UP,  # Most outbound are follow-ups
            message_id=result.message_id or generate_id(),
            in_reply_to=in_reply_to,
            from_address="onboard@arbie.work",
            to_addresses=recipients,
            cc_addresses=[],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            sent_at=result.timestamp,
            created_at=now,
            updated_at=now,
        )
        insert("emails", email.model_dump())

        return {
            "message_id": result.message_id,
            "status": result.status,
            "recipients": result.recipients,
            "timestamp": result.timestamp.isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to send email: {e}",
        }


@function_tool
def fetch_emails(
    direction: Literal["inbound", "outbound", "all"] = "all",
    limit: int = 50,
) -> Any:
    """
    Fetch email history for the current session.

    Retrieve emails related to this property onboarding session to:
    - Review past communication
    - Find information in previous messages
    - Check what questions have already been asked
    - Maintain context across interactions

    Args:
        direction: Filter by direction:
                   - "inbound": Only emails from property owner
                   - "outbound": Only emails sent by Arbie
                   - "all": Both directions (default)
        limit: Maximum number of emails to return (default: 50, max: 200)

    Returns:
        List of Email dicts, each with:
        - message_id: Unique message ID
        - direction: "inbound" or "outbound"
        - from_email: Sender email address
        - to_emails: List of recipient addresses
        - subject: Email subject
        - body: Email body content
        - attachments: List of attachment filenames
        - timestamp: When the email was sent/received
        - thread_id: Conversation thread ID

    Emails are returned in reverse chronological order (newest first).
    """
    session_id = get_session_context()
    if not session_id:
        return [
            {
                "status": "error",
                "message": "No session context available. Cannot fetch emails.",
            }
        ]

    # Clamp limit
    limit = min(max(1, limit), 200)

    # Get emails from database
    emails = get_emails_by_session(session_id)

    # Filter by direction if specified
    if direction != "all":
        dir_value = "inbound" if direction == "inbound" else "outbound"
        emails = [e for e in emails if e.get("direction") == dir_value]

    # Sort by timestamp (newest first)
    emails.sort(
        key=lambda e: e.get("received_at") or e.get("sent_at") or e.get("created_at"),
        reverse=True,
    )

    # Apply limit
    emails = emails[:limit]

    # Format for return
    result = []
    for email in emails:
        # Determine body content
        body = email.get("body_text") or email.get("body_html") or ""

        # Determine timestamp
        timestamp = (
            email.get("received_at")
            or email.get("sent_at")
            or email.get("created_at")
        )

        result.append(
            {
                "message_id": email.get("message_id"),
                "direction": email.get("direction"),
                "from_email": email.get("from_address"),
                "to_emails": email.get("to_addresses", []),
                "subject": email.get("subject"),
                "body": body[:2000] if len(body) > 2000 else body,  # Truncate long bodies
                "timestamp": timestamp.isoformat() if timestamp else None,
                "in_reply_to": email.get("in_reply_to"),
            }
        )

    return result
