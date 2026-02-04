"""Email processing service for inbound email handling.

Coordinates session matching, user lookup, and email storage.
"""

import asyncio
import hashlib
import io
import random
import re
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from PIL import Image

# Register HEIC/HEIF support once at module load
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # HEIC support not available

from arbie.models.base import generate_id, utc_now
from arbie.models.email import Attachment, Email
from arbie.models.enums import AttachmentStatus, EmailDirection, EmailType, SessionStatus
from arbie.models.session import Session
from arbie.models.user import User
from arbie.services.db.base import insert, insert_async, query
from arbie.services.graph_client import GraphAttachment, GraphMessage


# Reference code pattern: ARB-YYYY-XXXX (4 digits + 4 alphanumeric)
REFERENCE_CODE_PATTERN = re.compile(r"ARB-\d{4}-[A-Z0-9]{4}", re.IGNORECASE)


@dataclass
class ProcessResult:
    """Result of processing an inbound email."""

    session_id: str
    email_id: str
    user_id: str
    is_new_session: bool
    trigger_type: str  # "new_submission" or "follow_up_response"


def generate_reference_code() -> str:
    """Generate a unique session reference code.

    Format: ARB-YYYY-XXXX where YYYY is the year and XXXX is random alphanumeric.
    """
    year = datetime.now(timezone.utc).year
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ARB-{year}-{suffix}"


def find_session_by_thread(
    in_reply_to: str | None,
    references: list[str],
    subject: str,
) -> dict | None:
    """Find an existing session by email threading information.

    Matching logic (in order):
    1. Check In-Reply-To header against emails.message_id
    2. Check References header against emails.message_id
    3. Check subject for reference code (ARB-XXXX-XXXX)

    Args:
        in_reply_to: In-Reply-To email header value.
        references: List of Message-IDs from References header.
        subject: Email subject line.

    Returns:
        Session dict if found, None otherwise.
    """
    # 1. Check In-Reply-To
    if in_reply_to:
        emails = query("emails", pl.col("message_id") == in_reply_to)
        if emails:
            session_id = emails[0]["session_id"]
            sessions = query("sessions", pl.col("id") == session_id)
            if sessions:
                return sessions[0]

    # 2. Check References
    for ref in references:
        emails = query("emails", pl.col("message_id") == ref)
        if emails:
            session_id = emails[0]["session_id"]
            sessions = query("sessions", pl.col("id") == session_id)
            if sessions:
                return sessions[0]

    # 3. Check subject for reference code
    match = REFERENCE_CODE_PATTERN.search(subject)
    if match:
        ref_code = match.group(0).upper()
        sessions = query("sessions", pl.col("reference_code") == ref_code)
        if sessions:
            return sessions[0]

    return None


def find_or_create_user(email_address: str, name: str | None = None) -> dict:
    """Find an existing user by email or create a new one.

    Args:
        email_address: User's email address.
        name: Optional user name.

    Returns:
        User dict (existing or newly created).
    """
    # Normalize email
    email_address = email_address.lower().strip()

    # Check for existing user
    users = query("users", pl.col("email") == email_address)
    if users:
        return users[0]

    # Create new user
    now = utc_now()
    user = User(
        email=email_address,
        name=name,
        created_at=now,
        updated_at=now,
    )
    user_dict = user.model_dump()
    insert("users", user_dict)

    return user_dict


def create_new_session(user_id: str, thread_id: str | None = None) -> dict:
    """Create a new onboarding session.

    Args:
        user_id: ID of the user who initiated the session.
        thread_id: Optional email thread identifier.

    Returns:
        Session dict.
    """
    now = utc_now()
    session = Session(
        reference_code=generate_reference_code(),
        user_id=user_id,
        status=SessionStatus.RECEIVED,
        thread_id=thread_id,
        last_activity_at=now,
        created_at=now,
        updated_at=now,
    )
    session_dict = session.model_dump()
    insert("sessions", session_dict)

    return session_dict


def store_email(
    session_id: str,
    message: GraphMessage,
    direction: EmailDirection = EmailDirection.INBOUND,
    email_type: EmailType = EmailType.SUBMISSION,
) -> dict:
    """Store an email in the database.

    Args:
        session_id: Session this email belongs to.
        message: Parsed GraphMessage from Microsoft Graph.
        direction: Email direction (inbound/outbound).
        email_type: Type of email in the conversation.

    Returns:
        Email dict.
    """
    now = utc_now()
    email = Email(
        session_id=session_id,
        direction=direction,
        email_type=email_type,
        message_id=message.internet_message_id,
        in_reply_to=message.in_reply_to,
        from_address=message.from_address.address,
        to_addresses=[r.address for r in message.to_recipients],
        cc_addresses=[r.address for r in message.cc_recipients],
        subject=message.subject,
        body_text=message.body_text,
        body_html=message.body_html,
        received_at=message.received_datetime,
        processed_at=now,
        created_at=now,
        updated_at=now,
    )
    email_dict = email.model_dump()
    insert("emails", email_dict)

    return email_dict


# Image formats that should be converted to JPEG
# PNG, JPEG, GIF, WebP are widely supported - no conversion needed
CONVERTIBLE_IMAGE_EXTENSIONS = {".avif", ".heic", ".heif", ".bmp", ".tiff"}


def _is_convertible_image(filename: str) -> bool:
    """Check if file is an image that should be converted to JPEG."""
    ext = Path(filename).suffix.lower()
    return ext in CONVERTIBLE_IMAGE_EXTENSIONS


def convert_image_to_jpeg(image_data: bytes, original_filename: str) -> tuple[bytes, str, str]:
    """Convert any image format to JPEG.

    Handles: PNG, WEBP, AVIF, HEIC, BMP, TIFF, GIF, and more.

    Args:
        image_data: Raw image bytes.
        original_filename: Original filename.

    Returns:
        Tuple of (jpeg_bytes, new_filename, content_type).

    Raises:
        ValueError: If image cannot be converted.
    """
    ext = Path(original_filename).suffix.lower()

    # If already JPEG, return as-is
    if ext in {".jpg", ".jpeg"}:
        return image_data, original_filename, "image/jpeg"

    try:
        # Open the image
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (handles RGBA, P, L modes)
        if img.mode in ("RGBA", "P", "LA"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                # Handle alpha channel
                alpha = img.split()[-1]
                background.paste(img, mask=alpha)
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if too large (max 2048px on longest side for efficiency)
        max_size = 2048
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.BILINEAR)  # Faster than LANCZOS

        # Save as JPEG (no optimize flag - it's slow)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85)
        jpeg_bytes = output.getvalue()

        # Generate new filename
        new_filename = Path(original_filename).stem + ".jpg"

        return jpeg_bytes, new_filename, "image/jpeg"

    except Exception as e:
        raise ValueError(f"Failed to convert {original_filename}: {e}") from e


async def store_attachment(
    email_id: str,
    attachment_info: GraphAttachment,
    content: bytes,
    session_id: str,
) -> dict:
    """Store an attachment in the database and file storage.

    Converts images (AVIF, HEIC, PNG, WEBP, etc.) to JPEG before storage.

    Args:
        email_id: Email this attachment belongs to.
        attachment_info: Attachment metadata from Graph API.
        content: Raw attachment bytes.
        session_id: Session ID for storage path.

    Returns:
        Attachment dict.
    """
    from arbie.services.db.email import get_attachments_by_email

    filename = attachment_info.name

    # CHECK: Does this email already have an attachment with this filename?
    existing_attachments = get_attachments_by_email(email_id)
    for att in existing_attachments:
        if att["filename"] == filename:
            print(f"✓ Duplicate attachment skipped: {filename} already exists for email {email_id}")
            return att  # Return existing attachment record

    # No duplicate found - proceed with normal upload
    from arbie.services.storage import get_storage_service

    # Convert images to JPEG if needed
    content_type = attachment_info.content_type
    file_content = content

    if _is_convertible_image(filename):
        try:
            file_content, filename, content_type = convert_image_to_jpeg(content, filename)
            print(f"Converted {attachment_info.name} -> {filename}")
        except Exception as e:
            # If conversion fails, store original file
            print(f"Warning: Image conversion failed for {attachment_info.name}: {e}")

    # Calculate checksum from final content
    checksum = hashlib.sha256(file_content).hexdigest()

    # Store file in Azure Blob Storage
    storage_path = f"/attachments/{filename}"

    # Use Azure Blob storage service
    storage = get_storage_service()
    await storage.write_async(storage_path, file_content, session_id)

    now = utc_now()
    attachment = Attachment(
        email_id=email_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(file_content),
        storage_path=storage_path,
        checksum=checksum,
        status=AttachmentStatus.NOT_ANALYZED,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    attachment_dict = attachment.model_dump()
    await insert_async("attachments", attachment_dict)

    return attachment_dict


def update_session_activity(session_id: str) -> None:
    """Update session's last_activity_at timestamp.

    Args:
        session_id: Session to update.
    """
    from arbie.services.db.base import insert

    sessions = query("sessions", pl.col("id") == session_id)
    if sessions:
        session = sessions[0]
        session["last_activity_at"] = utc_now()
        session["updated_at"] = utc_now()
        insert("sessions", session)


async def process_inbound_email(
    message: GraphMessage,
    attachments: list[tuple[GraphAttachment, bytes]],
) -> ProcessResult:
    """Process an inbound email and prepare for agent execution.

    This is the main entry point for email processing:
    1. Find or create user
    2. Find existing session or create new one
    3. Store email record
    4. Store attachments
    5. Return processing result for agent trigger

    Args:
        message: Parsed email message from Graph API.
        attachments: List of (metadata, content) tuples for attachments.

    Returns:
        ProcessResult with session, email, and trigger information.
    """
    # 1. Find or create user
    user = find_or_create_user(
        email_address=message.from_address.address,
        name=message.from_address.name,
    )

    # 2. Find existing session or create new one
    existing_session = find_session_by_thread(
        in_reply_to=message.in_reply_to,
        references=message.references,
        subject=message.subject,
    )

    if existing_session:
        session = existing_session
        is_new_session = False
        email_type = EmailType.RESPONSE
        trigger_type = "follow_up_response"
    else:
        session = create_new_session(
            user_id=user["id"],
            thread_id=message.conversation_id,
        )
        is_new_session = True
        email_type = EmailType.SUBMISSION
        trigger_type = "new_submission"

    # 3. Store email record
    email = store_email(
        session_id=session["id"],
        message=message,
        direction=EmailDirection.INBOUND,
        email_type=email_type,
    )

    # 4. Store attachments in parallel for better performance
    if attachments:
        upload_tasks = [
            store_attachment(
                email_id=email["id"],
                attachment_info=att_info,
                content=att_content,
                session_id=session["id"],
            )
            for att_info, att_content in attachments
        ]
        await asyncio.gather(*upload_tasks)

    # 5. Update session activity
    update_session_activity(session["id"])

    return ProcessResult(
        session_id=session["id"],
        email_id=email["id"],
        user_id=user["id"],
        is_new_session=is_new_session,
        trigger_type=trigger_type,
    )
