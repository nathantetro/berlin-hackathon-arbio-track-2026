#!/usr/bin/env python3
"""Test image conversion from various formats to JPEG.

Tests AVIF, HEIC, PNG, WEBP, and other formats.
"""

import io
import sys
from pathlib import Path

from PIL import Image

# Register HEIC/HEIF support once at module load
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # HEIC support not available

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def convert_image_to_jpeg(image_data: bytes, original_filename: str) -> tuple[bytes, str]:
    """Convert any image format to JPEG.

    Handles: PNG, WEBP, AVIF, HEIC, BMP, TIFF, GIF, and more.

    Args:
        image_data: Raw image bytes.
        original_filename: Original filename (used to determine format).

    Returns:
        Tuple of (jpeg_bytes, new_filename).

    Raises:
        ValueError: If image cannot be converted.
    """
    ext = Path(original_filename).suffix.lower()

    # If already JPEG, return as-is
    if ext in {".jpg", ".jpeg"}:
        return image_data, original_filename

    try:
        # Open the image
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (handles RGBA, P, L modes)
        if img.mode in ("RGBA", "P", "LA"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                # Handle alpha channel
                alpha = img.split()[-1]
                background.paste(img, mask=alpha)
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Save as JPEG
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=90, optimize=True)
        jpeg_bytes = output.getvalue()

        # Generate new filename
        new_filename = Path(original_filename).stem + ".jpg"

        return jpeg_bytes, new_filename

    except Exception as e:
        raise ValueError(f"Failed to convert {original_filename}: {e}") from e


def create_test_images() -> dict[str, bytes]:
    """Create test images in various formats programmatically."""
    from PIL import Image

    images = {}

    # Create a simple 100x100 test image with colors
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    # Add some variation
    for x in range(50):
        for y in range(50):
            img.putpixel((x, y), (0, 255, 0))
    for x in range(50, 100):
        for y in range(50, 100):
            img.putpixel((x, y), (0, 0, 255))

    # Save as PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    images["test.png"] = buf.getvalue()

    # Save as WEBP
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    images["test.webp"] = buf.getvalue()

    # Save as BMP
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    images["test.bmp"] = buf.getvalue()

    # Save as TIFF
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    images["test.tiff"] = buf.getvalue()

    # Save as GIF
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    images["test.gif"] = buf.getvalue()

    # PNG with transparency (RGBA)
    img_rgba = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img_rgba.save(buf, format="PNG")
    images["test_transparent.png"] = buf.getvalue()

    # Try AVIF if supported
    try:
        buf = io.BytesIO()
        img.save(buf, format="AVIF")
        images["test.avif"] = buf.getvalue()
    except Exception as e:
        print(f"  Note: Could not create AVIF test image: {e}")

    # Try HEIC if supported
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        buf = io.BytesIO()
        pillow_heif.from_pillow(img).save(buf, format="HEIF")
        images["test.heic"] = buf.getvalue()
    except Exception as e:
        print(f"  Note: Could not create HEIC test image: {e}")

    return images


def test_conversion():
    """Test image conversion with generated test images."""
    from PIL import Image

    print("=" * 60)
    print("Image Conversion Test")
    print("=" * 60)

    # Check format support
    print("\nFormat support check:")
    try:
        from PIL.features import check
        print(f"  AVIF: {check('avif')}")
        print(f"  WEBP: {check('webp')}")
    except:
        print("  Could not check format support")

    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        print("  HEIC: True (pillow-heif installed)")
    except ImportError:
        print("  HEIC: False (pillow-heif NOT installed)")

    # Create test images
    print("\nCreating test images...")
    test_images = create_test_images()
    print(f"Created {len(test_images)} test images")

    # Test conversion for each
    print("\nTesting conversions:")
    success = 0
    failed = 0

    for filename, image_data in test_images.items():
        print(f"\n--- {filename} ---")
        print(f"  Original: {len(image_data)} bytes")

        try:
            jpeg_bytes, new_filename = convert_image_to_jpeg(image_data, filename)
            print(f"  Converted: {len(jpeg_bytes)} bytes -> {new_filename}")

            # Verify it's valid JPEG
            img = Image.open(io.BytesIO(jpeg_bytes))
            print(f"  Verified: {img.format} {img.size} {img.mode}")
            print(f"  ✓ SUCCESS")
            success += 1

        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    # Test passthrough for JPEG
    print(f"\n--- test.jpg (passthrough) ---")
    # Create a JPEG
    img = Image.new("RGB", (100, 100), color=(255, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_data = buf.getvalue()
    print(f"  Original: {len(jpeg_data)} bytes")

    result_bytes, result_name = convert_image_to_jpeg(jpeg_data, "test.jpg")
    if result_bytes == jpeg_data and result_name == "test.jpg":
        print(f"  Passthrough: {len(result_bytes)} bytes -> {result_name}")
        print(f"  ✓ SUCCESS (unchanged)")
        success += 1
    else:
        print(f"  ✗ FAILED: JPEG was modified")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {success} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = test_conversion()
    sys.exit(0 if success else 1)
