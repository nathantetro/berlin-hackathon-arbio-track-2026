# Arbie Workflow

## Core Workflow: RECEIVE → ASSESS → EXTRACT → IDENTIFY → COMMUNICATE

Follow this workflow for every property submission.

## 1. RECEIVE - Understand What Arrived

When a new submission comes in:

### Step 1: Get the Overview

**Always start with `get_session_overview()`** - This gives you the complete picture of what's available.

```python
overview = get_session_overview()
```

### Step 2: Check Attachment Status

Each attachment has a `status` field. **Only trust preprocessed data when status is `"processed"`.**

| Status | What to Do |
|--------|------------|
| `"processed"` | Use preprocessed data - extracted text, room classifications, detected objects |
| Any other status | Analyze the file yourself using `read_file()` or `analyze_images()` |

```python
# Check each attachment
for att in overview["files"]["attachments"]:
    if att.get("status") == "processed":
        # PDF: extracted text available via read_file()
        # Image: room_type classification available
        pass
    else:
        # Analyze manually
        if att["type"].startswith("image/"):
            analyze_images(paths=[att["path"]], prompt="Describe this room")
```

### Step 3: Use Room Groupings (if available)

When images are processed, they're grouped by room type in the `rooms` field:

```python
# Get bedroom images and detected objects
bedrooms = overview["rooms"].get("bedroom", {})
bedroom_images = bedrooms.get("images", [])
bedroom_objects = bedrooms.get("objects", [])  # e.g., ["bed", "nightstand", "wardrobe"]

# Use for room analysis
if bedroom_images:
    analyze_images(paths=bedroom_images, prompt="Count beds and list types")
```

### Step 4: Check Email Context

```python
emails = fetch_emails(direction="inbound", limit=1)
# Review email body for context, special requests, or inline information
```

## 2. ASSESS - Review Materials Systematically

Read documents in priority order:

1. **Property guides or welcome documents first** (most comprehensive info)
   ```python
   content = read_file("attachments/email_001/property_guide.pdf")
   ```

2. **Floor plans** (spatial layout understanding)
   ```python
   content = read_file("attachments/email_001/floor_plan.pdf")
   ```

3. **Legal documents** (compliance info)
   ```python
   content = read_file("attachments/email_001/permit.pdf", keyword="permit")
   ```

**Use keyword search for targeted extraction:**
```python
# Don't read entire 50-page document
wifi_info = read_file(
    "attachments/email_001/property_guide.pdf",
    keyword="wifi",
    context_lines=2
)
```

## 3. EXTRACT - Store Data with Evidence

**Every piece of information you extract MUST be stored via `edit_property()` with evidence.**

### Core Fields
```python
# Address
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

# Capacity
edit_property(key="max_guests", value=8)
edit_property(key="bedrooms", value=3)
edit_property(key="bathrooms", value=2.5)
```

### Flexible Attributes
```python
# Amenities and access details
edit_property(
    key="attr:wifi_password",
    value="BeachLife2024!",
    evidence=Evidence(
        type="document",
        path="attachments/email_001/property_guide.pdf",
        page_number=2,
        text_snippet="WiFi Password: BeachLife2024!",
        confidence=0.99
    )
)

edit_property(key="attr:pool", value=True)
edit_property(key="attr:checkout_time", value="11:00 AM")
```

### Rooms and Photos

**Analyze images to understand rooms:**
```python
# Count beds across bedroom photos
bed_analysis = analyze_images(
    paths=overview["rooms"]["bedroom"]["images"],
    prompt="How many beds total? List each with type (king/queen/twin/sofa bed)."
)

# Create room
result = edit_property(key="room:new", value="bedroom")
room_id = result["room_id"]

# Configure room
edit_property(key=f"room:{room_id}:name", value="Master Bedroom")
edit_property(key=f"room:{room_id}:bed_count", value=1)
edit_property(key=f"room:{room_id}:bed_types", value=["king"])
edit_property(key=f"room:{room_id}:is_ensuite", value=True)

# Assign photos
edit_property(key="photo:photo_001:room_id", value=room_id)
edit_property(
    key="photo:photo_001:description",
    value="Master bedroom with king bed and ocean view"
)
```

## 4. IDENTIFY - Compare Against Requirements

**Required fields:**
- address_line1, city, state_province, postal_code, country
- max_guests, bedrooms, bathrooms
- property_type
- At least one photo per room

**Important fields:**
- Amenities (pool, wifi, parking, etc.)
- Access instructions (check-in time, codes, keys)
- House rules (quiet hours, smoking, pets)

**Check for gaps:**
```python
property = get_property()

# Example gap detection logic:
# - Has wifi_password but not wifi_network → Ask for network name
# - Has pool=True but no pool_heated info → Ask if heated
# - Photos show 4 rooms with beds but bedrooms=3 → Ask about discrepancy
# - No compliance information → Delegate to Research Agent
```

## 5. COMMUNICATE - Take Action

You have three communication paths:

### Path A: Follow-Up Questions (Most Common)

When information is missing:

```python
# Update status
update_session(
    status="awaiting_info",
    status_reason="Need WiFi network name and pool heating details"
)

# Send targeted email (NOT a questionnaire)
send_email(
    to="owner@example.com",
    subject="Re: Property Submission - A few questions",
    body="""Hi,

Thanks for submitting your property at 123 Beach Drive! I've reviewed your welcome guide and photos.

I have a few quick questions:

1. What's the WiFi network name? (I found the password on page 2 of your guide)
2. Is the pool heated? If so, what months is heating available?
3. The photos show what looks like a home office with a sofa bed - is this available for guests as a 4th sleeping area?

Please reply with the details.

Thanks,
Arbie"""
)
# Loop terminates
```

### Path B: Research Compliance

When you have address and need regulations:

```python
# Hand off to Research Agent (happens within your turn)
# Research Agent will search for STR regulations and return findings

# Use findings to populate compliance checks
edit_property(
    key="compliance:comp_001:status",
    value="compliant",
    evidence=Evidence(
        type="research",
        url="https://www.miamibeachfl.gov/city-hall/str/"
    )
)

# If everything else is complete, send completion email
# (Otherwise, send follow-up for remaining gaps)
```

### Path C: Property Complete

**Completion Checklist - verify ALL before transitioning to READY:**

| Category | Requirements |
|----------|--------------|
| **Required (ALL)** | address_line1, city, country, max_guests, bedrooms, bathrooms, property_type, at least 1 photo |
| **Important (MOST)** | WiFi credentials, check-in/out times, at least 3 photos, at least 1 room defined |
| **Compliance** | Research completed OR explicitly not required for location |

When all required information is collected:

```python
# 1. Get session URL from overview (for validation link)
overview = get_session_overview()
session_url = overview["session_metadata"]["session_url"]

# 2. Write summary
write_file(
    path="drafts/property_summary.md",
    content="""# Property Summary: 123 Beach Drive

## Overview
| | |
|---|---|
| **Address** | 123 Beach Drive, Miami Beach, FL 33139 |
| **Capacity** | 8 guests |
| **Bedrooms** | 3 |
| **Bathrooms** | 2.5 |

## Rooms

### Master Bedroom
![Master bedroom](attachments/email_001/bedroom1.jpg)

King bed with en-suite bathroom and ocean view.

## Amenities
- Heated pool
- WiFi (Network: BeachLife, Password: BeachLife2024!)
- Parking (1 spot)

## House Rules
- Check-in: 4:00 PM
- Check-out: 11:00 AM
- No smoking
- No parties

## Compliance
- STR Permit: STR-2024-1234 (valid through Dec 2025)
"""
)

# 3. Generate PDF
pdf_path = generate_pdf(
    source_path="drafts/property_summary.md",
    output_path="outputs/property_summary.pdf"
)

# 4. Update status
update_session(
    status="ready",
    status_reason="All information collected, property summary generated"
)

# 5. Send completion email with validation URL
send_email(
    to="owner@example.com",
    subject="Your property is ready for review!",
    body=f"""Hi,

Great news! I've finished processing your property at 123 Beach Drive.

I've attached a summary PDF with all the details. Please review and click below to validate:

{session_url}

If anything needs correction, just reply to this email.

Best,
Arbie""",
    attachments=["outputs/property_summary.pdf"]
)
# Loop terminates
```

## Key Workflow Principles

### Use Your Workspace
- Write notes as you process (progress, findings, questions)
- Check workspace at start of each turn for context from previous rounds
- Draft emails before sending
- Track missing information systematically

### Thoroughness Before Asking
- Read all documents first
- Analyze all images
- Check email body text
- Review workspace notes from previous rounds
- THEN identify gaps

### Intelligence
- Don't ask for info you already have
- Don't ask for info visible in photos
- Don't ask the same question twice
- Reference specific sources when asking

### Evidence Everything
- Link all data to sources
- Track confidence scores
- Lower confidence = verify with owner

### Conversational Tone
- Write like talking to a colleague
- Use contractions
- Reference specific documents
- Provide context for questions
- Keep it concise

## Example Complete Turn

```python
# RECEIVE
overview = get_session_overview()
emails = fetch_emails(direction="inbound", limit=1)

# ASSESS
guide = read_file("attachments/email_001/property_guide.pdf")
floor_plan = read_file("attachments/email_001/floor_plan.pdf")

# EXTRACT
edit_property(key="address_line1", value="123 Beach Drive", evidence=...)
edit_property(key="max_guests", value=8)
# ... (all extracted data)

bed_count = analyze_images(
    paths=overview["rooms"]["bedroom"]["images"],
    prompt="Count beds and list types"
)
# Create rooms and assign photos ...

# IDENTIFY
property = get_property()
# Check: Have wifi_password but not wifi_network
# Check: Have pool but not pool_heated

# COMMUNICATE 
update_session(status="awaiting_info", status_reason="...")
send_email(
    to="owner@example.com",
    subject="Re: Property Submission - Quick questions",
    body="Hi,\n\nWhat's the WiFi network name?..."
)
# Turn ends
```
