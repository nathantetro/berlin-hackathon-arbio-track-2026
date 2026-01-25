"""Direct test of image processing functions without agent framework."""

import base64
import re
from io import BytesIO
from PIL import Image


def _maybe_resize_image(image_bytes: bytes, max_size_bytes: int = 1_000_000, max_width: int = 800) -> bytes:
    """Resize image if over max_size_bytes."""
    if len(image_bytes) <= max_size_bytes:
        return image_bytes

    img = Image.open(BytesIO(image_bytes))

    # Calculate new size maintaining aspect ratio
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Save as JPEG with reasonable quality
    output = BytesIO()
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    img.save(output, format='JPEG', quality=85, optimize=True)
    return output.getvalue()


def test_image_resizing():
    """Test that image resizing works correctly."""
    
    # Create a test image (100x100 red square)
    img = Image.new('RGB', (100, 100), color='red')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    small_image = buffer.getvalue()
    
    print(f"Small image size: {len(small_image)} bytes")
    
    # Should not resize (under 1MB)
    resized = _maybe_resize_image(small_image)
    assert resized == small_image, "Small image should not be resized"
    print("✓ Small image not resized (as expected)")
    
    # Create a large image (2000x2000 red square)
    large_img = Image.new('RGB', (2000, 2000), color='blue')
    buffer = BytesIO()
    large_img.save(buffer, format='PNG')
    large_image = buffer.getvalue()
    
    print(f"Large image size: {len(large_image)} bytes")
    
    # Should resize if over 1MB
    if len(large_image) > 1_000_000:
        resized = _maybe_resize_image(large_image)
        print(f"Resized image size: {len(resized)} bytes")
        assert len(resized) < len(large_image), "Large image should be smaller after resize"
        
        # Verify it's a valid image
        resized_img = Image.open(BytesIO(resized))
        assert resized_img.width <= 800, f"Width should be <= 800, got {resized_img.width}"
        print(f"✓ Large image resized to {resized_img.width}x{resized_img.height}")
    else:
        print("Note: Large test image is under 1MB, skipping resize test")


def test_markdown_image_conversion():
    """Test markdown image syntax is converted to HTML img tags."""
    
    markdown = """# Property Report

![Living Room](/extracted/photo_001.jpg)

Some text here.

![Kitchen](/workspace/kitchen.png)
"""
    
    # Simplified version of the regex from generation_tools.py
    html = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        r'<img src="\2" alt="\1" style="max-width: 100%; height: auto;">',
        markdown
    )
    
    # Verify conversions
    assert '<img src="/extracted/photo_001.jpg" alt="Living Room"' in html
    assert '<img src="/workspace/kitchen.png" alt="Kitchen"' in html
    assert '![' not in html, "All markdown image syntax should be converted"
    
    print("✓ Markdown image syntax converted to HTML")
    print("\nConverted HTML snippet:")
    print(html)


def test_base64_pattern_matching():
    """Test the regex pattern for finding img tags to convert."""
    
    html_with_images = """
<div>
    <img src="/extracted/photo_001.jpg" alt="Photo 1" style="max-width: 100%;">
    <p>Some text</p>
    <img class="thumb" src="/workspace/document.pdf" alt="Doc">
    <img src="/attachments/image.png">
</div>
"""
    
    # Pattern from generation_tools.py
    img_pattern = r'<img\s+([^>]*?)src="(/(?:extracted|attachments|workspace)/[^"]+)"([^>]*?)>'
    
    matches = list(re.finditer(img_pattern, html_with_images))
    
    print(f"Found {len(matches)} image tags to convert:")
    for match in matches:
        print(f"  - Path: {match.group(2)}")
    
    assert len(matches) == 3, f"Should find 3 images, found {len(matches)}"
    print("✓ Image pattern matching works correctly")


if __name__ == "__main__":
    print("Testing image processing functions...\n")
    
    print("=" * 60)
    print("TEST 1: Image Resizing")
    print("=" * 60)
    test_image_resizing()
    
    print("\n" + "=" * 60)
    print("TEST 2: Markdown to HTML Image Conversion")
    print("=" * 60)
    test_markdown_image_conversion()
    
    print("\n" + "=" * 60)
    print("TEST 3: Base64 Pattern Matching")
    print("=" * 60)
    test_base64_pattern_matching()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✓")
    print("=" * 60)
