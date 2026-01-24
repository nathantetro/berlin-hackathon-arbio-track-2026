"""Database module for Arbie Iceberg tables.

Simple Tower SDK usage - just functions, no repository classes.

Usage:
    from arbie.services import db
    from arbie.models.session import Session
    import polars as pl

    # Initialize tables (call once on startup)
    db.init_all_tables()

    # Write
    db.insert("sessions", session.model_dump())

    # Read
    row = db.get_by_id("sessions", session_id)
    session = Session(**row) if row else None

    # Query
    rows = db.query("sessions", pl.col("status") == "EXTRACTING")
    sessions = [Session(**r) for r in rows]

    # Domain-specific operations
    db.user.get_user_by_email("owner@example.com")
    db.session.get_active_sessions()
    db.property.get_rooms_by_property("prop-123")

See: https://github.com/tower/tower-examples
"""

from arbie.db.schemas import ALL_TABLES, JOIN_COLUMNS, TABLE_SCHEMAS
from arbie.services.db.base import (
    count,
    ensure_table,
    exists,
    get_all,
    get_by_id,
    get_table,
    init_all_tables,
    insert,
    insert_many,
    query,
    query_sorted,
)

__all__ = [
    # Schema exports
    "ALL_TABLES",
    "TABLE_SCHEMAS",
    "JOIN_COLUMNS",
    # Table access
    "get_table",
    "ensure_table",
    "init_all_tables",
    # CRUD operations
    "insert",
    "insert_many",
    "get_by_id",
    "query",
    "query_sorted",
    "get_all",
    "count",
    "exists",
]
