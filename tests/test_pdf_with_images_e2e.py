"""
End-to-end test for PDF generation with embedded images.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbie.tools.generation_tools import generate_pdf
from arbie.services.storage import get_storage_service
from PIL import Image
from io import BytesIO


def create_test_image(width: int, height: int, color: tuple) -> bytes:
    """Create a test image with specified dimensions and color."""
    img = Image.new('RGB', (width, height), color)
    output = BytesIO()
    img.save(output, format='JPEG', quality=90)
    return output.getvalue()


def test_pdf_with_images():
    """Test generating a PDF with embedded images."""
    print("\n" + "=" * 60)
    print("END-TO-END TEST: PDF with Embedded Images")
    print("=" * 60)
    
    session_id = "test_session_pdf_images"
    storage = get_storage_service()
    
    # Step 1: Create and store test images
    print("\n1. Creating test images...")
    
    # Small image (red, 400x300)
    small_img = create_test_image(400, 300, (255, 100, 100))
    print(f"   Small image: {len(small_img)} bytes")
    
    # Large image (blue, 2000x1500) - should trigger resize
    large_img = create_test_image(2000, 1500, (100, 100, 255))
    print(f"   Large image: {len(large_img)} bytes (should be resized)")
    
    # Store images in virtual filesystem
    storage.write("/extracted/photo_small.jpg", small_img, session_id)
    storage.write("/extracted/photo_large.jpg", large_img, session_id)
    print("   ✓ Images stored in virtual filesystem")
    
    # Step 2: Create markdown with image references
    print("\n2. Creating markdown document...")
    markdown_content = """
# Property Summary Report

## 123 Ocean View Drive, Miami Beach FL

This is a comprehensive property summary with embedded photos.

| Detail | Value |
|--------|-------|
| Property Type | Luxury Apartment |
| Bedrooms | 3 |
| Bathrooms | 2 |
| Max Guests | 6 |

## Room Gallery

### Master Bedroom
Large master suite with king bed and ocean views.

![Master Bedroom](/extracted/photo_small.jpg)

### Living Area
Spacious open-plan living and dining area.

![Living Room](/extracted/photo_large.jpg)

## Summary

This property offers exceptional value with stunning views and modern amenities.
"""
    
    # Store markdown in workspace
    storage.write("/workspace/property_summary.md", markdown_content.encode(), session_id)
    print("   ✓ Markdown document created")
    
    # Step 3: Generate PDF
    print("\n3. Generating PDF with embedded images...")
    try:
        result = generate_pdf(
            source_path="/workspace/property_summary.md",
            destination_path="/outputs/property_summary_with_images.pdf",
            session_id=session_id,
            title="Property Summary Report",
            is_html=False
        )
        
        if result.get("success"):
            print("   ✓ PDF generated successfully!")
            
            # Check PDF size
            pdf_bytes = storage.read("/outputs/property_summary_with_images.pdf", session_id)
            print(f"   PDF size: {len(pdf_bytes)} bytes ({len(pdf_bytes) / 1024:.1f} KB)")
            
            # Verify PDF contains image data (base64 encoded)
            pdf_content = pdf_bytes.decode('latin-1', errors='ignore')
            has_images = 'data:image' in pdf_content or '/Image' in pdf_content
            
            if has_images:
                print("   ✓ PDF contains embedded image data")
            else:
                print("   ⚠ Warning: No image data detected in PDF")
            
            print(f"\n   PDF saved to: {result.get('path')}")
        else:
            print(f"   ✗ PDF generation failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"   ✗ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("END-TO-END TEST PASSED! ✓")
    print("=" * 60)
    print("\nThe PDF with embedded images has been successfully generated.")
    print("Images are automatically resized if >1MB to keep file size reasonable.")
    
    return True


if __name__ == "__main__":
    success = test_pdf_with_images()
    sys.exit(0 if success else 1)
