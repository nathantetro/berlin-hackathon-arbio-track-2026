"""Database services - domain-specific Tower table operations.

Usage:
    from arbie.services.db import user, session, property

    user.get_user_by_email("owner@example.com")
    session.get_active_sessions()
    property.get_rooms_by_property("prop-123")

For generic CRUD operations:
    from arbie.services.db.base import insert, insert_many, get_by_id, query
"""

from arbie.services.db import (
    compliance,
    email,
    evidence,
    property,
    session,
    user,
    validation,
)
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
    # Domain modules
    "user",
    "session",
    "property",
    "email",
    "evidence",
    "compliance",
    "validation",
    # Base operations
    "get_table",
    "ensure_table",
    "init_all_tables",
    "insert",
    "insert_many",
    "get_by_id",
    "query",
    "query_sorted",
    "get_all",
    "count",
    "exists",
]
