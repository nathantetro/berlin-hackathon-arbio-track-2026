"""Session management tools for Arbie agent.

Provides tools to update session status and metadata.
"""

import json
import os
from datetime import datetime, timezone

from agents import function_tool

from arbie.models.enums import EventType, SessionStatus
from arbie.models.session import SessionEvent
from arbie.services.db import base as db


# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for session tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


@function_tool
def update_session(
    status: str | None = None,
    status_reason: str | None = None
) -> dict:
    """
    Update the current session's status and metadata.

    Use this to track progress through the onboarding workflow. Valid statuses:

    - **received**: Initial submission received
    - **extracting**: Processing attachments
    - **awaiting_info**: Waiting for owner response
    - **researching**: Compliance research in progress
    - **ready**: Ready for owner validation
    - **validated**: Owner confirmed, complete
    - **archived**: Session closed/archived

    Args:
        status: New status value (see valid statuses above)
        status_reason: Optional explanation for the status change.
                       Recommended when setting to "awaiting_info" or similar.

    Returns:
        SessionUpdate dict with:
        - status: "success" or "error"
        - session_id: Unique session identifier
        - session_status: The new status
        - status_reason: The reason provided (if any)
        - updated_at: Timestamp of the update

    Example:
        update_session(
            status="awaiting_info",
            status_reason="Need WiFi password and check-in instructions from owner"
        )
    """
    session_id = get_session_context()
    if not session_id:
        return {"status": "error", "message": "No session context available."}

    # Get current session
    session = db.get_by_id("sessions", session_id)
    if not session:
        return {"status": "error", "message": f"Session {session_id} not found."}

    # Track old status for event
    old_status = session.get("status")
    now = datetime.now(timezone.utc)

    # Validate and update status if provided
    if status is not None:
        try:
            validated_status = SessionStatus(status)
            session["status"] = validated_status.value
        except ValueError:
            valid = [s.value for s in SessionStatus]
            return {
                "status": "error",
                "message": f"Invalid status '{status}'. Valid: {valid}"
            }

    # Update status_reason if provided
    if status_reason is not None:
        session["status_reason"] = status_reason

    # Update timestamps
    session["updated_at"] = now
    session["last_activity_at"] = now

    # Handle completed_at for terminal states
    if session["status"] in [SessionStatus.VALIDATED.value, SessionStatus.ARCHIVED.value]:
        if session.get("completed_at") is None:
            session["completed_at"] = now

    # Persist the update
    db.insert("sessions", session)

    # Record STATUS_CHANGED event if status changed
    if status is not None and old_status != session["status"]:
        event = SessionEvent(
            session_id=session_id,
            event_type=EventType.STATUS_CHANGED,
            timestamp=now,
            data=json.dumps({
                "old_status": old_status,
                "new_status": session["status"],
                "reason": status_reason
            })
        )
        db.insert("session_events", event.model_dump())

    return {
        "status": "success",
        "session_id": session_id,
        "session_status": session["status"],
        "status_reason": session.get("status_reason"),
        "updated_at": now.isoformat()
    }
