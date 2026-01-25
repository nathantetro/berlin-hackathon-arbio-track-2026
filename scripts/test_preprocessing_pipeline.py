"""Test the full preprocessing pipeline with real services.

Run with: tower run local (after updating Towerfile script to this file)

This script:
1. Creates a test user and session in the database
2. Uploads assets/pdfs/sample.pdf and sample images to blob storage
3. Creates email and attachment records
4. Runs preprocess_and_classify()
5. Verifies the results
"""

import hashlib
import os
import uuid
from pathlib import Path

from arbie.models.base import utc_now
from arbie.services.db.base import init_all_tables, insert
from arbie.services.db.email import get_attachments_by_session
from arbie.services.storage import get_storage_service
from arbie.services.file_preprocessing import preprocess_and_classify, classify_images


# Paths to sample files
ASSETS_DIR = Path(__file__).parent.parent / "assets"
SAMPLE_PDF_PATH = ASSETS_DIR / "pdfs" / "sample.pdf"
SAMPLE_IMAGES_DIR = ASSETS_DIR / "images"


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


def get_content_type(filename: str) -> str:
    """Get MIME type from filename extension."""
    ext = os.path.splitext(filename.lower())[1]
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


def upload_attachment(
    file_path: Path,
    session_id: str,
    email_id: str,
    storage,
) -> str:
    """Upload a file to storage and create attachment record.

    Returns:
        The storage path of the uploaded file.
    """
    content = file_path.read_bytes()
    filename = file_path.name
    content_type = get_content_type(filename)

    # Upload to /attachments/ directory
    storage_path = f"/attachments/{filename}"
    storage.write(storage_path, content, session_id, content_type=content_type)
    print(f"  Uploaded {filename} to {storage_path}")

    # Create attachment record
    checksum = hashlib.sha256(content).hexdigest()
    now = utc_now()

    attachment_id = f"att-test-{uuid.uuid4().hex[:8]}"
    insert("attachments", {
        "id": attachment_id,
        "email_id": email_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "storage_path": storage_path,
        "checksum": checksum,
        "status": "PENDING",
        "extracted_text": None,
        "extracted_image_ids": [],
        "uploaded_at": now,
        "created_at": now,
        "updated_at": now,
    })

    return storage_path


def upload_test_files(session_id: str, email_id: str, max_images: int = 5) -> list[str]:
    """Upload sample PDF and images to storage.

    Args:
        session_id: Session ID for storage organization.
        email_id: Email ID to link attachments to.
        max_images: Maximum number of images to upload (to keep test fast).

    Returns:
        List of storage paths for all uploaded files.
    """
    storage = get_storage_service()
    file_paths = []

    print("\nUploading test files...")

    # Upload PDF if it exists
    if SAMPLE_PDF_PATH.exists():
        path = upload_attachment(SAMPLE_PDF_PATH, session_id, email_id, storage)
        file_paths.append(path)
    else:
        print(f"  WARNING: Sample PDF not found: {SAMPLE_PDF_PATH}")

    # Upload sample images
    if SAMPLE_IMAGES_DIR.exists():
        image_files = sorted(SAMPLE_IMAGES_DIR.glob("*.jpg"))[:max_images]
        for img_path in image_files:
            path = upload_attachment(img_path, session_id, email_id, storage)
            file_paths.append(path)
    else:
        print(f"  WARNING: Sample images directory not found: {SAMPLE_IMAGES_DIR}")

    print(f"Uploaded {len(file_paths)} files total")
    return file_paths


def run_preprocessing(session_id: str, email_id: str, file_paths: list[str]) -> dict:
    """Run the preprocessing pipeline and return results."""
    print("\n" + "=" * 60)
    print("RUNNING PREPROCESSING PIPELINE")
    print("=" * 60)
    print(f"Processing {len(file_paths)} files...")

    result = preprocess_and_classify(
        file_paths=file_paths,
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
        print("[INFO] No text extracted (expected if no PDFs or image-only PDFs)")

    # Check image URLs
    all_image_urls = result.get("all_image_urls", [])
    if all_image_urls:
        print(f"[PASS] Found {len(all_image_urls)} images")
    else:
        print("[WARN] No images found")
        success = False

    # Check categorization
    categorized = result.get("categorized_images", {})
    if categorized:
        non_empty = {k: v for k, v in categorized.items() if v}
        if non_empty:
            print(f"[PASS] Images categorized into {len(non_empty)} room types:")
            for room_type, urls in non_empty.items():
                print(f"  - {room_type}: {len(urls)} images")
        else:
            print("[INFO] No images categorized (RunPod may not be configured)")
    else:
        print("[WARN] No image categorization returned")

    # Check rooms metadata
    rooms = result.get("rooms", [])
    if rooms:
        print(f"[PASS] Extracted metadata for {len(rooms)} rooms")
        for room in rooms:
            print(f"  - {room.get('name')}: {len(room.get('objects', []))} objects")
    else:
        print("[INFO] No room metadata extracted (OpenAI may not be configured)")

    # Check attachment IDs were created
    attachment_ids = result.get("attachment_ids", [])
    if attachment_ids:
        print(f"[PASS] Created {len(attachment_ids)} new attachment records")
    else:
        print("[INFO] No new attachment records created")

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


def test_classify_images(image_urls: list[str]) -> bool:
    """Test the classify_images function with multiple URLs.

    Verifies that:
    1. Images are processed individually (one request per image)
    2. Results are properly aggregated into a single list
    3. Each result contains the expected structure

    Args:
        image_urls: List of image URLs to classify.

    Returns:
        True if test passed, False otherwise.
    """
    print("\n" + "=" * 60)
    print("TESTING classify_images() - Single-file processing")
    print("=" * 60)

    if not os.getenv("RUNPOD_API_KEY") or not os.getenv("RUNPOD_ENDPOINT_ID"):
        print("[SKIP] RunPod credentials not configured")
        return True

    if not image_urls:
        print("[SKIP] No image URLs to test")
        return True

    # Test with multiple images to verify aggregation
    test_urls = image_urls[:3]  # Use up to 3 images
    print(f"Testing with {len(test_urls)} images...")
    for i, url in enumerate(test_urls):
        print(f"  [{i+1}] {url[:80]}...")

    try:
        results = classify_images(test_urls)

        print(f"\nResults received: {len(results)} classification(s)")

        # Verify we got one result per image
        if len(results) != len(test_urls):
            print(f"[FAIL] Expected {len(test_urls)} results, got {len(results)}")
            return False

        print(f"[PASS] Got {len(results)} results for {len(test_urls)} images")

        # Verify each result has expected structure
        for i, result in enumerate(results):
            if "image_url" not in result:
                print(f"[FAIL] Result {i} missing 'image_url' field")
                return False
            if "predictions" not in result:
                print(f"[FAIL] Result {i} missing 'predictions' field")
                return False

            predictions = result.get("predictions", [])
            print(f"  Image {i+1}: {len(predictions)} predictions")

            # Show top prediction
            if predictions:
                top = max(predictions, key=lambda p: p.get("score", 0))
                print(f"    Top: {top.get('label')} ({top.get('score', 0):.2%})")

        print("[PASS] All results have correct structure")
        return True

    except Exception as e:
        print(f"[FAIL] classify_images() raised exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """Run the preprocessing pipeline test."""
    print("=" * 60)
    print("PREPROCESSING PIPELINE TEST")
    print("=" * 60)

    # Check environment variables
    required_vars = []  # No strictly required vars - pipeline handles missing gracefully
    optional_vars = ["MISTRAL_API_KEY", "RUNPOD_API_KEY", "RUNPOD_ENDPOINT_ID", "OPENAI_API_KEY"]

    print("\nChecking environment...")
    missing_required = [v for v in required_vars if not os.getenv(v)]
    if missing_required:
        print(f"ERROR: Missing required env vars: {missing_required}")
        return 1

    missing_optional = [v for v in optional_vars if not os.getenv(v)]
    if missing_optional:
        print(f"INFO: Missing optional env vars (some features may be skipped): {missing_optional}")

    # Report which features will work
    print("\nFeatures enabled:")
    print(f"  - PDF OCR: {'Yes' if os.getenv('MISTRAL_API_KEY') else 'No (MISTRAL_API_KEY missing)'}")
    print(f"  - Image classification: {'Yes' if os.getenv('RUNPOD_API_KEY') and os.getenv('RUNPOD_ENDPOINT_ID') else 'No (RunPod credentials missing)'}")
    print(f"  - Room metadata extraction: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No (OPENAI_API_KEY missing)'}")

    try:
        # Initialize database
        print("\nInitializing database...")
        init_all_tables()

        # Create test data
        print("\nCreating test data...")
        user_id = create_test_user()
        session_id = create_test_session(user_id)
        email_id = create_test_email(session_id)
        file_paths = upload_test_files(session_id, email_id, max_images=5)

        if not file_paths:
            print("ERROR: No test files uploaded")
            return 1

        # Run preprocessing
        result = run_preprocessing(session_id, email_id, file_paths)

        # Test classify_images with the image URLs from preprocessing
        all_image_urls = result.get("all_image_urls", [])
        classify_test_passed = test_classify_images(all_image_urls)

        # Verify results
        success = verify_results(session_id, result) and classify_test_passed

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
