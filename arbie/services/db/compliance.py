"""Compliance checks database operations."""

import polars as pl

from arbie.services.db.base import query

TABLE = "compliance_checks"


def get_compliance_checks_by_property(property_id: str) -> list[dict]:
    """Get all compliance checks for a property."""
    return query(TABLE, pl.col("property_id") == property_id)
