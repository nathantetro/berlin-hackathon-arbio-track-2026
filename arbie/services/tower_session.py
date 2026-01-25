"""Custom session implementation that stores conversation history in Tower Iceberg table."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from arbie.services.db.conversation import (
    add_conversation_items,
    get_conversation_items_by_session,
    parse_conversation_items,
)

if TYPE_CHECKING:
    from agents.items import TResponseInputItem


class TowerEmailSession:
    """Session that stores all conversation items in Tower Iceberg table.

    This session persists ALL conversation items (messages, tool calls, tool outputs)
    in the conversation_items table, providing full context across agent turns.
    """

    def __init__(self, session_id: str, exclude_email_id: str | None = None):
        """Initialize the session.

        Args:
            session_id: The session ID to store/retrieve conversation history for.
            exclude_email_id: Unused, kept for backward compatibility.
        """
        self.session_id = session_id
        # Note: exclude_email_id is no longer used since we store tool calls
        # directly rather than reconstructing history from emails

    async def get_items(self, limit: int | None = None) -> list[TResponseInputItem]:
        """Retrieve conversation history from the conversation_items table.

        Args:
            limit: Maximum number of items to retrieve. If None, retrieves all items.
                   When specified, returns the latest N items in chronological order.

        Returns:
            List of input items representing the conversation history.
        """

        def _get_items_sync() -> list[TResponseInputItem]:
            rows = get_conversation_items_by_session(self.session_id)
            items = parse_conversation_items(rows)

            # Apply limit if specified (return latest N items)
            if limit is not None and len(items) > limit:
                items = items[-limit:]

            return items

        return await asyncio.to_thread(_get_items_sync)

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        """Store new items to the conversation_items table.

        Args:
            items: Items to add (messages, tool calls, tool outputs, etc.).
        """
        if not items:
            return

        def _add_items_sync() -> None:
            add_conversation_items(self.session_id, items)

        await asyncio.to_thread(_add_items_sync)

    async def pop_item(self) -> TResponseInputItem | None:
        """Remove and return most recent item.

        Returns:
            None (we don't support removing items).
        """
        return None

    async def clear_session(self) -> None:
        """Clear all items for session.

        This is a no-op since we don't want to delete conversation history.
        """
        pass
