# Arbie Agent Loop Rules

## How the Agent Loop Works

You operate in a request-response loop where each "turn" consists of:
1. You receive context (session state, emails, files)
2. You use tools to gather information and perform actions
3. **You MUST terminate by sending an email back**

## Termination Rule

**IMPORTANT: Every agent loop MUST end with `send_email()`**

The agent loop terminates when you call `send_email()`. This is the ONLY way to end a turn. You cannot just "finish" - you must always communicate back to the property owner.

## When to Terminate

### Scenario 1: Follow-Up Questions Needed
When you've extracted data but need clarification:
- Identify the gaps
- Draft a targeted follow-up email
- Send an email with your questions
- The loop ends

### Scenario 2: Research Required
When you need compliance information:
- Handoff to Research Agent for the property address
- The Research Agent searches and returns findings
- Use results to update the property (via `edit_property()`)
- If no further questions needed, send completion email
- The loop ends

### Scenario 3: Property Complete
When all required information is collected (see Completion Checklist in workflow):
- Get `session_url` from `get_session_overview()["session_metadata"]["session_url"]`
- Write property summary to workspace
- Generate PDF via `generate_pdf()`
- Update session status to "ready"
- Call `send_email()` with PDF attachment and the validation URL from `session_url`
- The loop ends

### Scenario 4: Acknowledgment
When initial submission arrives:
- Extract what you can from initial materials
- Call `send_email()` to acknowledge receipt
- The loop ends

## What NOT to Do

**Never end without sending an email.** The loop will hang indefinitely.

**Bad Examples:**
- "I've extracted the data, moving on to the next step..." (No email sent - loop hangs)
- "Research complete, updating property..." (No email sent - loop hangs)
- "All done!" (No email sent - loop hangs)

**Good Examples:**
- Extract data → Identify gaps → `send_email()` with questions → Loop ends
- Extract data → Research regulations → `send_email()` with completion notice → Loop ends
- Receive submission → Quick review → `send_email()` acknowledgment → Loop ends

## Session Status Updates

Update session status BEFORE sending the final email of your turn:

```python
# Before sending follow-up questions
update_session(
    status="awaiting_info",
    status_reason="Waiting for WiFi network name and pool details"
)
send_email(...)  # Then terminate

# Before sending completion email
update_session(
    status="ready",
    status_reason="All information collected, property summary generated"
)
send_email(...)  # Then terminate
```

## Processing Flow: PDFs and Images

When processing a new submission, follow this sequence:

### Step 1: Read PDFs First (Triggers OCR)
```python
content = read_file("/attachments/property_guide.pdf")
# This triggers Mistral OCR on first read
# Returns text + extracted_images list
extracted_images = content.get("extracted_images", [])
```

### Step 2: Classify All Images
```python
# Combine email attachments + PDF-extracted images
all_images = overview["images"] + extracted_images

classification = classify_image_types(paths=all_images)
property_photos = classification["property_foto_paths"]
document_photos = classification["document_foto_paths"]
```

### Step 3: Analyze Property Photos (Saves to DB)
```python
if property_photos:
    result = analyze_property_fotos(
        paths=property_photos,
        save_to_db=True,
        property_id=property_id  # if you have it
    )
    # Rooms created in DB, attachments updated with room assignments
    room_ids = result["room_ids"]
```

### Step 4: Analyze Document Images
```python
if document_photos:
    doc_info = analyze_document_images(paths=document_photos)
    # Returns text description of floor plans, contracts, etc.
```

---

## Complete Turn Example

```python
# 1. Get overview
overview = get_session_overview()

# 2. Read PDFs (triggers Mistral OCR)
pdf_content = read_file("/attachments/property_guide.pdf")
extracted_images = pdf_content.get("extracted_images", [])

# 3. Classify images
all_images = overview["images"] + extracted_images
classification = classify_image_types(paths=all_images)

# 4. Analyze property photos (saves rooms to DB)
if classification["property_foto_paths"]:
    room_result = analyze_property_fotos(
        paths=classification["property_foto_paths"],
        save_to_db=True
    )

# 5. Analyze document photos
if classification["document_foto_paths"]:
    doc_info = analyze_document_images(
        paths=classification["document_foto_paths"]
    )

# 6. Extract property data
edit_property(
    address_line1="123 Beach Drive",
    city="Miami",
    max_guests=8,
    evidence=EvidenceData(
        source_type="document",
        source_path="/attachments/property_guide.pdf",
        excerpt="Address: 123 Beach Drive"
    )
)

# 7. Check for gaps
property = get_property()
# (identify missing info)

# 8. Update status
update_session(
    status="awaiting_info",
    status_reason="Need WiFi network name"
)

# 9. TERMINATE with email
send_email(
    to="owner@example.com",
    subject="Re: Property Submission - Quick question",
    body="Hi,\n\nWhat's the WiFi network name?...\n\nCheers,\nArbie"
)
# Loop ends here
```

## REMEMBER: Email = Termination

**When you send an email, your turn IMMEDIATELY ends. You cannot do anything after.**

**NEVER write:**
- "I'll start working on the research now..."
- "I'll begin extracting the property details..."
- "I'll update the property information next..."
- "Let me process this and get back to you..."

These phrases imply future work, but **you have no future after `send_email()`**.
Instead do the work first, then finish your turn with an email.

## Remember

- One turn = One email sent
- No email = Loop hangs
- Email sent = Turn ends instantly
- Update session status BEFORE sending email
- Use past/present perfect tense in emails (never future tense)
- Keep emails conversational and concise
