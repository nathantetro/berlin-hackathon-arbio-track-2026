"""Enum definitions for Arbie data models."""

from enum import Enum


class SessionStatus(str, Enum):
    """Session lifecycle states."""

    RECEIVED = "received"
    EXTRACTING = "extracting"
    AWAITING_INFO = "awaiting_info"
    RESEARCHING = "researching"
    READY = "ready"
    VALIDATED = "validated"
    ARCHIVED = "archived"


class EventType(str, Enum):
    """Types of events that can occur in a session."""

    EMAIL_RECEIVED = "email_received"
    EMAIL_SENT = "email_sent"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    PROPERTY_CREATED = "property_created"
    PROPERTY_UPDATED = "property_updated"
    GAP_DETECTED = "gap_detected"
    RESEARCH_STARTED = "research_started"
    RESEARCH_COMPLETED = "research_completed"
    COMPLIANCE_FLAG = "compliance_flag"
    STATUS_CHANGED = "status_changed"
    VALIDATION_REQUESTED = "validation_requested"
    VALIDATION_COMPLETED = "validation_completed"
    OWNER_EDIT = "owner_edit"
    TIMEOUT_WARNING = "timeout_warning"
    ARCHIVED = "archived"


class EmailDirection(str, Enum):
    """Direction of email communication."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EmailType(str, Enum):
    """Types of emails in the conversation."""

    SUBMISSION = "submission"
    ACKNOWLEDGMENT = "acknowledgment"
    FOLLOW_UP = "follow_up"
    RESPONSE = "response"
    READY_NOTIFICATION = "ready"
    REMINDER = "reminder"
    VALIDATION_CONFIRM = "validation"


class AttachmentStatus(str, Enum):
    """Processing status of attachments."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class PropertyStatus(str, Enum):
    """Property lifecycle states."""

    DRAFT = "draft"
    PENDING_INFO = "pending"
    PENDING_COMPLIANCE = "compliance"
    READY = "ready"
    VALIDATED = "validated"
    PUBLISHED = "published"
    REJECTED = "rejected"


class AttributeCategory(str, Enum):
    """Categories for flexible property attributes."""

    AMENITY = "amenity"
    RULE = "rule"
    ACCESS = "access"
    APPLIANCE = "appliance"
    CONTACT = "contact"
    LOCAL = "local"
    PRICING = "pricing"
    POLICY = "policy"
    OTHER = "other"


class EvidenceType(str, Enum):
    """Types of evidence sources."""

    DOCUMENT = "document"
    IMAGE = "image"
    EMAIL_BODY = "email_body"
    RESEARCH = "research"
    OWNER_INPUT = "owner"


class RoomType(str, Enum):
    """Types of rooms and spaces."""

    # Indoor rooms
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    KITCHEN = "kitchen"
    LIVING_ROOM = "living_room"
    DINING_ROOM = "dining_room"
    OFFICE = "office"
    LAUNDRY = "laundry"
    GARAGE = "garage"
    HALLWAY = "hallway"
    CLOSET = "closet"
    BASEMENT = "basement"
    ATTIC = "attic"

    # Outdoor spaces
    PATIO = "patio"
    BALCONY = "balcony"
    DECK = "deck"
    POOL_AREA = "pool_area"
    GARDEN = "garden"
    PARKING = "parking"

    # Generic
    EXTERIOR = "exterior"
    COMMON_AREA = "common_area"
    OTHER = "other"


class PhotoStatus(str, Enum):
    """Status of property photos."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ComplianceStatus(str, Enum):
    """Status of compliance checks."""

    PENDING = "pending"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"
    NEEDS_ACTION = "needs_action"
