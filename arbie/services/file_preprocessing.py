"""File preprocessing service for analyzing files before agent processing.

This service:
1. Extracts text and images from PDFs
2. Stores extracted images to Azure Blob Storage
3. Classifies all images using RunPod serverless endpoint
4. Categorizes images by room type
5. Extracts room metadata (clusters images into distinct rooms, extracts objects/amenities)
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
from mistralai import Mistral
from openai import OpenAI

from arbie.models.base import utc_now
from arbie.models.email import Attachment
from arbie.models.enums import AttachmentStatus
from arbie.services.db.base import insert
from arbie.services.storage import (
    get_storage_service,
    StorageService,
)

# Load file processor prompt (read directly since it has runtime placeholders)
FILE_PROCESSOR_PROMPT_PATH = Path(__file__).parent.parent / "agents" / "prompts" / "file_processor.md"
FILE_PROCESSOR_PROMPT = FILE_PROCESSOR_PROMPT_PATH.read_text()

# RunPod configuration
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "")
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")
RUNPOD_BASE_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"

# Room type identifiers (used as keys in results)
ROOM_TYPES = [
    "bedroom",
    "kitchen",
    "living_room",
    "bathroom",
    "outdoor",
    "pool",
    "dining_room",
    "balcony",
    "terrace",
    "garage",
    "garden",
    "document",
]

# CLIP-style labels for zero-shot classification (natural language works better)
CLIP_LABELS = [
    "a photo of a bedroom",
    "a photo of a kitchen",
    "a photo of a living room",
    "a photo of a bathroom",
    "a photo of an outdoor area",
    "a photo of a pool",
    "a photo of a dining room",
    "a photo of a balcony",
    "a photo of a terrace",
    "a photo of a garage",
    "a photo of a garden",
    "a scanned document",
]

# Mapping from CLIP label back to room type
CLIP_LABEL_TO_ROOM = dict(zip(CLIP_LABELS, ROOM_TYPES))


def _get_mistral_client() -> Mistral:
    """Get Mistral client instance."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set")
    return Mistral(api_key=api_key)


def extract_images_and_text(pdf_url: str) -> dict[str, Any]:
    """Extract text and images from a PDF file using Mistral OCR.

    Args:
        pdf_url: Public URL to the PDF file.

    Returns:
        Dict with:
            - 'text': Combined markdown text from all pages
            - 'images': List of dicts with 'data' (bytes) and 'filename' (str)
    """
    client = _get_mistral_client()

    # Call Mistral OCR API
    result = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": pdf_url,
        },
        include_image_base64=True,
    )

    # Combine text from all pages
    text_parts: list[str] = []
    images: list[dict[str, Any]] = []

    for page in result.pages:
        # Add page text
        if page.markdown:
            text_parts.append(f"--- Page {page.index + 1} ---\n{page.markdown}")

        # Extract images
        for img in page.images:
            if img.image_base64:
                img_data = base64.b64decode(img.image_base64)
                images.append({
                    "data": img_data,
                    "filename": f"page_{page.index}_{img.id}.png",
                })

    return {
        "text": "\n\n".join(text_parts),
        "images": images,
    }


def _get_signed_url(
    virtual_path: str,
    session_id: str,
    storage: StorageService,
) -> str:
    """Convert a virtual path to a signed blob URL for public access."""
    return storage.get_signed_url(virtual_path, session_id)


# TODO: iphone image format


def _get_content_type(filename: str) -> str:
    """Get MIME type from filename extension."""
    ext = os.path.splitext(filename.lower())[1]
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".json": "application/json",
        ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


def _is_image_file(path: str) -> bool:
    """Check if a file path points to an image based on extension."""
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    ext = os.path.splitext(path.lower())[1]
    return ext in image_extensions


def _is_pdf_file(path: str) -> bool:
    """Check if a file path points to a PDF."""
    return path.lower().endswith(".pdf")


def _create_attachment_record(
    email_id: str,
    filename: str,
    content: bytes,
    storage_path: str,
) -> dict:
    """Create an attachment record in the database.

    Follows the same logic as store_attachment() in email_processor.py:
    - Calculates checksum from content
    - Creates Attachment model instance
    - Inserts into attachments table

    Args:
        email_id: FK to Email (can be empty for extracted images).
        filename: Filename for the attachment.
        content: Raw file bytes (used for size and checksum).
        storage_path: Virtual path in storage (e.g., '/extracted/photo.png').

    Returns:
        Attachment dict with generated ID.
    """
    checksum = hashlib.sha256(content).hexdigest()
    content_type = _get_content_type(filename)
    now = utc_now()

    attachment = Attachment(
        email_id=email_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        storage_path=storage_path,
        checksum=checksum,
        status=AttachmentStatus.PENDING,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    attachment_dict = attachment.model_dump()
    insert("attachments", attachment_dict)

    return attachment_dict


def preprocess_files(
    file_paths: list[str],
    session_id: str,
    email_id: str = "",
    storage: StorageService | None = None,
) -> dict[str, Any]:
    """Preprocess all files: extract from PDFs and collect all image URLs.

    Args:
        file_paths: List of virtual paths (e.g., /attachments/photo.jpg) or blob URLs.
        session_id: Session ID for organizing extracted files.
        email_id: Email ID to link extracted images to (for DB records).
        storage: Optional StorageService instance (uses singleton if not provided).

    Returns:
        Dict with:
            - 'image_urls': List of all image URLs (original + extracted from PDFs)
            - 'extracted_text': Dict mapping PDF paths to extracted text
            - 'attachment_ids': List of created attachment record IDs
    """
    if storage is None:
        storage = get_storage_service()

    image_urls: list[str] = []
    extracted_text: dict[str, str] = {}
    attachment_ids: list[str] = []

    for path in file_paths:
        if _is_image_file(path):
            # Direct image file - convert to signed URL if it's a virtual path
            if path.startswith("/"):
                image_urls.append(_get_signed_url(path, session_id, storage))
            else:
                # Already a full URL
                image_urls.append(path)

        elif _is_pdf_file(path):
            # Convert virtual path to signed URL for Mistral API
            pdf_url = _get_signed_url(path, session_id, storage) if path.startswith("/") else path

            # Extract text and images using Mistral OCR
            extraction = extract_images_and_text(pdf_url)
            extracted_text[path] = extraction["text"]

            # Store extracted images to Azure Blob Storage and create DB records
            for idx, img_info in enumerate(extraction["images"]):
                pdf_name = os.path.splitext(os.path.basename(path))[0]
                img_bytes = img_info.get("data", b"")
                img_filename = img_info.get("filename", f"page_{idx}.png")

                # Store in /extracted/ directory
                virtual_path = f"/extracted/{pdf_name}_{img_filename}"
                storage.write(virtual_path, img_bytes, session_id, content_type=_get_content_type(img_filename))
                image_urls.append(_get_signed_url(virtual_path, session_id, storage))

                # Create attachment record in DB
                attachment = _create_attachment_record(
                    email_id=email_id,
                    filename=f"{pdf_name}_{img_filename}",
                    content=img_bytes,
                    storage_path=virtual_path,
                )
                attachment_ids.append(attachment["id"])

    return {
        "image_urls": image_urls,
        "extracted_text": extracted_text,
        "attachment_ids": attachment_ids,
    }


def classify_images(image_urls: list[str], timeout: float = 300.0) -> list[dict[str, Any]]:
    """Submit images to RunPod for classification and wait for results.

    Uses RunPod's /runsync endpoint which blocks until completion.

    Args:
        image_urls: List of image URLs to classify.
        timeout: Maximum seconds to wait for classification.

    Returns:
        List of classification results. Each item has:
            - 'image_url': The image URL
            - 'predictions': List of {'label': str, 'score': float}
    """
    if not image_urls:
        return []

    with httpx.Client() as client:
        response = client.post(
            f"{RUNPOD_BASE_URL}/runsync",
            headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
            json={
                "input": {
                    "image_urls": image_urls,
                    "labels": CLIP_LABELS,
                }
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "COMPLETED":
            return data.get("output", [])
        elif data.get("status") in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"RunPod job failed: {data}")
        else:
            # IN_QUEUE or IN_PROGRESS - runsync timed out
            raise TimeoutError(f"Classification did not complete in {timeout}s: {data}")


def categorize_images_by_room(
    classification_results: list[dict[str, Any]],
    confidence_threshold: float = 0.5,
) -> dict[str, list[str]]:
    """Categorize images by room type based on classification results.

    Args:
        classification_results: RunPod classification output. Each item has:
            - 'image_url': The image URL
            - 'predictions': List of {'label': str, 'score': float}
        confidence_threshold: Minimum confidence score to include.

    Returns:
        Dict mapping room types to lists of image URLs.
        Example: {
            'bedroom': ['url1', 'url2'],
            'kitchen': ['url3'],
            'living_room': [],
            ...
        }
    """
    # Initialize all categories
    categorized: dict[str, list[str]] = {room: [] for room in ROOM_TYPES}

    for result in classification_results:
        image_url = result.get("image_url", "")
        predictions = result.get("predictions", [])

        if not predictions:
            continue

        # Get the top prediction
        top_prediction = max(predictions, key=lambda p: p.get("score", 0))
        clip_label = top_prediction.get("label", "")
        score = top_prediction.get("score", 0)

        # Map CLIP label back to room type
        room_type = CLIP_LABEL_TO_ROOM.get(clip_label, "other")

        if score >= confidence_threshold:
            categorized[room_type].append(image_url)
        else:
            # Low confidence - put in other
            categorized["other"].append(image_url)

    return categorized


def _fetch_image_as_base64(url: str, client: httpx.Client) -> tuple[str, str]:
    """Fetch an image URL and return base64 data and content type."""
    response = client.get(url, timeout=30.0)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "image/jpeg")
    image_b64 = base64.b64encode(response.content).decode("utf-8")
    return image_b64, content_type


def extract_room_metadata(
    categorized_images: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Extract metadata for each room category using OpenAI Vision API.

    For each room type category with images, this function:
    1. Sends all images to OpenAI with the file_processor prompt
    2. The LLM clusters images into distinct physical rooms
    3. Extracts visible objects/amenities for each room

    Args:
        categorized_images: Dict mapping room types to lists of image URLs.
            Example: {'bedroom': ['url1', 'url2'], 'kitchen': ['url3']}

    Returns:
        List of room metadata dicts. Each dict has:
            - 'name': Room identifier (e.g., 'bedroom1', 'bedroom2')
            - 'objects': List of visible objects/amenities
            - 'attachments': List of image URLs belonging to this room
    """
    print("\n=== extract_room_metadata START ===")
    print(f"Categories received: {list(categorized_images.keys())}")
    for k, v in categorized_images.items():
        print(f"  {k}: {len(v)} images")

    all_rooms: list[dict[str, Any]] = []
    openai_client = OpenAI()

    with httpx.Client() as http_client:
        for room_type, image_urls in categorized_images.items():
            # Skip empty categories and documents
            if not image_urls or room_type == "document":
                continue

            print(f"\n--- Processing {room_type} ({len(image_urls)} images) ---")

            # Build system prompt with room type hint
            system_prompt = FILE_PROCESSOR_PROMPT.replace("{{ROOM_TYPE_HINT}}", room_type)
            print(f"System prompt length: {len(system_prompt)} chars")

            # Build list of image identifiers
            image_ids: list[str] = []
            for idx, url in enumerate(image_urls):
                # Extract filename from URL or generate one
                filename = url.split("/")[-1].split("?")[0]
                if not filename or filename == url:
                    filename = f"img_{idx}.jpg"
                image_ids.append(filename)

            # Build user message content with images
            user_content: list[dict[str, Any]] = [
                {"type": "text", "text": f"Analyze these {room_type} images. Image identifiers in order: {image_ids}"}
            ]

            # Fetch and encode each image
            url_to_index: dict[str, int] = {}
            for idx, url in enumerate(image_urls):
                try:
                    print(f"  Fetching image {idx + 1}/{len(image_urls)} ({image_ids[idx]}): {url[:60]}...")
                    image_b64, content_type = _fetch_image_as_base64(url, http_client)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{image_b64}",
                            "detail": "low",
                        }
                    })
                    url_to_index[url] = idx
                    print(f"    OK ({content_type}, {len(image_b64)} bytes b64)")
                except Exception as e:
                    print(f"    FAILED: {e}")

            if len(user_content) == 1:
                print(f"  Skipping {room_type}: no images loaded successfully")
                continue

            # Call OpenAI Vision API
            print(f"  Calling OpenAI API with {len(user_content) - 1} images...")
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-5.2",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    max_completion_tokens=4096,
                    response_format={"type": "json_object"},
                )

                result_text = response.choices[0].message.content or "[]"
                print(f"  Response received: {len(result_text)} chars")
                print(f"  Raw response: {result_text[:500]}...")
                rooms = json.loads(result_text)

                # Handle both array and object responses
                if isinstance(rooms, dict):
                    rooms = rooms.get("rooms", [rooms])

                # Map attachment indices back to URLs
                for room in rooms:
                    attachments = room.get("attachments", [])
                    # If attachments are indices, map to URLs
                    if attachments and isinstance(attachments[0], int):
                        room["attachments"] = [
                            image_urls[i] for i in attachments if i < len(image_urls)
                        ]
                    # If attachments are filenames, try to match to URLs
                    elif attachments and isinstance(attachments[0], str):
                        # Keep as-is if they're already URLs, otherwise try to match
                        matched_urls = []
                        for att in attachments:
                            if att.startswith("http"):
                                matched_urls.append(att)
                            else:
                                # Try to find URL containing this filename
                                for url in image_urls:
                                    if att in url:
                                        matched_urls.append(url)
                                        break
                        room["attachments"] = matched_urls if matched_urls else attachments

                    all_rooms.append(room)
                    print(f"  Added room: {room.get('name')} with {len(room.get('objects', []))} objects")

            except Exception as e:
                print(f"  ERROR for {room_type}: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n=== extract_room_metadata DONE: {len(all_rooms)} rooms extracted ===\n")
    return all_rooms


def preprocess_and_classify(
    file_paths: list[str],
    session_id: str,
    email_id: str = "",
    timeout: float = 300.0,
    storage: StorageService | None = None,
) -> dict[str, Any]:
    """Full preprocessing pipeline: extract, classify, categorize, and extract metadata.

    Args:
        file_paths: List of virtual paths (e.g., /attachments/photo.jpg) or blob URLs.
        session_id: Session ID for organizing files.
        email_id: Email ID to link extracted images to (for DB records).
        timeout: Maximum seconds to wait for classification.
        storage: Optional StorageService instance (uses singleton if not provided).

    Returns:
        Dict with:
            - 'categorized_images': Dict mapping room types to image URLs
            - 'extracted_text': Dict mapping PDF paths to extracted text
            - 'all_image_urls': List of all image URLs
            - 'rooms': List of room metadata
            - 'attachment_ids': List of created attachment record IDs
    """
    # Step 1: Preprocess files
    preprocessed = preprocess_files(file_paths, session_id, email_id, storage)
    image_urls = preprocessed["image_urls"]
    extracted_text = preprocessed["extracted_text"]
    attachment_ids = preprocessed["attachment_ids"]

    if not image_urls:
        return {
            "categorized_images": {label: [] for label in ROOM_TYPES},
            "extracted_text": extracted_text,
            "all_image_urls": [],
            "rooms": [],
            "attachment_ids": [],
        }

    # Step 2: Classify images (blocks until complete)
    results = classify_images(image_urls, timeout=timeout)

    # Step 3: Categorize by room type
    categorized = categorize_images_by_room(results)

    # Step 4: Extract room metadata
    rooms = extract_room_metadata(categorized)

    # Step 5: Save room metadata as JSON attachment
    room_meta_attachment_id = None
    if rooms:
        if storage is None:
            storage = get_storage_service()

        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        filename = f"room_meta_{timestamp}.json"
        json_content = json.dumps(rooms, indent=2).encode("utf-8")
        storage_path = f"/extracted/{filename}"

        # Store JSON to blob storage
        storage.write(storage_path, json_content, session_id, content_type="application/json")

        # Create attachment record (reusing same function as images)
        attachment = _create_attachment_record(
            email_id=email_id,
            filename=filename,
            content=json_content,
            storage_path=storage_path,
        )
        room_meta_attachment_id = attachment["id"]
        attachment_ids.append(room_meta_attachment_id)

    return {
        "categorized_images": categorized,
        "extracted_text": extracted_text,
        "all_image_urls": image_urls,
        "rooms": rooms,
        "attachment_ids": attachment_ids,
        "room_meta_attachment_id": room_meta_attachment_id,
    }