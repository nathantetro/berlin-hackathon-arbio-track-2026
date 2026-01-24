"""Arbie Gateway - FastAPI server for receiving email webhooks.

Handles Microsoft Graph webhook notifications and triggers the agent.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import tower
import uvicorn
from fastapi import FastAPI, Query, Request, Response
from pydantic import BaseModel

from arbie.services.db.base import init_all_tables
from arbie.services.email_processor import process_inbound_email
from arbie.services.graph_client import get_graph_client


# Configuration
WEBHOOK_CLIENT_STATE = os.getenv("GRAPH_WEBHOOK_CLIENT_STATE", "arbie-webhook-secret")


# --- Pydantic models for webhook payloads ---


class ResourceData(BaseModel):
    """Resource data from Graph notification."""

    id: str


class ChangeNotification(BaseModel):
    """Single change notification from Microsoft Graph."""

    subscriptionId: str
    clientState: str | None = None
    changeType: str
    resource: str
    resourceData: ResourceData


class WebhookPayload(BaseModel):
    """Microsoft Graph webhook notification payload."""

    value: list[ChangeNotification]


# --- FastAPI app ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    # Initialize database tables
    init_all_tables()
    yield


app = FastAPI(
    title="Arbie Gateway",
    description="Webhook receiver for Microsoft Graph email notifications",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "arbie-gateway"}


@app.get("/webhook")
async def webhook_validation(validationToken: str = Query(...)):
    """Handle Microsoft Graph subscription validation.

    Microsoft sends a GET request with validationToken when creating/renewing
    a subscription. We must return the token as plain text.
    """
    return Response(content=validationToken, media_type="text/plain")


@app.post("/webhook", status_code=202)
async def webhook_notification(request: Request):
    """Handle Microsoft Graph change notification.

    Microsoft sends a POST request when a new email arrives.
    We must respond with 202 Accepted within 3 seconds.
    Processing happens concurrently in the background.
    """
    # Parse the raw body first
    body = await request.json()

    # Validate payload structure
    try:
        payload = WebhookPayload(**body)
    except Exception as e:
        # Still return 202 to avoid Microsoft retrying invalid payloads
        print(f"Invalid webhook payload: {e}")
        return {"status": "accepted"}

    # Process each notification
    for notification in payload.value:
        # Verify clientState for security
        if notification.clientState != WEBHOOK_CLIENT_STATE:
            print(f"Invalid clientState: {notification.clientState}")
            continue

        # Only process 'created' events for new messages
        if notification.changeType != "created":
            continue

        # Extract message ID from resourceData
        message_id = notification.resourceData.id

        # Fire off background processing concurrently (non-blocking)
        asyncio.create_task(process_email_notification(message_id))

    return {"status": "accepted"}


async def process_email_notification(message_id: str) -> None:
    """Process an email notification in the background.

    Fetches the full email from Graph API, processes it, and triggers the agent.
    """
    try:
        print(f"Processing email notification: {message_id}")

        # Get Graph client
        graph = get_graph_client()

        # Fetch full message
        message = await graph.get_message(message_id)
        print(f"Fetched message: {message.subject} from {message.from_address.address}")

        # Fetch attachments if any
        attachments = []
        if message.has_attachments:
            att_list = await graph.list_attachments(message_id)
            for att in att_list:
                # Skip inline images (embedded in HTML)
                if att.is_inline:
                    continue
                content = await graph.get_attachment(message_id, att.id)
                attachments.append((att, content))
            print(f"Fetched {len(attachments)} attachments")

        # Process the email
        result = await process_inbound_email(message, attachments)
        print(
            f"Email processed: session={result.session_id}, "
            f"is_new={result.is_new_session}, trigger={result.trigger_type}"
        )

        # Mark email as read
        await graph.mark_as_read(message_id)

        # Trigger the agent app
        await trigger_agent(
            session_id=result.session_id,
            trigger_type=result.trigger_type,
            email_id=result.email_id,
        )

    except Exception as e:
        print(f"Error processing email notification: {e}")
        import traceback

        traceback.print_exc()


async def trigger_agent(
    session_id: str,
    trigger_type: str,
    email_id: str,
) -> None:
    """Trigger the arbie-agent app to process the session.

    Uses Tower's run_app to start the agent asynchronously.
    """
    print(
        f"Triggering agent: session_id={session_id}, "
        f"trigger_type={trigger_type}, email_id={email_id}"
    )

    # Run the agent app with parameters
    tower.run_app(
        "arbie-agent",
        parameters={
            "session_id": session_id,
            "trigger_type": trigger_type,
            "email_id": email_id,
        },
    )

    print(f"Agent triggered successfully for session {session_id}")


def main():
    """Entry point for Tower execution."""
    print("Starting Arbie Gateway...")
    print(f"Webhook client state configured: {'yes' if WEBHOOK_CLIENT_STATE else 'no'}")

    # Run the FastAPI server
    # Tower provides the PORT environment variable
    port = int(os.getenv("PORT", "8080"))
    workers = int(os.getenv("WORKERS", "4"))

    uvicorn.run(
        "main:app",  # String import path required for multiple workers
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level="info",
    )


if __name__ == "__main__":
    main()
