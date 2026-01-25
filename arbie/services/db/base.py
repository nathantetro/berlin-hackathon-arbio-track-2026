"""Core Tower table operations - generic CRUD and table access."""

import random
import time
from datetime import datetime, timezone

import polars as pl
import pyarrow as pa
import tower
from pyiceberg.exceptions import CommitFailedException

from arbie.db.schemas import JOIN_COLUMNS, TABLE_SCHEMAS

# === Retry Configuration ===
MAX_RETRIES = 5
BASE_DELAY = 0.1  # 100ms base delay
MAX_DELAY = 2.0  # 2 second max delay

# === Configuration ===

# Tower catalog configuration
# When running in Tower, use "default" catalog which is auto-configured
# The namespace groups related tables together
CATALOG = "arbie-properties"
NAMESPACE = "arbie"


# === Table Access ===


def _tables(name: str):
    """Get a Tower table reference with catalog and namespace configured."""
    return tower.tables(name, catalog=CATALOG, namespace=NAMESPACE)


def get_table(name: str):
    """Get a Tower table by name."""
    return _tables(name)


def ensure_table(name: str):
    """Get table, creating if needed."""
    return _tables(name).create_if_not_exists(TABLE_SCHEMAS[name])


def init_all_tables() -> None:
    """Initialize all tables."""
    for name, schema in TABLE_SCHEMAS.items():
        _tables(name).create_if_not_exists(schema)


# === Generic CRUD ===


def _retry_with_backoff(operation, *args, **kwargs):
    """Execute an operation with exponential backoff retry on CommitFailedException."""
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            return operation(*args, **kwargs)
        except CommitFailedException as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                # Exponential backoff with jitter
                delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.1), MAX_DELAY)
                time.sleep(delay)
            else:
                raise last_exception


def insert(table_name: str, data: dict) -> None:
    """Insert a single row with retry on concurrency conflicts."""
    data = _prepare_data(data)
    pa_table = pa.Table.from_pylist([data], schema=TABLE_SCHEMAS[table_name])
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    
    def do_upsert():
        table.upsert(pa_table, join_cols=JOIN_COLUMNS[table_name])
    
    _retry_with_backoff(do_upsert)


def insert_many(table_name: str, rows: list[dict]) -> None:
    """Insert multiple rows with retry on concurrency conflicts."""
    if not rows:
        return
    rows = [_prepare_data(r) for r in rows]
    pa_table = pa.Table.from_pylist(rows, schema=TABLE_SCHEMAS[table_name])
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    
    def do_upsert():
        table.upsert(pa_table, join_cols=JOIN_COLUMNS[table_name])
    
    _retry_with_backoff(do_upsert)


def get_by_id(table_name: str, id: str) -> dict | None:
    """Get a row by ID."""
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    lf = table.to_polars()  # Returns LazyFrame
    result = lf.filter(pl.col("id") == id).collect()
    return result.to_dicts()[0] if not result.is_empty() else None


def query(table_name: str, filter_expr: pl.Expr) -> list[dict]:
    """Query with a Polars filter expression."""
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    lf = table.to_polars()
    return lf.filter(filter_expr).collect().to_dicts()


def query_sorted(
    table_name: str, filter_expr: pl.Expr, sort_col: str, descending: bool = False
) -> list[dict]:
    """Query with a Polars filter expression, sorted."""
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    lf = table.to_polars()
    return lf.filter(filter_expr).sort(sort_col, descending=descending).collect().to_dicts()


def get_all(table_name: str, limit: int = 100) -> list[dict]:
    """Get all rows with limit."""
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    lf = table.to_polars()
    return lf.head(limit).collect().to_dicts()


def count(table_name: str) -> int:
    """Count rows in a table."""
    table = _tables(table_name).create_if_not_exists(TABLE_SCHEMAS[table_name])
    lf = table.to_polars()
    return lf.collect().height


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
