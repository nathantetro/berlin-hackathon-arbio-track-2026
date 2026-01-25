"""User database operations."""

import polars as pl

from arbie.services.db.base import get_by_id, query

TABLE = "users"


def get_user(user_id: str) -> dict | None:
    """Get a user by ID."""
    return get_by_id(TABLE, user_id)


def get_user_by_email(email: str) -> dict | None:
    """Get a user by email."""
    rows = query(TABLE, pl.col("email") == email)
    return rows[0] if rows else None
