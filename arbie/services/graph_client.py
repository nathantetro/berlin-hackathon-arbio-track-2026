"""Microsoft Graph API client for email operations.

Handles OAuth2 authentication and email fetching from Microsoft 365.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import msal


# Graph API configuration
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


@dataclass
class EmailAddress:
    """Represents an email address with optional name."""

    address: str
    name: str | None = None


@dataclass
class GraphAttachment:
    """Attachment metadata from Graph API."""

    id: str
    name: str
    content_type: str
    size: int
    is_inline: bool = False


@dataclass
class GraphMessage:
    """Parsed email message from Microsoft Graph."""

    id: str
    internet_message_id: str
    subject: str
    from_address: EmailAddress
    to_recipients: list[EmailAddress]
    cc_recipients: list[EmailAddress]
    body_text: str | None
    body_html: str | None
    has_attachments: bool
    received_datetime: datetime
    in_reply_to: str | None
    references: list[str]
    conversation_id: str | None


@dataclass
class GraphSubscription:
    """Webhook subscription for Graph API notifications."""

    id: str
    resource: str
    change_type: str
    notification_url: str
    expiration_datetime: datetime
    client_state: str | None


class GraphClient:
    """Client for Microsoft Graph API operations."""

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        mailbox: str = "onboard@arbie.work",
    ):
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")
        self.mailbox = mailbox

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing Azure credentials. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                "and AZURE_CLIENT_SECRET environment variables."
            )

        self._msal_app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        self._access_token: str | None = None

    def _get_access_token(self) -> str:
        """Acquire OAuth2 access token using client credentials flow."""
        result = self._msal_app.acquire_token_for_client(scopes=GRAPH_SCOPES)

        if "access_token" not in result:
            error = result.get("error", "unknown")
            error_desc = result.get("error_description", "No description")
            raise RuntimeError(f"Failed to acquire token: {error} - {error_desc}")

        self._access_token = result["access_token"]
        return self._access_token

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers with authorization."""
        token = self._access_token or self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def get_message(self, message_id: str) -> GraphMessage:
        """Fetch a complete email message by ID.

        Args:
            message_id: The Graph API message ID (from webhook notification).

        Returns:
            GraphMessage with full email content.
        """
        url = f"{GRAPH_BASE_URL}/users/{self.mailbox}/messages/{message_id}"
        params = {
            "$select": (
                "id,internetMessageId,subject,from,toRecipients,ccRecipients,"
                "body,hasAttachments,receivedDateTime,conversationId,"
                "internetMessageHeaders"
            )
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=self._get_headers(), params=params
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_message(data)

    def _parse_message(self, data: dict) -> GraphMessage:
        """Parse Graph API response into GraphMessage."""
        # Extract headers for In-Reply-To and References
        headers = {
            h["name"].lower(): h["value"]
            for h in data.get("internetMessageHeaders", [])
        }

        in_reply_to = headers.get("in-reply-to")
        references_str = headers.get("references", "")
        references = references_str.split() if references_str else []

        # Parse from address
        from_data = data.get("from", {}).get("emailAddress", {})
        from_address = EmailAddress(
            address=from_data.get("address", ""),
            name=from_data.get("name"),
        )

        # Parse recipients
        to_recipients = [
            EmailAddress(
                address=r["emailAddress"]["address"],
                name=r["emailAddress"].get("name"),
            )
            for r in data.get("toRecipients", [])
        ]

        cc_recipients = [
            EmailAddress(
                address=r["emailAddress"]["address"],
                name=r["emailAddress"].get("name"),
            )
            for r in data.get("ccRecipients", [])
        ]

        # Parse body
        body = data.get("body", {})
        body_content = body.get("content", "")
        is_html = body.get("contentType", "").lower() == "html"

        return GraphMessage(
            id=data["id"],
            internet_message_id=data.get("internetMessageId", ""),
            subject=data.get("subject", ""),
            from_address=from_address,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            body_text=None if is_html else body_content,
            body_html=body_content if is_html else None,
            has_attachments=data.get("hasAttachments", False),
            received_datetime=datetime.fromisoformat(
                data["receivedDateTime"].replace("Z", "+00:00")
            ),
            in_reply_to=in_reply_to,
            references=references,
            conversation_id=data.get("conversationId"),
        )

    async def list_attachments(self, message_id: str) -> list[GraphAttachment]:
        """List all attachments for a message.

        Args:
            message_id: The Graph API message ID.

        Returns:
            List of GraphAttachment metadata.
        """
        url = f"{GRAPH_BASE_URL}/users/{self.mailbox}/messages/{message_id}/attachments"
        params = {"$select": "id,name,contentType,size,isInline"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=self._get_headers(), params=params
            )
            response.raise_for_status()
            data = response.json()

        return [
            GraphAttachment(
                id=att["id"],
                name=att["name"],
                content_type=att.get("contentType", "application/octet-stream"),
                size=att.get("size", 0),
                is_inline=att.get("isInline", False),
            )
            for att in data.get("value", [])
        ]

    async def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment content.

        Args:
            message_id: The Graph API message ID.
            attachment_id: The attachment ID.

        Returns:
            Raw attachment bytes.
        """
        url = (
            f"{GRAPH_BASE_URL}/users/{self.mailbox}/messages/{message_id}"
            f"/attachments/{attachment_id}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

        # Attachments are base64 encoded in contentBytes
        import base64

        content_bytes = data.get("contentBytes", "")
        return base64.b64decode(content_bytes)

    async def mark_as_read(self, message_id: str) -> None:
        """Mark a message as read.

        Args:
            message_id: The Graph API message ID.
        """
        url = f"{GRAPH_BASE_URL}/users/{self.mailbox}/messages/{message_id}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers=self._get_headers(),
                json={"isRead": True},
            )
            response.raise_for_status()

    async def create_subscription(
        self,
        notification_url: str,
        client_state: str = "arbie-webhook-secret",
        expiration_hours: int = 48,
    ) -> GraphSubscription:
        """Create a webhook subscription for new mail notifications.

        Args:
            notification_url: The URL to receive webhook notifications.
            client_state: Secret string to verify webhook authenticity.
            expiration_hours: Hours until subscription expires (max 4230 min ~70h for mail).

        Returns:
            GraphSubscription with subscription details.
        """
        url = f"{GRAPH_BASE_URL}/subscriptions"

        # Calculate expiration (max ~70 hours for mail resources)
        expiration = datetime.now(timezone.utc) + timedelta(hours=min(expiration_hours, 70))

        payload = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": f"users/{self.mailbox}/messages",
            "expirationDateTime": expiration.isoformat(),
            "clientState": client_state,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=self._get_headers(), json=payload
            )
            response.raise_for_status()
            data = response.json()

        return GraphSubscription(
            id=data["id"],
            resource=data["resource"],
            change_type=data["changeType"],
            notification_url=data["notificationUrl"],
            expiration_datetime=datetime.fromisoformat(
                data["expirationDateTime"].replace("Z", "+00:00")
            ),
            client_state=data.get("clientState"),
        )

    async def list_subscriptions(self) -> list[GraphSubscription]:
        """List all active webhook subscriptions.

        Returns:
            List of GraphSubscription objects.
        """
        url = f"{GRAPH_BASE_URL}/subscriptions"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

        return [
            GraphSubscription(
                id=sub["id"],
                resource=sub["resource"],
                change_type=sub["changeType"],
                notification_url=sub["notificationUrl"],
                expiration_datetime=datetime.fromisoformat(
                    sub["expirationDateTime"].replace("Z", "+00:00")
                ),
                client_state=sub.get("clientState"),
            )
            for sub in data.get("value", [])
        ]

    async def renew_subscription(
        self, subscription_id: str, expiration_hours: int = 48
    ) -> GraphSubscription:
        """Renew an existing subscription.

        Args:
            subscription_id: The subscription ID to renew.
            expiration_hours: Hours until subscription expires.

        Returns:
            Updated GraphSubscription.
        """
        url = f"{GRAPH_BASE_URL}/subscriptions/{subscription_id}"
        expiration = datetime.now(timezone.utc) + timedelta(hours=min(expiration_hours, 70))

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers=self._get_headers(),
                json={"expirationDateTime": expiration.isoformat()},
            )
            response.raise_for_status()
            data = response.json()

        return GraphSubscription(
            id=data["id"],
            resource=data["resource"],
            change_type=data["changeType"],
            notification_url=data["notificationUrl"],
            expiration_datetime=datetime.fromisoformat(
                data["expirationDateTime"].replace("Z", "+00:00")
            ),
            client_state=data.get("clientState"),
        )

    async def delete_subscription(self, subscription_id: str) -> None:
        """Delete a webhook subscription.

        Args:
            subscription_id: The subscription ID to delete.
        """
        url = f"{GRAPH_BASE_URL}/subscriptions/{subscription_id}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=self._get_headers())
            response.raise_for_status()


# Module-level singleton
_client: GraphClient | None = None


def get_graph_client() -> GraphClient:
    """Get or create the Graph client singleton."""
    global _client
    if _client is None:
        _client = GraphClient()
    return _client
