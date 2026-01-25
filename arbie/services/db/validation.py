"""Validation token database operations."""

import polars as pl

from arbie.services.db.base import query

TABLE = "validation_tokens"


def get_validation_token(token: str) -> dict | None:
    """Get a validation token."""
    rows = query(TABLE, pl.col("token") == token)
    return rows[0] if rows else None


def get_validation_token_by_session(session_id: str) -> dict | None:
    """Get the validation token for a session."""
    rows = query(TABLE, pl.col("session_id") == session_id)
    return rows[0] if rows else None
