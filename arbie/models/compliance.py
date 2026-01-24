"""ComplianceCheck model."""

from datetime import date, datetime

from pydantic import Field

from arbie.models.base import BaseEntity, utc_now
from arbie.models.enums import ComplianceStatus


class ComplianceCheck(BaseEntity):
    """Results of regulatory research."""

    property_id: str = Field(..., description="FK to Property")
    check_type: str = Field(..., description="permit, occupancy, tax, registration")
    jurisdiction: str = Field(..., description="City/county/state that requires it")
    status: ComplianceStatus = Field(default=ComplianceStatus.PENDING)
    details: str = Field(..., description="Explanation")
    requirement_description: str | None = Field(default=None)
    required_documents: list[str] = Field(default_factory=list)
    deadline: date | None = Field(default=None)
    source_urls: list[str] = Field(default_factory=list)
    researched_at: datetime = Field(default_factory=utc_now)
    resolved: bool = Field(default=False)
    resolution_notes: str | None = Field(default=None)
