"""Database schemas for Arbie Iceberg tables.

For database operations, use arbie.services.db:
    from arbie.services.db.base import init_all_tables, insert, query, get_by_id

For schemas only:
    from arbie.db.schemas import TABLE_SCHEMAS, JOIN_COLUMNS, ALL_TABLES

See: https://github.com/tower/tower-examples
"""

from arbie.db.schemas import ALL_TABLES, JOIN_COLUMNS, TABLE_SCHEMAS

__all__ = [
    "ALL_TABLES",
    "TABLE_SCHEMAS",
    "JOIN_COLUMNS",
]
