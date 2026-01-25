# Arbie - Data Schema

## Overview

This document defines the core data models for the Arbie property onboarding system. The schema is designed to be:

- **Flexible**: Properties have both required fields and arbitrary key-value attributes
- **Traceable**: Every value links back to its source evidence
- **Auditable**: All changes are tracked with history
- **Stateful**: Clear lifecycle states for properties and sessions

---

## Core Entities

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    User     │──1:N──│   Session   │──1:1──│  Property   │
└─────────────┘       └─────────────┘       └─────────────┘
                            │                      │
                           1:N                    1:N
                            │                      ├──────────────┐
                      ┌─────▼─────┐         ┌──────▼──────┐ ┌─────▼─────┐
                      │   Email   │         │  Attribute  │ │   Room    │
                      └───────────┘         └─────────────┘ └───────────┘
                            │                      │              │
                           1:N                    1:1            1:N
                            │                      │              │
                      ┌─────▼─────┐         ┌──────▼──────┐ ┌─────▼─────┐
                      │Attachment │         │  Evidence   │ │   Photo   │
                      └───────────┘         └─────────────┘ └───────────┘
```

---

## 1. User

Represents a property owner or stakeholder.

```python
class User:
    # Identity
    id: str                     # UUID
    email: str                  # Primary email address

    # Profile (optional, extracted over time)
    name: str | None
    phone: str | None
    company: str | None

    # Metadata
    created_at: datetime
    updated_at: datetime

    # Relationships
    sessions: list[Session]     # All onboarding sessions for this user
```

**Notes:**
- User is identified primarily by email address
- Profile fields populated as Arbie learns from interactions
- One user can have multiple properties (multiple sessions)

---

## 2. Session

Represents an onboarding conversation between a User and Arbie.

```python
class SessionStatus(Enum):
    RECEIVED = "received"           # Initial submission received
    EXTRACTING = "extracting"       # Processing attachments
    AWAITING_INFO = "awaiting_info" # Waiting for owner response
    RESEARCHING = "researching"     # Compliance research in progress
    READY = "ready"                 # Ready for owner validation
    VALIDATED = "validated"         # Owner confirmed, complete
    ARCHIVED = "archived"           # Closed without completion

class Session:
    # Identity
    id: str                         # UUID
    reference_code: str             # Human-readable (e.g., "ARB-2024-X7K9")

    # Relationships
    user_id: str                    # FK to User
    property_id: str | None         # FK to Property (created during extraction)

    # State
    status: SessionStatus
    status_reason: str | None       # Why in this status

    # Conversation tracking
    thread_id: str | None           # Email thread identifier
    last_activity_at: datetime
    follow_up_count: int            # Number of follow-up rounds

    # Metadata
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    # Relationships
    emails: list[Email]
    events: list[SessionEvent]      # Timeline of all events
```

**Session Lifecycle:**
```
RECEIVED → EXTRACTING → AWAITING_INFO ←→ (loop) → RESEARCHING → READY → VALIDATED
                ↓                                      ↓
            ARCHIVED ←──────────────────────────── ARCHIVED
```

---

## 3. Session Event

Tracks everything that happens in a session for timeline/audit.

```python
class EventType(Enum):
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

class SessionEvent:
    id: str                     # UUID
    session_id: str             # FK to Session

    event_type: EventType
    timestamp: datetime

    # Event details (flexible)
    data: dict                  # Event-specific payload

    # Agent tracing
    agent_id: str | None        # Which agent/sub-agent
    trace_id: str | None        # Link to detailed trace log
```

---

## 4. Email

Represents an email in the conversation.

```python
class EmailDirection(Enum):
    INBOUND = "inbound"         # From owner to Arbie
    OUTBOUND = "outbound"       # From Arbie to owner

class EmailType(Enum):
    SUBMISSION = "submission"           # Initial property submission
    ACKNOWLEDGMENT = "acknowledgment"   # Receipt confirmation
    FOLLOW_UP = "follow_up"             # Arbie asking for more info
    RESPONSE = "response"               # Owner providing more info
    READY_NOTIFICATION = "ready"        # Property ready for validation
    REMINDER = "reminder"               # Nudge for inactive session
    VALIDATION_CONFIRM = "validation"   # Confirmation of validation

class Email:
    id: str                     # UUID
    session_id: str             # FK to Session

    # Email metadata
    direction: EmailDirection
    email_type: EmailType

    # Headers
    message_id: str             # Email Message-ID header
    in_reply_to: str | None     # For threading
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str

    # Content
    body_text: str | None       # Plain text version
    body_html: str | None       # HTML version

    # Timestamps
    sent_at: datetime | None    # When sent (outbound)
    received_at: datetime | None # When received (inbound)
    processed_at: datetime | None # When Arbie processed it

    # Relationships
    attachments: list[Attachment]
```

---

## 5. Attachment

Files attached to emails.

```python
class AttachmentStatus(Enum):
    PENDING = "pending"         # Not yet processed
    PROCESSING = "processing"   # Currently being extracted
    PROCESSED = "processed"     # Extraction complete
    FAILED = "failed"           # Extraction failed
    UNSUPPORTED = "unsupported" # File type not supported

class Attachment:
    id: str                     # UUID
    email_id: str               # FK to Email

    # File metadata
    filename: str
    content_type: str           # MIME type
    size_bytes: int

    # Storage
    storage_path: str           # Path in file storage (S3/Iceberg)
    checksum: str               # SHA-256 for integrity

    # Processing
    status: AttachmentStatus
    extracted_text: str | None  # OCR/parsed text content
    extracted_attachments: dict | None  # Structured data extracted

    # Timestamps
    uploaded_at: datetime
    processed_at: datetime | None
```

---

## 6. Property

The core entity - a vacation rental property being onboarded.

```python
class PropertyStatus(Enum):
    DRAFT = "draft"             # Being built from extractions
    PENDING_INFO = "pending"    # Missing required information
    PENDING_COMPLIANCE = "compliance"  # Awaiting compliance check
    READY = "ready"             # Complete, awaiting validation
    VALIDATED = "validated"     # Owner confirmed
    PUBLISHED = "published"     # Live on platform
    REJECTED = "rejected"       # Cannot be listed

class Property:
    id: str                     # UUID
    session_id: str             # FK to Session (origin)

    # Status
    status: PropertyStatus

    # ===== HARD ATTRIBUTES (required, typed) =====

    # Location (required)
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state_province: str | None
    postal_code: str | None
    country: str | None
    coordinates: tuple[float, float] | None  # (lat, lng)

    # Capacity (required)
    max_guests: int | None
    bedrooms: int | None
    beds: int | None
    bathrooms: float | None     # 1.5 for one and a half bath

    # Type
    property_type: str | None   # "apartment", "house", "villa", etc.

    # Compliance
    permit_number: str | None
    permit_expiry: date | None
    tax_id: str | None

    # ===== FLEXIBLE ATTRIBUTES =====
    attributes: list[PropertyAttribute]

    # ===== MEDIA =====
    photos: list[PropertyPhoto]

    # ===== COMPLIANCE =====
    compliance_checks: list[ComplianceCheck]

    # Metadata
    created_at: datetime
    updated_at: datetime
    validated_at: datetime | None
    validated_by_ip: str | None

    # Computed
    completeness_score: float   # 0.0 - 1.0

    def get_attribute(self, key: str) -> PropertyAttribute | None:
        """Get a flexible attribute by key."""
        pass

    def set_attribute(self, key: str, value: Any, evidence: Evidence) -> None:
        """Set a flexible attribute with evidence."""
        pass
```

---

## 7. Property Attribute

Flexible key-value storage for property details.

```python
class AttributeCategory(Enum):
    AMENITY = "amenity"             # Pool, WiFi, parking, etc.
    RULE = "rule"                   # House rules
    ACCESS = "access"               # Entry instructions, codes
    APPLIANCE = "appliance"         # How to use washer, etc.
    CONTACT = "contact"             # Emergency contacts
    LOCAL = "local"                 # Local recommendations
    PRICING = "pricing"             # Rates, fees
    POLICY = "policy"               # Cancellation, checkout
    OTHER = "other"

class PropertyAttribute:
    id: str                         # UUID
    property_id: str                # FK to Property

    # Key-value
    key: str                        # e.g., "wifi_password", "pool_hours"
    value: Any                      # Flexible type (str, int, bool, list, dict)
    value_type: str                 # "string", "number", "boolean", "list", "object"

    # Categorization
    category: AttributeCategory
    display_name: str | None        # Human-friendly name

    # Source tracking
    evidence_id: str                # FK to Evidence
    confidence: float               # 0.0 - 1.0, extraction confidence

    # Audit
    created_at: datetime
    updated_at: datetime
    created_by: str                 # "arbie" or "owner"
    updated_by: str | None

    # History
    previous_values: list[AttributeHistory]
```

### Common Attribute Keys

```python
# Amenities
COMMON_AMENITIES = [
    "wifi_network", "wifi_password",
    "parking_type", "parking_instructions",
    "pool", "pool_heated", "pool_hours",
    "hot_tub", "gym", "ev_charger",
    "air_conditioning", "heating",
    "washer", "dryer", "dishwasher",
    "kitchen_equipped", "coffee_maker",
    "tv", "streaming_services",
    "pets_allowed", "smoking_allowed",
]

# Access
COMMON_ACCESS = [
    "lockbox_location", "lockbox_code",
    "gate_code", "building_code",
    "key_location", "smart_lock_instructions",
    "checkin_time", "checkout_time",
    "early_checkin_available", "late_checkout_available",
]

# Rules
COMMON_RULES = [
    "quiet_hours", "max_noise_level",
    "party_policy", "visitor_policy",
    "trash_instructions", "recycling_instructions",
]
```

---

## 8. Attribute History

Tracks changes to attributes for audit.

```python
class AttributeHistory:
    id: str
    attribute_id: str           # FK to PropertyAttribute

    old_value: Any
    new_value: Any
    changed_at: datetime
    changed_by: str             # "arbie", "owner", or user email
    change_reason: str | None
```

---

## 9. Evidence

Links extracted data back to source material.

```python
class EvidenceType(Enum):
    DOCUMENT = "document"       # From PDF, DOCX, etc.
    IMAGE = "image"             # From photo analysis
    EMAIL_BODY = "email_body"   # From email text
    RESEARCH = "research"       # From web research
    OWNER_INPUT = "owner"       # Direct from owner (validation portal)

class Evidence:
    id: str                     # UUID

    evidence_type: EvidenceType

    # Source reference
    attachment_id: str | None   # FK to Attachment (if from file)
    email_id: str | None        # FK to Email (if from email body)
    research_url: str | None    # URL (if from research)

    # Location in source
    page_number: int | None     # For documents
    bounding_box: dict | None   # For images/PDFs {"x", "y", "width", "height"}
    text_snippet: str | None    # The actual text extracted

    # Metadata
    extracted_at: datetime
    extraction_method: str      # "ocr", "text_parse", "vision", "manual"
    confidence: float           # 0.0 - 1.0
```

---

## 10. Room

Represents a physical room or space in the property. Multiple photos can belong to the same room.

```python
class RoomType(Enum):
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
    EXTERIOR = "exterior"           # Outside view of property
    COMMON_AREA = "common_area"     # Shared building amenities
    OTHER = "other"

class Room:
    id: str                         # UUID
    property_id: str                # FK to Property

    # Classification
    room_type: RoomType
    name: str | None                # Optional custom name, e.g., "Master Bedroom", "Kids Room"
    floor: int | None               # Floor number (0 = ground, -1 = basement)

    # Details (editable via edit_property tool)
    description: str | None         # "Large bedroom with en-suite bathroom and ocean view"
    objects_detected: list[str]     # Aggregated from all photos of this room
    amenities: list[str]            # Amenities specific to this room

    # For bedrooms
    bed_count: int | None
    bed_types: list[str] | None     # ["king", "queen", "twin", "bunk"]

    # For bathrooms
    has_shower: bool | None
    has_bathtub: bool | None
    is_ensuite: bool | None         # Attached to a bedroom

    # Matching metadata (used by Arbie for photo grouping)
    visual_signature: str | None    # Embedding/hash for similarity matching
    confidence: float               # Confidence that photos belong together

    # Metadata
    created_at: datetime
    updated_at: datetime

    # Relationships
    photos: list[PropertyPhoto]     # All photos of this room
```

**Room Matching Logic:**

Arbie uses visual similarity and object detection to group photos into rooms:

1. **Visual embedding**: Each photo gets a visual signature (embedding vector)
2. **Object consistency**: Photos with same objects (same couch, same bed) likely same room
3. **Context clues**: Window views, flooring, wall colors help match
4. **Manual override**: Owner can reassign photos to different rooms in validation portal

```python
# Example: Arbie detects 3 photos are the same kitchen
Room(
    id="room_001",
    property_id="prop_456",
    room_type="kitchen",
    name="Main Kitchen",
    description="Modern kitchen with stainless steel appliances and island",
    objects_detected=["refrigerator", "stove", "island", "bar_stools", "dishwasher"],
    amenities=["dishwasher", "coffee_maker", "microwave"],
    confidence=0.89,  # 89% confident these photos belong together
    photos=[photo_1, photo_2, photo_3]  # 3 photos of this kitchen
)
```

---

## 11. Property Photo

Photos of the property, linked to rooms.

```python
class PhotoStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"       # Low quality, inappropriate, etc.

class PropertyPhoto:
    id: str                     # UUID
    property_id: str            # FK to Property
    attachment_id: str          # FK to original Attachment
    room_id: str | None         # FK to Room (photos are grouped by room)

    # Storage
    storage_path: str           # Processed/optimized version
    thumbnail_path: str         # Thumbnail version

    # Display
    is_primary: bool            # Main listing photo (for whole property)
    is_room_primary: bool       # Main photo for this room
    display_order: int          # Order within property gallery

    # Metadata extracted from vision (editable via edit_property tool)
    description: str | None     # "Spacious master bedroom with king bed and ocean view"
    objects_detected: list[str] # ["bed", "nightstand", "lamp", "window", "tv"]
    amenities_visible: list[str] # ["air_conditioning", "smart_tv", "balcony"]
    tags: list[str]             # ["ocean_view", "modern", "bright"]

    # Room matching (used by Arbie to group photos)
    visual_embedding: list[float] | None  # Vector for similarity comparison
    match_confidence: float | None        # How confident we are about room assignment

    # Quality (editable via edit_property tool)
    quality_score: float | None # 0.0 - 1.0
    quality_issues: list[str]   # ["blurry", "dark", "cropped"]

    # Status
    status: PhotoStatus
    rejection_reason: str | None

    # Metadata
    created_at: datetime
    updated_at: datetime
```

---

## 11. Compliance Check

Results of regulatory research.

```python
class ComplianceStatus(Enum):
    PENDING = "pending"         # Not yet researched
    COMPLIANT = "compliant"     # Meets requirements
    NON_COMPLIANT = "non_compliant"  # Fails requirements
    UNKNOWN = "unknown"         # Couldn't determine
    NEEDS_ACTION = "needs_action"    # Owner must do something

class ComplianceCheck:
    id: str                     # UUID
    property_id: str            # FK to Property

    # What was checked
    check_type: str             # "permit", "occupancy", "tax", "registration"
    jurisdiction: str           # City/county/state that requires it

    # Result
    status: ComplianceStatus
    details: str                # Explanation

    # Requirements
    requirement_description: str | None
    required_documents: list[str]
    deadline: date | None

    # Sources
    source_urls: list[str]      # Where we found the info
    researched_at: datetime

    # Resolution
    resolved: bool
    resolution_notes: str | None
```

---

## 12. Validation Token

Secure access to validation portal.

```python
class ValidationToken:
    id: str                     # UUID
    session_id: str             # FK to Session
    property_id: str            # FK to Property

    token: str                  # Secure random token (URL-safe)

    # Validity
    created_at: datetime
    expires_at: datetime

    # Usage
    accessed_at: datetime | None
    access_count: int
    last_ip: str | None

    # Status
    is_valid: bool              # Can be revoked
    validated_at: datetime | None
```

---

## Iceberg Table Structure

For Tower.dev storage, the entities map to Iceberg tables:

```
arbio/
├── users/                    # User table
├── sessions/                 # Session table
├── session_events/           # Event log (append-only)
├── emails/                   # Email records
├── attachments/              # Attachment metadata
├── properties/               # Property records
├── property_attributes/      # Flexible attributes (key-value data)
├── attribute_history/        # Audit log (append-only)
├── evidence/                 # Evidence records
├── rooms/                    # Physical rooms/spaces
├── property_photos/          # Photo metadata (linked to rooms)
├── compliance_checks/        # Compliance results
└── validation_tokens/        # Access tokens
```

**File Storage (S3/Blob):**
```
arbio-files/
├── attachments/
│   └── {session_id}/{attachment_id}/{filename}
├── photos/
│   ├── original/{property_id}/{photo_id}.{ext}
│   ├── processed/{property_id}/{photo_id}.{ext}
│   └── thumbnails/{property_id}/{photo_id}.jpg
└── exports/
    └── {session_id}/property-summary.pdf
```

---

## Schema Evolution

The flexible attribute system allows schema evolution without migrations:

1. **New property types**: Add new `AttributeCategory` values
2. **New fields**: Just use new `key` values in `PropertyAttribute`
3. **Pattern discovery**: Analyze common keys across properties to identify candidates for "hard" attributes
4. **Backward compatible**: Old properties work with new code, new attributes are optional

---

## Example: Complete Property

```json
{
  "id": "prop_abc123",
  "status": "validated",

  "address_line1": "123 Beach Drive",
  "city": "Miami Beach",
  "state_province": "FL",
  "postal_code": "33139",
  "country": "US",
  "coordinates": [25.7907, -80.1300],

  "max_guests": 8,
  "bedrooms": 3,
  "beds": 4,
  "bathrooms": 2.5,
  "property_type": "condo",

  "permit_number": "STR-2024-1234",
  "permit_expiry": "2025-12-31",

  "attributes": [
    {
      "key": "wifi_password",
      "value": "BeachLife2024!",
      "category": "access",
      "confidence": 0.95,
      "evidence": { "type": "document", "file": "welcome_guide.pdf", "page": 2 }
    },
    {
      "key": "pool",
      "value": true,
      "category": "amenity",
      "confidence": 0.99,
      "evidence": { "type": "image", "file": "IMG_001.jpg" }
    },
    {
      "key": "checkout_time",
      "value": "11:00",
      "category": "access",
      "confidence": 0.90,
      "evidence": { "type": "email_body", "snippet": "Please check out by 11am" }
    },
    {
      "key": "quiet_hours",
      "value": "10pm - 8am",
      "category": "rule",
      "confidence": 0.85,
      "evidence": { "type": "document", "file": "house_rules.pdf", "page": 1 }
    }
  ],

  "rooms": [
    {
      "id": "room_001",
      "room_type": "bedroom",
      "name": "Master Bedroom",
      "floor": 2,
      "bed_count": 1,
      "bed_types": ["king"],
      "is_ensuite": true,
      "photos": ["photo_1", "photo_2"]
    },
    {
      "id": "room_002",
      "room_type": "bedroom",
      "name": "Guest Bedroom",
      "floor": 2,
      "bed_count": 2,
      "bed_types": ["twin", "twin"],
      "photos": ["photo_3"]
    },
    {
      "id": "room_003",
      "room_type": "kitchen",
      "name": null,
      "description": "Modern kitchen with stainless steel appliances",
      "amenities": ["dishwasher", "coffee_maker"],
      "photos": ["photo_4", "photo_5", "photo_6"]
    },
    {
      "id": "room_004",
      "room_type": "pool_area",
      "name": "Pool & Deck",
      "photos": ["photo_7"]
    }
  ],

  "photos": [
    { "id": "photo_1", "room_id": "room_001", "is_primary": true, "tags": ["ocean_view"] },
    { "id": "photo_2", "room_id": "room_001", "is_room_primary": true },
    { "id": "photo_3", "room_id": "room_002" },
    { "id": "photo_4", "room_id": "room_003", "is_room_primary": true },
    { "id": "photo_5", "room_id": "room_003" },
    { "id": "photo_6", "room_id": "room_003" },
    { "id": "photo_7", "room_id": "room_004", "tags": ["amenity", "outdoor"] }
  ],

  "compliance_checks": [
    {
      "check_type": "permit",
      "jurisdiction": "Miami Beach",
      "status": "compliant",
      "details": "Valid STR permit on file, expires Dec 2025"
    },
    {
      "check_type": "tax",
      "jurisdiction": "Florida",
      "status": "needs_action",
      "details": "Must register for FL tourist tax",
      "required_documents": ["DR-1 form"]
    }
  ],

  "completeness_score": 0.92,
  "validated_at": "2024-01-15T14:30:00Z"
}
```
