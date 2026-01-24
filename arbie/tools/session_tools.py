"""Session management tools for Arbie agent.

Provides tools to update session status and metadata.
"""

from agents import function_tool


@function_tool
def update_session(
    status: str | None = None,
    status_reason: str | None = None
) -> dict:
    """
    Update the current session's status and metadata.

    Use this to track progress through the onboarding workflow. Valid statuses:

    - **new**: Initial state, no processing yet
    - **in_progress**: Actively working on property data
    - **waiting_for_info**: Blocked waiting for property owner response
    - **ready_for_review**: Complete, ready for human review
    - **approved**: Reviewed and approved by human
    - **published**: Property is live on platforms
    - **archived**: Session closed/archived

    Args:
        status: New status value (see valid statuses above)
        status_reason: Optional explanation for the status change.
                       Recommended when setting to "waiting_for_info" or similar.

    Returns:
        SessionUpdate dict with:
        - session_id: Unique session identifier
        - status: The new status
        - status_reason: The reason provided (if any)
        - updated_at: Timestamp of the update

    Example:
        update_session(
            status="waiting_for_info",
            status_reason="Need WiFi password and check-in instructions from owner"
        )
    """
    return {
        "status": "not_implemented",
        "message": f"update_session not implemented yet. Would set status to: {status}",
        "params": {
            "status": status,
            "status_reason": status_reason
        }
    }
