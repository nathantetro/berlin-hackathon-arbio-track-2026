"""Vision and image analysis tools for Arbie agent.

Provides image analysis capabilities using OpenAI Vision API.
"""

import base64
import os
from typing import Any

from agents import function_tool

from arbie.services.storage import get_storage_service


# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for vision tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


def _get_content_type(path: str) -> str:
    """Get MIME type from file extension."""
    ext = path.lower().split(".")[-1] if "." in path else ""
    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return content_types.get(ext, "image/jpeg")


def load_image_as_base64(path: str) -> tuple[str, str]:
    """Load an image file and return its base64 encoding and content type.
    
    Args:
        path: Path to the image file
        
    Returns:
        Tuple of (base64_encoded_string, content_type)
        
    Raises:
        FileNotFoundError: If the image file doesn't exist
        Exception: For other file reading errors
    """
    with open(path, "rb") as f:
        image_bytes = f.read()
    
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    content_type = _get_content_type(path)
    
    return image_b64, content_type


def analyze_images_impl(
    paths: list[str],
    prompt: str,
    session_id: str | None = None
) -> str:
    """Core implementation of image analysis without session context dependency.
    
    This function can be used directly for testing or when session context
    is provided explicitly.
    
    Args:
        paths: List of image file paths to analyze
        prompt: The analysis prompt/question to ask about the images
        session_id: Optional session ID for storage access. If None, reads from filesystem.
        
    Returns:
        The vision model's response as a string with the requested analysis.
    """
    from openai import OpenAI

    if not paths:
        return "Error: No image paths provided."

    client = OpenAI()

    # Build message content with images
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt}
    ]

    loaded_images = 0
    errors = []

    for path in paths:
        try:
            if session_id:
                # Read from storage service
                storage = get_storage_service()
                image_bytes = storage.read(path, session_id)
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                content_type = _get_content_type(path)
            else:
                # Read directly from filesystem (for testing)
                image_b64, content_type = load_image_as_base64(path)

            # Add image to content
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{image_b64}",
                    "detail": "high",
                }
            })
            loaded_images += 1

        except FileNotFoundError:
            errors.append(f"File not found: {path}")
        except Exception as e:
            errors.append(f"Failed to load {path}: {e}")

    if loaded_images == 0:
        return f"Error: Could not load any images. Errors: {'; '.join(errors)}"

    # Call OpenAI Vision API
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Vision-capable model
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_tokens=4096,
        )

        result = response.choices[0].message.content or "No response from vision model."

        # Append any errors that occurred during image loading
        if errors:
            result += f"\n\nNote: Some images could not be loaded: {'; '.join(errors)}"

        return result

    except Exception as e:
        return f"Error calling vision API: {e}"


@function_tool
def analyze_images(
    paths: list[str],
    prompt: str
) -> str:
    """
    Analyze one or more images using a vision model.

    Send images to a vision-capable model with a custom prompt to extract
    information. Useful for:
    - Identifying room types from photos
    - Counting beds, bathrooms, amenities
    - Assessing property condition
    - Reading text from images (signs, documents)
    - Detecting safety features (smoke detectors, fire extinguishers)

    Args:
        paths: List of image file paths to analyze (typically in /attachments/)
        prompt: The analysis prompt/question to ask about the images.
                Be specific about what information you want extracted.

    Returns:
        The vision model's response as a string with the requested analysis.

    Example:
        analyze_images(
            paths=["/attachments/bedroom1.jpg", "/attachments/bedroom2.jpg"],
            prompt="How many beds are in each image? What size are they?"
        )
    """
    session_id = get_session_context()
    if not session_id:
        return "Error: No session context available."

    return analyze_images_impl(paths, prompt, session_id)


IMAGE_TYPE_CLASSIFICATION_PROMPT_TEMPLATE = """Classify these images into two categories:

**property_foto**: Photos of the property itself
- Interior rooms (bedrooms, bathrooms, kitchens, living rooms, etc.)
- Exterior views (building facade, entrance, balconies)
- Outdoor areas (pool, garden, patio, terrace, parking)
- Amenities and features

**document_foto**: Scanned documents or plans
- Floor plans, blueprints, architectural drawings
- Contracts, certificates, licenses
- Text documents, forms, receipts
- Maps, diagrams

Images provided:
{image_list}

Return JSON with two arrays of file paths:
{{
  "property_foto_paths": ["/attachments/bedroom.jpg", ...],
  "document_foto_paths": ["/attachments/floorplan.jpg", ...]
}}

Classify ALL images. Return ONLY valid JSON.
"""


def classify_image_types_impl(
    paths: list[str],
    session_id: str | None = None
) -> dict[str, Any]:
    """Core implementation for image type classification.

    Args:
        paths: List of image file paths to classify
        session_id: Optional session ID for storage access

    Returns:
        Dict with property_foto_paths and document_foto_paths
    """
    from openai import OpenAI
    import json

    if not paths:
        return {"error": "No image paths provided."}

    storage = get_storage_service()
    client = OpenAI()

    # Build image list for prompt
    image_list = "\n".join([f"{i}. {path}" for i, path in enumerate(paths)])
    prompt = IMAGE_TYPE_CLASSIFICATION_PROMPT_TEMPLATE.format(image_list=image_list)

    # Build message content with all images
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt}
    ]

    loaded_indices = []
    errors = []

    for i, path in enumerate(paths):
        try:
            if session_id:
                # Read from storage service
                image_bytes = storage.read(path, session_id)
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                content_type = _get_content_type(path)
            else:
                # Read directly from filesystem (for testing)
                image_b64, content_type = load_image_as_base64(path)

            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{image_b64}",
                    "detail": "low",  # Low detail sufficient for type classification
                }
            })
            loaded_indices.append(i)

        except Exception as e:
            errors.append(f"Image {i} ({path}): {e}")

    if not loaded_indices:
        return {"error": f"Could not load any images: {'; '.join(errors)}"}

    # Call OpenAI Vision API with structured output
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content or "{}"
        result = json.loads(result_text)

        # LLM returns paths directly
        return {
            "property_foto_paths": result.get("property_foto_paths", []),
            "document_foto_paths": result.get("document_foto_paths", []),
        }

    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON response: {e}"}
    except Exception as e:
        return {"error": f"Vision API error: {e}"}


@function_tool
def classify_image_types(paths: list[str]) -> dict[str, Any]:
    """
    Classify images as property photos or document photos. **Use this tool to classify images before using the analyze_images tool.**.

    Analyzes each image to determine if it's:
    - property_foto: Photos of the property (interior rooms, exterior, pool, garden, etc.)
    - document_foto: Scanned documents, floor plans, contracts, certificates, etc.

    Args:
        paths: List of image file paths to classify (e.g., ["/attachments/img1.jpg", ...])

    Returns:
        Dict with two lists of paths:
        {
            "property_foto_paths": ["/attachments/bedroom.jpg", "/attachments/exterior.jpg"],
            "document_foto_paths": ["/attachments/floorplan.jpg"]
        }

    Example:
        result = classify_image_types([
            "/attachments/bedroom.jpg",
            "/attachments/floorplan.jpg",
            "/attachments/exterior.jpg"
        ])
    """
    session_id = get_session_context()
    if not session_id:
        return {"error": "No session context available."}

    return classify_image_types_impl(paths, session_id)
