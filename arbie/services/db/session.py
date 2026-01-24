"""Session and session events database operations."""

import polars as pl

from arbie.services.db.base import get_by_id, query, query_sorted

SESSIONS_TABLE = "sessions"
EVENTS_TABLE = "session_events"


# === Session Operations ===


def get_session(session_id: str) -> dict | None:
    """Get a session by ID."""
    return get_by_id(SESSIONS_TABLE, session_id)


def get_sessions_by_status(status: str) -> list[dict]:
    """Get sessions by status."""
    return query(SESSIONS_TABLE, pl.col("status") == status)


def get_session_by_reference(code: str) -> dict | None:
    """Get a session by reference code."""
    rows = query(SESSIONS_TABLE, pl.col("reference_code") == code)
    return rows[0] if rows else None


def get_sessions_by_user(user_id: str) -> list[dict]:
    """Get all sessions for a user."""
    return query(SESSIONS_TABLE, pl.col("user_id") == user_id)


def get_active_sessions() -> list[dict]:
    """Get non-archived sessions."""
    return query(
        SESSIONS_TABLE,
        ~pl.col("status").is_in(["VALIDATED", "ARCHIVED"]),
    )


# === Session Events Operations ===


def get_session_events(session_id: str) -> list[dict]:
    """Get all events for a session, ordered by timestamp."""
    return query_sorted(
        EVENTS_TABLE,
        pl.col("session_id") == session_id,
        "timestamp",
    )
