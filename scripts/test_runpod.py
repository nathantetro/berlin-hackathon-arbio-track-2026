"""Minimal test script for RunPod image classification endpoint.

Run with: python scripts/test_runpod.py [image_url1] [image_url2] ...

Requires env vars:
  - RUNPOD_API_KEY
  - RUNPOD_ENDPOINT_ID
"""

import os
import sys
import httpx

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")
RUNPOD_BASE_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}" if RUNPOD_ENDPOINT_ID else None

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

# Public test images
DEFAULT_TEST_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Bedroom_Mitcham.jpg/640px-Bedroom_Mitcham.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Kitchen_interior_design.jpg/640px-Kitchen_interior_design.jpg",
]


def classify_images(image_urls: list[str], timeout: float = 60.0) -> list[dict]:
    """Classify multiple images one at a time and aggregate results."""
    results = []

    with httpx.Client() as client:
        for i, url in enumerate(image_urls):
            print(f"  [{i+1}/{len(image_urls)}] Classifying: {url[:70]}...")

            response = client.post(
                f"{RUNPOD_BASE_URL}/runsync",
                headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
                json={
                    "input": {
                        "image_url": url,
                        "labels": CLIP_LABELS,
                    }
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status")
            print(f"       Status: {status}")

            if status == "COMPLETED":
                output = data.get("output", [])
                if output:
                    # Wrap predictions with image_url
                    results.append({
                        "image_url": url,
                        "predictions": output,
                    })
            elif status in ("FAILED", "CANCELLED"):
                print(f"       ERROR: {data}")
            else:
                print(f"       Unexpected: {data}")

    return results


ROOM_TYPES = [
    "bedroom", "kitchen", "living_room", "bathroom", "outdoor",
    "pool", "dining_room", "balcony", "terrace", "garage", "garden",
    "document", "other",
]

CLIP_LABEL_TO_ROOM = dict(zip(CLIP_LABELS, ROOM_TYPES))


def categorize_images_by_room(
    classification_results: list[dict],
    confidence_threshold: float = 0.5,
) -> dict[str, list[str]]:
    """Categorize images by room type based on classification results."""
    categorized: dict[str, list[str]] = {room: [] for room in ROOM_TYPES}

    for result in classification_results:
        image_url = result.get("image_url", "")
        predictions = result.get("predictions", [])

        if not predictions:
            continue

        top_prediction = max(predictions, key=lambda p: p.get("score", 0))
        clip_label = top_prediction.get("label", "")
        score = top_prediction.get("score", 0)

        room_type = CLIP_LABEL_TO_ROOM.get(clip_label, "other")

        if score >= confidence_threshold:
            categorized[room_type].append(image_url)
        else:
            categorized["other"].append(image_url)

    return categorized


def main():
    print("=" * 60)
    print("RunPod Image Classification Test")
    print("=" * 60)

    if not RUNPOD_API_KEY:
        print("ERROR: RUNPOD_API_KEY not set")
        return 1
    if not RUNPOD_ENDPOINT_ID:
        print("ERROR: RUNPOD_ENDPOINT_ID not set")
        return 1

    print(f"Endpoint: {RUNPOD_BASE_URL}\n")

    # Get URLs from args or use defaults
    image_urls = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TEST_URLS
    print(f"Testing with {len(image_urls)} image(s):\n")

    try:
        results = classify_images(image_urls)

        print(f"\n{'=' * 60}")
        print(f"Results: {len(results)} classification(s) for {len(image_urls)} image(s)")
        print(f"Match: {'PASS' if len(results) == len(image_urls) else 'FAIL'}")
        print("=" * 60)

        for i, res in enumerate(results):
            url = res.get("image_url", "unknown")
            print(f"\n[{i+1}] {url[:60]}...")

            predictions = res.get("predictions", [])
            if predictions:
                top = sorted(predictions, key=lambda x: x["score"], reverse=True)[:3]
                for p in top:
                    print(f"    {p['label']:30} {p['score']:.2%}")

        # Test categorization
        print(f"\n{'=' * 60}")
        print("Testing categorize_images_by_room()")
        print("=" * 60)

        categorized = categorize_images_by_room(results)

        print("\nCategorized results:")
        non_empty = {k: v for k, v in categorized.items() if v}
        for room_type, urls in non_empty.items():
            print(f"  {room_type}: {len(urls)} image(s)")
            for url in urls:
                print(f"    - {url[:50]}...")

        # Verify all images were categorized
        total_categorized = sum(len(urls) for urls in categorized.values())
        print(f"\nTotal categorized: {total_categorized} / {len(results)}")
        print(f"Categorization: {'PASS' if total_categorized == len(results) else 'FAIL'}")

        return 0 if len(results) == len(image_urls) and total_categorized == len(results) else 1

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
