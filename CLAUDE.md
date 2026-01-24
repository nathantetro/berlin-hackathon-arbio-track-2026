# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Arbie is an email-native AI agent for property onboarding at Arbio. It automates the process of turning chaotic property submissions (PDFs, photos, emails) into structured, ready-to-list vacation rentals. The agent extracts data, researches compliance, asks follow-up questions, and generates property summaries for owner validation.

## Development Commands

```bash
# Install dependencies
uv sync

# Run locally (requires Towerfile)
tower run local

# Deploy to Tower cloud
tower deploy
```

## Architecture

### Tech Stack
- **Tower.dev** - Agent orchestration, workflow scheduling, Iceberg tables for state
- **OpenAI Agents SDK** - Agent framework using `@function_tool` decorators
- **GPT-5.2** - Main LLM powering Arbie
- **Tavily** - Web research for compliance checks
- **MailerSend** - Email sending/receiving
- **WeasyPrint** - PDF generation from markdown

### Code Structure

```
arbie/
├── agents/    # Main Arbie agent + Research Agent (handoff)
├── tools/     # Function tools: file, vision, email, property, session
├── models/    # Pydantic schemas (see specs/schema.md for full details)
└── services/  # External integrations (email, storage, research)
```

### Core Concepts

**Session-based context**: All tools operate within an implicit session context. Tools do not require `session_id` parameters.

**Virtual file system per session**:
- `/attachments/**` - Read-only, from emails
- `/extracted/**` - Read-only, auto-generated text/images from PDFs
- `/workspace/**` - Read-write, Arbie's working area
- `/outputs/**` - Generated PDFs

**Tools are implemented with `@function_tool` decorator** from OpenAI Agents SDK. See `specs/tools.md` for the full tool specification.

**Sub-agents use handoffs**: The Research Agent (for compliance) is exposed to Arbie as a handoff, not a direct tool call.

### Data Model Highlights

Properties have both hard attributes (typed required fields like `address_line1`, `max_guests`) and flexible attributes (key-value pairs via `PropertyAttribute`). Every extracted value links back to source evidence for traceability.

Session lifecycle: `RECEIVED → EXTRACTING → AWAITING_INFO ↔ (loop) → RESEARCHING → READY → VALIDATED`

## Specifications

Detailed specs live in `/specs`:
- `schema.md` - Complete data model with Pydantic-style definitions
- `tools.md` - All tool signatures, parameters, and examples
- `user-stories.md` - Feature requirements organized by epic
- `initial-skeleton.md` - Original design rationale
