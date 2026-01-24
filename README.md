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

## Stack

- **Tower.dev** - orchestration & storage
- **OpenAI Agents SDK** - agent framework
- **GPT-5.2** - the brain
- **Keywords AI** - agent tracing & observability
- **Tavily** - web research
- **MailerSend** - email
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
