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

## Workspace Best Practices

Your workspace (`/workspace/`) is your scratch area. **Use it actively during processing:**

### Track Your Progress
```python
write_file(
    path="notes/progress.md",
    content="""# Processing Progress

## Documents Reviewed
- [x] property_guide.pdf - Address, capacity, amenities extracted
- [x] floor_plan.pdf - 3 bedrooms, 2.5 baths confirmed
- [ ] permit.pdf - Need to check

## Images Analyzed
- [x] Bedroom photos - 3 beds identified
- [ ] Kitchen photos - pending

## Missing Information
- WiFi network name (have password from page 2)
- Pool heating details
- Office sofa bed - confirm if for guests
"""
)
```

### Track Missing Information
```python
write_file(
    path="notes/missing_info.md",
    content="""# Missing Information

## Critical (blocking completion)
- [ ] WiFi network name

## Important (should ask)
- [ ] Is pool heated?
- [ ] Office sofa bed available for guests?

## Nice to have
- [ ] Parking spot number
"""
)
```

### Draft Emails Before Sending
```python
# Draft first, review, then send
write_file(
    path="drafts/follow_up.md",
    content="""Hi,

Thanks for submitting your property at 123 Beach Drive!

Questions:
1. WiFi network name?
2. Pool heated?

Best,
Arbie"""
)
```

### Why This Matters
- **Continuity**: Notes persist across turns - check workspace first on follow-ups
- **Thoroughness**: Tracking ensures nothing is missed
- **Quality**: Drafting emails improves communication

## File Tools

### get_session_overview()

**Purpose:** Get ALL files, preprocessing metadata, and room groupings available in this session

**When to use:** ALWAYS call this FIRST at the start of every turn

**Returns:**
```python
{
    "session_id": str,
    "files": {
        "attachments": [                      # Files from emails
            {
                "name": "property_guide.pdf",
                "path": "/attachments/property_guide.pdf",
                "type": "application/pdf",
                "status": "processed",        # IMPORTANT: check this
                "has_extracted_text": True,
                "extracted_text_preview": "Property at 123 Beach..."
            },
            {
                "name": "bedroom1.jpg",
                "path": "/attachments/bedroom1.jpg",
                "type": "image/jpeg",
                "status": "processed",
                "room_type": "bedroom"        # From image classification
            }
        ],
        "extracted": [...],                   # Auto-extracted from PDFs
        "workspace": [...],                   # Your notes and drafts
        "outputs": [...]                      # Generated PDFs
    },
    "images": ["/attachments/bedroom1.jpg", ...],
    "documents": ["/attachments/property_guide.pdf", ...],
    "rooms": {                                # Room groupings (when images are processed)
        "bedroom": {
            "count": 2,
            "images": ["/attachments/bedroom1.jpg", ...],
            "objects": ["bed", "nightstand", "wardrobe"]
        },
        "kitchen": {...}
    },
    "preprocessing_summary": {
        "pdfs_processed": 1,
        "images_classified": 8,
        "rooms_detected": 5
    },
    "session_metadata": {...}
}
```

**Attachment status field:**
- `"processed"` → Preprocessed data is available and reliable
- Any other value → Analyze the file yourself (see workflow for details)

### get_attachment_metadata(paths=None, include_extracted_text=False, include_room_details=False)

**Purpose:** Get detailed preprocessing metadata for specific attachments

**When to use:** When you need more detail than `get_session_overview()` provides

**Parameters:**
- `paths`: List of specific file paths, or None for all attachments
- `include_extracted_text`: If True, include full OCR text for PDFs
- `include_room_details`: If True, include full room clustering details

**Example:**
```python
# Get full details for bedroom images
metadata = get_attachment_metadata(
    paths=["/attachments/bedroom1.jpg", "/attachments/bedroom2.jpg"],
    include_room_details=True
)
# Returns:
# {
#   "attachments": [
#     {
#       "path": "/attachments/bedroom1.jpg",
#       "status": "processed",
#       "room_type": "bedroom",
#       "room_name": "bedroom1",
#       "objects": ["king bed", "nightstand", "lamp", "wardrobe"]
#     },
#     ...
#   ],
#   "rooms": [...]  # Full room metadata
# }

# Get full extracted text from a PDF
pdf_metadata = get_attachment_metadata(
    paths=["/attachments/property_guide.pdf"],
    include_extracted_text=True
)
full_text = pdf_metadata["attachments"][0].get("extracted_text", "")
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

**Purpose:** Read content from text-based files

**Supported formats:**
- `.txt`, `.md`, `.json` - Read directly from storage
- `.pdf` - **On-demand Mistral OCR** (see below)

**PDF behavior:**
- First read triggers `mistral-ocr-latest` OCR extraction
- Extracted text cached in DB for subsequent reads
- Images from PDF saved to `/extracted/{pdf_name}_{image}.jpg`
- Returns `extracted_images` list with paths to extracted images

**For images, use vision tools instead (see Vision Tools section).**

**Key features:**
- Keyword search with context lines
- Truncates long content (max_chars)
- Auto-extracts images from PDFs

**Examples:**
```python
# Read PDF (triggers OCR on first read)
content = read_file("/attachments/property_guide.pdf")
# Returns:
# {
#     "text": "Property at 123 Beach Drive...",
#     "path": "/attachments/property_guide.pdf",
#     "truncated": False,
#     "extracted_images": ["/extracted/property_guide_page1.jpg", ...]
# }

# Then analyze the extracted images:
if content.get("extracted_images"):
    doc_analysis = analyze_document_images(paths=content["extracted_images"])

# Search for specific info (don't read entire 50-page doc)
wifi_info = read_file(
    "/attachments/property_guide.pdf",
    keyword="wifi",
    context_lines=2
)
# Returns only sections mentioning "wifi" with 2 lines before/after

# Read your own notes
notes = read_file("/workspace/notes/missing_info.md")
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

There are three specialized vision tools. Use them in this order for image processing:

### classify_image_types(paths)

**Purpose:** First step for image analysis - classify images as property photos or document photos

**Model:** GPT-4o (detail: low - efficient for classification)

**Returns:**
```python
{
    "property_foto_paths": ["/attachments/bedroom.jpg", ...],
    "document_foto_paths": ["/attachments/floorplan.jpg", ...]
}
```

**Example:**
```python
result = classify_image_types(paths=overview["images"])
property_photos = result["property_foto_paths"]
document_photos = result["document_foto_paths"]
```

---

### analyze_property_fotos(paths, save_to_db=True, email_id="", property_id="")

**Purpose:** Cluster property photos into rooms, detect objects, classify room types

**Model:** GPT-4o (detail: high - detailed analysis)

**Key behavior:**
- `save_to_db=True` (default): Creates room records in DB + updates attachment metadata
- Returns `room_ids` list ONLY when save_to_db=True
- Clusters images showing the same room from different angles

**Returns:**
```python
{
    "rooms": [
        {
            "name": "bedroom1",
            "room_type": "bedroom",
            "objects": ["king bed", "nightstand", "wardrobe"],
            "attachments": ["/attachments/bed1.jpg", "/attachments/bed2.jpg"]
        },
        ...
    ],
    "room_ids": ["room-uuid-1", ...]  # Only when save_to_db=True
}
```

**Room types (24 canonical):**
- Indoor: bedroom, bathroom, kitchen, living_room, dining_room, office, laundry, garage, hallway, closet, basement, attic
- Outdoor: patio, balcony, deck, pool_area, garden, parking
- Generic: exterior, common_area, other

**Example:**
```python
result = analyze_property_fotos(
    paths=classification["property_foto_paths"],
    save_to_db=True,
    property_id=property_id
)
# Rooms created in DB, attachments updated with room assignments
room_ids = result["room_ids"]

for room in result["rooms"]:
    print(f"Found {room['room_type']}: {room['name']}")
    print(f"  Objects: {', '.join(room['objects'])}")
    print(f"  Images: {len(room['attachments'])}")
```

---

### analyze_document_images(paths)

**Purpose:** Extract information from document images (floor plans, contracts, certificates)

**Model:** GPT-4o (detail: high - for reading text)

**Returns:** TEXT (not JSON) - descriptive analysis including:
- Document type
- Key dates, names, measurements
- Signatures, stamps
- Layout/structure details

**Example:**
```python
description = analyze_document_images(paths=["/attachments/floorplan.jpg"])
# Returns: "Floor plan showing 2-bedroom layout. Master bedroom is 15x12 ft..."
```

## Property Tools

### edit_property(...)

**Purpose:** Create or update property fields with evidence tracking

**Parameters:**
- Location: `address_line1`, `address_line2`, `city`, `state_province`, `postal_code`, `country`, `coordinates_lat`, `coordinates_lng`
- Capacity: `max_guests`, `bedrooms`, `beds`, `bathrooms`
- Type: `property_type`
- Compliance: `permit_number`, `permit_expiry`, `tax_id`
- Flexible: `attribute_key`, `attribute_value`, `attribute_category`
- Evidence: `evidence` (optional)

**Evidence parameter:**
```python
evidence=EvidenceData(
    source_type="document",  # document, image, email, inference
    source_path="/attachments/guide.pdf",
    excerpt="Max occupancy: 8 guests",
    confidence="high"  # high, medium, low
)
```

**Examples:**
```python
# Update multiple hard attributes at once
edit_property(
    address_line1="123 Beach Drive",
    city="Miami",
    country="USA",
    max_guests=8,
    bedrooms=3,
    bathrooms=2.5,
    evidence=EvidenceData(
        source_type="document",
        source_path="/attachments/property_guide.pdf",
        excerpt="Property Address: 123 Beach Drive"
    )
)

# Set a flexible attribute
edit_property(
    attribute_key="wifi_password",
    attribute_value="BeachLife2024!",
    attribute_category="access"
)

# Attribute categories: amenity, rule, access, appliance, contact, local, pricing, policy, other
```

---

### edit_room(room_id=None, room_type=None, name=None, ...)

**Purpose:** Create or update room records

**Parameters:**
- `room_id`: Omit to create new, provide to update existing
- `room_type`: bedroom, bathroom, kitchen, etc. (required for new rooms)
- `name`: Custom name (e.g., "Master Bedroom")
- `floor`: Floor number (0 = ground)
- `bed_count`, `bed_types`: For bedrooms
- `has_shower`, `has_bathtub`, `is_ensuite`: For bathrooms
- `amenities`: List of room amenities

**Example:**
```python
# Create a new bedroom
result = edit_room(
    room_type="bedroom",
    name="Master Bedroom",
    bed_count=1,
    bed_types=["king"],
    amenities=["TV", "air_conditioning"]
)
room_id = result["room_id"]

# Update an existing room
edit_room(
    room_id=room_id,
    bed_count=2,
    bed_types=["queen", "twin"]
)
```

---

### edit_photo(photo_id, room_id=None, is_primary=None, ...)

**Purpose:** Assign photos to rooms and set metadata

**Parameters:**
- `photo_id`: ID of photo to update (required)
- `room_id`: Assign to a room
- `is_primary`: Main listing photo
- `is_room_primary`: Main photo for that room
- `display_order`: Gallery order (lower = earlier)
- `description`: Text description
- `tags`: List of tags

**Example:**
```python
edit_photo(
    photo_id="photo123",
    room_id=room_id,
    is_room_primary=True,
    description="Master bedroom with king bed"
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

**Purpose:** Retrieve emails for this session with full attachment metadata

**Parameters:**
- direction: "inbound", "outbound", or "all"
- limit: max number to return

**Returns:** Each email includes:
- Email metadata (direction, from, to, subject, body)
- **Attachments list** with filename, content_type, size_bytes, and storage_path
- Threading information (message_id, in_reply_to)

**Example:**
```python
# Get latest inbound email
emails = fetch_emails(direction="inbound", limit=1)
original_email = emails[0]

# Access fields
original_email["message_id"]  # For threading
original_email["body"]        # Email content
original_email["from_email"]
original_email["attachments"] # List of attachment dicts
# Example: [{"filename": "guide.pdf", "content_type": "application/pdf", 
#            "size_bytes": 1024000, "storage_path": "/attachments/guide.pdf"}]
```

### send_email(to, subject, body, attachments=None, reply_to_message_id=None)

**Purpose:** Send email from Arbie to property owner

**CRITICAL: This terminates the agent loop. Always call this to end your turn.**

**Examples:**
```python
# Send follow-up questions (threading is automatic)
send_email(
    to="owner@example.com",
    subject="Re: Property Submission - A few questions",
    body="""Hi,

Thanks for submitting your property at 123 Beach Drive!

I have a few quick questions:

1. What's the WiFi network name? (I found the password on page 2)
2. Is the pool heated year-round, or only certain months?

Please reply with the details.

Cheers,
Arbie"""
)

# Send completion email with PDF
send_email(
    to="owner@example.com",
    subject="Your property is ready for review!",
    body="""Hi,

Great news! I've finished processing your property at 123 Beach Drive.

I've attached a summary PDF. Please review it and validate:

https://arbie.arbio.com/validate/abc123xyz

All the best,
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

## Research Agent (Handoff)

**Purpose:** Research short-term rental regulations for a property address

**How it works:** The Research Agent is accessed via **handoff** from Arbie. When compliance research is needed, control transfers to the Research Agent which has access to:
- `web_search(query, max_results=5)` - Tavily web search
- `todo(action, item)` - Track research tasks (add, complete, list, clear)

**When to use:** After you have the property address and need to research:
- Required permits and licenses
- Registration requirements
- Occupancy limits
- Tax obligations
- Zoning restrictions

**After the handoff:** The Research Agent returns findings. Use them to update property compliance:
```python
# Use the research findings to update property
edit_property(
    permit_number="STR-2024-1234",
    permit_expiry="2025-12-31",
    evidence=EvidenceData(
        source_type="inference",
        excerpt="Miami Beach STR License required",
        confidence="high"
    )
)
```

**Note:** You don't call `research_compliance()` directly. The handoff happens automatically when you transfer to the Research Agent.
