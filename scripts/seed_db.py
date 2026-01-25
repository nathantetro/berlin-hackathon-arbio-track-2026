"""Seed database with test data via Tower.

Run with: tower run local (after updating Towerfile script)
"""

import uuid
from datetime import datetime, timezone

from arbie.services import db


def seed_users() -> list[str]:
    """Create test users."""
    print("Seeding users...")
    user_ids = []
    now = datetime.now(timezone.utc)

    users = [
        {
            "id": f"user-{uuid.uuid4().hex[:8]}",
            "email": "alice@example.com",
            "name": "Alice Owner",
            "phone": "+49123456789",
            "company": "Berlin Properties GmbH",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": f"user-{uuid.uuid4().hex[:8]}",
            "email": "bob@example.com",
            "name": "Bob Landlord",
            "phone": "+49987654321",
            "company": "Munich Rentals",
            "created_at": now,
            "updated_at": now,
        },
    ]

    for user in users:
        db.insert("users", user)
        user_ids.append(user["id"])
        print(f"  Created user: {user['name']} ({user['email']})")

    return user_ids


def seed_sessions(user_ids: list[str]) -> list[str]:
    """Create test sessions."""
    print("\nSeeding sessions...")
    session_ids = []
    now = datetime.now(timezone.utc)

    for i, user_id in enumerate(user_ids):
        session = {
            "id": f"sess-{uuid.uuid4().hex[:8]}",
            "reference_code": f"ARB-TEST{i+1:02d}",
            "user_id": user_id,
            "property_id": None,
            "status": "RECEIVED",
            "status_reason": "Initial submission via email",
            "thread_id": None,
            "last_activity_at": now,
            "follow_up_count": 0,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        db.insert("sessions", session)
        session_ids.append(session["id"])
        print(f"  Created session: {session['reference_code']}")

    return session_ids


def seed_properties(session_ids: list[str]) -> list[str]:
    """Create test properties."""
    print("\nSeeding properties...")
    property_ids = []
    now = datetime.now(timezone.utc)

    properties = [
        {
            "id": f"prop-{uuid.uuid4().hex[:8]}",
            "session_id": session_ids[0] if session_ids else None,
            "status": "DRAFT",
            "address_line1": "Friedrichstrasse 123",
            "address_line2": "4. OG",
            "city": "Berlin",
            "state_province": "Berlin",
            "postal_code": "10117",
            "country": "DE",
            "coordinates_lat": 52.5200,
            "coordinates_lng": 13.4050,
            "max_guests": 4,
            "bedrooms": 2,
            "beds": 3,
            "bathrooms": 1.0,
            "property_type": "APARTMENT",
            "permit_number": None,
            "permit_expiry": None,
            "tax_id": None,
            "validated_at": None,
            "validated_by_ip": None,
            "completeness_score": 0.6,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": f"prop-{uuid.uuid4().hex[:8]}",
            "session_id": session_ids[1] if len(session_ids) > 1 else None,
            "status": "DRAFT",
            "address_line1": "Maximilianstrasse 45",
            "address_line2": None,
            "city": "Munich",
            "state_province": "Bavaria",
            "postal_code": "80539",
            "country": "DE",
            "coordinates_lat": 48.1351,
            "coordinates_lng": 11.5820,
            "max_guests": 6,
            "bedrooms": 3,
            "beds": 4,
            "bathrooms": 2.0,
            "property_type": "HOUSE",
            "permit_number": "MUC-2024-12345",
            "permit_expiry": None,
            "tax_id": None,
            "validated_at": None,
            "validated_by_ip": None,
            "completeness_score": 0.8,
            "created_at": now,
            "updated_at": now,
        },
    ]

    for prop in properties:
        db.insert("properties", prop)
        property_ids.append(prop["id"])
        print(f"  Created property: {prop['address_line1']}, {prop['city']}")

    return property_ids


def verify_data() -> None:
    """Verify inserted data can be read back."""
    print("\n" + "=" * 60)
    print("VERIFYING DATA")
    print("=" * 60)

    user_count = db.count("users")
    session_count = db.count("sessions")
    property_count = db.count("properties")

    print(f"Users: {user_count}")
    print(f"Sessions: {session_count}")
    print(f"Properties: {property_count}")

    # Query some data
    print("\nActive sessions:")
    active = db.session.get_active_sessions()
    for s in active[:5]:
        print(f"  - {s['reference_code']}: {s['status']}")

    print("\nDraft properties:")
    drafts = db.property.get_properties_by_status("DRAFT")
    for p in drafts[:5]:
        print(f"  - {p['address_line1']}, {p['city']}")


def main() -> int:
    """Seed database with test data."""
    print("=" * 60)
    print("SEEDING ARBIE DATABASE")
    print("=" * 60)

    try:
        # Initialize tables first
        print("\nInitializing tables...")
        db.init_all_tables()
        print("Tables initialized.")

        # Seed data
        user_ids = seed_users()
        session_ids = seed_sessions(user_ids)
        property_ids = seed_properties(session_ids)

        # Verify
        verify_data()

        print("\n" + "=" * 60)
        print("SEEDING COMPLETE")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
