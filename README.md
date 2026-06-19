# Notes Processor

An automated system that receives messages from Telegram, processes them with Claude AI, and generates structured Obsidian notes with proper categorization, tagging, and wikilinks.

## What It Does

Send a message to your Telegram bot, and it automatically:
1. Detects language (Arabic or English)
2. Extracts key concepts, tags, and entities using Claude AI
3. Categorizes content (Sayings, Poetry, Jots, Islam, History, Strategy, Definitions, Path)
4. Creates Obsidian-formatted markdown notes with YAML frontmatter
5. Optionally syncs to GitHub for cloud storage
6. Translates Arabic terminology to English

## Key Features

- **Telegram Integration**: Secure, authorized access only to your account
- **HTTP API**: Programmatic access via REST API for automation and integrations
- **Database Storage**: SQLite/PostgreSQL for message history, replay, and analytics
- **Message Replay**: Reprocess failed messages with retry management
- **Analytics Dashboard**: Track message statistics by category, language, and status
- **YouTube Transcription**: Extract and process video transcripts automatically
- **Language Detection**: Automatic Arabic/English detection and organization
- **AI Processing**: Claude AI extracts concepts, tags, entities, and creates wikilinks
- **Category Enforcement**: Strict category matching with prefix support (`Poetry -> message`)
- **Limits**: Max 5 tags, concepts, and terms per note
- **Obsidian Vault**: Organized by language and category with rich metadata
- **Git Sync**: Optional automatic commits and push to GitHub
- **Cloud Deployment**: Ready for Railway, DigitalOcean, AWS (includes Docker)
- **Translations**: Automatic Arabic-to-English term translations for Arabic notes
- **Graceful Degradation**: System continues working even if database is unavailable

## Quick Start

**Local Testing:**
See [LOCAL_TESTING.md](./docs/LOCAL_TESTING.md) for complete setup instructions.

**Cloud Deployment:**
See [DEPLOYMENT.md](./docs/DEPLOYMENT.md) for Railway deployment with GitHub vault sync.

**Database Features:**
See [DATABASE.md](./docs/DATABASE.md) for message history, replay, and analytics documentation.

## Categories

Notes are organized into 8 predefined categories:

| Category | Use For |
|----------|---------|
| **Sayings** | Quotes, proverbs, wisdom |
| **Poetry** | Poems, verses, lyrical content |
| **Jots** | Quick notes, random thoughts (default) |
| **Kb** | knowledge, teachings |
| **History** | Historical facts, events |
| **Strategy** | Strategic thinking, planning |
| **Definitions** | Term definitions, explanations |
| **Path** | Personal growth, spiritual journey |

### Using Categories

**Specify with prefix:**
```
Poetry -> Roses are red, violets are blue
```

**Default to Jots:**
```
Just a random thought
```

Invalid categories automatically default to "Jots".

## Note Structure

Each note includes:

**YAML Frontmatter:**
```yaml
id: "20260517123456"
title: "Note Title"
language: ar/en
category: Poetry
tags: [max 5 tags]
concepts: [max 5 concepts]
entities:
  people: [max 5]
  places: [max 5]
  terms: [max 5]
source: telegram
created: "2026-05-17T12:34:56"
```

**Content Sections:**
- Summary (1-2 sentences)
- Content (AI-processed with wikilinks)
- Key Concepts (top 5)
- Entities (people, places, terms - max 5 each)
- Translations (Arabic notes only - max 5, legacy)
- **Key Terms Table** (all technical terms with translations & explanations)*
- **Comparison Table** (if content contains comparisons)*
- **Original Text** (exact copy of your message, preserved at bottom)

*_Automatically skipped for Sayings and Poetry categories_

## Vault Organization

```
vault/
├── arabic/
│   ├── sayings/
│   ├── poetry/
│   ├── jots/
│   ├── islam/
│   ├── history/
│   ├── strategy/
│   ├── definitions/
│   └── path/
└── english/
    ├── sayings/
    ├── poetry/
    ├── jots/
    ├── islam/
    ├── history/
    ├── strategy/
    ├── definitions/
    └── path/
```

## Usage Examples

**English with category:**
```
Sayings -> Knowledge is power
```
→ `vault/english/sayings/20260517_123456_knowledge_is_power.md`

**Arabic with category:**
```
Islam -> الصلاة عمود الدين
```
→ `vault/arabic/islam/20260517_123456_note.md` (with translations)

**No category (defaults to Jots):**
```
Just a random thought I had
```
→ `vault/english/jots/20260517_123456_note.md`

**YouTube video transcription:**
```
History -> https://youtube.com/watch?v=xxxxx
```
→ Transcribes video, processes with AI, creates note in `vault/english/history/`

**HTTP API (programmatic):**
```bash
curl -X POST http://localhost:8080/api/v1/notes \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Sayings -> Knowledge is power"}'
```

**YouTube via HTTP API:**
```bash
curl -X POST http://localhost:8080/api/v1/youtube \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=xxxxx", "category": "History"}'
```

## Architecture

```
┌─────────────┐         ┌─────────────┐
│  Telegram   │         │  HTTP API   │
│    User     │         │   Client    │
└──────┬──────┘         └──────┬──────┘
       │ Message               │ POST /api/v1/notes
       │                       │ POST /api/v1/youtube
       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐
│  Telegram Bot   │   │   HTTP API      │
│  (Authorized)   │   │  (API Key Auth) │
└──────┬──────────┘   └──────┬──────────┘
       │                     │
       └──────────┬──────────┘
                  │
       ┌──────────▼──────────┐
       │  YouTube URL?       │
       └──────┬───────┬──────┘
           Yes│       │No
              ▼       │
    ┌─────────────────┐
    │  YouTube        │
    │  Processor      │
    │ - Transcript API│
    │ - Whisper (fallback)
    │ - Summarization │
    └──────┬──────────┘
           │ Transcript
           ▼
┌─────────────────┐
│  Language       │
│  Detector       │
└──────┬──────────┘
       │ ar/en
       ▼
┌─────────────────┐
│  Claude AI      │
│  Processor      │
└──────┬──────────┘
       │ Structured data
       ▼
┌─────────────────┐
│  Obsidian Note  │
│  Generator      │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Git Sync       │
│  (Optional)     │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  GitHub Repo    │
│  (Private)      │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Obsidian       │
│  (Local Sync)   │
└─────────────────┘
```

## Documentation

- **[LOCAL_TESTING.md](LOCAL_TESTING.md)** - Complete local setup, testing, and troubleshooting
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Railway deployment with GitHub vault sync
- **README.md** (this file) - Project overview and reference

## Requirements

- Python 3.9+
- Telegram bot token (from @BotFather)
- Claude API key (from console.anthropic.com)
- GitHub account (for cloud sync, optional)

## License

MIT
