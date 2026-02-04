"""Vision and image analysis tools for Arbie agent.

Provides image analysis capabilities using OpenAI Vision API.
"""

import base64
import os
from pathlib import Path
from typing import Any

from agents import function_tool

from arbie.services.storage import get_storage_service
from arbie.services.openai_client import get_openai_client
from arbie.services.db.rooms import (
    create_room_records_from_vision,
    update_attachments_with_room_names,
)


# Load property photo analyzer prompt
PROPERTY_PHOTO_ANALYZER_PROMPT_PATH = (
    Path(__file__).parent.parent / "agents" / "prompts" / "property_photo_analyzer.md"
)
PROPERTY_PHOTO_ANALYZER_PROMPT = PROPERTY_PHOTO_ANALYZER_PROMPT_PATH.read_text()

# Load document image analyzer prompt
DOCUMENT_IMAGE_ANALYZER_PROMPT_PATH = (
    Path(__file__).parent.parent / "agents" / "prompts" / "document_image_analyzer.md"
)
DOCUMENT_IMAGE_ANALYZER_PROMPT = DOCUMENT_IMAGE_ANALYZER_PROMPT_PATH.read_text()


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
    if not paths:
        return "Error: No image paths provided."

    client = get_openai_client()

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
    import json

    if not paths:
        return {"error": "No image paths provided."}

    storage = get_storage_service()
    client = get_openai_client()

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


def analyze_property_fotos_impl(
    paths: list[str],
    session_id: str | None = None,
    save_to_db: bool = False,
    email_id: str = "",
    property_id: str = "",
) -> dict[str, Any]:
    """Core implementation for property photo analysis with room clustering.

    Args:
        paths: List of image file paths to analyze
        session_id: Optional session ID for storage access
        save_to_db: If True, create room records and update attachments in DB
        email_id: Email ID for linking attachments (optional)
        property_id: Property ID for linking rooms (optional, can be set later)

    Returns:
        Dict with:
        - 'rooms': List of room dicts with name, room_type, objects, attachments
        - 'room_ids': List of created room record IDs (empty if save_to_db=False)
    """
    import json

    if not paths:
        return {"rooms": [], "room_ids": []}

    storage = get_storage_service()
    client = get_openai_client()

    # Build image list for user message
    image_list = "\n".join([f"{i}. {path}" for i, path in enumerate(paths)])
    user_text = f"Analyze these property photos. Image identifiers in order:\n{image_list}"

    # Build message content with system prompt and images
    content: list[dict[str, Any]] = [
        {"type": "text", "text": user_text}
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
                    "detail": "high",  # High detail for detailed analysis
                }
            })
            loaded_indices.append(i)

        except Exception as e:
            errors.append(f"Image {i} ({path}): {e}")

    if not loaded_indices:
        return {"rooms": [], "room_ids": []}

    # Call OpenAI Vision API with system + user messages
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROPERTY_PHOTO_ANALYZER_PROMPT},
                {"role": "user", "content": content}
            ],
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content or "[]"
        result = json.loads(result_text)

        # Result should be array or dict with array
        if isinstance(result, dict):
            rooms = result.get("rooms", [])
        else:
            rooms = result

        # Database operations
        room_ids: list[str] = []

        if save_to_db and rooms:
            # Step 1: Create room records
            room_ids = create_room_records_from_vision(rooms, property_id)

            # Step 2: Update attachment records with room names
            update_attachments_with_room_names(rooms, session_id)

        return {
            "rooms": rooms,
            "room_ids": room_ids,
        }

    except json.JSONDecodeError:
        return {"rooms": [], "room_ids": []}
    except Exception:
        return {"rooms": [], "room_ids": []}


@function_tool
def analyze_property_fotos(
    paths: list[str],
    save_to_db: bool = True,
    email_id: str = "",
    property_id: str = "",
) -> dict[str, Any]:
    """
    Analyze property photos and cluster them into distinct rooms with room type classification.

    Analyzes property photos to:
    - Cluster images into distinct physical rooms
    - Classify each room's type (bedroom, bathroom, kitchen, living_room, etc.)
    - Extract visible objects and amenities
    - Group images that show the same room from different angles
    - **Optionally save results to database** (room records + attachment updates)

    This is ideal for processing a batch of mixed property photos where you need to
    understand the room structure and inventory.

    Args:
        paths: List of image file paths to analyze (typically in /attachments/)
        save_to_db: If True, create room records and update attachments in database (default: True)
        email_id: Email ID for linking attachments (optional)
        property_id: Property ID for linking rooms (optional, can be linked later)

    Returns:
        Dict with:
        - rooms: List of room dicts, each with:
            - name: Room identifier (e.g., 'bedroom1', 'kitchen1')
            - room_type: Canonical room type from RoomType enum (24 types)
            - objects: List of visible objects/amenities
            - attachments: List of image paths belonging to this room
        - room_ids: List of created room record IDs (empty list if save_to_db=False)

    Example:
        result = analyze_property_fotos([
            "/attachments/img1.jpg",
            "/attachments/img2.jpg",
            "/attachments/img3.jpg"
        ], save_to_db=True, property_id="prop-123")

        # Access rooms
        for room in result["rooms"]:
            print(f"Found {room['room_type']}: {room['name']}")
            print(f"  Objects: {', '.join(room['objects'])}")
            print(f"  Images: {len(room['attachments'])}")

        # Access room IDs for linking
        print(f"Created room IDs: {result['room_ids']}")
    """
    session_id = get_session_context()
    if not session_id:
        return {"rooms": [], "room_ids": []}

    return analyze_property_fotos_impl(
        paths,
        session_id,
        save_to_db=save_to_db,
        email_id=email_id,
        property_id=property_id,
    )


def analyze_document_images_impl(
    paths: list[str],
    session_id: str | None = None
) -> str:
    """Core implementation for document image analysis.

    Args:
        paths: List of document image paths to analyze
        session_id: Optional session ID for storage access

    Returns:
        Text description of documents with extracted information.
    """
    if not paths:
        return "Error: No document images provided."

    storage = get_storage_service()
    client = get_openai_client()

    # Build image list for user message
    image_list = "\n".join([f"{i}. {path}" for i, path in enumerate(paths)])
    user_text = f"Analyze these document images. Image identifiers in order:\n{image_list}"

    # Build message content
    content: list[dict[str, Any]] = [
        {"type": "text", "text": user_text}
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
                    "detail": "high",  # High detail for reading text
                }
            })
            loaded_indices.append(i)

        except Exception as e:
            errors.append(f"Image {i} ({path}): {e}")

    if not loaded_indices:
        return f"Error: Could not load any images. Errors: {'; '.join(errors)}"

    # Call OpenAI Vision API with system + user messages
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": DOCUMENT_IMAGE_ANALYZER_PROMPT},
                {"role": "user", "content": content}
            ],
            max_tokens=4096,
            # No response_format - returns text
        )

        result = response.choices[0].message.content or "No response from vision model."

        # Append any errors that occurred during image loading
        if errors:
            result += f"\n\nNote: Some images could not be loaded: {'; '.join(errors)}"

        return result

    except Exception as e:
        return f"Error calling vision API: {e}"


@function_tool
def analyze_document_images(paths: list[str]) -> str:
    """
    Analyze document images and extract key information.

    Analyzes scanned documents, floor plans, contracts, certificates, and other
    document-type images to:
    - Identify document type (floor plan, contract, license, certificate, etc.)
    - Extract visible text and key information
    - Describe layout, structure, and notable details
    - Report dates, names, signatures, stamps, measurements

    This is ideal for processing PDFs, scanned contracts, certificates, floor plans,
    and other text-heavy or technical documents.

    Args:
        paths: List of document image paths to analyze (typically in /attachments/)

    Returns:
        Text description of the documents with extracted information.

    Example:
        description = analyze_document_images([
            "/attachments/floorplan.jpg",
            "/attachments/contract.jpg"
        ])
        # Returns: "Image 1 (floorplan.jpg): Floor plan showing 2-bedroom layout...
        #           Image 2 (contract.jpg): Rental contract dated 2024-01-15..."
    """
    session_id = get_session_context()
    if not session_id:
        return "Error: No session context available."

    return analyze_document_images_impl(paths, session_id)
