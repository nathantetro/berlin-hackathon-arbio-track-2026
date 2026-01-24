"""File system tools for Arbie agent.

Provides access to the session file system for reading documents,
listing files, and writing notes/drafts.
"""

from typing import Any, Literal
from agents import function_tool


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
    return {
        "status": "not_implemented",
        "message": "get_session_overview not implemented yet. Would return session summary."
    }


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
    return [
        {
            "status": "not_implemented",
            "message": f"list_files not implemented yet. Would list: {path} (recursive={recursive})"
        }
    ]


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
    return {
        "status": "not_implemented",
        "message": f"read_file not implemented yet. Would read: {path}",
        "params": {
            "keyword": keyword,
            "context_lines": context_lines,
            "max_chars": max_chars
        }
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
    return {
        "status": "not_implemented",
        "message": f"write_file not implemented yet. Would write to: {path}",
        "params": {
            "mode": mode,
            "content_length": len(content)
        }
    }
