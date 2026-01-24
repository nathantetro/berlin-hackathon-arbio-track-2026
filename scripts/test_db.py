"""Test database operations with Tower Iceberg tables.

Run with: tower run local --script scripts/test_db.py
"""

import uuid
from datetime import datetime, timezone

from arbie.db.schemas import ALL_TABLES
from arbie.services import db


def test_init_tables() -> None:
    """Test table initialization."""
    print("=" * 60)
    print("Testing: init_all_tables()")
    print("=" * 60)

    db.init_all_tables()
    print(f"✓ Initialized {len(ALL_TABLES)} tables: {', '.join(ALL_TABLES)}")


def test_user_crud() -> None:
    """Test user CRUD operations."""
    print("\n" + "=" * 60)
    print("Testing: User CRUD")
    print("=" * 60)

    user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    now = datetime.now(timezone.utc)

    # Insert
    user_data = {
        "id": user_id,
        "email": email,
        "name": "Test User",
        "phone": "+1234567890",
        "company": "Test Company",
        "created_at": now,
        "updated_at": now,
    }
    db.insert("users", user_data)
    print(f"✓ Inserted user: {user_id}")

    # Read by ID
    user = db.user.get_user(user_id)
    assert user is not None, "User should exist"
    assert user["email"] == email
    print(f"✓ Read user by ID: {user['name']}")

    # Read by email
    user = db.user.get_user_by_email(email)
    assert user is not None, "User should exist by email"
    assert user["id"] == user_id
    print(f"✓ Read user by email: {user['email']}")

    # Update (upsert)
    user_data["name"] = "Updated User"
    user_data["updated_at"] = datetime.now(timezone.utc)
    db.insert("users", user_data)
    user = db.user.get_user(user_id)
    assert user["name"] == "Updated User"
    print(f"✓ Updated user name: {user['name']}")

    # Count
    count = db.count("users")
    assert count >= 1
    print(f"✓ User count: {count}")


def test_session_crud() -> None:
    """Test session CRUD operations."""
    print("\n" + "=" * 60)
    print("Testing: Session CRUD")
    print("=" * 60)

    session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
    ref_code = f"ARB-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)

    # Insert session
    session_data = {
        "id": session_id,
        "reference_code": ref_code,
        "user_id": None,
        "property_id": None,
        "status": "RECEIVED",
        "status_reason": "Initial submission",
        "thread_id": None,
        "last_activity_at": now,
        "follow_up_count": 0,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    db.insert("sessions", session_data)
    print(f"✓ Inserted session: {session_id}")

    # Read by ID
    session = db.session.get_session(session_id)
    assert session is not None
    assert session["status"] == "RECEIVED"
    print(f"✓ Read session: {session['reference_code']}")

    # Read by reference code
    session = db.session.get_session_by_reference(ref_code)
    assert session is not None
    assert session["id"] == session_id
    print(f"✓ Read by reference: {ref_code}")

    # Query by status
    sessions = db.session.get_sessions_by_status("RECEIVED")
    assert any(s["id"] == session_id for s in sessions)
    print(f"✓ Query by status: found {len(sessions)} RECEIVED sessions")

    # Get active sessions
    active = db.session.get_active_sessions()
    assert any(s["id"] == session_id for s in active)
    print(f"✓ Active sessions: {len(active)}")

    # Update status
    session_data["status"] = "EXTRACTING"
    session_data["updated_at"] = datetime.now(timezone.utc)
    db.insert("sessions", session_data)
    session = db.session.get_session(session_id)
    assert session["status"] == "EXTRACTING"
    print(f"✓ Updated status: {session['status']}")


def test_property_crud() -> None:
    """Test property CRUD operations."""
    print("\n" + "=" * 60)
    print("Testing: Property CRUD")
    print("=" * 60)

    property_id = f"test-prop-{uuid.uuid4().hex[:8]}"
    session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Insert property
    property_data = {
        "id": property_id,
        "session_id": session_id,
        "status": "DRAFT",
        "address_line1": "123 Test Street",
        "address_line2": "Apt 4B",
        "city": "Berlin",
        "state_province": "Berlin",
        "postal_code": "10115",
        "country": "DE",
        "coordinates_lat": 52.5200,
        "coordinates_lng": 13.4050,
        "max_guests": 4,
        "bedrooms": 2,
        "beds": 3,
        "bathrooms": 1.5,
        "property_type": "APARTMENT",
        "permit_number": None,
        "permit_expiry": None,
        "tax_id": None,
        "validated_at": None,
        "validated_by_ip": None,
        "completeness_score": 0.6,
        "created_at": now,
        "updated_at": now,
    }
    db.insert("properties", property_data)
    print(f"✓ Inserted property: {property_id}")

    # Read by ID
    prop = db.property.get_property(property_id)
    assert prop is not None
    assert prop["city"] == "Berlin"
    print(f"✓ Read property: {prop['address_line1']}, {prop['city']}")

    # Read by session
    prop = db.property.get_property_by_session(session_id)
    assert prop is not None
    assert prop["id"] == property_id
    print(f"✓ Read by session: {prop['id']}")

    # Query by status
    props = db.property.get_properties_by_status("DRAFT")
    assert any(p["id"] == property_id for p in props)
    print(f"✓ Query by status: found {len(props)} DRAFT properties")


def test_property_attributes() -> None:
    """Test property attributes CRUD."""
    print("\n" + "=" * 60)
    print("Testing: Property Attributes")
    print("=" * 60)

    attr_id = f"test-attr-{uuid.uuid4().hex[:8]}"
    property_id = f"test-prop-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Insert attribute
    attr_data = {
        "id": attr_id,
        "property_id": property_id,
        "key": "wifi_speed",
        "value_json": '"100 Mbps"',
        "value_type": "string",
        "category": "amenities",
        "display_name": "WiFi Speed",
        "evidence_id": None,
        "confidence": 0.95,
        "created_by": "arbie",
        "updated_by": "arbie",
        "created_at": now,
        "updated_at": now,
    }
    db.insert("property_attributes", attr_data)
    print(f"✓ Inserted attribute: {attr_id}")

    # Get attributes by property
    attrs = db.property.get_attributes_by_property(property_id)
    assert len(attrs) >= 1
    print(f"✓ Read attributes: found {len(attrs)} for property")

    # Get specific attribute
    attr = db.property.get_attribute_by_key(property_id, "wifi_speed")
    assert attr is not None
    assert attr["value_json"] == '"100 Mbps"'
    print(f"✓ Read by key: {attr['display_name']} = {attr['value_json']}")


def test_insert_many() -> None:
    """Test batch insert."""
    print("\n" + "=" * 60)
    print("Testing: Batch Insert")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    property_id = f"test-prop-{uuid.uuid4().hex[:8]}"

    rooms = [
        {
            "id": f"test-room-{uuid.uuid4().hex[:8]}",
            "property_id": property_id,
            "room_type": "BEDROOM",
            "name": "Master Bedroom",
            "floor": 1,
            "description": "Large bedroom with king bed",
            "objects_detected": ["bed", "wardrobe", "nightstand"],
            "amenities": ["air_conditioning"],
            "bed_count": 1,
            "bed_types": ["king"],
            "has_shower": False,
            "has_bathtub": False,
            "is_ensuite": False,
            "visual_signature": None,
            "confidence": 0.9,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": f"test-room-{uuid.uuid4().hex[:8]}",
            "property_id": property_id,
            "room_type": "BATHROOM",
            "name": "Main Bathroom",
            "floor": 1,
            "description": "Full bathroom with shower and tub",
            "objects_detected": ["toilet", "sink", "bathtub", "shower"],
            "amenities": ["towels", "toiletries"],
            "bed_count": 0,
            "bed_types": [],
            "has_shower": True,
            "has_bathtub": True,
            "is_ensuite": False,
            "visual_signature": None,
            "confidence": 0.85,
            "created_at": now,
            "updated_at": now,
        },
    ]

    db.insert_many("rooms", rooms)
    print(f"✓ Batch inserted {len(rooms)} rooms")

    # Verify
    fetched_rooms = db.property.get_rooms_by_property(property_id)
    assert len(fetched_rooms) == 2
    print(f"✓ Verified: found {len(fetched_rooms)} rooms for property")


def test_exists_and_count() -> None:
    """Test exists and count helpers."""
    print("\n" + "=" * 60)
    print("Testing: Exists and Count")
    print("=" * 60)

    # Count users
    user_count = db.count("users")
    print(f"✓ Users count: {user_count}")

    # Count sessions
    session_count = db.count("sessions")
    print(f"✓ Sessions count: {session_count}")

    # Check exists
    fake_id = "nonexistent-id-12345"
    assert not db.exists("users", fake_id)
    print(f"✓ Exists check: {fake_id} correctly not found")


def main() -> int:
    """Run all database tests."""
    print("\n🧪 ARBIE DATABASE TESTS")
    print("=" * 60)

    try:
        test_init_tables()
        test_user_crud()
        test_session_crud()
        test_property_crud()
        test_property_attributes()
        test_insert_many()
        test_exists_and_count()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
