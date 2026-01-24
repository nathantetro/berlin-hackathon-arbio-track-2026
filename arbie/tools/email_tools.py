"""Email communication tools for Arbie agent.

Provides tools to send and fetch emails through the MailerSend API.
"""

from typing import Any, Literal
from agents import function_tool


@function_tool
def send_email(
    to: Any,
    subject: str,
    body: str,
    attachments: Any = None,
    reply_to_message_id: str | None = None
) -> dict:
    """
    Send an email to the property owner or other recipients.

    Use this to:
    - Request missing information from property owners
    - Send status updates
    - Ask clarifying questions
    - Provide onboarding instructions
    - Share generated documents

    The email is sent via MailerSend API with Arbio branding.

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
    return {
        "status": "not_implemented",
        "message": f"send_email not implemented yet. Would send to: {to}",
        "params": {
            "subject": subject,
            "attachments": attachments,
            "reply_to_message_id": reply_to_message_id
        }
    }


@function_tool
def fetch_emails(
    direction: Literal["inbound", "outbound", "all"] = "all",
    limit: int = 50
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
    return [
        {
            "status": "not_implemented",
            "message": f"fetch_emails not implemented yet. Would fetch {direction} emails (limit={limit})"
        }
    ]
