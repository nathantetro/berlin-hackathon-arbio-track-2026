"""Arbie Gateway - FastAPI server for receiving email webhooks.

Handles Microsoft Graph webhook notifications and triggers the agent.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import tower
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from arbie.models.enums import EventType
from arbie.models.session import SessionEvent
from arbie.services.acknowledgment import send_acknowledgment_email
from arbie.services.db.base import init_all_tables, insert
from arbie.services.db.email import get_emails_by_session
from arbie.services.db.property import (
    get_attributes_by_property,
    get_photos_by_property,
    get_property_by_session,
    get_rooms_by_property,
)
from arbie.services.db.session import get_session, get_session_by_reference
from arbie.services.db.user import get_user
from arbie.services.email_processor import process_inbound_email
from arbie.services.graph_client import get_graph_client

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
    yield


app = FastAPI(
    title="Arbie Gateway",
    description="Webhook receiver for Microsoft Graph email notifications",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint for health checks."""
    return {"status": "healthy", "service": "arbie-gateway"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "arbie-gateway"}


# --- Session Viewer UI ---


@app.get("/session", response_class=HTMLResponse)
async def session_viewer_home(request: Request):
    """Session viewer home page with search."""
    return templates.TemplateResponse(
        "session.html",
        {"request": request, "reference": None, "session": None, "error": None}
    )


@app.get("/session/{reference}", response_class=HTMLResponse)
async def session_viewer(request: Request, reference: str):
    """View session details by reference code."""
    # Look up session by reference code
    session = get_session_by_reference(reference.upper())

    if not session:
        return templates.TemplateResponse(
            "session.html",
            {
                "request": request,
                "reference": reference,
                "session": None,
                "error": f"Session with reference '{reference}' not found.",
            }
        )

    # Get related data
    user = get_user(session.get("user_id", "")) if session.get("user_id") else None

    # Get property and related data
    property_data = get_property_by_session(session["id"])
    attributes = []
    rooms = []
    photos = []

    if property_data:
        property_id = property_data["id"]
        attributes = get_attributes_by_property(property_id)
        rooms = get_rooms_by_property(property_id)
        photos = get_photos_by_property(property_id)

    # Get emails
    emails = get_emails_by_session(session["id"])
    # Sort by timestamp (newest first for display)
    emails = sorted(
        emails,
        key=lambda e: e.get("received_at") or e.get("sent_at") or e.get("created_at") or "",
        reverse=True
    )

    # Convert datetime objects to strings for template
    def serialize_datetime(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return obj

    # Serialize session datetimes
    for key in ['created_at', 'updated_at', 'last_activity_at', 'completed_at']:
        if session.get(key):
            session[key] = serialize_datetime(session[key])

    # Serialize email datetimes
    for email in emails:
        for key in ['received_at', 'sent_at', 'created_at']:
            if email.get(key):
                email[key] = serialize_datetime(email[key])

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "reference": reference,
            "session": session,
            "user": user,
            "property": property_data or {},
            "attributes": attributes,
            "rooms": rooms,
            "photos": photos,
            "emails": emails,
            "error": None,
        }
    )


@app.get("/api/session/{reference}")
async def api_session_details(reference: str):
    """API endpoint to get session details as JSON."""
    session = get_session_by_reference(reference.upper())

    if not session:
        return {"error": f"Session with reference '{reference}' not found."}

    # Get related data
    user = get_user(session.get("user_id", "")) if session.get("user_id") else None
    property_data = get_property_by_session(session["id"])

    attributes = []
    rooms = []
    photos = []

    if property_data:
        property_id = property_data["id"]
        attributes = get_attributes_by_property(property_id)
        rooms = get_rooms_by_property(property_id)
        photos = get_photos_by_property(property_id)

    emails = get_emails_by_session(session["id"])

    return {
        "session": session,
        "user": user,
        "property": property_data,
        "attributes": attributes,
        "rooms": rooms,
        "photos": photos,
        "emails": emails,
    }


# --- Session Validation ---


class ValidateRequest(BaseModel):
    """Request body for validation endpoint."""

    action: str  # "validate"


def send_validation_confirmation_email(session: dict, user_email: str) -> None:
    """Send confirmation email after owner validates property."""
    from arbie.services.resend_client import get_resend_client

    client = get_resend_client()
    client.send_email_with_retry(
        to=[user_email],
        subject=f"Property Validated - {session['reference_code']}",
        body_text=f"""Hi,

Your property has been validated successfully!

Reference: {session['reference_code']}

We'll be in touch with next steps.

Best,
The Arbio Team""",
        session_reference=session["reference_code"],
    )


@app.post("/session/{reference}/validate")
async def validate_session(reference: str, request: ValidateRequest):
    """Handle property validation from owner."""
    # Look up session by reference code
    session = get_session_by_reference(reference.upper())
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{reference}' not found")

    # Only allow validation when status is "ready"
    if session.get("status") != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Session is not ready for validation. Current status: {session.get('status')}",
        )

    # Validate action
    if request.action != "validate":
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")

    # Transition to VALIDATED
    now = datetime.now(timezone.utc)
    session["status"] = "validated"
    session["status_reason"] = "Owner validated property data"
    session["completed_at"] = now
    session["updated_at"] = now

    # Save to database
    insert("sessions", session)

    # Record VALIDATION_COMPLETED event
    event = SessionEvent(
        session_id=session["id"],
        event_type=EventType.VALIDATION_COMPLETED,
        timestamp=now,
        data=json.dumps({"validated_by": "owner"}),
    )
    insert("session_events", event.model_dump())

    # Send confirmation email
    user = get_user(session.get("user_id", "")) if session.get("user_id") else None
    if user and user.get("email"):
        try:
            send_validation_confirmation_email(session, user["email"])
        except Exception as e:
            print(f"Failed to send validation confirmation email: {e}")

    return {"status": "success", "message": "Property validated successfully"}


# --- Subscription Management ---


@app.get("/subscriptions")
async def list_subscriptions():
    """List all active Microsoft Graph webhook subscriptions."""
    try:
        graph = get_graph_client()
        subs = await graph.list_subscriptions()
        return {
            "subscriptions": [
                {
                    "id": s.id,
                    "resource": s.resource,
                    "notification_url": s.notification_url,
                    "expiration": s.expiration_datetime.isoformat(),
                }
                for s in subs
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/subscriptions")
async def create_subscription(request: Request):
    """Create a new Microsoft Graph webhook subscription.

    Body (optional):
        notification_url: Override the webhook URL (defaults to this server's /webhook)
    """
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        # Default to this server's webhook URL
        # You'll need to provide the full URL including https://
        notification_url = body.get("notification_url")
        if not notification_url:
            return {
                "error": "Please provide notification_url in request body, e.g. https://your-gateway-url/webhook"
            }

        graph = get_graph_client()
        sub = await graph.create_subscription(
            notification_url=notification_url,
            client_state=WEBHOOK_CLIENT_STATE,
        )

        return {
            "status": "created",
            "subscription": {
                "id": sub.id,
                "resource": sub.resource,
                "notification_url": sub.notification_url,
                "expiration": sub.expiration_datetime.isoformat(),
            },
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """Delete a Microsoft Graph webhook subscription."""
    try:
        graph = get_graph_client()
        await graph.delete_subscription(subscription_id)
        return {"status": "deleted", "id": subscription_id}
    except Exception as e:
        return {"error": str(e)}


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
    # Log immediately when webhook is hit
    print(f"=== WEBHOOK POST RECEIVED ===")
    print(f"Headers: {dict(request.headers)}")
    print(f"Query params: {dict(request.query_params)}")

    # Handle validation POST - Microsoft may send POST with validationToken query param
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return Response(content=validation_token, media_type="text/plain")

    # Parse the raw body - handle empty body gracefully
    body_bytes = await request.body()
    if not body_bytes:
        print("Received empty webhook body")
        return {"status": "accepted"}

    try:
        body = await request.json()
    except Exception as e:
        print(f"Failed to parse webhook JSON: {e}, body: {body_bytes[:200]}")
        return {"status": "accepted"}

    # Validate payload structure
    try:
        payload = WebhookPayload(**body)
        print(f"Parsed webhook payload: {len(payload.value)} notification(s)")
    except Exception as e:
        # Still return 202 to avoid Microsoft retrying invalid payloads
        print(f"Invalid webhook payload: {e}")
        return {"status": "accepted"}

    # Process each notification
    for i, notification in enumerate(payload.value):
        print(f"--- Notification {i+1} ---")
        print(f"  subscriptionId: {notification.subscriptionId}")
        print(f"  changeType: {notification.changeType}")
        print(f"  resource: {notification.resource}")
        print(f"  clientState: {notification.clientState}")
        print(f"  expected clientState: {WEBHOOK_CLIENT_STATE}")

        # Verify clientState for security
        if notification.clientState != WEBHOOK_CLIENT_STATE:
            print(f"  ❌ clientState MISMATCH - skipping")
            continue

        print(f"  ✓ clientState OK")

        # Only process 'created' events for new messages
        if notification.changeType != "created":
            print(f"  Skipping non-created changeType: {notification.changeType}")
            continue

        # Extract message ID from resourceData
        message_id = notification.resourceData.id
        print(f"  ✓ Processing message: {message_id}")

        # Fire off background processing concurrently (non-blocking)
        asyncio.create_task(process_email_notification(message_id))
        print(f"  ✓ Background task created")

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

        # Fetch attachments (always check - hasAttachments can be False for inline-only emails)
        attachments = []
        att_list = await graph.list_attachments(message_id)
        for att in att_list:
            # Skip small inline images (likely signatures/icons) but keep larger ones (real photos)
            # Microsoft Graph marks many legitimate attachments as "inline"
            if att.is_inline and att.size < 10_000:  # Skip only if inline AND < 10KB
                print(f"  Skipping small inline image: {att.name} ({att.size} bytes)")
                continue
            content = await graph.get_attachment(message_id, att.id)
            attachments.append((att, content))
        if attachments:
            print(f"Fetched {len(attachments)} attachments")

        # Process the email (creates/finds session)
        result = await process_inbound_email(message, attachments)
        print(
            f"Email processed: session={result.session_id}, "
            f"is_new={result.is_new_session}, trigger={result.trigger_type}"
        )

        # Get session reference code for the acknowledgment email
        session = get_session(result.session_id)
        session_reference = session.get("reference_code") if session else None

        # Send acknowledgment email only for new sessions (not follow-ups)
        if result.is_new_session:
            try:
                send_acknowledgment_email(
                    to=message.from_address.address,
                    original_subject=message.subject,
                    in_reply_to=message.internet_message_id,
                    session_reference=session_reference,
                )
                print(f"Sent acknowledgment email to {message.from_address.address}")
            except Exception as ack_err:
                print(f"Failed to send acknowledgment email: {ack_err}")

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

    # Initialize database tables once in parent process (before forking workers)
    init_all_tables()
    print("Database tables initialized.")

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
