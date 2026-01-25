"""Acknowledgment email service.

Sends immediate confirmation emails when property submissions are received.
"""

from arbie.services.resend_client import get_resend_client

ACKNOWLEDGMENT_SUBJECT_PREFIX = "Re: "

ACKNOWLEDGMENT_BODY = """Hey there!

Our AI colleague Arbie just received your email and is already diving into it. Arbie's pretty quick, but give it a moment to work its magic - extracting info, checking details, and making sure everything's in order.

You'll hear back soon with any questions or a summary to review.

Cheers,
The Arbio Team
"""


def send_acknowledgment_email(
    to: str,
    original_subject: str,
    in_reply_to: str | None = None,
    session_reference: str | None = None,
) -> None:
    """Send an acknowledgment email for a received submission.

    Args:
        to: Recipient email address.
        original_subject: Subject of the original email (will be prefixed with "Re: ").
        in_reply_to: Message-ID of the original email for threading.
        session_reference: Optional session reference code to include in footer.
    """
    mailer = get_resend_client()
    mailer.send_email(
        to=to,
        subject=f"{ACKNOWLEDGMENT_SUBJECT_PREFIX}{original_subject}",
        body_text=ACKNOWLEDGMENT_BODY,
        in_reply_to=in_reply_to,
        references=[in_reply_to] if in_reply_to else None,
        session_reference=session_reference,
    )
