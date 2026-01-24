"""Arbie Agent Runner - Entry point for Tower execution.

Accepts parameters to process a specific session with context.
"""

import json
import os

from agents import Runner

from arbie.agents.arbie_agent import arbie_agent
from arbie.services.db.base import init_all_tables
from arbie.services.db.email import get_emails_by_session
from arbie.services.db.session import get_session
from arbie.tools.email_tools import set_session_context


def build_agent_prompt(
    session_id: str,
    trigger_type: str,
    email_id: str | None = None,
) -> str:
    """Build the agent prompt based on session context.

    Args:
        session_id: The session to process.
        trigger_type: Either "new_submission" or "follow_up_response".
        email_id: Optional specific email that triggered this run.

    Returns:
        Formatted prompt string for the agent.
    """
    # Load session data
    session = get_session(session_id)
    if not session:
        return f"Error: Session {session_id} not found."

    # Load emails for context
    emails = get_emails_by_session(session_id)

    # Build context summary
    context_parts = [
        f"Session ID: {session_id}",
        f"Reference Code: {session.get('reference_code', 'N/A')}",
        f"Status: {session.get('status', 'unknown')}",
        f"Total Emails: {len(emails)}",
    ]

    # Get the latest email if available
    latest_email = None
    if email_id:
        for email in emails:
            if email.get("id") == email_id:
                latest_email = email
                break
    elif emails:
        # Sort by received_at descending to get latest
        sorted_emails = sorted(
            emails,
            key=lambda e: e.get("received_at") or e.get("created_at"),
            reverse=True,
        )
        latest_email = sorted_emails[0] if sorted_emails else None

    if latest_email:
        context_parts.extend([
            "",
            "Latest Email:",
            f"  From: {latest_email.get('from_address', 'unknown')}",
            f"  Subject: {latest_email.get('subject', 'No subject')}",
            f"  Has Text: {'yes' if latest_email.get('body_text') else 'no'}",
            f"  Has HTML: {'yes' if latest_email.get('body_html') else 'no'}",
        ])

    context = "\n".join(context_parts)

    # Build prompt based on trigger type
    if trigger_type == "new_submission":
        prompt = f"""
A new property submission has been received! Here's the context:

{context}

Please process this new submission:

1. **Get an overview** - Use get_session_overview to see all files and materials
2. **Read the email content** - Understand what the property owner has submitted
3. **Extract property information** - From documents, images, and email body
4. **Identify missing information** - What's needed to complete the listing?
5. **Send acknowledgment email** - Thank the owner and let them know next steps

If critical information is missing, prepare a follow-up email with specific questions.
Remember to update the session status as you progress.
"""
    elif trigger_type == "follow_up_response":
        prompt = f"""
The property owner has responded to a follow-up request! Here's the context:

{context}

Please process this response:

1. **Review the response** - Read the new email and any attachments
2. **Extract new information** - Update the property record with new details
3. **Check completeness** - Do we now have everything needed?
4. **Decide next steps**:
   - If complete: Move to research/compliance checks
   - If still missing info: Send another follow-up (be specific about what's still needed)
   - If ready: Update status to ready_for_review

Be conversational and helpful in any responses. Remember to update session status.
"""
    else:
        # Generic processing prompt
        prompt = f"""
Process the session with the following context:

{context}

Review the current state and take appropriate actions based on the session status.
"""

    return prompt


def main() -> int:
    """Main entry point for Arbie agent runner."""
    # Get parameters from environment (Tower passes them this way)
    session_id = os.getenv("session_id")
    trigger_type = os.getenv("trigger_type", "unknown")
    email_id = os.getenv("email_id")

    print("Arbie Agent Runner v1.0.0")
    print("=" * 60)
    print(f"Session ID: {session_id}")
    print(f"Trigger Type: {trigger_type}")
    print(f"Email ID: {email_id or 'N/A'}")
    print("=" * 60)

    # Validate required parameters
    if not session_id:
        print("Error: session_id parameter is required")
        return 1

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        return 1

    # Initialize database tables
    init_all_tables()

    # Set session context for email tools
    set_session_context(session_id)

    # Build the agent prompt
    prompt = build_agent_prompt(
        session_id=session_id,
        trigger_type=trigger_type,
        email_id=email_id,
    )

    print(f"\nAgent Prompt:\n{prompt}\n")
    print("=" * 60)
    print("Running agent...\n")

    # Run agent synchronously
    try:
        result = Runner.run_sync(
            starting_agent=arbie_agent,
            input=prompt,
        )

        print("\n" + "=" * 60)
        print("Agent Response:")
        print("=" * 60)
        print(result.final_output)
        print("\n" + "=" * 60)

        return 0

    except Exception as e:
        print(f"\nError running agent: {e}")
        import traceback

        traceback.print_exc()

        # Send burnout notification on failure
        try:
            from arbie.services.db.user import get_user
            from arbie.services.db.email import get_emails_by_session
            from arbie.services.resend_client import get_resend_client

            session = get_session(session_id)
            if session:
                user = get_user(session.get("user_id", ""))
                if user and user.get("email"):
                    # Get threading info from session emails
                    emails = get_emails_by_session(session_id)
                    in_reply_to = emails[0].get("message_id") if emails else None

                    client = get_resend_client()
                    client._send_burnout_notification(
                        original_to=user["email"],
                        original_subject=f"Session {session.get('reference_code', session_id)}",
                        error=e,
                        in_reply_to=in_reply_to,
                        references=[in_reply_to] if in_reply_to else None,
                    )
        except Exception as notify_error:
            print(f"Failed to send burnout notification: {notify_error}")

        return 1


if __name__ == "__main__":
    exit(main())
