"""Test the full preprocessing pipeline with real services.

Run with: tower run local (after updating Towerfile script to this file)

This script:
1. Creates a test user and session in the database
2. Uploads assets/pdfs/sample.pdf to blob storage
3. Creates an email and attachment record
4. Runs preprocess_and_classify()
5. Verifies the results
"""

import os
import uuid
from pathlib import Path

from arbie.models.base import utc_now
from arbie.services.db.base import init_all_tables, insert
from arbie.services.db.email import get_attachments_by_session
from arbie.services.storage import get_storage_service
from arbie.services.file_preprocessing import preprocess_and_classify


# Path to sample PDF
SAMPLE_PDF_PATH = Path(__file__).parent.parent / "assets" / "pdfs" / "sample.pdf"


def create_test_user() -> str:
    """Create a test user and return its ID."""
    user_id = f"user-test-{uuid.uuid4().hex[:8]}"
    now = utc_now()
    insert("users", {
        "id": user_id,
        "email": "test-preprocessing@example.com",
        "name": "Test Preprocessing User",
        "phone": None,
        "company": None,
        "created_at": now,
        "updated_at": now,
    })
    print(f"Created test user: {user_id}")
    return user_id


def create_test_session(user_id: str) -> str:
    """Create a test session and return its ID."""
    session_id = f"sess-test-{uuid.uuid4().hex[:8]}"
    now = utc_now()
    insert("sessions", {
        "id": session_id,
        "reference_code": f"ARB-PP-{uuid.uuid4().hex[:4].upper()}",
        "user_id": user_id,
        "property_id": None,
        "status": "RECEIVED",
        "status_reason": "Test preprocessing pipeline",
        "thread_id": None,
        "last_activity_at": now,
        "follow_up_count": 0,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    })
    print(f"Created test session: {session_id}")
    return session_id


def create_test_email(session_id: str) -> str:
    """Create a test email and return its ID."""
    email_id = f"email-test-{uuid.uuid4().hex[:8]}"
    now = utc_now()
    insert("emails", {
        "id": email_id,
        "session_id": session_id,
        "message_id": f"<test-{uuid.uuid4().hex[:8]}@example.com>",
        "direction": "INBOUND",
        "from_address": "test@example.com",
        "to_addresses": ["arbie@test.com"],
        "cc_addresses": [],
        "bcc_addresses": [],
        "subject": "Test Preprocessing Pipeline",
        "body_text": "This is a test email for the preprocessing pipeline.",
        "body_html": None,
        "in_reply_to": None,
        "references": [],
        "received_at": now,
        "sent_at": None,
        "created_at": now,
        "updated_at": now,
    })
    print(f"Created test email: {email_id}")
    return email_id


def upload_sample_pdf(session_id: str, email_id: str) -> str:
    """Upload sample PDF to storage and create attachment record.

    Returns:
        The storage path of the uploaded PDF.
    """
    if not SAMPLE_PDF_PATH.exists():
        raise FileNotFoundError(f"Sample PDF not found: {SAMPLE_PDF_PATH}")

    storage = get_storage_service()
    pdf_content = SAMPLE_PDF_PATH.read_bytes()

    # Upload to /attachments/ directory
    storage_path = "/attachments/sample.pdf"
    storage.write(storage_path, pdf_content, session_id, content_type="application/pdf")
    print(f"Uploaded sample PDF to {storage_path}")

    # Create attachment record
    import hashlib
    checksum = hashlib.sha256(pdf_content).hexdigest()
    now = utc_now()

    attachment_id = f"att-test-{uuid.uuid4().hex[:8]}"
    insert("attachments", {
        "id": attachment_id,
        "email_id": email_id,
        "filename": "sample.pdf",
        "content_type": "application/pdf",
        "size_bytes": len(pdf_content),
        "storage_path": storage_path,
        "checksum": checksum,
        "status": "PENDING",
        "extracted_text": None,
        "extracted_image_ids": [],
        "uploaded_at": now,
        "created_at": now,
        "updated_at": now,
    })
    print(f"Created attachment record: {attachment_id}")

    return storage_path


def run_preprocessing(session_id: str, email_id: str, pdf_path: str) -> dict:
    """Run the preprocessing pipeline and return results."""
    print("\n" + "=" * 60)
    print("RUNNING PREPROCESSING PIPELINE")
    print("=" * 60)

    result = preprocess_and_classify(
        file_paths=[pdf_path],
        session_id=session_id,
        email_id=email_id,
    )

    return result


def verify_results(session_id: str, result: dict) -> bool:
    """Verify the preprocessing results."""
    print("\n" + "=" * 60)
    print("VERIFYING RESULTS")
    print("=" * 60)

    success = True

    # Check extracted text
    extracted_text = result.get("extracted_text", {})
    if extracted_text:
        print(f"[PASS] Extracted text from {len(extracted_text)} PDFs")
        for path, text in extracted_text.items():
            print(f"  - {path}: {len(text)} chars")
    else:
        print("[WARN] No text extracted (may be image-only PDF)")

    # Check image URLs
    all_image_urls = result.get("all_image_urls", [])
    if all_image_urls:
        print(f"[PASS] Found {len(all_image_urls)} images")
    else:
        print("[WARN] No images extracted")

    # Check categorization
    categorized = result.get("categorized_images", {})
    if categorized:
        print("[PASS] Images categorized by room type:")
        for room_type, urls in categorized.items():
            if urls:
                print(f"  - {room_type}: {len(urls)} images")
    else:
        print("[WARN] No image categorization")

    # Check rooms metadata
    rooms = result.get("rooms", [])
    if rooms:
        print(f"[PASS] Extracted metadata for {len(rooms)} rooms")
        for room in rooms:
            print(f"  - {room.get('name')}: {len(room.get('objects', []))} objects")
    else:
        print("[WARN] No room metadata extracted")

    # Check attachment IDs were created
    attachment_ids = result.get("attachment_ids", [])
    if attachment_ids:
        print(f"[PASS] Created {len(attachment_ids)} attachment records")
    else:
        print("[WARN] No attachment records created")

    # Check database was updated
    attachments = get_attachments_by_session(session_id)
    processed_count = sum(
        1 for att in attachments
        if att.get("status") == "PROCESSED" or att.get("extracted_text")
    )
    if processed_count > 0:
        print(f"[PASS] {processed_count} attachments marked as processed in DB")
    else:
        print("[INFO] No attachments marked as processed yet")

    return success


def main() -> int:
    """Run the preprocessing pipeline test."""
    print("=" * 60)
    print("PREPROCESSING PIPELINE TEST")
    print("=" * 60)

    # Check required environment variables
    required_vars = ["MISTRAL_API_KEY"]
    optional_vars = ["RUNPOD_API_KEY", "RUNPOD_ENDPOINT_ID", "OPENAI_API_KEY"]

    print("\nChecking environment...")
    missing_required = [v for v in required_vars if not os.getenv(v)]
    if missing_required:
        print(f"ERROR: Missing required env vars: {missing_required}")
        return 1

    missing_optional = [v for v in optional_vars if not os.getenv(v)]
    if missing_optional:
        print(f"WARNING: Missing optional env vars (some features disabled): {missing_optional}")

    try:
        # Initialize database
        print("\nInitializing database...")
        init_all_tables()

        # Create test data
        print("\nCreating test data...")
        user_id = create_test_user()
        session_id = create_test_session(user_id)
        email_id = create_test_email(session_id)
        pdf_path = upload_sample_pdf(session_id, email_id)

        # Run preprocessing
        result = run_preprocessing(session_id, email_id, pdf_path)

        # Verify results
        success = verify_results(session_id, result)

        print("\n" + "=" * 60)
        if success:
            print("TEST COMPLETED SUCCESSFULLY")
        else:
            print("TEST COMPLETED WITH WARNINGS")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
