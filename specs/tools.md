# Arbie - Tools Specification

## Overview

Arbie uses tools to interact with the external world: reading files, sending emails, updating properties, and researching regulations. Tools are implemented as Python functions decorated with `@function_tool` from the OpenAI Agents SDK.

Sub-agents (like the Research Agent) are exposed to Arbie as handoffs, allowing delegation of specialized tasks.

---

## Tool Categories

```
┌─────────────────────────────────────────────────────────────┐
│                         ARBIE                                │
├─────────────────────────────────────────────────────────────┤
│  Property Tools    │  Email Tools    │  File Tools          │
│  ─────────────────│─────────────────│─────────────────────  │
│  • edit_property   │  • send_email   │  • read_file         │
│  • get_property    │  • fetch_emails │  • extract_text      │
│                    │                 │  • analyze_image     │
├─────────────────────────────────────────────────────────────┤
│  Session Tools     │  Sub-Agents (Handoffs)                 │
│  ─────────────────│────────────────────────────────────────  │
│  • get_session     │  • Research Agent                      │
│  • update_session  │  • (future: Pricing Agent, etc.)       │
│  • log_event       │                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Property Tools

### `edit_property`

Create or update a property and its attributes. This is the primary tool for building up property data.

```python
@function_tool
def edit_property(
    session_id: str,
    property_id: str | None = None,  # None = create new property
    key: str,                         # What to update
    value: Any,                       # New value
    evidence: Evidence | None = None  # Source of this data
) -> EditPropertyResult:
    """
    Create or update a property field.

    Args:
        session_id: The session this property belongs to
        property_id: Property to update, or None to create new
        key: The field to set (see Key Patterns below)
        value: The value to set
        evidence: Optional source evidence for traceability

    Returns:
        EditPropertyResult with property_id and success status
    """
```

**Key Patterns:**

| Pattern | Example | Description |
|---------|---------|-------------|
| `status` | `status` | Property status (draft, ready, etc.) |
| `{hard_attr}` | `address_line1`, `max_guests`, `bedrooms` | Hard attributes |
| `attr:{key}` | `attr:wifi_password`, `attr:pool` | Flexible attributes |
| `attr:{key}:category` | `attr:wifi_password:category` | Set attribute category |
| `room:new` | `room:new` | Create a new room (value = room_type) |
| `room:{id}:{field}` | `room:r123:name`, `room:r123:bed_count` | Room metadata |
| `photo:{id}:{field}` | `photo:p123:description` | Photo metadata |
| `photo:{id}:room_id` | `photo:p123:room_id` | Assign photo to a room |
| `photo:{id}:status` | `photo:p123:status` | Photo approval status |
| `compliance:{id}:{field}` | `compliance:c1:status` | Compliance check fields |

**Evidence Object:**

```python
class Evidence:
    type: "document" | "image" | "email_body" | "research" | "owner"
    attachment_id: str | None      # Source file
    email_id: str | None           # Source email
    url: str | None                # Research source URL
    page_number: int | None        # Page in document
    text_snippet: str | None       # Relevant text excerpt
    confidence: float              # 0.0 - 1.0
```

**Examples:**

```python
# Create a new property
result = edit_property(
    session_id="sess_123",
    property_id=None,
    key="address_line1",
    value="123 Beach Drive",
    evidence=Evidence(type="document", attachment_id="att_456", page_number=1)
)
# Returns: {"property_id": "prop_789", "success": True}

# Update flexible attribute
edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="attr:wifi_password",
    value="BeachLife2024!",
    evidence=Evidence(type="document", attachment_id="att_456", page_number=2, text_snippet="WiFi: BeachLife2024!")
)

# Create a new room
result = edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="room:new",
    value="bedroom"
)
# Returns: {"room_id": "room_001", ...}

# Set room details
edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="room:room_001:name",
    value="Master Bedroom"
)

edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="room:room_001:bed_count",
    value=1
)

edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="room:room_001:bed_types",
    value=["king"]
)

# Assign photo to a room
edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="photo:photo_001:room_id",
    value="room_001"
)

# Set photo description
edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="photo:photo_001:description",
    value="Master bedroom with king bed and ocean view"
)

# Update compliance check
edit_property(
    session_id="sess_123",
    property_id="prop_789",
    key="compliance:comp_001:status",
    value="compliant",
    evidence=Evidence(type="research", url="https://miami-beach.gov/str-rules")
)
```

---

### `get_property`

Retrieve current state of a property.

```python
@function_tool
def get_property(
    property_id: str,
    include_history: bool = False
) -> Property:
    """
    Get the current state of a property.

    Args:
        property_id: The property to retrieve
        include_history: Whether to include attribute change history

    Returns:
        Full Property object with all attributes, photos, compliance checks
    """
```

**Example:**

```python
property = get_property("prop_789")
# Returns full Property object as defined in schema.md
```

---

## 2. Email Tools

### `send_email`

Send an email from Arbie to the property owner.

```python
@function_tool
def send_email(
    session_id: str,
    to: str | list[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
    attachments: list[AttachmentRef] | None = None,
    email_type: EmailType = "follow_up",
    in_reply_to: str | None = None
) -> SendEmailResult:
    """
    Send an email as Arbie.

    Args:
        session_id: Session this email belongs to
        to: Recipient email address(es)
        subject: Email subject line
        body_text: Plain text body (required)
        body_html: Optional HTML body
        attachments: Files to attach (e.g., summary PDF)
        email_type: Type of email for tracking
        in_reply_to: Message-ID to thread with

    Returns:
        SendEmailResult with message_id and delivery status
    """
```

**Email Types:**

- `acknowledgment` — Receipt confirmation
- `follow_up` — Requesting missing information
- `ready` — Property ready for validation
- `reminder` — Nudge for inactive session
- `validation` — Confirmation of validation

**Example:**

```python
# Send follow-up asking for missing info
send_email(
    session_id="sess_123",
    to="owner@example.com",
    subject="Re: Property Submission - A few questions",
    body_text="""Hi,

Thanks for submitting your property at 123 Beach Drive!

I've reviewed your documents and have a few questions:

1. How many beds are in the second bedroom? The photos show bunk beds but I want to confirm the count.

2. What are the WiFi network name and password?

3. Is the pool heated? If so, what months is heating available?

Please reply to this email with the details.

Best,
Arbie
""",
    email_type="follow_up",
    in_reply_to="<original-message-id@mail.com>"
)
```

---

### `fetch_emails`

Retrieve emails for a session (or check for new inbound emails).

```python
@function_tool
def fetch_emails(
    direction: "inbound" | "outbound" | "all" = "all",
    limit: int = 50
) -> list[Email]:
    """
    Fetch emails for a session.

    Args:
        direction: Filter by direction
        limit: Maximum number to return

    Returns:
        List of Email objects with attachments
    """
```



---

## 3. File Tools

### `read_file`

Read and extract content from a file with optional keyword filtering.

```python
@function_tool
def read_file(
    file_path: str,
    keyword: str | None = None,
    context_lines: int = 3,
    max_chars: int = 10000,
    extract_tables: bool = False
) -> FileContent:
    """
    Read a file and extract its content, optionally filtering by keyword.

    Args:
        file_path: Path to the file to read
        keyword: Optional keyword to search for (case-insensitive)
        context_lines: Number of lines to include around keyword matches
        max_chars: Maximum characters to return (truncates if exceeded)
        extract_tables: Whether to extract tables as structured data

    Returns:
        FileContent with extracted text, matches, and metadata
    """
```

**Returns:**

```python
class FileContent:
    file_path: str
    filename: str
    content_type: str
    size_bytes: int

    # Extracted content
    text: str | None              # Full text content (or filtered by keyword)
    matches: list[Match] | None   # Keyword match locations
    tables: list[Table] | None    # Extracted tables
    pages: int | None             # Page count for documents
    truncated: bool               # True if max_chars limit was hit

    # For images
    dimensions: tuple[int, int] | None  # (width, height)

class Match:
    line_number: int
    text: str                     # The matched line with context
    keyword_position: int         # Character offset of keyword in text
```

**Examples:**

```python
# Read full file content
content = read_file("/path/to/property-info.pdf")
print(content.text)  # Full document text

# Search for keyword with context
content = read_file(
    "/path/to/regulations.txt",
    keyword="permit",
    context_lines=2,
    max_chars=5000
)
# Returns only sections mentioning "permit" with 2 lines before/after

# Extract tables from spreadsheet
content = read_file(
    "/path/to/pricing.xlsx",
    extract_tables=True
)
print(content.tables[0])  # First table as structured data
```


---


### `analyze_image`

Analyze an image using vision AI to extract metadata.

```python
@function_tool
def analyze_image(
    attachment_id: str,
    analysis_types: list[str] = ["room", "objects", "amenities", "quality"]
) -> ImageAnalysis:
    """
    Analyze an image for property-relevant content.

    Args:
        attachment_id: The image attachment to analyze
        analysis_types: What to analyze for:
            - "room": Detect room type
            - "objects": Detect objects in scene
            - "amenities": Detect visible amenities
            - "quality": Assess image quality
            - "description": Generate natural description

    Returns:
        ImageAnalysis with detected elements
    """
```

**Returns:**

```python
class ImageAnalysis:
    attachment_id: str

    # Detection results
    room_type: str | None           # "bedroom", "bathroom", etc.
    room_confidence: float

    objects_detected: list[str]     # ["bed", "nightstand", "lamp"]
    amenities_visible: list[str]    # ["pool", "tv", "air_conditioning"]

    description: str | None         # "Spacious bedroom with king bed..."

    # Quality assessment
    quality_score: float            # 0.0 - 1.0
    quality_issues: list[str]       # ["blurry", "dark"]

    # Safety
    inappropriate_content: bool
    pii_detected: bool              # Personal info visible
```

**Example:**

```python
# Analyze a property photo
analysis = analyze_image("att_789", analysis_types=["room", "objects", "amenities", "description"])

# Use results to update property
edit_property(
    session_id="sess_123",
    property_id="prop_456",
    key="photo:photo_001:room_type",
    value=analysis.room_type
)
edit_property(
    session_id="sess_123",
    property_id="prop_456",
    key="photo:photo_001:objects_detected",
    value=analysis.objects_detected
)
```

---

## 4. Session Tools

### `get_session`

Retrieve session details and history.

```python
@function_tool
def get_session(
    session_id: str,
    include_events: bool = True
) -> Session:
    """
    Get session details including conversation history.

    Args:
        session_id: The session to retrieve
        include_events: Whether to include full event timeline

    Returns:
        Session object with user, property, emails, and events
    """
```

---

### `update_session`

Update session status or metadata.

```python
@function_tool
def update_session(
    session_id: str,
    status: SessionStatus | None = None,
    status_reason: str | None = None
) -> Session:
    """
    Update session status.

    Args:
        session_id: The session to update
        status: New status
        status_reason: Explanation for status change

    Returns:
        Updated Session object
    """
```

**Example:**

```python
# Move session to awaiting info
update_session(
    session_id="sess_123",
    status="awaiting_info",
    status_reason="Waiting for owner to confirm bed count and provide WiFi password"
)
```


---

## 5. Sub-Agents (Handoffs)

Sub-agents are specialized agents that Arbie can delegate to for specific tasks. In OpenAI Agents SDK, these are implemented as handoffs.

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
    model="gpt-5.2"
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
- Extracts info from miami-beach.gov
- Returns structured compliance requirements

[Returns to Arbie with results]
```

**Research Agent Tools:**

| Tool | Description |
|------|-------------|
| `tavily_search` | Web search optimized for LLMs |
| `tavily_extract` | Extract clean content from URLs |

**Example Research Result:**

```python
{
    "jurisdiction": "Miami Beach, FL",
    "regulations": {
        "permit_required": True,
        "permit_name": "Resort Tax Certificate",
        "permit_url": "https://miami-beach.gov/str-permit",
        "occupancy_limit": "2 persons per bedroom + 2",
        "minimum_stay": "None (no minimum)",
        "taxes": [
            {"name": "Resort Tax", "rate": "4%"},
            {"name": "Tourist Development Tax", "rate": "6%"}
        ],
        "registration_deadline": "Before first rental",
        "renewal": "Annual"
    },
    "sources": [
        "https://miami-beach.gov/str-regulations",
        "https://miami-beach.gov/resort-tax"
    ],
    "researched_at": "2024-01-15T10:30:00Z"
}
```

---

## Tool Implementation Notes

### Error Handling

All tools should return structured errors:

```python
class ToolError:
    error_code: str          # "not_found", "validation_error", "service_error"
    message: str             # Human-readable message
    retriable: bool          # Whether Arbie should retry
    details: dict | None     # Additional context
```

### Idempotency

- `edit_property` with same key/value is idempotent
- `send_email` is NOT idempotent (creates new email each time)
- `log_event` is NOT idempotent (creates new event each time)

### Rate Limits

| Tool | Limit | Notes |
|------|-------|-------|
| `send_email` | 5/minute per session | Prevent spam |
| `analyze_image` | 20/minute | Vision API costs |
| `tavily_search` | 100/day | API quota |

### Tracing

All tool calls are automatically traced with:
- Input parameters
- Output results
- Execution time
- Agent context (which agent called it)

---

## Tool Dependency Graph

```
                    ┌─────────────────┐
                    │  fetch_emails   │
                    └────────┬────────┘
                             │ triggers
                             ▼
                    ┌─────────────────┐
                    │   read_file     │
                    └────────┬────────┘
                             │ extracts
                             ▼
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │  extract_text   │           │  analyze_image  │
    └────────┬────────┘           └────────┬────────┘
             │                             │
             └──────────────┬──────────────┘
                            │ populates
                            ▼
                   ┌─────────────────┐
                   │  edit_property  │◄──── Research Agent results
                   └────────┬────────┘
                            │ when complete
                            ▼
                   ┌─────────────────┐
                   │   send_email    │ (ready notification)
                   └─────────────────┘
```

---

## Future Tools (TBD)

| Tool | Purpose |
|------|---------|
| `generate_pdf` | Create property summary PDF |
| `create_validation_token` | Generate secure validation URL |
| `geocode_address` | Convert address to coordinates |
| `check_image_duplicates` | Detect duplicate/stock photos |
| `translate_text` | Translate content for international owners |
