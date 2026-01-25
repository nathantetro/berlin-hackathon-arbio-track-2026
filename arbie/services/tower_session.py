"""Custom session implementation that reads conversation history from Tower emails table."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from arbie.services.db.email import get_emails_by_session_chronological

if TYPE_CHECKING:
    from agents.items import TResponseInputItem


class TowerEmailSession:
    """Session that reads conversation history from the Tower emails table.

    This session maps emails to conversation items:
    - Inbound emails (from property owners) → user role
    - Outbound emails (from Arbie) → assistant role

    The emails table is the source of truth - this session only reads from it.
    Writing is handled by the send_email tool, so add_items is a no-op.
    """

    def __init__(self, session_id: str, exclude_email_id: str | None = None):
        """Initialize the session.

        Args:
            session_id: The session ID to load conversation history for.
            exclude_email_id: Optional email ID to exclude from history (typically
                the triggering email, which is already in the prompt context).
        """
        self.session_id = session_id
        self.exclude_email_id = exclude_email_id

    async def get_items(self, limit: int | None = None) -> list[TResponseInputItem]:
        """Retrieve conversation history from the emails table.

        Args:
            limit: Maximum number of items to retrieve. If None, retrieves all items.
                   When specified, returns the latest N items in chronological order.

        Returns:
            List of input items representing the conversation history.
        """

        def _get_items_sync() -> list[TResponseInputItem]:
            emails = get_emails_by_session_chronological(self.session_id)

            items: list[TResponseInputItem] = []
            for email in emails:
                # Skip the triggering email (it's already in the prompt context)
                if self.exclude_email_id and email.get("id") == self.exclude_email_id:
                    continue
                item = self._email_to_item(email)
                if item:
                    items.append(item)

            # Apply limit if specified (return latest N items)
            if limit is not None and len(items) > limit:
                items = items[-limit:]

            return items

        return await asyncio.to_thread(_get_items_sync)

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        """No-op: emails are saved by the send_email tool.

        Args:
            items: Items to add (ignored).
        """
        pass

    async def pop_item(self) -> TResponseInputItem | None:
        """No-op: we don't modify email history.

        Returns:
            None (we don't support removing items).
        """
        return None

    async def clear_session(self) -> None:
        """No-op: we don't delete emails."""
        pass

    def _email_to_item(self, email: dict) -> TResponseInputItem | None:
        """Convert an email record to a conversation item.

        Args:
            email: Email record from the database.

        Returns:
            Conversation item with role and content, or None if invalid.
        """
        direction = email.get("direction")
        if not direction:
            return None

        # Get email body - prefer text, fall back to HTML
        body = email.get("body_text") or ""
        if not body and email.get("body_html"):
            # Basic HTML stripping - just extract text
            import re

            html = email.get("body_html", "")
            body = re.sub(r"<[^>]+>", "", html)
            body = body.strip()

        if not body:
            return None

        # Include subject for context
        subject = email.get("subject", "")
        content = f"Subject: {subject}\n\n{body}" if subject else body

        # Map direction to role
        if direction == "inbound":
            return {"role": "user", "content": content}
        elif direction == "outbound":
            return {"role": "assistant", "content": content}
        else:
            return None
