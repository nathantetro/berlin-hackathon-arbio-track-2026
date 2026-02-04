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
    ├── workspace/         ← Agent's working notes/drafts
    │   └── notes.md
    └── outputs/           ← Generated PDFs
        └── property-summary.pdf
```

**Note:** `/extracted/` folder is defined in specs but NOT USED.

## Agent Tools

### File Tools (`arbie/tools/file_tools.py`)

| Tool | Purpose |
|------|---------|
| `get_session_overview()` | **Call FIRST every turn.** Returns all files, images, documents, room metadata, preprocessing status |
| `list_files(path, recursive)` | List directory contents |
| `read_file(path, keyword)` | Read text files. PDFs return pre-extracted text from DB |
| `write_file(path, content, mode)` | Write to `/workspace/` only |
| `get_attachment_metadata(paths)` | Get detailed preprocessing metadata for attachments |

### Vision Tools (`arbie/tools/vision_tools.py`)

| Tool | Purpose |
|------|---------|
| `classify_image_types(paths)` | Classify images as `property_foto` or `document_foto` |
| `analyze_property_fotos(paths)` | Cluster photos into rooms, detect objects, save to DB |
| `analyze_document_images(paths)` | Extract text/info from document images |

### Property Tools (`arbie/tools/property_tools.py`)

| Tool | Purpose |
|------|---------|
| `get_property(include_history)` | Get current property data with all fields, rooms, photos |
| `edit_property(...)` | Create/update property fields (address, bedrooms, etc.) |
| `edit_room(...)` | Create/update room records |
| `edit_photo(...)` | Assign photos to rooms, set display order |

### Email Tools (`arbie/tools/email_tools.py`)

| Tool | Purpose |
|------|---------|
| `send_email(to, subject, body)` | Send email via Resend. Auto-threads to session |
| `fetch_emails(direction, limit)` | Get email history for session |

### Session Tools (`arbie/tools/session_tools.py`)

| Tool | Purpose |
|------|---------|
| `update_session(status, reason)` | Update session status (received → extracting → awaiting_info → ready → validated) |

### Generation Tools (`arbie/tools/generation_tools.py`)

| Tool | Purpose |
|------|---------|
| `generate_pdf(source_path, output_path)` | Convert markdown/HTML to PDF with Arbio branding |
| `generate_property_summary_pdf(data)` | Generate structured property summary PDF |

### Research Tool (Handoff)

| Tool | Purpose |
|------|---------|
| `research_compliance(address)` | Research short-term rental regulations via Tavily |

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
RECEIVED → EXTRACTING → AWAITING_INFO ↔ (loop) → RESEARCHING → READY → VALIDATED
```

## Environment Variables

```bash
# S3 Storage
AWS_S3_BUCKET_NAME=berlin-hackathon-arbio
AWS_REGION=eu-north-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# AI Services
OPENAI_API_KEY=...
MISTRAL_API_KEY=...   # For PDF OCR

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
| File preprocessing (DISABLED) | `arbie/services/file_preprocessing.py` |
