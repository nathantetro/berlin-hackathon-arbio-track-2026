# Arbie Agent - Technical Overview

## Flow: Email → Agent

```
Email arrives
     ↓
Gateway receives webhook (apps/gateway/main.py)
     ↓
process_inbound_email() (arbie/services/email_processor.py)
  - Find/create user
  - Find/create session
  - Store email in DB
  - Upload attachments to S3 → /attachments/{filename}
     ↓
Arbie agent runs (arbie/agents/arbie_agent.py)
  - Uses tools to explore files, analyze images, build property
  - Sends emails to owner for missing info
  - Generates PDF summary when complete
```

**Note:** `preprocess_and_classify()` is DISABLED (commented out in `apps/agent/main.py`). The agent handles image classification directly via vision tools.

## S3 Bucket Structure

```
s3://berlin-hackathon-arbio/
└── {session_id}/
    ├── attachments/       ← Email attachments (uploaded by email_processor)
    │   ├── photo1.jpg
    │   └── document.pdf
    ├── extracted/         ← PDF-extracted images (created by read_file on-demand)
    │   └── document_page1.jpg
    ├── workspace/         ← Agent's working notes/drafts
    │   └── notes.md
    └── outputs/           ← Generated PDFs
        └── property-summary.pdf
```

**`/extracted/` folder:** Stores images extracted from PDFs via Mistral OCR. Created by `_extract_pdf_on_demand()` when `read_file()` is called on a PDF for the first time. Files are named `{pdf_basename}_{img_filename}`.

**Note:** Room clustering does NOT save to JSON files in `/extracted/`. The `analyze_property_fotos()` vision tool saves room records directly to the database.

## Agent Tools

### File Tools (`arbie/tools/file_tools.py`)

| Tool | Purpose |
|------|---------|
| `get_session_overview()` | **Call FIRST every turn.** Returns all files, images, documents, room metadata, preprocessing status |
| `list_files(path, recursive=False)` | List directory contents |
| `read_file(path, keyword=None, context_lines=3, max_chars=10000)` | Read text files (.txt, .md, .json). **PDFs trigger on-demand Mistral OCR** (`mistral-ocr-latest`) on first read, then cached. Returns `extracted_images` list with paths to images saved in `/extracted/`. Supports keyword filtering with context. |
| `write_file(path, content, mode="w")` | Write to `/workspace/` only (append mode supported) |
| `get_attachment_metadata(paths)` | Get detailed preprocessing metadata for attachments |

### Vision Tools (`arbie/tools/vision_tools.py`)

| Tool | Purpose |
|------|---------|
| `classify_image_types(paths)` | Classify images as `property_foto` or `document_foto`. Uses GPT-4o (detail: **low**). Returns `{property_foto_paths, document_foto_paths}` |
| `analyze_property_fotos(paths, save_to_db=True, email_id="", property_id="")` | Cluster photos into rooms with room types, detect objects. Uses GPT-4o (detail: **high**). **Saves to DB by default** (`save_to_db=True`) - creates room records + updates attachments. Returns `{rooms: [...], room_ids: [...]}`. `room_ids` only populated when `save_to_db=True`. |
| `analyze_document_images(paths)` | Extract text/info from floor plans, contracts, certificates, scanned documents. Uses GPT-4o (detail: **high**). Returns **TEXT** (not JSON) - includes document type, dates, names, measurements, signatures. |

**Note:** `analyze_images()` is disabled (generic vision tool - use specialized tools above instead).

### Room Types (24 canonical types)

Used by `analyze_property_fotos()` for room classification:

**Indoor rooms:**
- `bedroom`, `bathroom`, `kitchen`, `living_room`, `dining_room`, `office`
- `laundry`, `garage`, `hallway`, `closet`, `basement`, `attic`

**Outdoor spaces:**
- `patio`, `balcony`, `deck`, `pool_area`, `garden`, `parking`

**Generic:**
- `exterior`, `common_area`, `other`

### Property Tools (`arbie/tools/property_tools.py`)

| Tool | Purpose |
|------|---------|
| `get_property(include_history)` | Get current property data with all fields, rooms, photos |
| `edit_property(...)` | Create/update property fields (address, bedrooms, etc.) |
| `edit_room(...)` | Create/update room records |
| `edit_photo(...)` | Assign photos to rooms, set display order |

**Evidence Tracking:** All property edits support an optional `evidence` parameter for source traceability:
- `source_type`: "document", "image", "email", or "inference"
- `source_path`: Path to the source file
- `excerpt`: Relevant text snippet
- `confidence`: "high", "medium", or "low"

**Completeness Score:** Calculated from 6 required fields: `address_line1`, `city`, `country`, `max_guests`, `bedrooms`, `bathrooms`

### Email Tools (`arbie/tools/email_tools.py`)

| Tool | Purpose |
|------|---------|
| `send_email(to, subject, body, attachments, reply_to_message_id)` | Send email via Resend. **Auto-threads** to most recent inbound email if `reply_to_message_id` not specified. |
| `fetch_emails(direction="all", limit=50)` | Get email history for session. Returns reverse chronological order. |

### Session Tools (`arbie/tools/session_tools.py`)

| Tool | Purpose |
|------|---------|
| `update_session(status, reason)` | Update session status: `received`, `extracting`, `awaiting_info`, `researching`, `ready`, `validated`, `archived` |

### Generation Tools (`arbie/tools/generation_tools.py`)

| Tool | Purpose |
|------|---------|
| `generate_pdf(source_path, output_path)` | Convert markdown/HTML to PDF with Arbio branding |
| `generate_property_summary_pdf(data)` | Generate structured property summary PDF |

### Research Agent (Handoff from Arbie)

Arbie can handoff to the Research Agent for compliance research. The Research Agent is accessed via **handoff** (not a direct tool call).

**Research Agent's Internal Tools** (`arbie/tools/research_tools.py`):
- `web_search(query, max_results=5)` - Search web via Tavily for regulations, permits, taxes
- `todo(action, item)` - Manage research todo list:
  - `add`: Add a new item to research
  - `complete`: Mark an item as done
  - `list`: Show current todo list
  - `clear`: Clear all items

## Database Tables

- `users` - Property owners
- `sessions` - Onboarding sessions (status, reference_code)
- `emails` - Email records with threading
- `attachments` - File metadata + extracted_text
- `properties` - Core property data (address, bedrooms, etc.)
- `property_attributes` - Flexible key-value attributes
- `rooms` - Room records with objects/amenities
- `property_photos` - Photo metadata + room assignment
- `evidence` - Source traceability for extracted data
- `session_events` - Audit log

## Session Status Flow

```
RECEIVED → EXTRACTING → AWAITING_INFO ↔ (loop) → RESEARCHING → READY → VALIDATED → ARCHIVED
```

- `VALIDATED` and `ARCHIVED` are terminal states (set `completed_at` timestamp)

## Environment Variables

```bash
# S3 Storage
AWS_S3_BUCKET_NAME=berlin-hackathon-arbio
AWS_REGION=eu-north-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# AI Services
OPENAI_API_KEY=...      # GPT-5.2 for agent, GPT-4o for vision
MISTRAL_API_KEY=...     # For PDF OCR (mistral-ocr-latest - extracts text + images)
TAVILY_API_KEY=...      # For Research Agent web search

# Email
RESEND_API_KEY=...

# Preprocessing (DISABLED - not currently used)
# RUNPOD_ENDPOINT_ID=...
# RUNPOD_API_KEY=...
```

## Key Code Paths

| Purpose | File |
|---------|------|
| Agent definition | `arbie/agents/arbie_agent.py` |
| Agent runner | `apps/agent/main.py` |
| Email ingestion | `arbie/services/email_processor.py` |
| S3 storage | `arbie/services/storage.py` |
| Gateway server | `apps/gateway/main.py` |
| Agent prompts | `arbie/agents/prompts/*.md` |
| DB operations: Rooms | `arbie/services/db/rooms.py` |
| DB operations: Property | `arbie/services/db/property.py` |
| DB operations: Email | `arbie/services/db/email.py` |
| File preprocessing (DISABLED) | `arbie/services/file_preprocessing.py` |
