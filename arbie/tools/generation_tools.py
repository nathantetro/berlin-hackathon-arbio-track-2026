"""Document generation tools for Arbie agent.

Provides tools to generate formatted documents like PDFs using WeasyPrint.
"""

import os
from io import BytesIO
from typing import Any

from agents import function_tool

from arbie.services.storage import get_storage_service


# Session context - set by the agent runner
_current_session_id: str | None = None


def set_session_context(session_id: str) -> None:
    """Set the current session context for generation tools."""
    global _current_session_id
    _current_session_id = session_id


def get_session_context() -> str | None:
    """Get the current session context."""
    return _current_session_id or os.getenv("session_id")


# Default CSS for PDF styling with Arbio branding
DEFAULT_CSS = """
@page {
    size: A4;
    margin: 2cm;
    @top-center {
        content: "Arbio Property Onboarding";
        font-family: system-ui, sans-serif;
        font-size: 10pt;
        color: #666;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: system-ui, sans-serif;
        font-size: 9pt;
        color: #666;
    }
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
    max-width: 100%;
}

h1 {
    font-size: 24pt;
    color: #1a1a1a;
    border-bottom: 2px solid #3b82f6;
    padding-bottom: 0.3em;
    margin-top: 0;
}

h2 {
    font-size: 18pt;
    color: #1a1a1a;
    margin-top: 1.5em;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 0.2em;
}

h3 {
    font-size: 14pt;
    color: #374151;
    margin-top: 1.2em;
}

p {
    margin: 0.8em 0;
}

ul, ol {
    margin: 0.5em 0;
    padding-left: 1.5em;
}

li {
    margin: 0.3em 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
}

th, td {
    border: 1px solid #e5e7eb;
    padding: 0.5em 0.8em;
    text-align: left;
}

th {
    background-color: #f9fafb;
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: #f9fafb;
}

code {
    background-color: #f3f4f6;
    padding: 0.1em 0.3em;
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.9em;
}

pre {
    background-color: #f3f4f6;
    padding: 1em;
    border-radius: 5px;
    overflow-x: auto;
}

blockquote {
    border-left: 4px solid #3b82f6;
    margin: 1em 0;
    padding-left: 1em;
    color: #4b5563;
}

.header {
    text-align: center;
    margin-bottom: 2em;
    padding-bottom: 1em;
    border-bottom: 2px solid #3b82f6;
}

.header img {
    max-height: 50px;
}

.footer {
    margin-top: 2em;
    padding-top: 1em;
    border-top: 1px solid #e5e7eb;
    font-size: 9pt;
    color: #6b7280;
    text-align: center;
}
"""


def _markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML.

    Uses a simple regex-based converter for basic markdown.
    For more complex documents, consider using a proper markdown library.
    """
    import re

    html = markdown_text

    # Escape HTML entities first
    html = html.replace("&", "&amp;")
    html = html.replace("<", "&lt;")
    html = html.replace(">", "&gt;")

    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Code blocks
    html = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", html, flags=re.DOTALL)
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)

    # Blockquotes
    lines = html.split("\n")
    in_blockquote = False
    new_lines = []
    for line in lines:
        if line.startswith("&gt; "):
            if not in_blockquote:
                new_lines.append("<blockquote>")
                in_blockquote = True
            new_lines.append(line[5:])
        else:
            if in_blockquote:
                new_lines.append("</blockquote>")
                in_blockquote = False
            new_lines.append(line)
    if in_blockquote:
        new_lines.append("</blockquote>")
    html = "\n".join(new_lines)

    # Lists (simple unordered)
    lines = html.split("\n")
    in_list = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if not in_list:
                new_lines.append("<ul>")
                in_list = True
            content = line.strip()[2:]
            new_lines.append(f"<li>{content}</li>")
        else:
            if in_list:
                new_lines.append("</ul>")
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append("</ul>")
    html = "\n".join(new_lines)

    # Ordered lists
    lines = html.split("\n")
    in_list = False
    new_lines = []
    for line in lines:
        match = re.match(r"^\d+\.\s+(.+)$", line.strip())
        if match:
            if not in_list:
                new_lines.append("<ol>")
                in_list = True
            new_lines.append(f"<li>{match.group(1)}</li>")
        else:
            if in_list:
                new_lines.append("</ol>")
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append("</ol>")
    html = "\n".join(new_lines)

    # Horizontal rules
    html = re.sub(r"^---+$", r"<hr>", html, flags=re.MULTILINE)
    html = re.sub(r"^\*\*\*+$", r"<hr>", html, flags=re.MULTILINE)

    # Links
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)

    # Paragraphs - wrap text blocks
    paragraphs = html.split("\n\n")
    new_paragraphs = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("<"):
            # Wrap plain text in <p> tags
            lines = p.split("\n")
            wrapped_lines = []
            for line in lines:
                if line and not line.startswith("<"):
                    wrapped_lines.append(f"<p>{line}</p>")
                else:
                    wrapped_lines.append(line)
            new_paragraphs.append("\n".join(wrapped_lines))
        else:
            new_paragraphs.append(p)
    html = "\n\n".join(new_paragraphs)

    return html


@function_tool
def generate_pdf(
    source_path: str,
    output_path: str = "/outputs/output.pdf"
) -> str:
    """
    Generate a PDF from a source document.

    Converts markdown or HTML files to professionally formatted PDFs using
    WeasyPrint. Useful for:
    - Creating property information sheets
    - Generating compliance reports
    - Producing formatted documentation

    The generated PDF includes:
    - Arbio branding/header
    - Professional formatting
    - Table of contents (for longer docs)
    - Page numbers

    Args:
        source_path: Path to source file (markdown or HTML) in /workspace/
        output_path: Where to save the PDF (default: /outputs/output.pdf)

    Returns:
        Path to the generated PDF file.

    Example:
        # First write a markdown file
        write_file(
            "/workspace/property-report.md",
            "# Property Report\\n\\n## Summary\\n..."
        )

        # Then generate PDF
        pdf_path = generate_pdf(
            source_path="/workspace/property-report.md",
            output_path="/outputs/property-report.pdf"
        )
    """
    from weasyprint import HTML, CSS

    session_id = get_session_context()
    if not session_id:
        return "Error: No session context available."

    # Validate output path
    if not output_path.startswith("/outputs/"):
        return "Error: Output path must be in /outputs/ directory."

    storage = get_storage_service()

    try:
        # Read source file
        source_content = storage.read_text(source_path, session_id)

        # Determine if HTML or Markdown
        is_html = source_path.lower().endswith((".html", ".htm"))

        if is_html:
            html_content = source_content
        else:
            # Convert Markdown to HTML
            html_content = _markdown_to_html(source_content)

        # Wrap in full HTML document
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Arbio Property Document</title>
</head>
<body>
    <div class="header">
        <h1 style="border: none; margin: 0;">Arbio</h1>
        <p style="margin: 0;">Property Onboarding</p>
    </div>
    {html_content}
    <div class="footer">
        Generated by Arbie - Arbio's AI Property Onboarding Agent
    </div>
</body>
</html>"""

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=full_html).write_pdf(
            pdf_buffer,
            stylesheets=[CSS(string=DEFAULT_CSS)],
        )
        pdf_bytes = pdf_buffer.getvalue()

        # Save to storage
        storage.write(output_path, pdf_bytes, session_id, content_type="application/pdf")

        return output_path

    except FileNotFoundError:
        return f"Error: Source file not found: {source_path}"
    except Exception as e:
        return f"Error generating PDF: {e}"


@function_tool
def generate_property_summary_pdf(
    property_data: dict[str, Any],
    output_path: str = "/outputs/property-summary.pdf"
) -> str:
    """
    Generate a formatted property summary PDF from structured data.

    Creates a professional property summary document with:
    - Property address and basic info
    - Room breakdown and amenities
    - Compliance status
    - Missing information checklist

    Args:
        property_data: Dict containing property information:
            - address: Property address
            - property_type: Type (apartment, house, etc.)
            - bedrooms: Number of bedrooms
            - bathrooms: Number of bathrooms
            - max_guests: Maximum guest capacity
            - amenities: List of amenities
            - compliance: Compliance check results
            - missing_info: List of missing information items
        output_path: Where to save the PDF (default: /outputs/property-summary.pdf)

    Returns:
        Path to the generated PDF file.
    """
    from weasyprint import HTML, CSS

    session_id = get_session_context()
    if not session_id:
        return "Error: No session context available."

    if not output_path.startswith("/outputs/"):
        return "Error: Output path must be in /outputs/ directory."

    storage = get_storage_service()

    try:
        # Build HTML content from property data
        address = property_data.get("address", "Address not provided")
        property_type = property_data.get("property_type", "Unknown")
        bedrooms = property_data.get("bedrooms", "?")
        bathrooms = property_data.get("bathrooms", "?")
        max_guests = property_data.get("max_guests", "?")
        amenities = property_data.get("amenities", [])
        compliance = property_data.get("compliance", {})
        missing_info = property_data.get("missing_info", [])

        # Build amenities list
        amenities_html = ""
        if amenities:
            amenities_items = "".join(f"<li>{a}</li>" for a in amenities)
            amenities_html = f"<ul>{amenities_items}</ul>"
        else:
            amenities_html = "<p><em>No amenities specified</em></p>"

        # Build compliance section
        compliance_html = ""
        if compliance:
            compliance_items = ""
            for check, status in compliance.items():
                icon = "&#10003;" if status else "&#10007;"
                color = "green" if status else "red"
                compliance_items += f'<li style="color: {color};">{icon} {check}</li>'
            compliance_html = f"<ul>{compliance_items}</ul>"
        else:
            compliance_html = "<p><em>Compliance checks pending</em></p>"

        # Build missing info section
        missing_html = ""
        if missing_info:
            missing_items = "".join(f"<li>{item}</li>" for item in missing_info)
            missing_html = f"""
            <h2>Missing Information</h2>
            <p>The following information is still needed:</p>
            <ul>{missing_items}</ul>
            """

        html_content = f"""
        <h1>Property Summary</h1>

        <h2>Property Details</h2>
        <table>
            <tr><th>Address</th><td>{address}</td></tr>
            <tr><th>Property Type</th><td>{property_type}</td></tr>
            <tr><th>Bedrooms</th><td>{bedrooms}</td></tr>
            <tr><th>Bathrooms</th><td>{bathrooms}</td></tr>
            <tr><th>Max Guests</th><td>{max_guests}</td></tr>
        </table>

        <h2>Amenities</h2>
        {amenities_html}

        <h2>Compliance Status</h2>
        {compliance_html}

        {missing_html}
        """

        # Wrap in full HTML document
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Property Summary - Arbio</title>
</head>
<body>
    <div class="header">
        <h1 style="border: none; margin: 0;">Arbio</h1>
        <p style="margin: 0;">Property Onboarding Summary</p>
    </div>
    {html_content}
    <div class="footer">
        Generated by Arbie - Arbio's AI Property Onboarding Agent
    </div>
</body>
</html>"""

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=full_html).write_pdf(
            pdf_buffer,
            stylesheets=[CSS(string=DEFAULT_CSS)],
        )
        pdf_bytes = pdf_buffer.getvalue()

        # Save to storage
        storage.write(output_path, pdf_bytes, session_id, content_type="application/pdf")

        return output_path

    except Exception as e:
        return f"Error generating PDF: {e}"
