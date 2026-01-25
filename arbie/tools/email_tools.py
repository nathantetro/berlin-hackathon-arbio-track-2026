"""Email communication tools for Arbie agent.

Provides tools to send and fetch emails through Resend API
and retrieve email history from the database.
"""

import os
from typing import Literal

from agents import function_tool

from arbie.models.base import generate_id, utc_now
from arbie.models.email import Email
from arbie.models.enums import EmailDirection, EmailType
from arbie.services.db.base import insert, query
from arbie.services.db.email import get_emails_by_session
from arbie.services.db.session import get_session
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


@function_tool(strict_mode=False)
def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    attachments: list[str] | None = None,
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
        reply_to_message_id: Optional message ID to reply to. If not provided,
            automatically threads to the most recent inbound email in the session.

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

    print(f"[send_email] Starting send_email tool")
    print(f"[send_email] to={to}, subject={subject[:50]}..., attachments={attachments}, reply_to_message_id={reply_to_message_id}")
    print(f"[send_email] body length={len(body)}")

    session_id = get_session_context()
    print(f"[send_email] Session context: {session_id}")
    if not session_id:
        print("[send_email] ERROR: No session context available")
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

    # Auto-thread to most recent inbound email if not explicitly specified
    parent_email = None
    print(f"[send_email] Auto-threading: reply_to_message_id={reply_to_message_id}")
    if not reply_to_message_id:
        print(f"[send_email] No reply_to_message_id provided, looking up inbound emails for session")
        emails = get_emails_by_session(session_id)
        print(f"[send_email] Found {len(emails)} emails in session")
        # Filter to inbound only and sort by timestamp (newest first)
        inbound = [e for e in emails if e.get("direction") == "inbound"]
        print(f"[send_email] Found {len(inbound)} inbound emails")
        if inbound:
            inbound.sort(
                key=lambda e: e.get("received_at") or e.get("created_at") or "",
                reverse=True
            )
            parent_email = inbound[0]
            reply_to_message_id = parent_email.get("message_id")
            print(f"[send_email] Auto-selected parent email: message_id={reply_to_message_id}")

    # Look up threading information if we don't already have the parent email
    if reply_to_message_id and not parent_email:
        print(f"[send_email] Looking up parent email by message_id={reply_to_message_id}")
        emails = query("emails", pl.col("message_id") == reply_to_message_id)
        if emails:
            parent_email = emails[0]
            print(f"[send_email] Found parent email")
        else:
            print(f"[send_email] Parent email not found in database")

    # Build threading headers
    in_reply_to = None
    references = []
    if parent_email:
        in_reply_to = parent_email.get("message_id")
        # Build references chain: include parent's references plus parent's message_id
        if parent_email.get("in_reply_to"):
            references.append(parent_email["in_reply_to"])
        references.append(parent_email["message_id"])
    print(f"[send_email] Threading: in_reply_to={in_reply_to}, references={references}")

    # Get session reference code for footer
    session_data = get_session(session_id)
    session_reference = session_data.get("reference_code") if session_data else None
    print(f"[send_email] Session reference code: {session_reference}")

    # Load attachments if provided
    email_attachments = []
    if attachments:
        print(f"[send_email] Loading {len(attachments)} attachments")
        from arbie.services.storage import get_storage_service

        storage = get_storage_service()
        att_list = attachments if isinstance(attachments, list) else [attachments]
        for att_path in att_list:
            try:
                print(f"[send_email] Loading attachment: {att_path}")
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
                print(f"[send_email] Attachment loaded: filename={filename}, content_type={content_type}, size={len(content)} bytes")

                email_attachments.append(
                    EmailAttachment(
                        filename=filename,
                        content=content,
                        content_type=content_type,
                    )
                )
            except Exception as e:
                print(f"[send_email] ERROR: Failed to load attachment {att_path}: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to load attachment {att_path}: {e}",
                }
    else:
        print("[send_email] No attachments to load")

    # Send the email
    try:
        print(f"[send_email] Getting Resend client")
        client = get_resend_client()
        print(f"[send_email] Sending email via Resend API")
        print(f"[send_email] Recipients: {recipients}")
        print(f"[send_email] Subject: {subject}")
        print(f"[send_email] Body type: {'HTML' if body_html else 'plain text'}")
        print(f"[send_email] Attachments count: {len(email_attachments)}")
        result = client.send_email_with_retry(
            to=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=email_attachments if email_attachments else None,
            in_reply_to=in_reply_to,
            references=references if references else None,
            session_reference=session_reference,
        )
        print(f"[send_email] Resend API response: message_id={result.message_id}, status={result.status}")

        # Store the outbound email in the database
        print(f"[send_email] Storing outbound email in database")
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
        print(f"[send_email] Email stored in database successfully")

        print(f"[send_email] SUCCESS: Email sent successfully")
        return {
            "message_id": result.message_id,
            "status": result.status,
            "recipients": result.recipients,
            "timestamp": result.timestamp.isoformat(),
        }

    except Exception as e:
        import traceback
        print(f"[send_email] ERROR: Failed to send email: {e}")
        print(f"[send_email] Traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "message": f"Failed to send email: {e}",
        }


@function_tool
def fetch_emails(
    direction: Literal["inbound", "outbound", "all"] = "all",
    limit: int = 50,
) -> list[dict]:
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
        - attachments: List of attachment dicts with:
          - filename: Name of the attached file
          - content_type: MIME type (e.g., "application/pdf", "image/jpeg")
          - size_bytes: File size in bytes
          - storage_path: Path to file in storage (for use with read_file)
        - timestamp: When the email was sent/received
        - in_reply_to: Message ID this email is replying to

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

        # Get attachments for this email
        from arbie.services.db.email import get_attachments_by_email
        email_attachments = get_attachments_by_email(email.get("id", ""))
        attachments_info = [
            {
                "filename": att.get("filename"),
                "content_type": att.get("content_type"),
                "size_bytes": att.get("size_bytes"),
                "storage_path": att.get("storage_path"),
            }
            for att in email_attachments
        ]

        result.append(
            {
                "message_id": email.get("message_id"),
                "direction": email.get("direction"),
                "from_email": email.get("from_address"),
                "to_emails": email.get("to_addresses", []),
                "subject": email.get("subject"),
                "body": body[:2000] if len(body) > 2000 else body,  # Truncate long bodies
                "attachments": attachments_info,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "in_reply_to": email.get("in_reply_to"),
            }
        )

    return result
