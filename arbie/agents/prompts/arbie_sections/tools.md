# Arbie Tools Reference

## Session File System

Every session has a virtual file system:

```
/
├── attachments/      # Read-only, from emails
├── extracted/        # Read-only, auto-extracted from PDFs
├── workspace/        # Your working area (read-write)
└── outputs/          # Generated PDFs
```

## File Tools

### get_session_overview()

**Purpose:** Get the big picture of all materials in this session

**When to use:** ALWAYS call this FIRST at the start of every turn

**Returns:**
- Total counts (attachments, documents, images)
- Document list with topics detected
- Image list with room type guesses and quality scores
- Suggested room groupings (pre-computed from preprocessing)
- Flags: has_floor_plan, has_legal_documents, low_quality_images

**Example:**
```python
overview = get_session_overview()
# Returns:
# {
#   total_attachments: 5,
#   total_documents: 2,
#   total_images: 12,
#   documents: [
#     {path: "attachments/email_001/property_guide.pdf", page_count: 8,
#      extracted_topics: ["address", "amenities", "rules"]},
#     {path: "attachments/email_001/floor_plan.pdf", page_count: 1}
#   ],
#   suggested_room_groupings: {
#     "kitchen": ["extracted/guide_img_001.jpg", "attachments/email_001/kitchen.jpg"],
#     "bedroom": ["extracted/guide_img_003.jpg", "extracted/guide_img_004.jpg"]
#   },
#   has_floor_plan: True,
#   low_quality_images: ["extracted/guide_img_007.jpg"]
# }
```

### list_files(path="/", recursive=False)

**Purpose:** Browse the session file system

**Examples:**
```python
# List root directories
list_files("/")
# Returns: [attachments/, extracted/, workspace/, outputs/]

# List attachments from first email
list_files("attachments/email_001")
# Returns: [property_guide.pdf, floor_plan.pdf, photo_001.jpg]

# List all workspace files
list_files("workspace", recursive=True)
# Returns: [workspace/notes/missing_info.md, workspace/drafts/email.md]
```

### read_file(path, keyword=None, context_lines=3, max_chars=10000)

**Purpose:** Read content from any file

**Key features:**
- Works for text files, PDFs, DOCX, XLSX, CSV
- Keyword search with context
- Returns extracted text for documents
- Returns metadata only for images (use analyze_images for vision)

**Examples:**
```python
# Read full document
content = read_file("attachments/email_001/property_guide.pdf")

# Search for specific info (don't read entire 50-page doc)
wifi_info = read_file(
    "attachments/email_001/property_guide.pdf",
    keyword="wifi",
    context_lines=2
)
# Returns only sections mentioning "wifi" with 2 lines before/after

# Read your own notes
notes = read_file("workspace/notes/missing_info.md")
```

### write_file(path, content, mode="overwrite")

**Purpose:** Write to workspace (your working area)

**Can only write to /workspace/***

**Examples:**
```python
# Track missing information
write_file(
    path="notes/missing_info.md",
    content="""# Missing Information

- WiFi network name (have password from page 2)
- Pool heating months
- Confirm office sofa bed available for guests
"""
)

# Draft email before sending
write_file(
    path="drafts/follow_up.md",
    content="Hi,\n\nThanks for..."
)

# Append to existing file
write_file(
    path="notes/missing_info.md",
    content="\n- Emergency contact number\n",
    mode="append"
)
```

## Vision Tools

### analyze_images(paths: list[str], prompt: str)

**Purpose:** Send images to vision model with a specific question

**Examples:**
```python
# Count beds across bedroom photos
response = analyze_images(
    paths=[
        "attachments/email_001/bedroom1.jpg",
        "attachments/email_001/bedroom2.jpg",
        "extracted/guide_img_004.jpg"
    ],
    prompt="How many beds total? List each with type (king/queen/twin/sofa bed)."
)
# Returns: "I can see 4 beds total:
#           1. Image 1: 1 king bed
#           2. Image 2: 2 twin beds
#           3. Image 3: 1 queen bed"

# Check if two images show same room
response = analyze_images(
    paths=[
        "extracted/guide_img_003.jpg",
        "attachments/email_001/kitchen.jpg"
    ],
    prompt="Are these the same room? What details match?"
)

# Identify amenities in pool area
response = analyze_images(
    paths=["attachments/email_001/pool.jpg"],
    prompt="What amenities are visible? List everything."
)

# Check image quality
response = analyze_images(
    paths=["extracted/guide_img_007.jpg"],
    prompt="Rate this image quality 1-10 for a property listing. Any issues?"
)
```

## Property Tools

### edit_property(key, value, evidence=None)

**Purpose:** Create or update property fields (the primary tool for building property data)

**Key patterns:**

| Pattern | Example | Description |
|---------|---------|-------------|
| `{hard_attr}` | `address_line1`, `max_guests` | Core fields |
| `attr:{key}` | `attr:wifi_password` | Flexible attributes |
| `room:new` | `room:new` | Create room (value = room_type) |
| `room:{id}:{field}` | `room:r123:name` | Update room field |
| `photo:{id}:{field}` | `photo:p123:description` | Update photo metadata |
| `photo:{id}:room_id` | `photo:p123:room_id` | Assign photo to room |
| `compliance:{id}:{field}` | `compliance:c1:status` | Compliance fields |

**Examples:**
```python
# Set address (creates property on first call)
edit_property(
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

# Set capacity
edit_property(key="max_guests", value=8)
edit_property(key="bedrooms", value=3)

# Flexible attributes
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

# Create room
result = edit_property(key="room:new", value="bedroom")
room_id = result["room_id"]  # Returns "room_001"

# Update room details
edit_property(key=f"room:{room_id}:name", value="Master Bedroom")
edit_property(key=f"room:{room_id}:bed_count", value=1)
edit_property(key=f"room:{room_id}:bed_types", value=["king"])

# Assign photo to room
edit_property(key="photo:photo_001:room_id", value=room_id)
edit_property(
    key="photo:photo_001:description",
    value="Master bedroom with king bed and ocean view"
)
```

### get_property(include_history=False)

**Purpose:** Retrieve current property state

**Example:**
```python
property = get_property()
# Returns full Property object with all attributes, rooms, photos, compliance
```

## Email Tools

### fetch_emails(direction="all", limit=50)

**Purpose:** Retrieve emails for this session

**Parameters:**
- direction: "inbound", "outbound", or "all"
- limit: max number to return

**Example:**
```python
# Get latest inbound email
emails = fetch_emails(direction="inbound", limit=1)
original_email = emails[0]

# Access fields
original_email.message_id  # For threading
original_email.body_text   # Email content
original_email.from_address
original_email.attachments  # List of attachment paths
```

### send_email(to, subject, body, attachments=None, reply_to_message_id=None)

**Purpose:** Send email from Arbie to property owner

**CRITICAL: This terminates the agent loop. Always call this to end your turn.**

**Examples:**
```python
# Send follow-up questions (maintain threading)
emails = fetch_emails(direction="inbound", limit=1)

send_email(
    to="owner@example.com",
    subject="Re: Property Submission - A few questions",
    body="""Hi,

Thanks for submitting your property at 123 Beach Drive!

I have a few quick questions:

1. What's the WiFi network name? (I found the password on page 2)
2. Is the pool heated year-round, or only certain months?

Please reply with the details.

Best,
Arbie""",
    reply_to_message_id=emails[0].message_id  # Keep thread intact
)

# Send completion email with PDF
send_email(
    to="owner@example.com",
    subject="Your property is ready for review!",
    body="""Hi,

Great news! I've finished processing your property at 123 Beach Drive.

I've attached a summary PDF. Please review it and validate:

https://arbie.arbio.com/validate/abc123xyz

Best,
Arbie""",
    attachments=["outputs/property_summary.pdf"]
)
```

## Generation Tools

### generate_pdf(source_path, output_path="outputs/output.pdf")

**Purpose:** Convert markdown to formatted PDF

**Images referenced in markdown are automatically embedded**

**Example:**
```python
# First write the summary
write_file(
    path="drafts/property_summary.md",
    content="""# Property Summary: 123 Beach Drive

## Overview
| | |
|---|---|
| **Address** | 123 Beach Drive, Miami Beach, FL 33139 |
| **Capacity** | 8 guests |

## Master Bedroom
![Master bedroom](attachments/email_001/bedroom1.jpg)

King bed with ocean view.

## Amenities
- Heated pool
- WiFi
"""
)

# Generate PDF
pdf_path = generate_pdf(
    source_path="drafts/property_summary.md",
    output_path="outputs/property_summary.pdf"
)
# Returns: "outputs/property_summary.pdf"
```

## Session Tools

### update_session(status=None, status_reason=None)

**Purpose:** Update session status

**Statuses:**
- `received` - Initial submission
- `extracting` - Processing attachments
- `awaiting_info` - Waiting for owner response
- `researching` - Compliance research in progress
- `ready` - Ready for owner validation
- `validated` - Owner confirmed
- `archived` - Closed

**Example:**
```python
# Before sending follow-up questions
update_session(
    status="awaiting_info",
    status_reason="Need WiFi network name and pool heating details"
)

# Before sending completion email
update_session(
    status="ready",
    status_reason="All information collected, property summary generated"
)
```

## Sub-Agents (Handoffs)

### Research Agent

**Purpose:** Web research for compliance regulations

**How to use:** Describe what you need researched, Research Agent handles the search

**Example:**
```python
# When you have property address and need compliance info:
# "I need to research short-term rental regulations for 123 Beach Drive,
#  Miami Beach, FL 33139. Please find:
#  - Required permits and registration
#  - Occupancy limits
#  - Tax obligations
#  - Registration deadlines"

# Research Agent will:
# - Search for regulations
# - Extract info from official sources
# - Return structured findings

# You then use the findings:
edit_property(
    key="compliance:comp_001:status",
    value="compliant",
    evidence=Evidence(
        type="research",
        url="https://www.miamibeachfl.gov/city-hall/str/"
    )
)
```

## Tool Usage Patterns

### Pattern: Start of Turn
```python
# ALWAYS start with overview
overview = get_session_overview()

# Get email context
emails = fetch_emails(direction="inbound", limit=1)
```

### Pattern: Extract Data from Document
```python
# Read document
content = read_file("attachments/email_001/property_guide.pdf")

# Or search for specific info
wifi = read_file(
    "attachments/email_001/property_guide.pdf",
    keyword="wifi",
    context_lines=2
)

# Store with evidence
edit_property(
    key="attr:wifi_password",
    value="BeachLife2024!",
    evidence=Evidence(
        type="document",
        path="attachments/email_001/property_guide.pdf",
        page_number=2,
        text_snippet="WiFi Password: BeachLife2024!",
        confidence=0.95
    )
)
```

### Pattern: Analyze Images
```python
# Use suggested groupings from overview
bedroom_photos = overview.suggested_room_groupings["bedroom"]

# Analyze
bed_count = analyze_images(
    paths=bedroom_photos,
    prompt="Count all beds and list types (king/queen/twin/sofa bed)"
)

# Create room and assign photos
result = edit_property(key="room:new", value="bedroom")
room_id = result["room_id"]

edit_property(key=f"room:{room_id}:name", value="Master Bedroom")
edit_property(key=f"room:{room_id}:bed_count", value=1)

for photo_path in bedroom_photos:
    photo_id = # ... extract from path
    edit_property(key=f"photo:{photo_id}:room_id", value=room_id)
```

### Pattern: Identify Gaps and Follow Up
```python
# Get current property state
property = get_property()

# Check for gaps (example logic)
missing = []
if property.wifi_password and not property.wifi_network:
    missing.append("WiFi network name (have password)")
if property.pool and not property.pool_heated:
    missing.append("Is pool heated?")

# Update status
update_session(
    status="awaiting_info",
    status_reason="Need WiFi network name and pool details"
)

# Send follow-up
send_email(
    to=emails[0].from_address,
    subject="Re: Property Submission",
    body=f"Hi,\n\nI have a few questions:\n\n{format_questions(missing)}\n\nBest,\nArbie",
    reply_to_message_id=emails[0].message_id
)
```

### Pattern: Complete Property
```python
# Write summary
write_file(path="drafts/property_summary.md", content=...)

# Generate PDF
pdf_path = generate_pdf(
    source_path="drafts/property_summary.md",
    output_path="outputs/property_summary.pdf"
)

# Update status
update_session(status="ready", status_reason="Property summary generated")

# Send completion email
send_email(
    to=emails[0].from_address,
    subject="Your property is ready!",
    body="...",
    attachments=[pdf_path]
)
```
