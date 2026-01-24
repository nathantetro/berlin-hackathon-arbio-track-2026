"""Evidence model for source linking."""

from datetime import datetime

from pydantic import Field

from arbie.models.base import BaseEntity, utc_now
from arbie.models.enums import EvidenceType


class Evidence(BaseEntity):
    """Links extracted data back to source material."""

    evidence_type: EvidenceType = Field(...)
    attachment_id: str | None = Field(default=None, description="FK to Attachment")
    email_id: str | None = Field(default=None, description="FK to Email")
    research_url: str | None = Field(default=None, description="URL if from research")
    page_number: int | None = Field(default=None, description="For documents")
    bounding_box_x: float | None = Field(default=None)
    bounding_box_y: float | None = Field(default=None)
    bounding_box_width: float | None = Field(default=None)
    bounding_box_height: float | None = Field(default=None)
    text_snippet: str | None = Field(default=None, description="The actual text extracted")
    extracted_at: datetime = Field(default_factory=utc_now)
    extraction_method: str = Field(..., description="ocr, text_parse, vision, manual")
    confidence: float = Field(default=1.0, description="0.0 - 1.0")
