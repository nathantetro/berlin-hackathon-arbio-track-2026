"""Resend client for sending outbound emails.

Handles email sending via Resend API with Arbio branding.
"""

import html
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import resend


# Sender configuration
FROM_EMAIL = "onboard@arbie.work"
FROM_NAME = "Arbie - Arbio Onboarding"
REPLY_TO_EMAIL = "onboard@arbie.work"

# Gateway URL for session viewer links
GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", "https://arbie-gateway.apps.tower.dev")


def build_session_footer(reference_code: str) -> tuple[str, str]:
    """Build the session link footer for emails.

    Args:
        reference_code: The session reference code (e.g., ARB-2024-X7K9)

    Returns:
        Tuple of (plain_text_footer, html_footer)
    """
    session_url = f"{GATEWAY_BASE_URL}/session/{reference_code}"

    text_footer = f"""
---
View your session: {session_url}
Reference: {reference_code}
Arbie is an AI and can make mistakes.
"""

    # HTML-escape the URL to prevent issues with email client link wrapping
    escaped_url = html.escape(session_url)
    escaped_code = html.escape(reference_code)

    html_footer = f"""
<hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
<p style="font-size: 12px; color: #6b7280; margin: 0; font-family: sans-serif;">
    <a href="{escaped_url}" style="color: #6b7280; text-decoration: underline;">View this session on our website</a>
    &nbsp;·&nbsp;
    Reference: <code style="background: #f3f4f6; padding: 2px 6px; border-radius: 4px; color: #6b7280; font-size: 12px;">{escaped_code}</code>
    &nbsp;·&nbsp;
    <span style="color: #6b7280;">Need support? Pay $800 extra</span>
</p>
<p style="font-size: 12px; color: #6b7280; margin: 8px 0 0 0; font-family: sans-serif;">
    Arbie is an AI and can make mistakes.
</p>
"""

    return text_footer, html_footer


@dataclass
class SendResult:
    """Result of sending an email."""

    message_id: str
    status: str
    recipients: list[str]
    timestamp: datetime


@dataclass
class EmailAttachment:
    """Attachment for outbound email."""

    filename: str
    content: bytes
    content_type: str


class ResendClient:
    """Client for sending emails via Resend API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("RESEND_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Missing Resend API key. Set RESEND_API_KEY environment variable."
            )

        resend.api_key = self.api_key

    def send_email(
        self,
        to: str | list[str],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[EmailAttachment] | None = None,
        reply_to_message_id: str | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        session_reference: str | None = None,
    ) -> SendResult:
        """Send an email via Resend.

        Args:
            to: Recipient email address(es).
            subject: Email subject line.
            body_text: Plain text body (optional if body_html provided).
            body_html: HTML body (optional if body_text provided).
            attachments: Optional list of attachments.
            reply_to_message_id: Internal message ID for tracking replies.
            in_reply_to: Email Message-ID header for threading.
            references: List of Message-IDs for threading.
            session_reference: Optional session reference code to include in footer.

        Returns:
            SendResult with message ID and status.
        """
        # Normalize recipients
        recipients = [to] if isinstance(to, str) else to

        # Add session footer if reference provided
        if session_reference:
            text_footer, html_footer = build_session_footer(session_reference)
            if body_text:
                body_text = body_text + text_footer
            if body_html:
                body_html = body_html + html_footer
            # If only text provided, also create an HTML version with footer
            if body_text and not body_html:
                # Wrap plain text in simple HTML and add footer
                body_html = f"<pre style='font-family: sans-serif; white-space: pre-wrap;'>{body_text.replace(text_footer, '')}</pre>{html_footer}"

        # Build email payload
        payload: dict = {
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": recipients,
            "subject": subject,
            "reply_to": REPLY_TO_EMAIL,
        }

        # Set body
        if body_text:
            payload["text"] = body_text
        if body_html:
            payload["html"] = body_html

        # Generate a custom Message-ID before sending so we can set it on the email
        # and store the same value in our database for threading consistency
        custom_message_id = f"<{uuid.uuid4()}@arbie.work>"

        # Set threading headers including our custom Message-ID
        headers = {"Message-ID": custom_message_id}
        if in_reply_to:
            headers["In-Reply-To"] = in_reply_to
        if references:
            headers["References"] = " ".join(references)
        payload["headers"] = headers

        # Add attachments
        if attachments:
            payload["attachments"] = [
                {
                    "filename": att.filename,
                    "content": list(att.content),  # Resend expects list of bytes
                    "content_type": att.content_type,
                }
                for att in attachments
            ]

        # Send email
        response = resend.Emails.send(payload)

        # Use our custom Message-ID (which is set on the actual email header)
        # This ensures replies from recipients will have In-Reply-To matching our stored value
        message_id = custom_message_id

        return SendResult(
            message_id=message_id,
            status="sent",
            recipients=recipients,
            timestamp=datetime.now(timezone.utc),
        )

    def send_email_with_retry(
        self,
        to: str | list[str],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[EmailAttachment] | None = None,
        reply_to_message_id: str | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        max_retries: int = 1,
        session_reference: str | None = None,
    ) -> SendResult:
        """Send an email with retry on failure.

        Same parameters as send_email, plus max_retries.

        On final failure, sends a burnout notification email.
        """
        import time

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return self.send_email(
                    to=to,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                    attachments=attachments,
                    reply_to_message_id=reply_to_message_id,
                    in_reply_to=in_reply_to,
                    references=references,
                    session_reference=session_reference,
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2**attempt)  # Exponential backoff

        # All retries failed - send burnout notification
        self._send_burnout_notification(
            to, subject, last_error,
            in_reply_to=in_reply_to,
            references=references
        )
        raise last_error

    def _send_burnout_notification(
        self,
        original_to: str | list[str],
        original_subject: str,
        error: Exception | None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> None:
        """Send notification that Arbie couldn't complete the task."""
        recipients = [original_to] if isinstance(original_to, str) else original_to

        # Keep "Re:" prefix to maintain thread in email clients that use subject-based threading
        burnout_subject = f"Re: {original_subject}" if not original_subject.lower().startswith("re:") else original_subject
        burnout_body = f"""Hi there,

Well, this is awkward... Arbie just experienced a technical burnout while working on your request.

Fun Fact: Did you know that burnout isn't just feeling tired? It's actually recognized by the World Health Organization as an "occupational phenomenon" that can lead to exhaustion, mental distance from one's job, and reduced effectiveness. Even AI assistants need to respect their limits!

Your submission is completely safe and sound - we're just giving our systems a quick coffee break.

While you wait, here's an interesting read about burnout awareness and prevention:
https://peertac.org/2024/12/03/understanding-burnout-awareness-consequences-and-prevention/

We'll be back up and running faster than you can say "work-life balance"!

Thanks for your patience (and for being cool about this),
The Arbio Team

P.S. - Arbie promises to come back stronger.
"""

        try:
            payload = {
                "from": f"{FROM_NAME} <{FROM_EMAIL}>",
                "to": recipients,
                "subject": burnout_subject,
                "text": burnout_body,
            }

            # Generate a custom Message-ID for threading consistency
            custom_message_id = f"<{uuid.uuid4()}@arbie.work>"

            # Add threading headers - always include Message-ID for proper threading
            headers = {"Message-ID": custom_message_id}
            if in_reply_to:
                headers["In-Reply-To"] = in_reply_to
            if references:
                headers["References"] = " ".join(references)
            payload["headers"] = headers

            resend.Emails.send(payload)
        except Exception:
            # Don't let burnout notification failure mask original error
            pass


# Module-level singleton
_client: ResendClient | None = None


def get_resend_client() -> ResendClient:
    """Get or create the Resend client singleton."""
    global _client
    if _client is None:
        _client = ResendClient()
    return _client
