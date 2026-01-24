"""Base model definitions for Arbie entities."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def generate_id() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class BaseEntity(BaseModel):
    """Base class for all Arbie entities."""

    id: str = Field(default_factory=generate_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        """Ensure updated_at is set on creation."""
        if self.updated_at is None:
            self.updated_at = self.created_at
