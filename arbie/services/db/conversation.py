"""Conversation items database operations."""

import json
import uuid

import polars as pl

from arbie.db.schemas import CONVERSATION_ITEMS_TABLE
from arbie.models.base import utc_now
from arbie.services.db.base import insert_many, query_sorted


def get_conversation_items_by_session(session_id: str) -> list[dict]:
    """Get all conversation items for a session, ordered by sequence_number.

    Args:
        session_id: Session ID to get conversation items for.

    Returns:
        List of conversation item dicts ordered by sequence_number.
    """
    return query_sorted(
        CONVERSATION_ITEMS_TABLE,
        pl.col("session_id") == session_id,
        sort_col="sequence_number",
        descending=False,
    )


def get_next_sequence_number(session_id: str) -> int:
    """Get the next sequence number for a session.

    Args:
        session_id: Session ID to get next sequence number for.

    Returns:
        Next sequence number (max + 1, or 0 if no items exist).
    """
    items = get_conversation_items_by_session(session_id)
    if not items:
        return 0
    return max(item["sequence_number"] for item in items) + 1


def add_conversation_items(session_id: str, items: list[dict]) -> None:
    """Store conversation items to the database.

    Args:
        session_id: Session ID to store items for.
        items: List of TResponseInputItem dicts to store.
    """
    if not items:
        return

    next_seq = get_next_sequence_number(session_id)
    now = utc_now()

    rows = []
    for i, item in enumerate(items):
        item_type = _get_item_type(item)
        rows.append({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "sequence_number": next_seq + i,
            "item_type": item_type,
            "item_data": json.dumps(item),
            "created_at": now,
            "updated_at": now,
        })

    insert_many(CONVERSATION_ITEMS_TABLE, rows)


def parse_conversation_items(rows: list[dict]) -> list[dict]:
    """Parse stored conversation items back to TResponseInputItem format.

    Args:
        rows: List of database rows with item_data JSON.

    Returns:
        List of parsed TResponseInputItem dicts.
    """
    items = []
    for row in rows:
        item_data = row.get("item_data")
        if item_data:
            try:
                items.append(json.loads(item_data))
            except json.JSONDecodeError:
                pass
    return items


def _get_item_type(item: dict) -> str:
    """Determine the item type from a TResponseInputItem.

    Args:
        item: A TResponseInputItem dict.

    Returns:
        Item type string (e.g., "message", "function_call", "function_call_output").
    """
    if "type" in item:
        return item["type"]
    if "role" in item:
        return "message"
    return "unknown"
