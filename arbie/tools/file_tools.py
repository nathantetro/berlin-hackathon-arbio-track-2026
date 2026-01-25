"""File system tools for Arbie agent.

Provides access to the session file system for reading documents,
listing files, and writing notes/drafts.
"""

import json
import os
from typing import Any, Literal

import polars as pl
from agents import function_tool

from arbie.models.enums import AttachmentStatus
from arbie.services.db.base import query
from arbie.services.storage import get_storage_service

# Whitelist of supported file extensions for read_file
ALLOWED_READ_EXTENSIONS = {".txt", ".md", ".json", ".pdf"}

# Gateway URL for session viewer links (used by agent to build validation URLs)
GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", "https://arbie-gateway.apps.tower.dev")


# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for file tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


def _get_attachment_status_map(session_id: str) -> dict[str, dict]:
    """Get attachment metadata from database, keyed by storage_path."""
    # Query emails for this session first
    emails = query("emails", pl.col("session_id") == session_id)
    if not emails:
        return {}

    email_ids = [e["id"] for e in emails]

    # Query attachments for these emails
    attachments = query("attachments", pl.col("email_id").is_in(email_ids))

    return {
        att["storage_path"]: {
            "id": att["id"],
            "status": att.get("status", "not_analyzed"),
            "extracted_text": att.get("extracted_text"),
            "extracted_metadata": att.get("extracted_metadata", []),
        }
        for att in attachments
    }


def _load_room_metadata(session_id: str, storage) -> list[dict]:
    """Load room metadata from room_meta_*.json files in /extracted/."""
    rooms = []
    try:
        extracted_files = storage.list_files("/extracted/", session_id, recursive=True)
        for f in extracted_files:
            if f.name.startswith("room_meta_") and f.name.endswith(".json"):
                try:
                    content = storage.read(f.path, session_id)
                    room_data = json.loads(content.decode("utf-8"))
                    if isinstance(room_data, list):
                        rooms.extend(room_data)
                    elif isinstance(room_data, dict):
                        rooms.append(room_data)
                except Exception:
                    pass  # Skip malformed JSON
    except Exception:
        pass  # Directory might not exist
    return rooms


def _build_rooms_summary(rooms: list[dict]) -> dict[str, dict]:
    """Build a summary of rooms grouped by type."""
    summary: dict[str, dict] = {}

    for room in rooms:
        room_name = room.get("name", "unknown")
        # Extract room type from name (e.g., "bedroom1" -> "bedroom")
        room_type = "".join(c for c in room_name if not c.isdigit()).rstrip("_")
        if not room_type:
            room_type = "other"

        if room_type not in summary:
            summary[room_type] = {
                "count": 0,
                "images": [],
                "objects": set(),
            }

        summary[room_type]["count"] += 1
        summary[room_type]["images"].extend(room.get("attachments", []))
        summary[room_type]["objects"].update(room.get("objects", []))

    # Convert sets to sorted lists for JSON serialization
    for room_type in summary:
        summary[room_type]["objects"] = sorted(summary[room_type]["objects"])

    return summary


@function_tool
def get_session_overview() -> dict:
    """
    Get a high-level overview of the current session including all files and preprocessing metadata.

    Call this FIRST at the start of every turn to understand what's available.

    Returns:
        dict with:
        - files: Complete file tree organized by directory
          - attachments: List of files with preprocessing status and metadata
          - extracted: List of auto-extracted files (text from PDFs, images)
          - workspace: List of your notes and drafts
          - outputs: List of generated PDFs
        - images: List of all image paths (for use with analyze_images)
        - documents: List of readable document paths (.pdf, .txt, .md, .json)
        - rooms: Room groupings from preprocessing (if available)
        - preprocessing_summary: Counts of processed files
        - session_metadata: Status, reference_code, timestamps

    Attachment status meanings:
        - "processed": Preprocessed data available - use extracted text and room metadata
        - Any other status: Analyze the file manually using read_file() or analyze_images()
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    storage = get_storage_service()

    # Get session info from database
    sessions = query("sessions", pl.col("id") == session_id)
    session = sessions[0] if sessions else None

    # Get attachment metadata from database
    attachment_status_map = _get_attachment_status_map(session_id)

    # Load room metadata from preprocessing
    room_metadata = _load_room_metadata(session_id, storage)
    rooms_summary = _build_rooms_summary(room_metadata)

    # Collect files from all directories
    files = {
        "attachments": [],
        "extracted": [],
        "workspace": [],
        "outputs": [],
    }
    images = []
    documents = []

    # Preprocessing counters
    pdfs_processed = 0
    images_classified = 0

    # Helper to categorize files
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    document_extensions = {".pdf", ".txt", ".md", ".json"}

    def process_file(f, category):
        nonlocal pdfs_processed, images_classified

        file_info = {
            "name": f.name,
            "path": f.path,
            "size": f.size,
            "type": f.content_type,
        }

        # Add preprocessing metadata from database
        att_meta = attachment_status_map.get(f.path, {})
        if att_meta:
            status = att_meta.get("status", "not_analyzed")
            file_info["status"] = status

            # For PDFs, add extracted text info
            ext = os.path.splitext(f.name.lower())[1]
            if ext == ".pdf":
                extracted_text = att_meta.get("extracted_text")
                if extracted_text:
                    file_info["has_extracted_text"] = True
                    # Add preview (first 200 chars)
                    file_info["extracted_text_preview"] = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
                    if status == AttachmentStatus.PROCESSED.value:
                        pdfs_processed += 1
                else:
                    file_info["has_extracted_text"] = False

            # For images, find room type from room metadata
            if ext in image_extensions or (f.content_type and f.content_type.startswith("image/")):
                # Check if this image is in any room's attachments
                for room in room_metadata:
                    if f.path in room.get("attachments", []):
                        room_name = room.get("name", "")
                        room_type = "".join(c for c in room_name if not c.isdigit()).rstrip("_")
                        file_info["room_type"] = room_type
                        if status == AttachmentStatus.PROCESSED.value:
                            images_classified += 1
                        break

        files[category].append(file_info)

        # Categorize by type for quick access lists
        ext = os.path.splitext(f.name.lower())[1]
        if ext in image_extensions or (f.content_type and f.content_type.startswith("image/")):
            images.append(f.path)
        elif ext in document_extensions:
            documents.append(f.path)

    # List all directories
    for directory, category in [
        ("/attachments/", "attachments"),
        ("/extracted/", "extracted"),
        ("/workspace/", "workspace"),
        ("/outputs/", "outputs"),
    ]:
        try:
            dir_files = storage.list_files(directory, session_id, recursive=True)
            for f in dir_files:
                process_file(f, category)
        except Exception:
            pass  # Directory might not exist yet

    # Build overview
    overview = {
        "session_id": session_id,
        "files": files,
        "images": images,
        "image_count": len(images),
        "documents": documents,
        "document_count": len(documents),
        "rooms": rooms_summary,
        "preprocessing_summary": {
            "pdfs_processed": pdfs_processed,
            "images_classified": images_classified,
            "rooms_detected": len(room_metadata),
        },
        "session_metadata": {
            "status": session.get("status") if session else "unknown",
            "reference_code": session.get("reference_code") if session else None,
            "session_url": f"{GATEWAY_BASE_URL}/session/{session.get('reference_code')}" if session and session.get("reference_code") else None,
            "created_at": session.get("created_at").isoformat() if session and session.get("created_at") else None,
            "last_activity_at": session.get("last_activity_at").isoformat() if session and session.get("last_activity_at") else None,
        },
    }

    return overview


@function_tool
def list_files(
    path: str = "/",
    recursive: bool = False
) -> Any:
    """
    List files and directories in the session file system.

    The session file system structure:
    - /attachments/ - Read-only email attachments
    - /extracted/ - Read-only preprocessed content
    - /workspace/ - Your working area for notes and drafts
    - /outputs/ - Generated files (PDFs)

    Args:
        path: Directory path to list (default: root "/")
        recursive: If True, recursively list all subdirectories

    Returns:
        List of file/directory info dicts with:
        - name: File/directory name
        - path: Full path
        - type: "file" or "directory"
        - size: Size in bytes (for files)
        - modified: Last modified timestamp
    """
    session_id = get_session_context()
    if not session_id:
        return [{
            "status": "error",
            "message": "No session context available.",
        }]

    storage = get_storage_service()

    # Handle root path specially
    if path == "/" or path == "":
        # Return the top-level directories
        return [
            {"name": "attachments", "path": "/attachments/", "type": "directory", "size": 0, "modified": None},
            {"name": "extracted", "path": "/extracted/", "type": "directory", "size": 0, "modified": None},
            {"name": "workspace", "path": "/workspace/", "type": "directory", "size": 0, "modified": None},
            {"name": "outputs", "path": "/outputs/", "type": "directory", "size": 0, "modified": None},
        ]

    try:
        files = storage.list_files(path, session_id, recursive=recursive)
        return [
            {
                "name": f.name,
                "path": f.path,
                "type": "directory" if f.content_type == "directory" else "file",
                "size": f.size,
                "modified": f.modified.isoformat() if f.modified else None,
            }
            for f in files
        ]
    except ValueError as e:
        return [{
            "status": "error",
            "message": str(e),
        }]
    except Exception as e:
        return [{
            "status": "error",
            "message": f"Failed to list files: {e}",
        }]


@function_tool
def read_file(
    path: str,
    keyword: str | None = None,
    context_lines: int = 3,
    max_chars: int = 10000
) -> dict:
    """
    Read content from a text-based file.

    Supported formats:
    - .txt, .md, .json - Read directly from storage
    - .pdf - Returns pre-extracted text from preprocessing

    For images, use analyze_images() instead.

    Args:
        path: Path to the file to read
        keyword: Optional keyword to search for (case-insensitive).
                 If provided, only matching sections are returned.
        context_lines: Number of lines of context around keyword matches (default: 3)
        max_chars: Maximum characters to return (default: 10000).
                   Content is truncated if longer.

    Returns:
        dict with:
        - text: The file content (or filtered excerpts)
        - path: Full path to the file
        - truncated: Boolean indicating if content was truncated
        - matches: Number of keyword matches (if keyword provided)
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    # Check file extension against whitelist
    ext = os.path.splitext(path.lower())[1]
    if ext not in ALLOWED_READ_EXTENSIONS:
        return {
            "status": "error",
            "error_code": "unsupported_format",
            "message": f"Unsupported file type '{ext}'. Supported: .txt, .md, .json, .pdf. For images, use analyze_images() instead.",
        }

    # Handle PDFs - get extracted_text from attachments table
    if ext == ".pdf":
        try:
            attachments = query("attachments", pl.col("storage_path") == path)
            if attachments and len(attachments) > 0:
                attachment = attachments[0]
                extracted_text = attachment.get("extracted_text")
                if extracted_text:
                    text = extracted_text
                else:
                    return {
                        "status": "error",
                        "message": "PDF text not yet extracted. Please wait for preprocessing to complete.",
                    }
            else:
                return {
                    "status": "error",
                    "message": f"PDF not found in attachments: {path}",
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read PDF extracted text: {e}",
            }
    else:
        # Handle text files (.txt, .md, .json) - read from storage
        storage = get_storage_service()
        try:
            content_bytes = storage.read(path, session_id)
            text = content_bytes.decode("utf-8")
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"File not found: {path}",
            }
        except ValueError as e:
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read file: {e}",
            }

    # Apply keyword filtering if requested
    if keyword:
        lines = text.split("\n")
        keyword_lower = keyword.lower()
        matching_sections = []
        match_count = 0

        for i, line in enumerate(lines):
            if keyword_lower in line.lower():
                match_count += 1
                # Get context around the match
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                section = "\n".join(lines[start:end])
                matching_sections.append(f"... (line {i + 1})\n{section}")

        if matching_sections:
            text = "\n\n".join(matching_sections)
        else:
            return {
                "text": "",
                "path": path,
                "truncated": False,
                "matches": 0,
                "message": f"No matches found for keyword: {keyword}",
            }

        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + "\n... [truncated]"

        return {
            "text": text,
            "path": path,
            "truncated": truncated,
            "matches": match_count,
        }

    # No keyword - return full content (possibly truncated)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "\n... [truncated]"

    return {
        "text": text,
        "path": path,
        "truncated": truncated,
    }


@function_tool
def write_file(
    path: str,
    content: str,
    mode: Literal["overwrite", "append"] = "overwrite"
) -> dict:
    """
    Write notes or drafts to your workspace.

    Use this actively during processing to:
    - Track your thinking and progress as you work
    - Note missing information you need to follow up on
    - Draft emails before sending (review quality)
    - Prepare property summaries for PDF generation
    - Document decisions and findings

    Can only write to /workspace/**

    Args:
        path: Path under workspace/ (e.g., "notes/progress.md", "drafts/email.md")
        content: Content to write (markdown recommended)
        mode: "overwrite" (default) or "append"

    Returns:
        dict with:
        - path: Full path to the written file
        - bytes_written: Number of bytes written
        - mode: The mode that was used
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    # Validate path is in /workspace/
    normalized_path = path.strip()
    if not normalized_path.startswith("/workspace/"):
        return {
            "status": "error",
            "message": "Can only write to /workspace/ directory.",
        }

    storage = get_storage_service()

    try:
        # Handle append mode
        if mode == "append":
            try:
                existing = storage.read_text(path, session_id)
                content = existing + content
            except FileNotFoundError:
                pass  # File doesn't exist yet, just write new content

        # Write the content
        bytes_written = storage.write(path, content, session_id, content_type="text/plain; charset=utf-8")

        return {
            "path": path,
            "bytes_written": bytes_written,
            "mode": mode,
        }

    except ValueError as e:
        return {
            "status": "error",
            "message": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to write file: {e}",
        }


@function_tool
def get_attachment_metadata(
    paths: list[str] | None = None,
    include_extracted_text: bool = False,
    include_room_details: bool = False
) -> dict:
    """
    Get detailed preprocessing metadata for attachments.

    Use this when you need more detail than get_session_overview() provides,
    such as full extracted text from PDFs or detailed room clustering data.

    Args:
        paths: Specific file paths to get metadata for, or None for all attachments
        include_extracted_text: If True, include full OCR text for PDFs (can be large)
        include_room_details: If True, include full room clustering details from preprocessing

    Returns:
        dict with:
        - attachments: List of attachment metadata
          - path: File path
          - status: Processing status (only "processed" means data is reliable)
          - extracted_text: Full OCR text (if include_extracted_text=True and available)
          - room_type: Classified room type (for images)
          - objects: Detected objects (if include_room_details=True)
        - rooms: Full room metadata (if include_room_details=True)

    Status meanings:
        - "processed": Preprocessed data is reliable - use it
        - Any other status: Analyze the file manually
    """
    session_id = get_session_context()
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available.",
        }

    storage = get_storage_service()

    # Get attachment metadata from database
    attachment_status_map = _get_attachment_status_map(session_id)

    # Load room metadata if requested
    room_metadata = []
    if include_room_details:
        room_metadata = _load_room_metadata(session_id, storage)

    # Build image-to-room mapping for quick lookup
    image_to_room: dict[str, dict] = {}
    for room in room_metadata:
        for img_path in room.get("attachments", []):
            image_to_room[img_path] = room

    # Filter to requested paths if specified
    if paths:
        filtered_map = {p: attachment_status_map.get(p, {}) for p in paths}
    else:
        filtered_map = attachment_status_map

    # Build response
    attachments = []
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

    for path, meta in filtered_map.items():
        att_info = {
            "path": path,
            "status": meta.get("status", "not_analyzed"),
        }

        ext = os.path.splitext(path.lower())[1]

        # Add extracted text for PDFs
        if ext == ".pdf":
            extracted_text = meta.get("extracted_text")
            if extracted_text:
                att_info["has_extracted_text"] = True
                if include_extracted_text:
                    att_info["extracted_text"] = extracted_text
                else:
                    att_info["extracted_text_preview"] = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
            else:
                att_info["has_extracted_text"] = False

        # Add room info for images
        if ext in image_extensions:
            room = image_to_room.get(path)
            if room:
                room_name = room.get("name", "")
                room_type = "".join(c for c in room_name if not c.isdigit()).rstrip("_")
                att_info["room_type"] = room_type
                if include_room_details:
                    att_info["room_name"] = room_name
                    att_info["objects"] = room.get("objects", [])

        attachments.append(att_info)

    result = {
        "attachments": attachments,
    }

    if include_room_details:
        result["rooms"] = room_metadata

    return result
