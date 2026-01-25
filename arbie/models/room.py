"""Room and PropertyPhoto models."""

from pydantic import Field

from arbie.models.base import BaseEntity
from arbie.models.enums import PhotoStatus, RoomType


class Room(BaseEntity):
    """Represents a physical room or space in the property."""

    property_id: str = Field(..., description="FK to Property")
    room_type: RoomType = Field(...)
    name: str | None = Field(default=None, description="Custom name, e.g., Master Bedroom")
    floor: int | None = Field(default=None, description="Floor number (0 = ground)")
    description: str | None = Field(default=None)
    objects_detected: list[str] = Field(default_factory=list)
    amenities: list[str] = Field(default_factory=list)

    # For bedrooms
    bed_count: int | None = Field(default=None)
    bed_types: list[str] = Field(default_factory=list, description="king, queen, twin, bunk")

    # For bathrooms
    has_shower: bool | None = Field(default=None)
    has_bathtub: bool | None = Field(default=None)
    is_ensuite: bool | None = Field(default=None)

    # Matching metadata
    visual_signature: str | None = Field(default=None)
    confidence: float = Field(default=1.0)


class PropertyPhoto(BaseEntity):
    """Photos of the property, linked to rooms."""

    property_id: str = Field(..., description="FK to Property")
    attachment_id: str = Field(..., description="FK to original Attachment")
    room_id: str | None = Field(default=None, description="FK to Room")

    # Storage
    storage_path: str = Field(..., description="Processed/optimized version")
    thumbnail_path: str = Field(..., description="Thumbnail version")

    # Display
    is_primary: bool = Field(default=False, description="Main listing photo")
    is_room_primary: bool = Field(default=False, description="Main photo for this room")
    display_order: int = Field(default=0)

    # Metadata extracted from vision
    description: str | None = Field(default=None)
    objects_detected: list[str] = Field(default_factory=list)
    amenities_visible: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Room matching
    visual_embedding: list[float] = Field(default_factory=list)
    match_confidence: float | None = Field(default=None)

    # Quality
    quality_score: float | None = Field(default=None)
    quality_issues: list[str] = Field(default_factory=list)

    # Status
    status: PhotoStatus = Field(default=PhotoStatus.PENDING)
    rejection_reason: str | None = Field(default=None)
