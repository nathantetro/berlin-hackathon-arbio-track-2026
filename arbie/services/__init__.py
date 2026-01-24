"""Arbie services module.

Provides external service integrations:
- graph_client: Microsoft Graph API for email receiving
- mailersend_client: MailerSend API for email sending
- email_processor: Email processing and session matching
"""

from arbie.services.graph_client import GraphClient, get_graph_client
from arbie.services.mailersend_client import MailerSendClient, get_mailersend_client
from arbie.services.email_processor import process_inbound_email

__all__ = [
    "GraphClient",
    "get_graph_client",
    "MailerSendClient",
    "get_mailersend_client",
    "process_inbound_email",
]
