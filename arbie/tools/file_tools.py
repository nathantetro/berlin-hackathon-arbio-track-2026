"""File system tools for Arbie agent.

Provides access to the session file system for reading documents,
listing files, and writing notes/drafts.
"""

import os
from typing import Any, Literal

import polars as pl
from agents import function_tool

from arbie.services.db.base import query
from arbie.services.storage import get_storage_service

# Whitelist of supported file extensions for read_file
ALLOWED_READ_EXTENSIONS = {".txt", ".md", ".json", ".pdf"}


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
    Get a high-level overview of the current session including all files.

    Call this FIRST at the start of every turn to understand what's available.

    Returns:
        dict with:
        - files: Complete file tree organized by directory
          - attachments: List of files from emails
          - extracted: List of auto-extracted files (text from PDFs, images)
          - workspace: List of your notes and drafts
          - outputs: List of generated PDFs
        - images: List of all image paths (for use with analyze_images)
        - documents: List of readable document paths (.pdf, .txt, .md, .json)
        - session_metadata: Status, reference_code, timestamps
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

    # Collect files from all directories
    files = {
        "attachments": [],
        "extracted": [],
        "workspace": [],
        "outputs": [],
    }
    images = []
    documents = []

    # Helper to categorize files
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    document_extensions = {".pdf", ".txt", ".md", ".json"}

    def process_file(f, category):
        file_info = {
            "name": f.name,
            "path": f.path,
            "size": f.size,
            "type": f.content_type,
        }
        files[category].append(file_info)

        # Categorize by type
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
