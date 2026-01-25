"""Arbie Agent Runner - Entry point for Tower execution.

Accepts parameters to process a specific session with context.
"""

import os
from pathlib import Path

from agents import Runner
from agents.tracing import set_trace_processors

import arbie
from arbie.agents.arbie_agent import arbie_agent
from arbie.services.keywordsai_tracing import KeywordsAITraceProcessor
from arbie.services.db.base import init_all_tables
from arbie.services.db.email import get_attachments_by_session, get_emails_by_session
from arbie.services.db.session import get_session
from arbie.services.file_preprocessing import preprocess_and_classify
from arbie.services.tower_session import TowerEmailSession
from arbie.tools.email_tools import set_session_context as set_email_session_context
from arbie.tools.session_tools import set_session_context as set_session_session_context

# Path to trigger prompts - use arbie module location for Tower compatibility
PROMPTS_DIR = Path(arbie.__file__).parent / "agents" / "prompts" / "triggers"


def load_trigger_prompt(trigger_type: str) -> str:
    """Load a trigger prompt from the prompts directory.

    Args:
        trigger_type: The type of trigger (new_submission, follow_up_response, or generic).

    Returns:
        The prompt template string.
    """
    prompt_file = PROMPTS_DIR / f"{trigger_type}.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    # Fall back to generic prompt
    return (PROMPTS_DIR / "generic.md").read_text()


def build_session_context(
    session_id: str,
    email_id: str | None = None,
) -> str | None:
    """Build a context summary for the session.

    Args:
        session_id: The session to get context for.
        email_id: Optional specific email that triggered this run.

    Returns:
        Formatted context string, or None if session not found.
    """
    session = get_session(session_id)
    if not session:
        return None

    emails = get_emails_by_session(session_id)

    context_parts = [
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
        ])
        # Include email body content
        body_text = latest_email.get("body_text")
        if body_text:
            context_parts.extend([
                "",
                "Email Content:",
                body_text.strip(),
            ])

    return "\n".join(context_parts)


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
    context = build_session_context(session_id, email_id)
    if context is None:
        return f"Error: Session {session_id} not found."

    prompt_template = load_trigger_prompt(trigger_type)
    return prompt_template.replace("{{context}}", context)


def main() -> int:
    """Main entry point for Arbie agent runner."""
    # Get parameters from environment (Tower passes them this way)
    session_id = os.getenv("session_id")
    trigger_type = os.getenv("trigger_type", "unknown")
    email_id = os.getenv("email_id")

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

    # Initialize Keywords AI tracing
    keywordsai_api_key = os.getenv("KEYWORDSAI_API_KEY")
    if keywordsai_api_key:
        set_trace_processors([
            KeywordsAITraceProcessor(
                api_key=keywordsai_api_key,
                endpoint="https://api.keywordsai.co/api/openai/v1/traces/ingest",
            ),
        ])
        print("Keywords AI tracing enabled")
    else:
        print("Warning: KEYWORDSAI_API_KEY not set, tracing disabled")

    # Initialize database tables
    init_all_tables()

    # Set session context for tools
    set_email_session_context(session_id)
    set_session_session_context(session_id)

    # Build the agent prompt
    prompt = build_agent_prompt(
        session_id=session_id,
        trigger_type=trigger_type,
        email_id=email_id,
    )

    print(f"\nAgent Prompt:\n{prompt}\n")
    print("=" * 60)

    # Preprocess attachments (PDFs and images) before agent runs
    attachments = get_attachments_by_session(session_id)
    file_paths = [
        att["storage_path"]
        for att in attachments
        if att.get("storage_path")
    ]

    if file_paths:
        print(f"Preprocessing {len(file_paths)} attachments...")
        try:
            preprocess_result = preprocess_and_classify(
                file_paths=file_paths,
                session_id=session_id,
                email_id=email_id or "",
            )
            print(f"Extracted text from {len(preprocess_result['extracted_text'])} PDFs")
            print(f"Classified {len(preprocess_result['all_image_urls'])} images")
            print(f"Found {len(preprocess_result['rooms'])} rooms")
        except Exception as e:
            print(f"Warning: Preprocessing failed: {e}")
            # Continue anyway - agent can still work without preprocessing

    print("=" * 60)
    print("Running agent...\n")

    # Create session to load conversation history from emails
    # Exclude the triggering email since it's already in the prompt context
    session = TowerEmailSession(session_id, exclude_email_id=email_id)

    # Run agent synchronously
    try:
        result = Runner.run_sync(
            starting_agent=arbie_agent,
            input=prompt,
            session=session,
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
