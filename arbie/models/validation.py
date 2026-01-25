"""ValidationToken model."""

from datetime import datetime

from pydantic import Field

from arbie.models.base import BaseEntity, utc_now


class ValidationToken(BaseEntity):
    """Secure access to validation portal."""

    session_id: str = Field(..., description="FK to Session")
    property_id: str = Field(..., description="FK to Property")
    token: str = Field(..., description="Secure random token (URL-safe)")
    expires_at: datetime = Field(...)
    accessed_at: datetime | None = Field(default=None)
    access_count: int = Field(default=0)
    last_ip: str | None = Field(default=None)
    is_valid: bool = Field(default=True, description="Can be revoked")
    validated_at: datetime | None = Field(default=None)
