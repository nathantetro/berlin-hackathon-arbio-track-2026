"""Test PDF generation with images."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbie.tools.generation_tools import generate_pdf, set_session_context
from arbie.services.storage import get_storage_service


def test_pdf_with_images():
    """Test generating a PDF with embedded images."""
    
    # Set up test session
    session_id = "test_pdf_images"
    set_session_context(session_id)
    storage = get_storage_service()
    
    # Create a simple test image (1x1 red pixel PNG)
    test_image_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf'
        b'\xc0\x00\x00\x00\x03\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    
    # Save test image to storage
    storage.write("/extracted/test_photo.png", test_image_data, session_id)
    
    # Create markdown with image
    markdown_content = """# Property Summary

## 123 Beach Drive, Miami FL

| Detail | Value |
|--------|-------|
| Type | Apartment |
| Bedrooms | 3 |
| Max Guests | 6 |

## Rooms

### Master Bedroom
King bed, ensuite bathroom, ocean view

![Master Bedroom](/extracted/test_photo.png)

### Living Room
Open plan with kitchen, seats 8

![Living Room](/extracted/test_photo.png)
"""
    
    # Save markdown to storage
    storage.write_text("/workspace/test_summary.md", markdown_content, session_id)
    
    # Generate PDF
    result = generate_pdf(
        source_path="/workspace/test_summary.md",
        output_path="/outputs/test_property_summary.pdf"
    )
    
    print(f"PDF generation result: {result}")
    
    # Verify PDF was created
    if result.startswith("/outputs/"):
        pdf_data = storage.read(result, session_id)
        print(f"PDF size: {len(pdf_data)} bytes")
        
        # Basic check that it's a PDF
        assert pdf_data.startswith(b'%PDF'), "Output is not a valid PDF"
        print("✓ PDF generated successfully with images!")
        
        # Optional: Save to local file for manual inspection
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "test_property_summary.pdf"
        output_file.write_bytes(pdf_data)
        print(f"✓ PDF saved to: {output_file}")
    else:
        print(f"Error: {result}")


if __name__ == "__main__":
    test_pdf_with_images()
