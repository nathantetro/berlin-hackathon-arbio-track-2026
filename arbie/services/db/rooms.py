"""Database operations for Room records."""

import re
import uuid
from typing import Any

from arbie.models.base import utc_now
from arbie.services.db.base import insert
from arbie.services.db.email import update_attachment_extracted_text


def create_room_records_from_vision(
    rooms: list[dict[str, Any]],
    property_id: str = "",
) -> list[str]:
    """Create room records in database from vision analysis results.

    This follows the same pattern as file_preprocessing.create_room_records().

    Args:
        rooms: List of room dicts from vision analysis
        property_id: FK to Property (can be empty, linked later)

    Returns:
        List of created room IDs
    """
    room_ids: list[str] = []
    now = utc_now()

    for room in rooms:
        name = room.get("name", "")
        if not name:
            continue

        # Extract room_type from room dict (already includes room_type from vision analysis)
        room_type = room.get("room_type", "")

        # If room_type not present, extract from name by removing trailing digits
        if not room_type:
            room_type = re.sub(r'\d+$', '', name)

        # Process attachment paths (convert to storage paths if needed)
        attachment_paths: list[str] = []
        for attachment in room.get("attachments", []):
            # Attachments should already be storage paths like "/attachments/img.jpg"
            if attachment.startswith("/attachments/"):
                attachment_paths.append(attachment)
            else:
                # Fallback: ensure it starts with /attachments/
                attachment_paths.append(f"/attachments/{attachment}")

        # Create room record
        room_data = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "room_type": room_type,
            "name": name,
            "floor": None,
            "description": None,
            "objects_detected": room.get("objects", []),
            "attachments": attachment_paths,
            "visual_signature": None,
            "confidence": None,
            "created_at": now,
            "updated_at": now,
        }

        insert("rooms", room_data)
        room_ids.append(room_data["id"])

    return room_ids


def update_attachments_with_room_names(
    rooms: list[dict[str, Any]],
    session_id: str | None = None,
) -> None:
    """Update attachment records with room names from vision analysis.

    Sets the extracted_text field of each attachment to its room name.
    This helps track which room each photo belongs to.

    Args:
        rooms: List of room dicts from vision analysis
        session_id: Optional session ID (for logging/debugging)
    """
    for room in rooms:
        room_name = room.get("name", "")
        if not room_name:
            continue

        for attachment_path in room.get("attachments", []):
            # Ensure path starts with /attachments/
            if not attachment_path.startswith("/attachments/"):
                attachment_path = f"/attachments/{attachment_path}"

            # Update the attachment's extracted_text field
            update_attachment_extracted_text(attachment_path, room_name)
