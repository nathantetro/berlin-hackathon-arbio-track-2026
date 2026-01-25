"""PyArrow schemas for all Iceberg tables."""

import pyarrow as pa

# Table names
USERS_TABLE = "users"
SESSIONS_TABLE = "sessions"
SESSION_EVENTS_TABLE = "session_events"
EMAILS_TABLE = "emails"
ATTACHMENTS_TABLE = "attachments"
PROPERTIES_TABLE = "properties"
PROPERTY_ATTRIBUTES_TABLE = "property_attributes"
ATTRIBUTE_HISTORY_TABLE = "attribute_history"
EVIDENCE_TABLE = "evidence"
ROOMS_TABLE = "rooms"
PROPERTY_PHOTOS_TABLE = "property_photos"
COMPLIANCE_CHECKS_TABLE = "compliance_checks"
VALIDATION_TOKENS_TABLE = "validation_tokens"

# Common timestamp type
TIMESTAMP_TYPE = pa.timestamp("us", tz="UTC")

# Users schema
USERS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("email", pa.string()),
    ("name", pa.string()),
    ("phone", pa.string()),
    ("company", pa.string()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Sessions schema
SESSIONS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("reference_code", pa.string()),
    ("user_id", pa.string()),
    ("property_id", pa.string()),
    ("status", pa.string()),
    ("status_reason", pa.string()),
    ("thread_id", pa.string()),
    ("last_activity_at", TIMESTAMP_TYPE),
    ("follow_up_count", pa.int32()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
    ("completed_at", TIMESTAMP_TYPE),
])

# Session Events schema
SESSION_EVENTS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("session_id", pa.string()),
    ("event_type", pa.string()),
    ("timestamp", TIMESTAMP_TYPE),
    ("data", pa.string()),  # JSON string
    ("agent_id", pa.string()),
    ("trace_id", pa.string()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Emails schema
EMAILS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("session_id", pa.string()),
    ("direction", pa.string()),
    ("email_type", pa.string()),
    ("message_id", pa.string()),
    ("in_reply_to", pa.string()),
    ("from_address", pa.string()),
    ("to_addresses", pa.list_(pa.string())),
    ("cc_addresses", pa.list_(pa.string())),
    ("subject", pa.string()),
    ("body_text", pa.string()),
    ("body_html", pa.string()),
    ("sent_at", TIMESTAMP_TYPE),
    ("received_at", TIMESTAMP_TYPE),
    ("processed_at", TIMESTAMP_TYPE),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Attachments schema
ATTACHMENTS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("email_id", pa.string()),
    ("filename", pa.string()),
    ("content_type", pa.string()),
    ("size_bytes", pa.int64()),
    ("storage_path", pa.string()),
    ("checksum", pa.string()),
    ("status", pa.string()),
    ("extracted_text", pa.string()),
    ("extracted_metadata", pa.list_(pa.string())),  # List of attachment IDs
    ("uploaded_at", TIMESTAMP_TYPE),
    ("processed_at", TIMESTAMP_TYPE),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Properties schema
PROPERTIES_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("session_id", pa.string()),
    ("status", pa.string()),
    # Location
    ("address_line1", pa.string()),
    ("address_line2", pa.string()),
    ("city", pa.string()),
    ("state_province", pa.string()),
    ("postal_code", pa.string()),
    ("country", pa.string()),
    ("coordinates_lat", pa.float64()),
    ("coordinates_lng", pa.float64()),
    # Capacity
    ("max_guests", pa.int32()),
    ("bedrooms", pa.int32()),
    ("beds", pa.int32()),
    ("bathrooms", pa.float32()),
    # Type
    ("property_type", pa.string()),
    # Compliance
    ("permit_number", pa.string()),
    ("permit_expiry", pa.date32()),
    ("tax_id", pa.string()),
    # Validation
    ("validated_at", TIMESTAMP_TYPE),
    ("validated_by_ip", pa.string()),
    # Computed
    ("completeness_score", pa.float32()),
    # Metadata
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Property Attributes schema
PROPERTY_ATTRIBUTES_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("property_id", pa.string()),
    ("key", pa.string()),
    ("value_json", pa.string()),  # JSON string for flexible types
    ("value_type", pa.string()),
    ("category", pa.string()),
    ("display_name", pa.string()),
    ("evidence_id", pa.string()),
    ("confidence", pa.float32()),
    ("created_by", pa.string()),
    ("updated_by", pa.string()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Attribute History schema
ATTRIBUTE_HISTORY_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("attribute_id", pa.string()),
    ("old_value_json", pa.string()),
    ("new_value_json", pa.string()),
    ("changed_at", TIMESTAMP_TYPE),
    ("changed_by", pa.string()),
    ("change_reason", pa.string()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Evidence schema
EVIDENCE_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("evidence_type", pa.string()),
    ("attachment_id", pa.string()),
    ("email_id", pa.string()),
    ("research_url", pa.string()),
    ("page_number", pa.int32()),
    ("bounding_box_x", pa.float32()),
    ("bounding_box_y", pa.float32()),
    ("bounding_box_width", pa.float32()),
    ("bounding_box_height", pa.float32()),
    ("text_snippet", pa.string()),
    ("extracted_at", TIMESTAMP_TYPE),
    ("extraction_method", pa.string()),
    ("confidence", pa.float32()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Rooms schema
ROOMS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("property_id", pa.string()),
    ("room_type", pa.string()),
    ("name", pa.string()),
    ("floor", pa.int32()),
    ("description", pa.string()),
    ("objects_detected", pa.list_(pa.string())),
    ("attachments", pa.list_(pa.string())),  # Attachment URLs
    # Matching
    ("visual_signature", pa.string()),
    ("confidence", pa.float32()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Property Photos schema
PROPERTY_PHOTOS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("property_id", pa.string()),
    ("attachment_id", pa.string()),
    ("room_id", pa.string()),
    # Storage
    ("storage_path", pa.string()),
    ("thumbnail_path", pa.string()),
    # Display
    ("is_primary", pa.bool_()),
    ("is_room_primary", pa.bool_()),
    ("display_order", pa.int32()),
    # Metadata
    ("description", pa.string()),
    ("objects_detected", pa.list_(pa.string())),
    ("amenities_visible", pa.list_(pa.string())),
    ("tags", pa.list_(pa.string())),
    # Room matching
    ("visual_embedding", pa.list_(pa.float32())),
    ("match_confidence", pa.float32()),
    # Quality
    ("quality_score", pa.float32()),
    ("quality_issues", pa.list_(pa.string())),
    # Status
    ("status", pa.string()),
    ("rejection_reason", pa.string()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Compliance Checks schema
COMPLIANCE_CHECKS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("property_id", pa.string()),
    ("check_type", pa.string()),
    ("jurisdiction", pa.string()),
    ("status", pa.string()),
    ("details", pa.string()),
    ("requirement_description", pa.string()),
    ("required_documents", pa.list_(pa.string())),
    ("deadline", pa.date32()),
    ("source_urls", pa.list_(pa.string())),
    ("researched_at", TIMESTAMP_TYPE),
    ("resolved", pa.bool_()),
    ("resolution_notes", pa.string()),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Validation Tokens schema
VALIDATION_TOKENS_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("session_id", pa.string()),
    ("property_id", pa.string()),
    ("token", pa.string()),
    ("expires_at", TIMESTAMP_TYPE),
    ("accessed_at", TIMESTAMP_TYPE),
    ("access_count", pa.int32()),
    ("last_ip", pa.string()),
    ("is_valid", pa.bool_()),
    ("validated_at", TIMESTAMP_TYPE),
    ("created_at", TIMESTAMP_TYPE),
    ("updated_at", TIMESTAMP_TYPE),
])

# Table schemas registry
TABLE_SCHEMAS: dict[str, pa.Schema] = {
    USERS_TABLE: USERS_SCHEMA,
    SESSIONS_TABLE: SESSIONS_SCHEMA,
    SESSION_EVENTS_TABLE: SESSION_EVENTS_SCHEMA,
    EMAILS_TABLE: EMAILS_SCHEMA,
    ATTACHMENTS_TABLE: ATTACHMENTS_SCHEMA,
    PROPERTIES_TABLE: PROPERTIES_SCHEMA,
    PROPERTY_ATTRIBUTES_TABLE: PROPERTY_ATTRIBUTES_SCHEMA,
    ATTRIBUTE_HISTORY_TABLE: ATTRIBUTE_HISTORY_SCHEMA,
    EVIDENCE_TABLE: EVIDENCE_SCHEMA,
    ROOMS_TABLE: ROOMS_SCHEMA,
    PROPERTY_PHOTOS_TABLE: PROPERTY_PHOTOS_SCHEMA,
    COMPLIANCE_CHECKS_TABLE: COMPLIANCE_CHECKS_SCHEMA,
    VALIDATION_TOKENS_TABLE: VALIDATION_TOKENS_SCHEMA,
}

# Join columns for upsert operations
JOIN_COLUMNS: dict[str, list[str]] = {
    USERS_TABLE: ["id"],
    SESSIONS_TABLE: ["id"],
    SESSION_EVENTS_TABLE: ["id"],
    EMAILS_TABLE: ["id"],
    ATTACHMENTS_TABLE: ["id"],
    PROPERTIES_TABLE: ["id"],
    PROPERTY_ATTRIBUTES_TABLE: ["id"],
    ATTRIBUTE_HISTORY_TABLE: ["id"],
    EVIDENCE_TABLE: ["id"],
    ROOMS_TABLE: ["id"],
    PROPERTY_PHOTOS_TABLE: ["id"],
    COMPLIANCE_CHECKS_TABLE: ["id"],
    VALIDATION_TOKENS_TABLE: ["id"],
}

# All tables for iteration
ALL_TABLES = list(TABLE_SCHEMAS.keys())
