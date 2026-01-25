"""Property data management tools for Arbie agent.

Provides tools to read and write structured property information.
"""

import json
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal

from agents import function_tool
from pydantic import BaseModel

from arbie.models.enums import AttributeCategory, EvidenceType, PropertyStatus, RoomType
from arbie.services.db import base as db
from arbie.services.db import property as db_property

# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for property tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


class EvidenceData(BaseModel):
    """Evidence for property field value."""
    source_type: Literal["document", "image", "email", "inference"]
    source_path: str | None = None
    excerpt: str | None = None
    confidence: Literal["high", "medium", "low"] = "medium"


# Required fields for completeness calculation
REQUIRED_FIELDS = [
    "address_line1", "city", "country",
    "max_guests", "bedrooms", "bathrooms"
]


def _calculate_completeness(property_data: dict) -> float:
    """Calculate property completeness score (0.0 - 1.0)."""
    filled = sum(1 for f in REQUIRED_FIELDS if property_data.get(f) is not None)
    return filled / len(REQUIRED_FIELDS)


def _json_serialize(value: Any) -> str:
    """Serialize a value to JSON string."""
    return json.dumps(value)


def _json_deserialize(value_json: str) -> Any:
    """Deserialize a JSON string to a value."""
    try:
        return json.loads(value_json)
    except (json.JSONDecodeError, TypeError):
        return value_json


def _get_value_type(value: Any) -> str:
    """Get the type string for a value."""
    if isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "number"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, list):
        return "list"
    elif isinstance(value, dict):
        return "object"
    else:
        return "string"


def _create_evidence_record(evidence: EvidenceData | None) -> str | None:
    """Create an evidence record in the database and return its ID."""
    if evidence is None:
        return None

    evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Map source_type to EvidenceType
    type_map = {
        "document": EvidenceType.DOCUMENT,
        "image": EvidenceType.IMAGE,
        "email": EvidenceType.EMAIL_BODY,
        "inference": EvidenceType.RESEARCH,
    }

    # Map confidence to numeric
    confidence_map = {"high": 1.0, "medium": 0.7, "low": 0.4}

    evidence_record = {
        "id": evidence_id,
        "evidence_type": type_map.get(evidence.source_type, EvidenceType.DOCUMENT).value,
        "attachment_id": None,
        "email_id": None,
        "research_url": None,
        "page_number": None,
        "bounding_box_x": None,
        "bounding_box_y": None,
        "bounding_box_width": None,
        "bounding_box_height": None,
        "text_snippet": evidence.excerpt,
        "extracted_at": now,
        "extraction_method": "agent",
        "confidence": confidence_map.get(evidence.confidence, 0.7),
        "created_at": now,
        "updated_at": now,
    }

    db.insert("evidence", evidence_record)
    return evidence_id


@function_tool
def get_property(include_history: bool = False) -> dict:
    """
    Get the current property data structure.

    Retrieve the full property object with all recorded information.
    Useful for:
    - Reviewing what's been recorded so far
    - Identifying missing required fields
    - Checking for inconsistencies
    - Understanding evidence chain

    Args:
        include_history: If True, include the full edit history with timestamps
                        and evidence for each field. Default: False.

    Returns:
        Property dict with:
        - status: "success", "no_property", or "error"
        - property_id: Unique property identifier
        - property: All hard property fields and values
        - attributes: Flexible attributes list
        - rooms: List of rooms with their details
        - photos: List of photos
        - completeness_score: 0.0 - 1.0 indicating data completeness
        - history: (if include_history=True) Full edit history with evidence
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    # Get property for this session
    prop = db_property.get_property_by_session(session_id)
    if not prop:
        return {
            "status": "no_property",
            "property": None,
            "message": "No property exists for this session yet. Use edit_property to create one.",
        }

    property_id = prop["id"]

    # Build property data dict with hard attributes
    property_data = {
        "address_line1": prop.get("address_line1"),
        "address_line2": prop.get("address_line2"),
        "city": prop.get("city"),
        "state_province": prop.get("state_province"),
        "postal_code": prop.get("postal_code"),
        "country": prop.get("country"),
        "coordinates_lat": prop.get("coordinates_lat"),
        "coordinates_lng": prop.get("coordinates_lng"),
        "max_guests": prop.get("max_guests"),
        "bedrooms": prop.get("bedrooms"),
        "beds": prop.get("beds"),
        "bathrooms": prop.get("bathrooms"),
        "property_type": prop.get("property_type"),
        "permit_number": prop.get("permit_number"),
        "permit_expiry": prop.get("permit_expiry").isoformat() if prop.get("permit_expiry") else None,
        "tax_id": prop.get("tax_id"),
        "status": prop.get("status"),
        "validated_at": prop.get("validated_at").isoformat() if prop.get("validated_at") else None,
    }

    # Get flexible attributes
    attrs = db_property.get_attributes_by_property(property_id)
    attributes = [
        {
            "id": attr["id"],
            "key": attr["key"],
            "value": _json_deserialize(attr.get("value_json", "null")),
            "category": attr.get("category"),
            "confidence": attr.get("confidence"),
            "display_name": attr.get("display_name"),
        }
        for attr in attrs
    ]

    # Get rooms
    rooms_list = db_property.get_rooms_by_property(property_id)
    rooms = [
        {
            "id": room["id"],
            "room_type": room.get("room_type"),
            "name": room.get("name"),
            "floor": room.get("floor"),
            "description": room.get("description"),
            "bed_count": room.get("bed_count"),
            "bed_types": room.get("bed_types", []),
            "has_shower": room.get("has_shower"),
            "has_bathtub": room.get("has_bathtub"),
            "is_ensuite": room.get("is_ensuite"),
            "amenities": room.get("amenities", []),
        }
        for room in rooms_list
    ]

    # Get photos
    photos_list = db_property.get_photos_by_property(property_id)
    photos = [
        {
            "id": photo["id"],
            "room_id": photo.get("room_id"),
            "storage_path": photo.get("storage_path"),
            "is_primary": photo.get("is_primary"),
            "is_room_primary": photo.get("is_room_primary"),
            "display_order": photo.get("display_order"),
            "description": photo.get("description"),
            "tags": photo.get("tags", []),
        }
        for photo in photos_list
    ]

    result = {
        "status": "success",
        "property_id": property_id,
        "property": property_data,
        "attributes": attributes,
        "rooms": rooms,
        "photos": photos,
        "completeness_score": prop.get("completeness_score", _calculate_completeness(property_data)),
    }

    # Include history if requested
    if include_history:
        history = db_property.get_all_attribute_history_by_property(property_id)
        result["history"] = [
            {
                "attribute_id": h["attribute_id"],
                "old_value": _json_deserialize(h.get("old_value_json", "null")),
                "new_value": _json_deserialize(h.get("new_value_json", "null")),
                "changed_at": h["changed_at"].isoformat() if h.get("changed_at") else None,
                "changed_by": h.get("changed_by"),
                "change_reason": h.get("change_reason"),
            }
            for h in history
        ]

    return result


@function_tool(strict_mode=False)
def edit_property(
    # Location (all nullable)
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    state_province: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    coordinates_lat: float | None = None,
    coordinates_lng: float | None = None,
    # Capacity
    max_guests: int | None = None,
    bedrooms: int | None = None,
    beds: int | None = None,
    bathrooms: float | None = None,
    # Type
    property_type: str | None = None,
    # Compliance
    permit_number: str | None = None,
    permit_expiry: str | None = None,  # ISO date string
    tax_id: str | None = None,
    # Flexible attribute (key-value)
    attribute_key: str | None = None,
    attribute_value: str | int | float | bool | list[str] | None = None,
    attribute_category: str | None = None,  # amenity, rule, access, etc.
    # Evidence for traceability
    evidence: EvidenceData | None = None
) -> dict:
    """
    Create or update property fields.

    Use this to record structured property information with source traceability.
    Can update multiple hard attributes at once, or set a flexible attribute.

    **Hard Attributes (typed fields):**
    - Location: address_line1, address_line2, city, state_province, postal_code, country, coordinates_lat, coordinates_lng
    - Capacity: max_guests, bedrooms, beds, bathrooms
    - Type: property_type (e.g., "house", "apartment", "villa")
    - Compliance: permit_number, permit_expiry, tax_id

    **Flexible Attributes (via attribute_key/attribute_value):**
    Use for amenities, rules, access info, etc. that don't have dedicated fields.
    Examples: wifi_password, pool_hours, pet_policy, check_in_time

    Args:
        address_line1: Street address
        address_line2: Apartment/suite number
        city: City name
        state_province: State or province
        postal_code: Postal/ZIP code
        country: Country name
        coordinates_lat: Latitude
        coordinates_lng: Longitude
        max_guests: Maximum occupancy
        bedrooms: Number of bedrooms
        beds: Total number of beds
        bathrooms: Number of bathrooms (use 1.5 for one and a half)
        property_type: Type of property (house, apartment, villa, condo, etc.)
        permit_number: Rental permit/license number
        permit_expiry: Permit expiration date (ISO format: YYYY-MM-DD)
        tax_id: Tax registration ID
        attribute_key: Key for a flexible attribute (e.g., "wifi_password")
        attribute_value: Value for the flexible attribute
        attribute_category: Category: amenity, rule, access, appliance, contact, local, pricing, policy, other
        evidence: Source evidence for traceability

    Returns:
        Dict with status, property_id, updated_fields, and any created IDs

    Example:
        # Update multiple hard attributes
        edit_property(
            address_line1="123 Beach Rd",
            city="Miami",
            country="USA",
            bedrooms=3,
            bathrooms=2.5
        )

        # Set a flexible attribute
        edit_property(
            attribute_key="wifi_password",
            attribute_value="beach2024",
            attribute_category="access"
        )
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    now = datetime.now(timezone.utc)
    evidence_id = _create_evidence_record(evidence)

    # Get or create property
    prop = db_property.get_property_by_session(session_id)
    created_property = False

    if not prop:
        # Create new property
        property_id = str(uuid.uuid4())
        prop = {
            "id": property_id,
            "session_id": session_id,
            "status": PropertyStatus.DRAFT.value,
            "address_line1": None,
            "address_line2": None,
            "city": None,
            "state_province": None,
            "postal_code": None,
            "country": None,
            "coordinates_lat": None,
            "coordinates_lng": None,
            "max_guests": None,
            "bedrooms": None,
            "beds": None,
            "bathrooms": None,
            "property_type": None,
            "permit_number": None,
            "permit_expiry": None,
            "tax_id": None,
            "validated_at": None,
            "validated_by_ip": None,
            "completeness_score": 0.0,
            "created_at": now,
            "updated_at": now,
        }
        created_property = True
    else:
        property_id = prop["id"]

    # Collect hard attribute updates
    updated_fields = []

    hard_attrs = {
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state_province": state_province,
        "postal_code": postal_code,
        "country": country,
        "coordinates_lat": coordinates_lat,
        "coordinates_lng": coordinates_lng,
        "max_guests": max_guests,
        "bedrooms": bedrooms,
        "beds": beds,
        "bathrooms": bathrooms,
        "property_type": property_type,
        "permit_number": permit_number,
        "tax_id": tax_id,
    }

    for field, value in hard_attrs.items():
        if value is not None:
            prop[field] = value
            updated_fields.append(field)

    # Handle permit_expiry (date conversion)
    if permit_expiry is not None:
        try:
            prop["permit_expiry"] = date.fromisoformat(permit_expiry)
            updated_fields.append("permit_expiry")
        except ValueError:
            return {
                "status": "error",
                "message": f"Invalid date format for permit_expiry: {permit_expiry}. Use YYYY-MM-DD.",
            }

    # Calculate completeness score and update timestamp
    completeness = _calculate_completeness(prop)
    prop["completeness_score"] = completeness
    prop["updated_at"] = now

    # Save property (upsert handles both create and update)
    db.insert("properties", prop)

    # Handle flexible attribute
    attribute_updated = None
    if attribute_key is not None:
        # Check if attribute exists
        existing_attr = db_property.get_attribute_by_key(property_id, attribute_key)

        # Determine category
        cat = AttributeCategory.OTHER
        if attribute_category:
            try:
                cat = AttributeCategory(attribute_category)
            except ValueError:
                pass  # Use default OTHER

        if existing_attr:
            # Record history before update
            history_id = str(uuid.uuid4())
            history_record = {
                "id": history_id,
                "attribute_id": existing_attr["id"],
                "old_value_json": existing_attr.get("value_json", "null"),
                "new_value_json": _json_serialize(attribute_value),
                "changed_at": now,
                "changed_by": "arbie",
                "change_reason": None,
                "created_at": now,
                "updated_at": now,
            }
            db.insert("attribute_history", history_record)

            # Update existing attribute
            existing_attr["value_json"] = _json_serialize(attribute_value)
            existing_attr["value_type"] = _get_value_type(attribute_value)
            existing_attr["category"] = cat.value
            existing_attr["evidence_id"] = evidence_id or existing_attr.get("evidence_id")
            existing_attr["updated_by"] = "arbie"
            existing_attr["updated_at"] = now
            db.insert("property_attributes", existing_attr)  # Upsert
        else:
            # Create new attribute
            attr_id = str(uuid.uuid4())
            new_attr = {
                "id": attr_id,
                "property_id": property_id,
                "key": attribute_key,
                "value_json": _json_serialize(attribute_value),
                "value_type": _get_value_type(attribute_value),
                "category": cat.value,
                "display_name": attribute_key.replace("_", " ").title(),
                "evidence_id": evidence_id,
                "confidence": 1.0,
                "created_by": "arbie",
                "updated_by": None,
                "created_at": now,
                "updated_at": now,
            }
            db.insert("property_attributes", new_attr)

        attribute_updated = attribute_key

    return {
        "status": "success",
        "property_id": property_id,
        "created": created_property,
        "updated_fields": updated_fields,
        "attribute_updated": attribute_updated,
        "evidence_id": evidence_id,
        "completeness_score": completeness,
    }


@function_tool(strict_mode=False)
def edit_room(
    room_id: str | None = None,  # None = create new room
    # Room properties
    room_type: str | None = None,  # bedroom, bathroom, kitchen, etc.
    name: str | None = None,
    floor: int | None = None,
    description: str | None = None,
    # Bedroom-specific
    bed_count: int | None = None,
    bed_types: list[str] | None = None,
    # Bathroom-specific
    has_shower: bool | None = None,
    has_bathtub: bool | None = None,
    is_ensuite: bool | None = None,
    # Amenities
    amenities: list[str] | None = None,
) -> dict:
    """
    Create or update a room in the property.

    Use this to record room information. Rooms represent physical spaces
    like bedrooms, bathrooms, kitchen, living areas, etc.

    Args:
        room_id: ID of existing room to update. Omit to create a new room.
        room_type: Type of room (bedroom, bathroom, kitchen, living_room, dining_room, office, etc.)
        name: Custom name (e.g., "Master Bedroom", "Kids Room")
        floor: Floor number (0 = ground floor)
        description: Text description of the room
        bed_count: Number of beds (for bedrooms)
        bed_types: List of bed types: king, queen, twin, bunk, sofa_bed
        has_shower: Has a shower (for bathrooms)
        has_bathtub: Has a bathtub (for bathrooms)
        is_ensuite: Is attached to a bedroom (for bathrooms)
        amenities: List of room amenities (e.g., TV, air_conditioning, desk)

    Returns:
        Dict with status, room_id, and whether room was created

    Example:
        # Create a new bedroom
        edit_room(
            room_type="bedroom",
            name="Master Bedroom",
            floor=1,
            bed_count=1,
            bed_types=["king"],
            amenities=["TV", "air_conditioning", "ensuite"]
        )

        # Update an existing room
        edit_room(
            room_id="abc123",
            bed_count=2,
            bed_types=["queen", "twin"]
        )
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    # Get property for this session
    prop = db_property.get_property_by_session(session_id)
    if not prop:
        return {
            "status": "error",
            "message": "No property exists for this session. Use edit_property first.",
        }

    property_id = prop["id"]
    now = datetime.now(timezone.utc)
    created = False

    if room_id is None:
        # Create new room
        if room_type is None:
            return {
                "status": "error",
                "message": "room_type is required when creating a new room.",
            }

        # Validate room_type
        try:
            rt = RoomType(room_type)
        except ValueError:
            return {
                "status": "error",
                "message": f"Invalid room_type: {room_type}. Valid types: bedroom, bathroom, kitchen, living_room, etc.",
            }

        room_id = str(uuid.uuid4())
        room = {
            "id": room_id,
            "property_id": property_id,
            "room_type": rt.value,
            "name": name,
            "floor": floor,
            "description": description,
            "objects_detected": [],
            "amenities": amenities or [],
            "bed_count": bed_count,
            "bed_types": bed_types or [],
            "has_shower": has_shower,
            "has_bathtub": has_bathtub,
            "is_ensuite": is_ensuite,
            "visual_signature": None,
            "confidence": 1.0,
            "created_at": now,
            "updated_at": now,
        }
        db.insert("rooms", room)
        created = True
    else:
        # Update existing room
        room = db.get_by_id("rooms", room_id)
        if not room:
            return {
                "status": "error",
                "message": f"Room not found: {room_id}",
            }

        # Verify room belongs to this property
        if room.get("property_id") != property_id:
            return {
                "status": "error",
                "message": "Room does not belong to this session's property.",
            }

        # Apply updates
        if room_type is not None:
            try:
                rt = RoomType(room_type)
                room["room_type"] = rt.value
            except ValueError:
                return {
                    "status": "error",
                    "message": f"Invalid room_type: {room_type}",
                }

        if name is not None:
            room["name"] = name
        if floor is not None:
            room["floor"] = floor
        if description is not None:
            room["description"] = description
        if bed_count is not None:
            room["bed_count"] = bed_count
        if bed_types is not None:
            room["bed_types"] = bed_types
        if has_shower is not None:
            room["has_shower"] = has_shower
        if has_bathtub is not None:
            room["has_bathtub"] = has_bathtub
        if is_ensuite is not None:
            room["is_ensuite"] = is_ensuite
        if amenities is not None:
            room["amenities"] = amenities

        room["updated_at"] = now
        db.insert("rooms", room)  # Upsert

    return {
        "status": "success",
        "room_id": room_id,
        "created": created,
    }


@function_tool
def edit_photo(
    photo_id: str,
    # Room assignment
    room_id: str | None = None,
    # Display settings
    is_primary: bool | None = None,
    is_room_primary: bool | None = None,
    display_order: int | None = None,
    # Metadata
    description: str | None = None,
    tags: list[str] | None = None
) -> dict:
    """
    Update photo metadata and room assignment.

    Use this to assign photos to rooms, set display order, and update metadata.

    Args:
        photo_id: ID of the photo to update (required)
        room_id: Assign photo to a room (use room ID from edit_room)
        is_primary: Set as the main listing photo
        is_room_primary: Set as the main photo for its assigned room
        display_order: Order in the photo gallery (lower = earlier)
        description: Text description of what's shown in the photo
        tags: List of tags/labels for the photo

    Returns:
        Dict with status and photo_id

    Example:
        # Assign photo to a room and make it primary for that room
        edit_photo(
            photo_id="photo123",
            room_id="room456",
            is_room_primary=True,
            description="Master bedroom with king bed"
        )
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    # Get property for this session
    prop = db_property.get_property_by_session(session_id)
    if not prop:
        return {
            "status": "error",
            "message": "No property exists for this session.",
        }

    property_id = prop["id"]

    # Get the photo
    photo = db.get_by_id("property_photos", photo_id)
    if not photo:
        return {
            "status": "error",
            "message": f"Photo not found: {photo_id}",
        }

    # Verify photo belongs to this property
    if photo.get("property_id") != property_id:
        return {
            "status": "error",
            "message": "Photo does not belong to this session's property.",
        }

    now = datetime.now(timezone.utc)

    # Apply updates
    if room_id is not None:
        # Verify room exists and belongs to property
        if room_id != "":  # Allow unsetting room with empty string
            room = db.get_by_id("rooms", room_id)
            if not room:
                return {
                    "status": "error",
                    "message": f"Room not found: {room_id}",
                }
            if room.get("property_id") != property_id:
                return {
                    "status": "error",
                    "message": "Room does not belong to this property.",
                }
        photo["room_id"] = room_id if room_id != "" else None

    if is_primary is not None:
        photo["is_primary"] = is_primary
    if is_room_primary is not None:
        photo["is_room_primary"] = is_room_primary
    if display_order is not None:
        photo["display_order"] = display_order
    if description is not None:
        photo["description"] = description
    if tags is not None:
        photo["tags"] = tags

    photo["updated_at"] = now
    db.insert("property_photos", photo)  # Upsert

    return {
        "status": "success",
        "photo_id": photo_id,
    }
