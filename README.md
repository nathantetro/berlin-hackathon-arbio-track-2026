# ARBIE

**A**gent for **R**eally **B**rilliant **I**nsights & **E**xecution

An email-native AI agent that automates property onboarding at Arbio, turning chaotic submissions (PDFs, photos, emails) into structured, ready-to-list vacation rentals.

## Overview

Arbie receives property documents via email, extracts structured data, researches compliance requirements, asks follow-up questions when information is missing, and generates a validated property summary for owners to approve before listing.

## Architecture

### Agentic System

Arbie is built on the OpenAI Agents SDK with GPT-5.2 as the reasoning engine. Each session operates independently with:

- **Session-based workflow**: Persistent state tracked through Iceberg tables with status progression (`RECEIVED → EXTRACTING → AWAITING_INFO → RESEARCHING → READY → VALIDATED`)
- **Virtual file system**: Session-scoped file access (`/attachments/`, `/extracted/`, `/workspace/`, `/outputs/`)
- **Function tools**: File analysis, vision processing, property management, email communication (see `specs/tools.md`)
- **Sub-agent handoffs**: Research Agent for compliance checks via handoff pattern

All tools are implemented with `@function_tool` decorators and operate within implicit session context.

### Tower Orchestration

Tower.dev provides the orchestration layer:

- **Gateway App**: FastAPI server running 24/7, listening to Microsoft Graph webhooks for incoming emails
- **Agent Spawning**: Each email spawns a dedicated agent app via `tower.run_app()` with isolated execution
- **Concurrency**: Multiple simultaneous property submissions run as parallel agent instances
- **Data Storage**: All state persisted in Iceberg tables (Tower catalog: `arbie-properties`)
  - 14 tables: `sessions`, `emails`, `attachments`, `properties`, `rooms`, `evidence`, and more
  - ACID-compliant with retry logic for concurrent write conflicts
  - See `specs/schema.md` for complete data model

### RunPod Preprocessing Pipeline

Before Arbie processes a submission, all attachments go through automated preprocessing:

**Step 1: PDF Extraction**
- Mistral OCR extracts text and embedded images from PDFs
- Results stored in `/extracted/` virtual filesystem

**Step 2: Image Classification**
- RunPod serverless CLIP model classifies all images (PDFs + direct uploads)
- Categories: bedroom, kitchen, bathroom, living room, exterior, documents, etc.

![Image Classification](assets/readme/log1.png)
*RunPod CLIP classifies images by room type*

**Step 3: Room Deduplication**
- OpenAI Vision API (GPT-5.2) analyzes grouped images per room type
- Identifies individual rooms (e.g., multiple photos of the same bedroom → one room)
- Extracts objects and amenities from each room

![Room Deduplication](assets/readme/log2.png)
*Vision API identifies individual rooms and extracts objects*

**Output**: Structured room metadata available before agent runs. See [`specs/preprocessing-pipeline.md`](specs/preprocessing-pipeline.md) for detailed diagrams.

### Email Communication

Arbie communicates exclusively via email:

- **Inbound**: Microsoft Graph webhook triggers gateway, spawns agent
- **Outbound**: Resend API sends responses (questions, summaries, validation requests)
- **Tracking**: Every email includes session URL (`{gateway}/session/{reference-code}`)
- **Web Dashboard**: Real-time progress tracking with neon-themed UI
- **Final Output**: Property summary PDF generated with WeasyPrint, sent for owner validation

## Tech Stack

- **Tower.dev** - Orchestration, Iceberg tables, agent spawning
- **OpenAI Agents SDK** - Agent framework with function tools
- **GPT-5.2** - Main LLM for reasoning and vision analysis
- **Mistral OCR** - PDF text and image extraction
- **RunPod** - Serverless CLIP image classification
- **Azure Blob Storage** - Persistent file storage
- **Microsoft Graph** - Inbound email webhooks
- **Resend** - Outbound email delivery
- **Tavily** - Web research for compliance checks
- **WeasyPrint** - PDF generation from markdown

## Quick Start

```bash
# Install dependencies
uv sync

# Run locally (requires Towerfile)
tower run local

# Deploy to Tower cloud
tower deploy
```

## Project Structure

```
arbie/
├── agents/    # Main Arbie agent + Research Agent (handoff)
├── tools/     # Function tools: file, vision, email, property, session
├── models/    # Pydantic schemas (see specs/schema.md)
└── services/  # External integrations (email, storage, research)
```

See [`CLAUDE.md`](CLAUDE.md) for detailed development guidance and [`specs/`](specs/) for complete specifications.

## License

MIT
