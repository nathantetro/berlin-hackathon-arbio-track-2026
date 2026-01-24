"""Resend client for sending outbound emails.

Handles email sending via Resend API with Arbio branding.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import resend


# Sender configuration
FROM_EMAIL = "onboard@arbie.work"
FROM_NAME = "Arbie - Arbio Onboarding"
REPLY_TO_EMAIL = "onboard@arbie.work"


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

        Returns:
            SendResult with message ID and status.
        """
        # Normalize recipients
        recipients = [to] if isinstance(to, str) else to

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

        # Set threading headers
        headers = {}
        if in_reply_to:
            headers["In-Reply-To"] = in_reply_to
        if references:
            headers["References"] = " ".join(references)
        if headers:
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

        # Parse response
        message_id = response.get("id", "") if isinstance(response, dict) else ""

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

        burnout_subject = "Arbie hit the wall..."
        burnout_body = f"""Hi there,

    Well, this is awkward... Arbie just experienced a technical burnout while working on:
    "{original_subject}"

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

            # Add threading headers if available
            headers = {}
            if in_reply_to:
                headers["In-Reply-To"] = in_reply_to
            if references:
                headers["References"] = " ".join(references)
            if headers:
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
