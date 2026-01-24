"""File preprocessing service for analyzing files before agent processing.

This service:
1. Extracts text and images from PDFs
2. Stores extracted images to S3
3. Classifies all images using RunPod serverless endpoint
4. Categorizes images by room type



idea later:
- extract amenitites of each individual rooms (store attachament paths list for each individual room)
(- extra LLM call to extract important ameneities)
"""

import os
import httpx
from typing import Any


# RunPod configuration
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "")
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")
RUNPOD_BASE_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"

# Image classification labels for property photos
ROOM_LABELS = [
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
    "other",
]


def extract_images_and_text(pdf_path: str) -> dict[str, Any]:
    """Extract text and images from a PDF file.

    Args:
        pdf_path: S3 path to the PDF file.

    Returns:
        Dict with 'text' (str) and 'images' (list of image bytes).
    """
    # Mock implementation
    return {
        "text": f"Extracted text from {pdf_path}",
        "images": [],  # Would contain image bytes in real implementation
    }


def store_to_s3(image_data: bytes, filename: str, session_id: str) -> str:
    """Store an image to S3 and return its URL.

    Args:
        image_data: Raw image bytes.
        filename: Desired filename for the image.
        session_id: Session ID for organizing files.

    Returns:
        S3 URL of the stored image.
    """
    # Mock implementation
    return f"https://s3.example.com/{session_id}/extracted/{filename}"


def _is_image_file(path: str) -> bool:
    """Check if a file path points to an image based on extension."""
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    ext = os.path.splitext(path.lower())[1]
    return ext in image_extensions


def _is_pdf_file(path: str) -> bool:
    """Check if a file path points to a PDF."""
    return path.lower().endswith(".pdf")


def preprocess_files(
    file_paths: list[str],
    session_id: str,
) -> dict[str, Any]:
    """Preprocess all files: extract from PDFs and collect all image URLs.

    Args:
        file_paths: List of S3 paths to files.
        session_id: Session ID for organizing extracted files.

    Returns:
        Dict with:
            - 'image_urls': List of all image URLs (original + extracted)
            - 'extracted_text': Dict mapping PDF paths to extracted text
    """
    image_urls: list[str] = []
    extracted_text: dict[str, str] = {}

    for path in file_paths:
        if _is_image_file(path):
            # Direct image file - add to list
            image_urls.append(path)

        elif _is_pdf_file(path):
            # PDF file - extract text and images
            extraction = extract_images_and_text(path)
            extracted_text[path] = extraction["text"]

            # Store extracted images to S3
            for idx, img_bytes in enumerate(extraction["images"]):
                pdf_name = os.path.splitext(os.path.basename(path))[0]
                filename = f"{pdf_name}_page_{idx}.png"
                stored_url = store_to_s3(img_bytes, filename, session_id)
                image_urls.append(stored_url)

    return {
        "image_urls": image_urls,
        "extracted_text": extracted_text,
    }


async def classify_images_async(image_urls: list[str]) -> str:
    """Submit images to RunPod for classification (async).

    Args:
        image_urls: List of image URLs to classify.

    Returns:
        RunPod job ID for polling results.
    """
    if not image_urls:
        return ""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{RUNPOD_BASE_URL}/run",
            headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
            json={
                "input": {
                    "image_urls": image_urls,
                    "labels": ROOM_LABELS,
                }
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("id", "")


def classify_images_sync(image_urls: list[str]) -> str:
    """Submit images to RunPod for classification (sync).

    Args:
        image_urls: List of image URLs to classify.

    Returns:
        RunPod job ID for polling results.
    """
    if not image_urls:
        return ""

    with httpx.Client() as client:
        response = client.post(
            f"{RUNPOD_BASE_URL}/run",
            headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
            json={
                "input": {
                    "image_urls": image_urls,
                    "labels": ROOM_LABELS,
                }
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("id", "")


async def get_classification_results_async(job_id: str) -> list[dict[str, Any]] | None:
    """Poll RunPod for job results (async).

    Args:
        job_id: RunPod job ID.

    Returns:
        List of classification results or None if not ready.
    """
    if not job_id:
        return []

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{RUNPOD_BASE_URL}/status/{job_id}",
            headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "COMPLETED":
            return data.get("output", [])
        elif data.get("status") in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"RunPod job failed: {data}")

        return None  # Still in progress


def get_classification_results_sync(job_id: str) -> list[dict[str, Any]] | None:
    """Poll RunPod for job results (sync).

    Args:
        job_id: RunPod job ID.

    Returns:
        List of classification results or None if not ready.
    """
    if not job_id:
        return []

    with httpx.Client() as client:
        response = client.get(
            f"{RUNPOD_BASE_URL}/status/{job_id}",
            headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "COMPLETED":
            return data.get("output", [])
        elif data.get("status") in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"RunPod job failed: {data}")

        return None  # Still in progress


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
    categorized: dict[str, list[str]] = {label: [] for label in ROOM_LABELS}

    for result in classification_results:
        image_url = result.get("image_url", "")
        predictions = result.get("predictions", [])

        if not predictions:
            continue

        # Get the top prediction
        top_prediction = max(predictions, key=lambda p: p.get("score", 0))
        label = top_prediction.get("label", "other")
        score = top_prediction.get("score", 0)

        if score >= confidence_threshold:
            # Normalize label (handle spaces, underscores)
            normalized_label = label.lower().replace(" ", "_")
            if normalized_label in categorized:
                categorized[normalized_label].append(image_url)
            else:
                categorized["other"].append(image_url)
        else:
            # Low confidence - put in other
            categorized["other"].append(image_url)

    return categorized


async def preprocess_and_classify_async(
    file_paths: list[str],
    session_id: str,
    poll_interval: float = 1.0,
    max_wait: float = 300.0,
) -> dict[str, Any]:
    """Full preprocessing pipeline: extract, classify, and categorize (async).

    Args:
        file_paths: List of S3 paths to files.
        session_id: Session ID for organizing files.
        poll_interval: Seconds between polling attempts.
        max_wait: Maximum seconds to wait for classification.

    Returns:
        Dict with:
            - 'categorized_images': Dict mapping room types to image URLs
            - 'extracted_text': Dict mapping PDF paths to extracted text
            - 'all_image_urls': List of all image URLs
    """
    import asyncio

    # Step 1: Preprocess files
    preprocessed = preprocess_files(file_paths, session_id)
    image_urls = preprocessed["image_urls"]
    extracted_text = preprocessed["extracted_text"]

    if not image_urls:
        return {
            "categorized_images": {label: [] for label in ROOM_LABELS},
            "extracted_text": extracted_text,
            "all_image_urls": [],
        }

    # Step 2: Submit for classification
    job_id = await classify_images_async(image_urls)

    # Step 3: Poll for results
    elapsed = 0.0
    results = None
    while elapsed < max_wait:
        results = await get_classification_results_async(job_id)
        if results is not None:
            break
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    if results is None:
        raise TimeoutError(f"Classification job {job_id} did not complete in {max_wait}s")

    # Step 4: Categorize
    categorized = categorize_images_by_room(results)

    return {
        "categorized_images": categorized,
        "extracted_text": extracted_text,
        "all_image_urls": image_urls,
    }


def preprocess_and_classify_sync(
    file_paths: list[str],
    session_id: str,
    poll_interval: float = 1.0,
    max_wait: float = 300.0,
) -> dict[str, Any]:
    """Full preprocessing pipeline: extract, classify, and categorize (sync).

    Args:
        file_paths: List of S3 paths to files.
        session_id: Session ID for organizing files.
        poll_interval: Seconds between polling attempts.
        max_wait: Maximum seconds to wait for classification.

    Returns:
        Dict with:
            - 'categorized_images': Dict mapping room types to image URLs
            - 'extracted_text': Dict mapping PDF paths to extracted text
            - 'all_image_urls': List of all image URLs
    """
    import time

    # Step 1: Preprocess files
    preprocessed = preprocess_files(file_paths, session_id)
    image_urls = preprocessed["image_urls"]
    extracted_text = preprocessed["extracted_text"]

    if not image_urls:
        return {
            "categorized_images": {label: [] for label in ROOM_LABELS},
            "extracted_text": extracted_text,
            "all_image_urls": [],
        }

    # Step 2: Submit for classification
    job_id = classify_images_sync(image_urls)

    # Step 3: Poll for results
    elapsed = 0.0
    results = None
    while elapsed < max_wait:
        results = get_classification_results_sync(job_id)
        if results is not None:
            break
        time.sleep(poll_interval)
        elapsed += poll_interval

    if results is None:
        raise TimeoutError(f"Classification job {job_id} did not complete in {max_wait}s")

    # Step 4: Categorize
    categorized = categorize_images_by_room(results)

    return {
        "categorized_images": categorized,
        "extracted_text": extracted_text,
        "all_image_urls": image_urls,
    }