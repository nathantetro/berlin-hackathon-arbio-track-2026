"""Session and SessionEvent models."""

from datetime import datetime

from pydantic import Field

from arbie.models.base import BaseEntity, utc_now
from arbie.models.enums import EventType, SessionStatus


class Session(BaseEntity):
    """Represents an onboarding conversation between a User and Arbie."""

    reference_code: str = Field(..., description="Human-readable code (e.g., ARB-2024-X7K9)")
    user_id: str = Field(..., description="FK to User")
    property_id: str | None = Field(default=None, description="FK to Property")
    status: SessionStatus = Field(default=SessionStatus.RECEIVED)
    status_reason: str | None = Field(default=None, description="Why in this status")
    thread_id: str | None = Field(default=None, description="Email thread identifier")
    last_activity_at: datetime = Field(default_factory=utc_now)
    follow_up_count: int = Field(default=0)
    completed_at: datetime | None = Field(default=None)


class SessionEvent(BaseEntity):
    """Tracks events in a session for timeline/audit."""

    session_id: str = Field(..., description="FK to Session")
    event_type: EventType = Field(...)
    timestamp: datetime = Field(default_factory=utc_now)
    data: str = Field(default="{}", description="Event-specific payload as JSON string")
    agent_id: str | None = Field(default=None, description="Which agent/sub-agent")
    trace_id: str | None = Field(default=None, description="Link to detailed trace log")
