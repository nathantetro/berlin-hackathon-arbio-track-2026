"""MailerSend client for sending outbound emails.

Handles email sending via MailerSend API with Arbio branding.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from mailersend import emails


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


class MailerSendClient:
    """Client for sending emails via MailerSend API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("MAILERSEND_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Missing MailerSend API key. Set MAILERSEND_API_KEY environment variable."
            )

        self._mailer = emails.NewEmail(self.api_key)

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
        """Send an email via MailerSend.

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

        # Build mail body
        mail_body = {}

        # Set from
        self._mailer.set_mail_from(
            {"email": FROM_EMAIL, "name": FROM_NAME}, mail_body
        )

        # Set recipients
        self._mailer.set_mail_to(
            [{"email": email} for email in recipients], mail_body
        )

        # Set reply-to
        self._mailer.set_reply_to(
            {"email": REPLY_TO_EMAIL, "name": FROM_NAME}, mail_body
        )

        # Set subject
        self._mailer.set_subject(subject, mail_body)

        # Set body
        if body_text:
            self._mailer.set_plaintext_content(body_text, mail_body)
        if body_html:
            self._mailer.set_html_content(body_html, mail_body)

        # Set custom headers for threading
        custom_headers = []
        if in_reply_to:
            custom_headers.append({"name": "In-Reply-To", "value": in_reply_to})
        if references:
            custom_headers.append(
                {"name": "References", "value": " ".join(references)}
            )
        if custom_headers:
            mail_body["headers"] = custom_headers

        # Add attachments
        if attachments:
            import base64

            attachment_list = []
            for att in attachments:
                attachment_list.append(
                    {
                        "filename": att.filename,
                        "content": base64.b64encode(att.content).decode("utf-8"),
                        "type": att.content_type,
                    }
                )
            self._mailer.set_attachments(attachment_list, mail_body)

        # Send email
        response = self._mailer.send(mail_body)

        # Parse response - MailerSend returns message ID in x-message-id header
        # The SDK returns a string response on success
        message_id = ""
        status = "sent"

        if isinstance(response, str):
            # Successful send - response is the message ID
            message_id = response
        elif hasattr(response, "headers"):
            message_id = response.headers.get("x-message-id", "")

        return SendResult(
            message_id=message_id,
            status=status,
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
        self._send_burnout_notification(to, subject, last_error)
        raise last_error

    def _send_burnout_notification(
        self,
        original_to: str | list[str],
        original_subject: str,
        error: Exception | None,
    ) -> None:
        """Send notification that Arbie couldn't complete the task."""
        recipients = [original_to] if isinstance(original_to, str) else original_to

        burnout_subject = "Arbie needs a moment - Your request couldn't be processed"
        burnout_body = f"""Hi there,

Arbie got a burnout and wasn't able to finish the work on your request:
"{original_subject}"

This sometimes happens when our systems are under heavy load. Don't worry - your submission is safe and we'll process it as soon as possible.

In the meantime, you might find this resource helpful:
https://peertac.org/2024/12/03/understanding-burnout-awareness-consequences-and-prevention/

We apologize for the inconvenience and appreciate your patience.

Best regards,
The Arbio Team
"""

        try:
            mail_body = {}
            self._mailer.set_mail_from(
                {"email": FROM_EMAIL, "name": FROM_NAME}, mail_body
            )
            self._mailer.set_mail_to(
                [{"email": email} for email in recipients], mail_body
            )
            self._mailer.set_subject(burnout_subject, mail_body)
            self._mailer.set_plaintext_content(burnout_body, mail_body)
            self._mailer.send(mail_body)
        except Exception:
            # Don't let burnout notification failure mask original error
            pass


# Module-level singleton
_client: MailerSendClient | None = None


def get_mailersend_client() -> MailerSendClient:
    """Get or create the MailerSend client singleton."""
    global _client
    if _client is None:
        _client = MailerSendClient()
    return _client
