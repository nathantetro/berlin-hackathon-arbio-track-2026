"""Unit tests for database services."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import polars as pl


class TestBaseOperations:
    """Test base CRUD operations."""

    def test_prepare_data_handles_datetime(self):
        """Test that _prepare_data converts naive datetimes to UTC."""
        from arbie.services.db.base import _prepare_data

        naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        data = {"created_at": naive_dt, "name": "test"}

        result = _prepare_data(data)

        assert result["created_at"].tzinfo is not None
        assert result["name"] == "test"

    def test_prepare_data_preserves_aware_datetime(self):
        """Test that _prepare_data preserves timezone-aware datetimes."""
        from arbie.services.db.base import _prepare_data

        aware_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = {"created_at": aware_dt}

        result = _prepare_data(data)

        assert result["created_at"] == aware_dt

    def test_prepare_data_handles_enum(self):
        """Test that _prepare_data extracts enum values."""
        from arbie.services.db.base import _prepare_data
        from enum import Enum

        class Status(Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        data = {"status": Status.ACTIVE, "count": 5}

        result = _prepare_data(data)

        assert result["status"] == "active"
        assert result["count"] == 5


class TestUserService:
    """Test user service operations."""

    def test_get_user_returns_none_for_missing(self, mock_tower_table):
        """Test get_user returns None when user doesn't exist."""
        get_table, storage = mock_tower_table
        storage["users"] = []

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import user

            result = user.get_user("nonexistent-id")
            assert result is None

    def test_get_user_returns_user(self, mock_tower_table, sample_user):
        """Test get_user returns user when exists."""
        get_table, storage = mock_tower_table
        storage["users"] = [sample_user]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import user

            result = user.get_user(sample_user["id"])
            assert result is not None
            assert result["email"] == sample_user["email"]

    def test_get_user_by_email(self, mock_tower_table, sample_user):
        """Test get_user_by_email finds user."""
        get_table, storage = mock_tower_table
        storage["users"] = [sample_user]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import user

            result = user.get_user_by_email(sample_user["email"])
            assert result is not None
            assert result["id"] == sample_user["id"]

    def test_get_user_by_email_not_found(self, mock_tower_table):
        """Test get_user_by_email returns None when not found."""
        get_table, storage = mock_tower_table
        storage["users"] = []

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import user

            result = user.get_user_by_email("missing@example.com")
            assert result is None


class TestSessionService:
    """Test session service operations."""

    def test_get_session(self, mock_tower_table, sample_session):
        """Test get_session returns session."""
        get_table, storage = mock_tower_table
        storage["sessions"] = [sample_session]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import session

            result = session.get_session(sample_session["id"])
            assert result is not None
            assert result["reference_code"] == sample_session["reference_code"]

    def test_get_session_by_reference(self, mock_tower_table, sample_session):
        """Test get_session_by_reference finds session."""
        get_table, storage = mock_tower_table
        storage["sessions"] = [sample_session]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import session

            result = session.get_session_by_reference(sample_session["reference_code"])
            assert result is not None
            assert result["id"] == sample_session["id"]

    def test_get_sessions_by_status(self, mock_tower_table, sample_session):
        """Test get_sessions_by_status filters correctly."""
        get_table, storage = mock_tower_table
        other_session = {**sample_session, "id": "sess-2", "status": "EXTRACTING"}
        storage["sessions"] = [sample_session, other_session]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import session

            received = session.get_sessions_by_status("RECEIVED")
            assert len(received) == 1
            assert received[0]["id"] == sample_session["id"]

    def test_get_active_sessions_excludes_validated(self, mock_tower_table, sample_session):
        """Test get_active_sessions excludes VALIDATED status."""
        get_table, storage = mock_tower_table
        validated_session = {**sample_session, "id": "sess-validated", "status": "VALIDATED"}
        storage["sessions"] = [sample_session, validated_session]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import session

            active = session.get_active_sessions()
            assert len(active) == 1
            assert active[0]["status"] != "VALIDATED"


class TestPropertyService:
    """Test property service operations."""

    def test_get_property(self, mock_tower_table, sample_property):
        """Test get_property returns property."""
        get_table, storage = mock_tower_table
        storage["properties"] = [sample_property]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import property

            result = property.get_property(sample_property["id"])
            assert result is not None
            assert result["city"] == "Berlin"

    def test_get_property_by_session(self, mock_tower_table, sample_property):
        """Test get_property_by_session finds property."""
        get_table, storage = mock_tower_table
        storage["properties"] = [sample_property]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import property

            result = property.get_property_by_session(sample_property["session_id"])
            assert result is not None
            assert result["id"] == sample_property["id"]

    def test_get_attributes_by_property(self, mock_tower_table):
        """Test get_attributes_by_property returns attributes."""
        get_table, storage = mock_tower_table
        now = datetime.now(timezone.utc)
        attrs = [
            {
                "id": "attr-1",
                "property_id": "prop-123",
                "key": "wifi",
                "value_json": '"fast"',
                "value_type": "string",
                "category": "amenities",
                "display_name": "WiFi",
                "evidence_id": None,
                "confidence": 0.9,
                "created_by": "arbie",
                "updated_by": "arbie",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "attr-2",
                "property_id": "prop-123",
                "key": "parking",
                "value_json": "true",
                "value_type": "boolean",
                "category": "amenities",
                "display_name": "Parking",
                "evidence_id": None,
                "confidence": 0.85,
                "created_by": "arbie",
                "updated_by": "arbie",
                "created_at": now,
                "updated_at": now,
            },
        ]
        storage["property_attributes"] = attrs

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import property

            result = property.get_attributes_by_property("prop-123")
            assert len(result) == 2

    def test_get_attribute_by_key(self, mock_tower_table):
        """Test get_attribute_by_key finds specific attribute."""
        get_table, storage = mock_tower_table
        now = datetime.now(timezone.utc)
        storage["property_attributes"] = [
            {
                "id": "attr-1",
                "property_id": "prop-123",
                "key": "wifi",
                "value_json": '"100mbps"',
                "value_type": "string",
                "category": "amenities",
                "display_name": "WiFi Speed",
                "evidence_id": None,
                "confidence": 0.9,
                "created_by": "arbie",
                "updated_by": "arbie",
                "created_at": now,
                "updated_at": now,
            },
        ]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db import property

            result = property.get_attribute_by_key("prop-123", "wifi")
            assert result is not None
            assert result["value_json"] == '"100mbps"'

            missing = property.get_attribute_by_key("prop-123", "nonexistent")
            assert missing is None


class TestInsertOperations:
    """Test insert operations."""

    def test_insert_adds_row(self, mock_tower_table, sample_user):
        """Test insert adds a row to storage."""
        get_table, storage = mock_tower_table
        storage["users"] = []

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db.base import insert

            insert("users", sample_user)

            assert len(storage["users"]) == 1
            assert storage["users"][0]["email"] == sample_user["email"]

    def test_insert_many_adds_multiple_rows(self, mock_tower_table):
        """Test insert_many adds multiple rows."""
        get_table, storage = mock_tower_table
        storage["users"] = []
        now = datetime.now(timezone.utc)

        users = [
            {"id": "u1", "email": "a@test.com", "name": "A", "phone": "", "company": "", "created_at": now, "updated_at": now},
            {"id": "u2", "email": "b@test.com", "name": "B", "phone": "", "company": "", "created_at": now, "updated_at": now},
        ]

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db.base import insert_many

            insert_many("users", users)

            assert len(storage["users"]) == 2

    def test_insert_many_empty_list(self, mock_tower_table):
        """Test insert_many does nothing for empty list."""
        get_table, storage = mock_tower_table
        storage["users"] = []

        with patch("arbie.services.db.base.tower.tables", get_table):
            from arbie.services.db.base import insert_many

            insert_many("users", [])

            assert len(storage["users"]) == 0
