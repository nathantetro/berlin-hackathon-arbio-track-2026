# ARBIE

**A**gent for **R**eally **B**rilliant **I**nsights & **E**xecution


An AI agent that turns chaotic property submissions into structured, ready-to-list vacation rentals.

## What it does

1. Receives property docs via email (PDFs, photos, random notes)
2. Extracts and structures everything automatically
3. Asks smart follow-up questions when info is missing
4. Researches local regulations
5. Generates a polished property summary
6. Lets owners validate before going live

## Attachment Preprocessing

Before Arbie runs, all attachments go through an automated preprocessing pipeline:

```
Email Attachments
       ↓
   ┌───┴───┐
   ↓       ↓
  PDFs   Images
   ↓       ↓
Mistral    ├──────────────┐
  OCR      ↓              ↓
   ↓    RunPod CLIP    (collected)
   ├→ extracted text   classification
   └→ extracted images     ↓
          ↓           room types
          └─────┬─────────┘
                ↓
         OpenAI Vision
                ↓
         Rich Room Metadata
      (objects, amenities)
                ↓
           Arbie Agent
```

1. **PDFs** → Mistral OCR extracts text and embedded images
2. **All images** → RunPod CLIP classifies by room type (bedroom, kitchen, bathroom, etc.)
3. **Grouped images** → OpenAI Vision clusters into distinct rooms and extracts visible objects
4. **Result** → Structured room metadata available to Arbie before it starts

See [`specs/preprocessing-pipeline.md`](specs/preprocessing-pipeline.md) for detailed diagrams.

## Stack

- **Tower.dev** - orchestration & scheduling
- **OpenAI Agents SDK** - agent framework
- **GPT-5.2** - the brain
- **Mistral OCR** - PDF text & image extraction
- **RunPod** - CLIP image classification
- **Azure Blob Storage** - file storage
- **Microsoft Graph** - email receiving
- **Resend** - email sending
- **Tavily** - web research
- **WeasyPrint** - PDF generation

## Quick start

```bash
uv sync
tower run local
```

## Project structure

```
arbie/
├── agents/    # Arbie + Research Agent
├── tools/     # File, vision, email, property tools
├── models/    # Data schemas
└── services/  # External integrations
```

## License

MIT
