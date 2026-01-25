"""User model for property owners."""

from pydantic import Field

from arbie.models.base import BaseEntity


class User(BaseEntity):
    """Represents a property owner or stakeholder."""

    email: str = Field(..., description="Primary email address")
    name: str | None = Field(default=None, description="User's full name")
    phone: str | None = Field(default=None, description="Phone number")
    company: str | None = Field(default=None, description="Company name")
