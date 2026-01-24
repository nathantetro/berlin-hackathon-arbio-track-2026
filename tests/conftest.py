"""Pytest configuration and fixtures."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import polars as pl


@pytest.fixture
def mock_tower_table():
    """Create a mock Tower table that stores data in memory."""
    storage = {}
    schemas = {}  # Store schemas for empty DataFrame creation

    class MockTable:
        def __init__(self, name: str):
            self.name = name
            if name not in storage:
                storage[name] = []

        def create_if_not_exists(self, schema):
            """Store schema for creating properly typed empty DataFrames."""
            schemas[self.name] = schema
            return self

        def read(self) -> pl.DataFrame:
            """Return data as Polars DataFrame (used by base.py operations)."""
            if not storage[self.name]:
                # Return empty DataFrame with correct schema if available
                if self.name in schemas:
                    import pyarrow as pa
                    empty_table = schemas[self.name].empty_table()
                    return pl.from_arrow(empty_table)
                return pl.DataFrame({"id": []})  # Fallback with id column
            return pl.DataFrame(storage[self.name])

        def to_polars(self) -> pl.LazyFrame:
            """Return data as Polars LazyFrame (for lazy queries)."""
            return self.read().lazy()

        def upsert(self, pa_table, join_cols):
            """Upsert rows based on join columns."""
            rows = pa_table.to_pylist()
            existing = storage[self.name]

            for row in rows:
                # Find by join columns and update or insert
                found = False
                for i, existing_row in enumerate(existing):
                    match = all(existing_row.get(col) == row.get(col) for col in join_cols)
                    if match:
                        existing[i] = row
                        found = True
                        break
                if not found:
                    existing.append(row)

        def insert(self, pa_table):
            """Insert rows without upsert logic."""
            rows = pa_table.to_pylist()
            storage[self.name].extend(rows)

        def load(self):
            """Load existing table (returns self for compatibility)."""
            return self

    def get_table(name: str):
        return MockTable(name)

    return get_table, storage


@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    now = datetime.now(timezone.utc)
    return {
        "id": "user-test-123",
        "email": "test@example.com",
        "name": "Test User",
        "phone": "+1234567890",
        "company": "Test Co",
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
def sample_session():
    """Sample session data for testing."""
    now = datetime.now(timezone.utc)
    return {
        "id": "sess-test-123",
        "reference_code": "ARB-TEST01",
        "user_id": "user-test-123",
        "property_id": None,
        "status": "RECEIVED",
        "status_reason": "Test session",
        "thread_id": None,
        "last_activity_at": now,
        "follow_up_count": 0,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }


@pytest.fixture
def sample_property():
    """Sample property data for testing."""
    now = datetime.now(timezone.utc)
    return {
        "id": "prop-test-123",
        "session_id": "sess-test-123",
        "status": "DRAFT",
        "address_line1": "123 Test St",
        "address_line2": None,
        "city": "Berlin",
        "state_province": "Berlin",
        "postal_code": "10115",
        "country": "DE",
        "coordinates_lat": 52.52,
        "coordinates_lng": 13.405,
        "max_guests": 4,
        "bedrooms": 2,
        "beds": 2,
        "bathrooms": 1.0,
        "property_type": "APARTMENT",
        "permit_number": None,
        "permit_expiry": None,
        "tax_id": None,
        "validated_at": None,
        "validated_by_ip": None,
        "completeness_score": 0.5,
        "created_at": now,
        "updated_at": now,
    }
