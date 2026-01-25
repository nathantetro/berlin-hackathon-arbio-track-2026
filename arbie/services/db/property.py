"""Property, attributes, rooms, and photos database operations."""

import polars as pl

from arbie.services.db.base import get_by_id, query, query_sorted

PROPERTIES_TABLE = "properties"
ATTRIBUTES_TABLE = "property_attributes"
ATTRIBUTE_HISTORY_TABLE = "attribute_history"
ROOMS_TABLE = "rooms"
PHOTOS_TABLE = "property_photos"


# === Property Operations ===


def get_property(property_id: str) -> dict | None:
    """Get a property by ID."""
    return get_by_id(PROPERTIES_TABLE, property_id)


def get_property_by_session(session_id: str) -> dict | None:
    """Get the property for a session."""
    rows = query(PROPERTIES_TABLE, pl.col("session_id") == session_id)
    return rows[0] if rows else None


def get_properties_by_status(status: str) -> list[dict]:
    """Get properties by status."""
    return query(PROPERTIES_TABLE, pl.col("status") == status)


# === Property Attributes Operations ===


def get_attributes_by_property(property_id: str) -> list[dict]:
    """Get all attributes for a property."""
    return query(ATTRIBUTES_TABLE, pl.col("property_id") == property_id)


def get_attribute_by_key(property_id: str, key: str) -> dict | None:
    """Get a specific attribute by property and key."""
    rows = query(
        ATTRIBUTES_TABLE,
        (pl.col("property_id") == property_id) & (pl.col("key") == key),
    )
    return rows[0] if rows else None


# === Room Operations ===


def get_rooms_by_property(property_id: str) -> list[dict]:
    """Get all rooms for a property."""
    return query(ROOMS_TABLE, pl.col("property_id") == property_id)


# === Photo Operations ===


def get_photos_by_property(property_id: str) -> list[dict]:
    """Get all photos for a property."""
    return query(PHOTOS_TABLE, pl.col("property_id") == property_id)


def get_photos_by_room(room_id: str) -> list[dict]:
    """Get all photos for a room."""
    return query(PHOTOS_TABLE, pl.col("room_id") == room_id)


# === Attribute History Operations ===


def get_attribute_history(attribute_id: str) -> list[dict]:
    """Get change history for an attribute."""
    return query_sorted(
        ATTRIBUTE_HISTORY_TABLE,
        pl.col("attribute_id") == attribute_id,
        "changed_at",
        descending=True
    )


def get_all_attribute_history_by_property(property_id: str) -> list[dict]:
    """Get all attribute history for a property's attributes."""
    attrs = get_attributes_by_property(property_id)
    attr_ids = [a["id"] for a in attrs]
    if not attr_ids:
        return []
    return query_sorted(
        ATTRIBUTE_HISTORY_TABLE,
        pl.col("attribute_id").is_in(attr_ids),
        "changed_at",
        descending=True
    )
