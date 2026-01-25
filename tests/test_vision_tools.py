"""Tests for vision tools."""

from pathlib import Path

from arbie.tools.vision_tools import analyze_images_impl, load_image_as_base64

# Hardcoded paths to test images
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "images"

TEST_IMAGE_PATHS = [str(ASSETS_DIR / f"{i}.jpg") for i in range(1, 14)]


def test_analyze_images():
    """Test analyzing images from assets directory."""
    # Filter to only existing images
    existing_paths = [p for p in TEST_IMAGE_PATHS if Path(p).exists()]

    if not existing_paths:
        print(f"No images found in {ASSETS_DIR}")
        print("Add images to assets/images/ to test")
        return

    print(f"\nAnalyzing {len(existing_paths)} images:")
    for p in existing_paths:
        print(f"  - {p}")

    result = analyze_images_impl(
        paths=existing_paths,
        prompt="Describe each room shown in these images. What type of room is it? What amenities or features do you see?"
    )

    print(f"\n--- Vision Model Response ---\n{result}\n")
    assert isinstance(result, str)
    assert len(result) > 0


if __name__ == "__main__":
    test_analyze_images()