# Arbie - Tools Specification

## Overview

Arbie uses tools to interact with the external world: reading files, analyzing images, sending emails, updating properties, and researching regulations. Tools are implemented as Python functions decorated with `@function_tool` from the OpenAI Agents SDK.

**Key principle:** Session context is always implicit. Tools do not require `session_id` parameters - Arbie always operates within a single session context.

Sub-agents (like the Research Agent) are exposed to Arbie as handoffs, allowing delegation of specialized tasks.

---

## Tool Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                         ARBIE                                    │
├─────────────────────────────────────────────────────────────────┤
│  File Tools        │  Vision Tools     │  Property Tools        │
│  ─────────────────│──────────────────│──────────────────────── │
│  • get_session_overview              │  • edit_property        │
│  • list_files      │  • analyze_images │  • get_property        │
│  • read_file       │                   │                        │
│  • write_file      │                   │                        │
├─────────────────────────────────────────────────────────────────┤
│  Email Tools       │  Generation Tools │  Session Tools         │
│  ─────────────────│──────────────────│──────────────────────── │
│  • send_email      │  • generate_pdf   │  • update_session      │
│  • fetch_emails    │                   │                        │
├─────────────────────────────────────────────────────────────────┤
│  Sub-Agents (Handoffs)                                          │
│  ─────────────────────────────────────────────────────────────  │
│  • Research Agent                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Session File System

Each session has a virtual file system that Arbie can navigate:

```
/
├── attachments/              # Read-only, from emails
│   ├── email_001/
│   │   ├── property_guide.pdf
│   │   ├── floor_plan.pdf
│   │   └── photo_001.jpg
│   └── email_002/
│       └── additional_info.docx
│
├── extracted/                # Read-only, auto-generated during preprocessing
│   ├── property_guide.txt    # Text extracted from PDF
│   ├── property_guide_img_001.jpg  # Image extracted from PDF
│   ├── property_guide_img_002.jpg
│   └── ...
│
├── workspace/                # Read-write, Arbie's working area
│   ├── notes/
│   │   ├── missing_info.md
│   │   └── research_notes.md
│   └── drafts/
│       └── follow_up_email.md
│
└── outputs/                  # Generated artifacts
    └── property_summary.pdf
```

**Permissions:**

| Path | Read | Write | Created By |
|------|------|-------|------------|
| `/attachments/**` | ✅ | ❌ | Email ingest |
| `/extracted/**` | ✅ | ❌ | Preprocessing pipeline |
| `/workspace/**` | ✅ | ✅ | Arbie |
| `/outputs/**` | ✅ | via `generate_pdf` | Generation tools |

---

## 1. File Tools

### `get_session_overview`

Get a summary of all attachments and workspace files.

```python
@function_tool
def get_session_overview() -> SessionOverview:
    """
    Get a summary of attachments and workspace for the current session.

    Returns:
        SessionOverview with attachment inventory and suggested groupings
    """
```

**Returns:**

```python
class SessionOverview:
    # Counts
    total_attachments: int
    total_documents: int
    total_images: int

    # Documents (text-based files)
    documents: list[DocumentInfo]

    # Images (standalone + extracted from PDFs)
    images: list[ImageInfo]

    # Pre-computed groupings (from preprocessing)
    suggested_room_groupings: dict[str, list[str]]  # room_type → image paths

    # Flags
    has_floor_plan: bool
    has_legal_documents: bool
    low_quality_images: list[str]
    potential_duplicates: list[tuple[str, str]]

    # Agent's workspace files
    workspace_files: list[str]

class DocumentInfo:
    path: str
    filename: str
    content_type: str
    page_count: int | None
    extracted_topics: list[str]  # e.g., ["address", "amenities", "house_rules"]
    has_tables: bool

class ImageInfo:
    path: str
    filename: str
    source: str                  # "standalone" or "extracted_from:{path}"
    room_type_guess: str | None  # "bedroom", "kitchen", etc.
    quality_score: float         # 0.0 - 1.0
    dimensions: tuple[int, int]
```

**Example:**

```python
overview = get_session_overview()
# Returns:
# SessionOverview(
#     total_attachments=5,
#     total_documents=2,
#     total_images=12,
#     documents=[
#         DocumentInfo(path="attachments/email_001/property_guide.pdf",
#                      page_count=8, extracted_topics=["address", "amenities", "rules"]),
#         DocumentInfo(path="attachments/email_001/floor_plan.pdf",
#                      page_count=1, extracted_topics=["layout"])
#     ],
#     images=[...],
#     suggested_room_groupings={
#         "kitchen": ["extracted/property_guide_img_001.jpg", "attachments/email_001/kitchen.jpg"],
#         "bedroom": ["extracted/property_guide_img_003.jpg", "extracted/property_guide_img_004.jpg"],
#         "pool_area": ["attachments/email_001/pool.jpg"],
#         "uncategorized": ["extracted/property_guide_img_002.jpg"]
#     },
#     has_floor_plan=True,
#     low_quality_images=["extracted/property_guide_img_002.jpg"],
#     ...
# )
```

---

### `list_files`

Browse the session file system.

```python
@function_tool
def list_files(
    path: str = "/",
    recursive: bool = False
) -> list[FileInfo]:
    """
    List files in the session file system.

    Args:
        path: Directory path to list (default: root)
        recursive: Whether to include subdirectories

    Returns:
        List of files with metadata
    """
```

**Returns:**

```python
class FileInfo:
    path: str
    filename: str
    is_directory: bool
    content_type: str | None     # MIME type for files
    size_bytes: int
    created_at: datetime
```

**Examples:**

```python
# List root
list_files("/")
# → [attachments/, extracted/, workspace/, outputs/]

# List attachments from first email
list_files("attachments/email_001")
# → [property_guide.pdf, floor_plan.pdf, photo_001.jpg, photo_002.jpg]

# List all workspace files recursively
list_files("workspace", recursive=True)
# → [workspace/notes/missing_info.md, workspace/drafts/follow_up.md]
```

---

### `read_file`

Read content from any file.

```python
@function_tool
def read_file(
    path: str,
    keyword: str | None = None,
    context_lines: int = 3,
    max_chars: int = 10000
) -> FileContent:
    """
    Read a file and extract its content, optionally filtering by keyword.

    Works for:
    - Text files (txt, md, etc.)
    - Documents (PDF, DOCX) - returns extracted text
    - Spreadsheets (XLSX, CSV) - returns as text/tables
    - Agent's workspace files

    For images, returns metadata only (use analyze_images for vision).

    Args:
        path: Path to the file
        keyword: Optional keyword to filter content (case-insensitive)
        context_lines: Lines of context around keyword matches
        max_chars: Maximum characters to return

    Returns:
        FileContent with text and metadata
    """
```

**Returns:**

```python
class FileContent:
    path: str
    filename: str
    content_type: str
    size_bytes: int

    # Content
    text: str | None              # Extracted text (or filtered by keyword)
    matches: list[Match] | None   # Keyword match locations
    tables: list[Table] | None    # Extracted tables (if any)

    # Document metadata
    page_count: int | None
    truncated: bool               # True if max_chars limit was hit

    # Image metadata (if image file)
    is_image: bool
    dimensions: tuple[int, int] | None

class Match:
    line_number: int
    text: str                     # The matched line with context
    page_number: int | None       # For documents
```

**Examples:**

```python
# Read full document
content = read_file("attachments/email_001/property_guide.pdf")
print(content.text)  # Full extracted text

# Search for specific info
content = read_file(
    "attachments/email_001/property_guide.pdf",
    keyword="wifi",
    context_lines=2
)
# Returns only sections mentioning "wifi" with 2 lines before/after

# Read agent's notes
notes = read_file("workspace/notes/missing_info.md")
```

---

### `write_file`

Write content to the workspace.

```python
@function_tool
def write_file(
    path: str,
    content: str,
    mode: Literal["overwrite", "append"] = "overwrite"
) -> WriteResult:
    """
    Write to the agent's workspace area.

    Args:
        path: Path under workspace/ (e.g., "notes/missing_info.md")
        content: Content to write
        mode: "overwrite" replaces file, "append" adds to end

    Returns:
        WriteResult with success status and full path

    Note: Can only write to /workspace/**. Cannot write to
    /attachments or /extracted (read-only).
    """
```

**Returns:**

```python
class WriteResult:
    success: bool
    path: str                    # Full path: "workspace/notes/missing_info.md"
    size_bytes: int
```

**Examples:**

```python
# Create notes about missing information
write_file(
    path="notes/missing_info.md",
    content="""# Missing Information

- [ ] WiFi network name (have password but not SSID)
- [ ] Pool hours - is it heated?
- [ ] Confirm: is the office sofa bed available for guests?
- [ ] Gate code for parking garage
"""
)

# Append to existing notes
write_file(
    path="notes/missing_info.md",
    content="\n- [ ] Emergency contact number\n",
    mode="append"
)

# Draft a follow-up email
write_file(
    path="drafts/follow_up_email.md",
    content="""Hi,

Thanks for submitting your property at 123 Beach Drive!

I have a few quick questions:

1. What is the WiFi network name? I found the password in your guide.
2. What are the pool hours? Is the pool heated?

Best,
Arbie
"""
)

# Draft property summary for PDF generation
write_file(
    path="drafts/property_summary.md",
    content="""# Property Summary: 123 Beach Drive

## Overview
- **Address:** 123 Beach Drive, Miami Beach, FL 33139
- **Type:** Condo
- **Capacity:** 8 guests
- **Bedrooms:** 3
- **Bathrooms:** 2.5

## Rooms

### Master Bedroom
![Master bedroom with ocean view](attachments/email_001/bedroom1.jpg)

King bed with en-suite bathroom and ocean view.

### Kitchen
![Modern kitchen](extracted/property_guide_img_003.jpg)

Fully equipped kitchen with stainless steel appliances.

## Amenities
- Pool (heated)
- WiFi
- Parking (1 spot)
- Smart TV with Netflix

## House Rules
- Check-in: 4:00 PM
- Check-out: 11:00 AM
- No smoking
- No parties
"""
)
```

---

## 2. Vision Tools

### `analyze_images`

Send images to a vision model with a prompt.

```python
@function_tool
def analyze_images(
    paths: list[str],
    prompt: str
) -> str:
    """
    Send one or more images to a vision model with a prompt.

    Args:
        paths: List of image paths to analyze
        prompt: Free-form prompt/question for the vision model

    Returns:
        The vision model's raw response as a string
    """
```

**Examples:**

```python
# Count beds across bedroom photos
response = analyze_images(
    paths=[
        "attachments/email_001/bedroom1.jpg",
        "attachments/email_001/bedroom2.jpg",
        "extracted/property_guide_img_004.jpg"
    ],
    prompt="How many beds total are shown across these images? List each bed with its type (king, queen, twin, bunk, sofa bed)."
)
# → "I can see 4 beds total:\n1. Image 1: 1 king bed\n2. Image 2: 2 twin beds\n3. Image 3: 1 queen bed"

# Check if two images show the same room
response = analyze_images(
    paths=[
        "extracted/property_guide_img_003.jpg",
        "attachments/email_001/kitchen.jpg"
    ],
    prompt="Do these two images show the same room? What details make you think so?"
)
# → "Yes, these appear to be the same kitchen. Both show the same distinctive blue tile backsplash, stainless steel refrigerator, and kitchen island with granite countertop."

# Identify amenities in pool area
response = analyze_images(
    paths=["attachments/email_001/pool.jpg", "attachments/email_001/deck.jpg"],
    prompt="What amenities are visible in these outdoor/pool area photos? List everything you can see."
)
# → "Visible amenities:\n- In-ground pool\n- Hot tub/jacuzzi\n- Outdoor dining table (seats 6)\n- BBQ grill\n- Lounge chairs (4)\n- Pool umbrella\n- Outdoor shower"

# Verify room classification
response = analyze_images(
    paths=["extracted/property_guide_img_002.jpg"],
    prompt="What type of room is this? Is it a bedroom, office, living room, or something else? If there's a bed or sofa bed, describe it."
)
# → "This is a home office that doubles as a guest room. There's a desk with a computer, bookshelves, and a pull-out sofa bed against the wall."

# Check image quality
response = analyze_images(
    paths=["extracted/property_guide_img_007.jpg"],
    prompt="Assess the quality of this image for a property listing. Is it blurry, dark, poorly framed, or otherwise unsuitable? Rate it 1-10."
)
# → "Quality: 4/10. The image is quite dark and slightly blurry. The room appears to be a bathroom but the lighting makes it hard to see details. I'd recommend retaking this photo with better lighting."
```

---

## 3. Property Tools

### `edit_property`

Create or update property fields. This is the primary tool for building up property data.

```python
@function_tool
def edit_property(
    key: str,
    value: Any,
    evidence: Evidence | None = None
) -> EditPropertyResult:
    """
    Create or update a property field.

    On first call, creates the property for this session.
    Subsequent calls update the existing property.

    Args:
        key: The field to set (see Key Patterns below)
        value: The value to set
        evidence: Optional source evidence for traceability

    Returns:
        EditPropertyResult with property_id and any created entity IDs
    """
```

**Key Patterns:**

| Pattern | Example | Description |
|---------|---------|-------------|
| `status` | `status` | Property status (draft, ready, etc.) |
| `{hard_attr}` | `address_line1`, `max_guests`, `bedrooms` | Core property fields |
| `attr:{key}` | `attr:wifi_password`, `attr:pool` | Flexible attributes |
| `attr:{key}:category` | `attr:wifi_password:category` | Set attribute category |
| `room:new` | `room:new` | Create a new room (value = room_type) |
| `room:{id}:{field}` | `room:r123:name`, `room:r123:bed_count` | Update room fields |
| `photo:{id}:{field}` | `photo:p123:description` | Update photo metadata |
| `photo:{id}:room_id` | `photo:p123:room_id` | Assign photo to a room |
| `photo:{id}:status` | `photo:p123:status` | Photo approval status |
| `compliance:{id}:{field}` | `compliance:c1:status` | Compliance check fields |

**Evidence Object:**

```python
class Evidence:
    type: Literal["document", "image", "email_body", "research", "owner"]
    path: str | None              # File path in session
    url: str | None               # Research source URL
    page_number: int | None       # Page in document
    text_snippet: str | None      # Relevant text excerpt
    confidence: float             # 0.0 - 1.0
```

**Examples:**

```python
# Set address (creates property on first call)
result = edit_property(
    key="address_line1",
    value="123 Beach Drive",
    evidence=Evidence(
        type="document",
        path="attachments/email_001/property_guide.pdf",
        page_number=1,
        text_snippet="Property Address: 123 Beach Drive",
        confidence=0.95
    )
)
# Returns: {"property_id": "prop_789", "created": True}

# Set capacity
edit_property(key="max_guests", value=8)
edit_property(key="bedrooms", value=3)
edit_property(key="bathrooms", value=2.5)

# Set flexible attributes
edit_property(
    key="attr:wifi_password",
    value="BeachLife2024!",
    evidence=Evidence(
        type="document",
        path="attachments/email_001/property_guide.pdf",
        page_number=2,
        text_snippet="WiFi Password: BeachLife2024!"
    )
)

edit_property(key="attr:pool", value=True)
edit_property(key="attr:pool_heated", value=True)
edit_property(key="attr:checkout_time", value="11:00 AM")

# Create a room
result = edit_property(key="room:new", value="bedroom")
# Returns: {"room_id": "room_001", ...}

# Update room details
edit_property(key="room:room_001:name", value="Master Bedroom")
edit_property(key="room:room_001:bed_count", value=1)
edit_property(key="room:room_001:bed_types", value=["king"])
edit_property(key="room:room_001:is_ensuite", value=True)

# Assign photo to room
edit_property(key="photo:photo_001:room_id", value="room_001")
edit_property(
    key="photo:photo_001:description",
    value="Master bedroom with king bed and ocean view"
)

# Update compliance status
edit_property(
    key="compliance:comp_001:status",
    value="compliant",
    evidence=Evidence(
        type="research",
        url="https://www.miamibeachfl.gov/city-hall/finance/resort-tax/"
    )
)
```

---

### `get_property`

Retrieve current state of the property.

```python
@function_tool
def get_property(
    include_history: bool = False
) -> Property:
    """
    Get the current state of the session's property.

    Args:
        include_history: Whether to include attribute change history

    Returns:
        Full Property object with all attributes, rooms, photos, compliance checks
    """
```

**Example:**

```python
property = get_property()
# Returns full Property object as defined in schema.md
```

---

## 4. Email Tools

### `send_email`

Send an email from Arbie to the property owner.

```python
@function_tool
def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    reply_to_message_id: str | None = None
) -> SendEmailResult:
    """
    Send an email as Arbie.

    Args:
        to: Recipient email address(es)
        subject: Email subject line
        body: Email body (plain text)
        attachments: Optional list of file paths to attach (from workspace/outputs)
        reply_to_message_id: Message-ID to thread with previous email

    Returns:
        SendEmailResult with message_id and delivery status
    """
```

**Returns:**

```python
class SendEmailResult:
    success: bool
    message_id: str
    sent_at: datetime
```

**Examples:**

```python
# Send follow-up asking for missing info
send_email(
    to="owner@example.com",
    subject="Re: Property Submission - A few questions",
    body="""Hi,

Thanks for submitting your property at 123 Beach Drive!

I've reviewed your documents and have a few questions:

1. What is the WiFi network name? I found the password in your welcome guide.

2. Is the pool heated? If so, what months is heating available?

3. The photos show what looks like a home office with a sofa bed. Is this available for guests as a 4th sleeping area?

Please reply to this email with the details.

Best,
Arbie
""",
    reply_to_message_id="<original-message-id@mail.com>"
)

# Send property ready notification with PDF
send_email(
    to="owner@example.com",
    subject="Your property is ready for review!",
    body="""Hi,

Great news! I've finished processing your property at 123 Beach Drive.

I've attached a summary PDF with all the details. Please review it and click the link below to validate:

https://arbie.arbio.com/validate/abc123xyz

If anything needs correction, you can make changes on that page before validating.

Best,
Arbie
""",
    attachments=["outputs/property_summary.pdf"]
)
```

---

### `fetch_emails`

Retrieve emails for the session.

```python
@function_tool
def fetch_emails(
    direction: Literal["inbound", "outbound", "all"] = "all",
    limit: int = 50
) -> list[Email]:
    """
    Fetch emails for this session.

    Args:
        direction: Filter by direction
        limit: Maximum number to return

    Returns:
        List of Email objects with attachment references
    """
```

**Returns:**

```python
class Email:
    message_id: str
    direction: str               # "inbound" or "outbound"
    from_address: str
    to_addresses: list[str]
    subject: str
    body_text: str
    sent_at: datetime | None
    received_at: datetime | None
    attachments: list[str]       # Paths in /attachments/
```

---

## 5. Generation Tools

### `generate_pdf`

Convert a markdown file to PDF.

```python
@function_tool
def generate_pdf(
    source_path: str,
    output_path: str = "outputs/output.pdf"
) -> str:
    """
    Convert a markdown file to a formatted PDF.

    Images referenced in markdown (![alt](path)) are embedded.
    Basic styling and branding applied automatically.

    Args:
        source_path: Path to markdown file (in workspace/)
        output_path: Where to save the PDF (in outputs/)

    Returns:
        Path to the generated PDF
    """
```

**Example:**

```python
# First, write the summary markdown
write_file(
    path="drafts/property_summary.md",
    content="""# Property Summary: 123 Beach Drive

## Overview
| | |
|---|---|
| **Address** | 123 Beach Drive, Miami Beach, FL 33139 |
| **Type** | Condo |
| **Capacity** | 8 guests |
| **Bedrooms** | 3 |
| **Bathrooms** | 2.5 |

## Rooms

### Master Bedroom
![Master bedroom](attachments/email_001/bedroom1.jpg)

King bed with en-suite bathroom and ocean view.

### Second Bedroom
![Second bedroom](attachments/email_001/bedroom2.jpg)

Two twin beds, shared bathroom.

### Kitchen
![Kitchen](extracted/property_guide_img_003.jpg)

Fully equipped with stainless steel appliances, dishwasher, and coffee maker.

## Amenities
- Heated pool
- High-speed WiFi
- Smart TV with Netflix
- Washer/dryer in unit
- 1 parking spot

## House Rules
- Check-in: 4:00 PM
- Check-out: 11:00 AM
- No smoking
- No parties or events
- Quiet hours: 10 PM - 8 AM

## Compliance
- **STR Permit:** STR-2024-1234 (valid through Dec 2025)
- **Resort Tax:** Registered
"""
)

# Then generate the PDF
pdf_path = generate_pdf(
    source_path="drafts/property_summary.md",
    output_path="outputs/property_summary.pdf"
)
# Returns: "outputs/property_summary.pdf"
```

---

## 6. Session Tools

### `update_session`

Update session status.

```python
@function_tool
def update_session(
    status: SessionStatus | None = None,
    status_reason: str | None = None
) -> Session:
    """
    Update session status.

    Args:
        status: New status
        status_reason: Explanation for status change

    Returns:
        Updated Session object
    """
```

**Session Statuses:**

| Status | Description |
|--------|-------------|
| `received` | Initial submission received |
| `extracting` | Processing attachments |
| `awaiting_info` | Waiting for owner response |
| `researching` | Compliance research in progress |
| `ready` | Ready for owner validation |
| `validated` | Owner confirmed, complete |
| `archived` | Closed without completion |

**Example:**

```python
update_session(
    status="awaiting_info",
    status_reason="Waiting for owner to confirm bed count and provide WiFi network name"
)
```

---

## 7. Sub-Agents (Handoffs)

Sub-agents are specialized agents that Arbie can delegate to for specific tasks.

### Research Agent

Researches information using web search (Tavily). Primary use case: local STR regulations.

```python
research_agent = Agent(
    name="Research Agent",
    instructions="""You are a research specialist. Your job is to find accurate,
    up-to-date information from authoritative sources.

    For regulatory research:
    - Find official government sources
    - Identify specific permit requirements
    - Note registration deadlines
    - Find tax obligations
    - Always cite your sources with URLs
    """,
    tools=[tavily_search, tavily_extract],
    model="gpt-4o"
)

# Arbie has this as a handoff
arbie = Agent(
    name="Arbie",
    handoffs=[research_agent],
    ...
)
```

**When Arbie hands off to Research Agent:**

```
Arbie: "I need to research short-term rental regulations for 123 Beach Drive, Miami Beach, FL 33139"

[Handoff to Research Agent]

Research Agent:
- Searches "Miami Beach short-term rental regulations 2024"
- Extracts info from miamibeachfl.gov
- Returns structured compliance requirements

[Returns to Arbie with results]
```

**Research Agent Tools:**

| Tool | Description |
|------|-------------|
| `tavily_search` | Web search optimized for LLMs |
| `tavily_extract` | Extract clean content from URLs |

---

## Error Handling

All tools return structured errors when they fail:

```python
class ToolError:
    error_code: str          # "not_found", "permission_denied", "validation_error"
    message: str             # Human-readable message
    retriable: bool          # Whether Arbie should retry
    details: dict | None     # Additional context
```

**Common Error Codes:**

| Code | Description |
|------|-------------|
| `not_found` | File or resource doesn't exist |
| `permission_denied` | Cannot write to read-only location |
| `validation_error` | Invalid parameters |
| `rate_limited` | Too many requests (e.g., vision API) |
| `service_error` | External service failure |

---

## Rate Limits

| Tool | Limit | Notes |
|------|-------|-------|
| `send_email` | 5/minute | Prevent spam |
| `analyze_images` | 20/minute | Vision API costs |
| `tavily_search` | 100/day | API quota |

---

## Tool Summary

| Tool | Purpose |
|------|---------|
| **Files** | |
| `get_session_overview()` | Summary of attachments, images, suggested room groupings |
| `list_files(path?, recursive?)` | Browse the file system |
| `read_file(path, keyword?, max_chars?)` | Read any file with optional search |
| `write_file(path, content, mode?)` | Write notes, drafts to workspace |
| **Vision** | |
| `analyze_images(paths, prompt)` | Send images + prompt to vision model |
| **Property** | |
| `edit_property(key, value, evidence?)` | Create/update property, rooms, photos |
| `get_property(include_history?)` | Get current property state |
| **Email** | |
| `send_email(to, subject, body, ...)` | Send email from Arbie |
| `fetch_emails(direction?, limit?)` | Get session emails |
| **Generation** | |
| `generate_pdf(source_path, output_path?)` | Render markdown to PDF |
| **Session** | |
| `update_session(status?, reason?)` | Update session state |
| **Handoffs** | |
| → Research Agent | Web research for compliance |
