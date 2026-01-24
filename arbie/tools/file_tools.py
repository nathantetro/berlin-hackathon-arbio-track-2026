"""File system tools for Arbie agent.

Provides access to the session file system for reading documents,
listing files, and writing notes/drafts.
"""

import os
from typing import Any, Literal

from agents import function_tool

from arbie.services.storage import get_storage_service


# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for file tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


@function_tool
def get_session_overview() -> dict:
    """
    Get a high-level overview of the current session.

    Provides a summary of:
    - Number and types of attachments
    - Image files available
    - Suggested room groupings based on images
    - Session status and metadata

    Returns:
        SessionOverview dict with:
        - attachments: List of attachment summaries
        - images: List of image paths
        - suggested_rooms: Suggested groupings of images by room
        - session_metadata: Status, dates, etc.
    """
    import polars as pl

    from arbie.services.db.base import query

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

    # List files in each directory
    attachments = []
    images = []

    try:
        # List attachment files
        attachment_files = storage.list_files("/attachments/", session_id, recursive=True)
        for f in attachment_files:
            attachments.append({
                "name": f.name,
                "path": f.path,
                "size": f.size,
                "type": f.content_type,
            })

            # Track images separately
            if f.content_type and f.content_type.startswith("image/"):
                images.append(f.path)
    except Exception:
        pass  # No attachments yet

    try:
        # List extracted files (text from PDFs, etc.)
        extracted_files = storage.list_files("/extracted/", session_id, recursive=True)
        for f in extracted_files:
            if f.content_type and f.content_type.startswith("image/"):
                images.append(f.path)
    except Exception:
        pass  # No extracted files yet

    # Build overview
    overview = {
        "session_id": session_id,
        "attachments": attachments,
        "attachment_count": len(attachments),
        "images": images,
        "image_count": len(images),
        "session_metadata": {
            "status": session.get("status") if session else "unknown",
            "reference_code": session.get("reference_code") if session else None,
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
    Read a file and extract its content, optionally filtering by keyword.

    Supports reading from:
    - /attachments/ - Original email attachments
    - /extracted/ - Preprocessed content (plain text from PDFs, etc.)
    - /workspace/ - Your working notes
    - /outputs/ - Generated files

    Args:
        path: Path to the file to read
        keyword: Optional keyword to search for (case-insensitive).
                 If provided, only matching sections are returned.
        context_lines: Number of lines of context around keyword matches (default: 3)
        max_chars: Maximum characters to return (default: 10000).
                   Content is truncated if longer.

    Returns:
        FileContent dict with:
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

    storage = get_storage_service()

    try:
        # Read file content
        content_bytes = storage.read(path, session_id)

        # Try to decode as text
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Binary file - return info about it
            return {
                "status": "binary",
                "path": path,
                "message": f"Binary file ({len(content_bytes)} bytes). Use analyze_images for images.",
                "size": len(content_bytes),
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


@function_tool
def write_file(
    path: str,
    content: str,
    mode: Literal["overwrite", "append"] = "overwrite"
) -> dict:
    """
    Write content to a file in the workspace.

    Can only write to /workspace/ directory. Use this to:
    - Create notes about missing information
    - Draft emails for review
    - Track research findings
    - Document decisions

    Args:
        path: Path to write to (must be in /workspace/)
        content: Content to write
        mode: Write mode - "overwrite" (default) or "append"

    Returns:
        WriteResult dict with:
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
