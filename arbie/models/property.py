"""Property, PropertyAttribute, and AttributeHistory models."""

from datetime import date, datetime

from pydantic import Field

from arbie.models.base import BaseEntity
from arbie.models.enums import AttributeCategory, PropertyStatus


class Coordinates(BaseEntity):
    """Geographic coordinates."""

    lat: float = Field(...)
    lng: float = Field(...)


class Property(BaseEntity):
    """The core entity - a vacation rental property being onboarded."""

    session_id: str = Field(..., description="FK to Session (origin)")
    status: PropertyStatus = Field(default=PropertyStatus.DRAFT)

    # Location (required)
    address_line1: str | None = Field(default=None)
    address_line2: str | None = Field(default=None)
    city: str | None = Field(default=None)
    state_province: str | None = Field(default=None)
    postal_code: str | None = Field(default=None)
    country: str | None = Field(default=None)
    coordinates_lat: float | None = Field(default=None)
    coordinates_lng: float | None = Field(default=None)

    # Capacity (required)
    max_guests: int | None = Field(default=None)
    bedrooms: int | None = Field(default=None)
    beds: int | None = Field(default=None)
    bathrooms: float | None = Field(default=None, description="1.5 for one and a half bath")

    # Type
    property_type: str | None = Field(default=None, description="apartment, house, villa, etc.")

    # Compliance
    permit_number: str | None = Field(default=None)
    permit_expiry: date | None = Field(default=None)
    tax_id: str | None = Field(default=None)

    # Validation
    validated_at: datetime | None = Field(default=None)
    validated_by_ip: str | None = Field(default=None)

    # Computed
    completeness_score: float = Field(default=0.0, description="0.0 - 1.0")


class PropertyAttribute(BaseEntity):
    """Flexible key-value storage for property details."""

    property_id: str = Field(..., description="FK to Property")
    key: str = Field(..., description="e.g., wifi_password, pool_hours")
    value_json: str = Field(..., description="Value stored as JSON string")
    value_type: str = Field(..., description="string, number, boolean, list, object")
    category: AttributeCategory = Field(default=AttributeCategory.OTHER)
    display_name: str | None = Field(default=None, description="Human-friendly name")
    evidence_id: str = Field(..., description="FK to Evidence")
    confidence: float = Field(default=1.0, description="0.0 - 1.0")
    created_by: str = Field(default="arbie", description="arbie or owner")
    updated_by: str | None = Field(default=None)


class AttributeHistory(BaseEntity):
    """Tracks changes to attributes for audit."""

    attribute_id: str = Field(..., description="FK to PropertyAttribute")
    old_value_json: str = Field(..., description="Previous value as JSON")
    new_value_json: str = Field(..., description="New value as JSON")
    changed_at: datetime = Field(...)
    changed_by: str = Field(..., description="arbie, owner, or user email")
    change_reason: str | None = Field(default=None)
