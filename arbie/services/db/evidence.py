"""Evidence database operations."""

import polars as pl

from arbie.services.db.base import query

TABLE = "evidence"


def get_evidence_by_attachment(attachment_id: str) -> list[dict]:
    """Get all evidence from an attachment."""
    return query(TABLE, pl.col("attachment_id") == attachment_id)
