"""Test OpenAI Vision API with signed URLs passed directly.

Run with: python scripts/test_openai_vision.py [image_url1] [image_url2] ...

Requires: OPENAI_API_KEY
"""

import os
import sys
import json
from openai import OpenAI

# Default test images (public Unsplash URLs)
DEFAULT_TEST_URLS = [
    "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=640",  # bedroom
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=640",  # kitchen
]

SYSTEM_PROMPT = """You are analyzing property images. For each image, identify:
1. The room type (bedroom, kitchen, bathroom, living room, etc.)
2. Key objects/amenities visible

Return JSON in this format:
{
  "rooms": [
    {
      "name": "bedroom1",
      "objects": ["bed", "nightstand", "lamp"],
      "attachments": [0]
    }
  ]
}

Use attachment indices (0-based) to reference which images belong to each room.
"""


def test_openai_vision(image_urls: list[str]) -> dict:
    """Test OpenAI Vision API with URLs passed directly."""
    client = OpenAI()

    # Build image identifiers
    image_ids = [f"img_{i}.jpg" for i in range(len(image_urls))]

    # Build user content with image URLs
    user_content = [
        {"type": "text", "text": f"Analyze these images. Image identifiers: {image_ids}"}
    ]

    for idx, url in enumerate(image_urls):
        print(f"  Adding image {idx + 1}/{len(image_urls)}: {url[:60]}...")
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": url,
                "detail": "low",
            }
        })

    print(f"\nCalling OpenAI API with {len(image_urls)} images...")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=1024,
        response_format={"type": "json_object"},
    )

    result_text = response.choices[0].message.content or "{}"
    print(f"Response received: {len(result_text)} chars")

    return json.loads(result_text)


def main():
    print("=" * 60)
    print("OpenAI Vision API Test (Direct URL Pass)")
    print("=" * 60)

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set")
        return 1

    # Get URLs from args or use defaults
    image_urls = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TEST_URLS
    print(f"\nTesting with {len(image_urls)} image(s):\n")

    try:
        result = test_openai_vision(image_urls)

        print(f"\n{'=' * 60}")
        print("Result:")
        print("=" * 60)
        print(json.dumps(result, indent=2))

        rooms = result.get("rooms", [])
        print(f"\nExtracted {len(rooms)} room(s)")
        for room in rooms:
            print(f"  - {room.get('name')}: {len(room.get('objects', []))} objects")

        print("\n[PASS] Test completed successfully")
        return 0

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
