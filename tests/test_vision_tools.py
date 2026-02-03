"""Tests for vision tools."""

from pathlib import Path

from arbie.tools.vision_tools import analyze_images_impl, load_image_as_base64, classify_image_types_impl

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


def test_classify_image_types_empty():
    """Test with empty paths list."""
    result = classify_image_types_impl([], session_id=None)
    assert "error" in result
    assert "No image paths provided" in result["error"]


def test_classify_image_types_property_photos():
    """Test classification of property photos.

    This test requires property photo images in the assets directory.
    If images are missing, it will skip gracefully.
    """
    # Filter to only existing images
    existing_paths = [p for p in TEST_IMAGE_PATHS if Path(p).exists()]

    if not existing_paths:
        print(f"\nSkipping test_classify_image_types_property_photos - no images found in {ASSETS_DIR}")
        return

    print(f"\nClassifying {len(existing_paths)} images as property/document:")
    for p in existing_paths:
        print(f"  - {p}")

    result = classify_image_types_impl(existing_paths, session_id=None)

    # Should not have error
    assert "error" not in result, f"Unexpected error: {result.get('error')}"

    # Should have required keys
    assert "property_foto_paths" in result
    assert "document_foto_paths" in result

    # All paths should be accounted for
    property_paths = result["property_foto_paths"]
    document_paths = result["document_foto_paths"]
    total_classified = len(property_paths) + len(document_paths)
    assert total_classified == len(existing_paths), f"Expected {len(existing_paths)} images, got {total_classified}"

    # All returned paths should be in the input
    for path in property_paths:
        assert path in existing_paths, f"Property path {path} not in input"
    for path in document_paths:
        assert path in existing_paths, f"Document path {path} not in input"

    print(f"\n--- Classification Results ---")
    print(f"Property photos: {len(property_paths)} images")
    for p in property_paths:
        print(f"  - {Path(p).name}")

    print(f"\nDocument photos: {len(document_paths)} images")
    for p in document_paths:
        print(f"  - {Path(p).name}")


def test_classify_image_types_mixed():
    """Test mixed property and document photos.

    This is a conceptual test that demonstrates the expected behavior.
    In a real scenario, you'd have a mix of property photos and documents.
    """
    # This test requires actual mixed content
    # For now, we'll test with whatever images exist
    existing_paths = [p for p in TEST_IMAGE_PATHS[:3] if Path(p).exists()]

    if len(existing_paths) < 2:
        print("\nSkipping test_classify_image_types_mixed - need at least 2 images")
        return

    result = classify_image_types_impl(existing_paths, session_id=None)

    assert "error" not in result
    assert "property_foto_paths" in result
    assert "document_foto_paths" in result

    # Should classify all images
    total_classified = len(result["property_foto_paths"]) + len(result["document_foto_paths"])
    assert total_classified == len(existing_paths)

    print(f"\n--- Mixed Classification Test ---")
    print(f"Total images: {len(existing_paths)}")
    print(f"Property photos: {len(result['property_foto_paths'])}")
    print(f"Document photos: {len(result['document_foto_paths'])}")


if __name__ == "__main__":
    test_analyze_images()
    print("\n" + "="*60 + "\n")
    test_classify_image_types_empty()
    print("\n" + "="*60 + "\n")
    test_classify_image_types_property_photos()
    print("\n" + "="*60 + "\n")
    test_classify_image_types_mixed()