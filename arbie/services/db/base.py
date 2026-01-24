"""Core Tower table operations - generic CRUD and table access."""

from datetime import datetime, timezone

import polars as pl
import pyarrow as pa
import tower

from arbie.db.schemas import JOIN_COLUMNS, TABLE_SCHEMAS


# === Table Access ===


def get_table(name: str) -> tower.Table:
    """Get a Tower table by name."""
    return tower.tables(name)


def ensure_table(name: str) -> tower.Table:
    """Get table, creating if needed."""
    return tower.tables(name).create_if_not_exists(TABLE_SCHEMAS[name])


def init_all_tables() -> None:
    """Initialize all tables."""
    for name, schema in TABLE_SCHEMAS.items():
        tower.tables(name).create_if_not_exists(schema)


# === Generic CRUD ===


def insert(table_name: str, data: dict) -> None:
    """Insert a single row."""
    data = _prepare_data(data)
    pa_table = pa.Table.from_pylist([data], schema=TABLE_SCHEMAS[table_name])
    tower.tables(table_name).upsert(pa_table, join_cols=JOIN_COLUMNS[table_name])


def insert_many(table_name: str, rows: list[dict]) -> None:
    """Insert multiple rows."""
    if not rows:
        return
    rows = [_prepare_data(r) for r in rows]
    pa_table = pa.Table.from_pylist(rows, schema=TABLE_SCHEMAS[table_name])
    tower.tables(table_name).upsert(pa_table, join_cols=JOIN_COLUMNS[table_name])


def get_by_id(table_name: str, id: str) -> dict | None:
    """Get a row by ID."""
    df = tower.tables(table_name).load().to_polars()
    result = df.filter(pl.col("id") == id)
    return result.to_dicts()[0] if not result.is_empty() else None


def query(table_name: str, filter_expr: pl.Expr) -> list[dict]:
    """Query with a Polars filter expression."""
    df = tower.tables(table_name).load().to_polars()
    return df.filter(filter_expr).to_dicts()


def query_sorted(
    table_name: str, filter_expr: pl.Expr, sort_col: str, descending: bool = False
) -> list[dict]:
    """Query with a Polars filter expression, sorted."""
    df = tower.tables(table_name).load().to_polars()
    return df.filter(filter_expr).sort(sort_col, descending=descending).to_dicts()


def get_all(table_name: str, limit: int = 100) -> list[dict]:
    """Get all rows with limit."""
    df = tower.tables(table_name).load().to_polars()
    return df.head(limit).to_dicts()


def count(table_name: str) -> int:
    """Count rows in a table."""
    df = tower.tables(table_name).load().to_polars()
    return len(df)


def exists(table_name: str, id: str) -> bool:
    """Check if a row exists by ID."""
    return get_by_id(table_name, id) is not None


# === Helpers ===


def _prepare_data(data: dict) -> dict:
    """Prepare dict for PyArrow (handle datetimes, enums)."""
    result = {}
    for k, v in data.items():
        if isinstance(v, datetime):
            result[k] = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
        elif hasattr(v, "value"):  # Enum
            result[k] = v.value
        else:
            result[k] = v
    return result
