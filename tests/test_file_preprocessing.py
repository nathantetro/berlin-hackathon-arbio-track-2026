"""Test Mistral OCR extraction from a local PDF."""

import base64
import os
from pathlib import Path

from mistralai import Mistral

# Paths
PDF_PATH = Path(__file__).parent.parent / "assets" / "pdfs" / "sample.pdf"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def test_extract_images_and_text():
    """Extract images and text from PDF using Mistral OCR."""
    # Check API key
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("ERROR: Set MISTRAL_API_KEY environment variable")
        print("  export MISTRAL_API_KEY='your-key-here'")
        return

    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        return

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"Processing PDF: {PDF_PATH}")
    print(f"Size: {PDF_PATH.stat().st_size} bytes")

    # Call Mistral OCR API
    client = Mistral(api_key=api_key)

    # Upload file to Mistral first
    print("\nUploading file to Mistral...")
    with open(PDF_PATH, "rb") as f:
        uploaded_file = client.files.upload(
            file={"file_name": PDF_PATH.name, "content": f},
            purpose="ocr",
        )
    print(f"Uploaded file ID: {uploaded_file.id}")

    # Get signed URL for the uploaded file
    signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
    print(f"Got signed URL")

    print("\nCalling Mistral OCR API...")
    result = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": signed_url.url,
        },
        include_image_base64=True,
    )

    # Extract text and images
    text_parts = []
    images = []

    for page in result.pages:
        if page.markdown:
            text_parts.append(f"--- Page {page.index + 1} ---\n{page.markdown}")

        for img in page.images:
            if img.image_base64:
                # Strip data URI prefix if present (e.g., "data:image/jpeg;base64,")
                image_data = img.image_base64
                if image_data.startswith("data:"):
                    image_data = image_data.split(",", 1)[1]

                img_data = base64.b64decode(image_data)
                images.append({
                    "data": img_data,
                    "filename": f"page_{page.index}_{img.id}",
                })

    full_text = "\n\n".join(text_parts)

    # Save text
    text_file = OUTPUT_DIR / "extracted_text.txt"
    text_file.write_text(full_text)
    print(f"\nSaved text to: {text_file}")
    print(f"Text length: {len(full_text)} chars")

    # Save images
    print(f"\nExtracted {len(images)} images:")
    for img in images:
        img_path = OUTPUT_DIR / img["filename"]
        img_path.write_bytes(img["data"])
        print(f"  - {img_path} ({len(img['data'])} bytes)")

    print("\n✓ Done!")


if __name__ == "__main__":
    test_extract_images_and_text()