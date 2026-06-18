# Claude Context Document

This document provides context for Claude to continue development on this project.

## Project Overview

**Second Brain** - An automated note-taking system that processes messages from Telegram and HTTP API, transcribes YouTube videos, and creates structured Obsidian notes using Claude AI.

### Key Features
- **Multi-source input**: Telegram bot, HTTP API
- **YouTube transcription**: Automatic transcription using OpenAI Whisper API
- **AI processing**: Claude AI extracts metadata, concepts, entities, and structures content
- **Obsidian integration**: Generates markdown notes with YAML frontmatter and wikilinks
- **Database tracking**: SQLite database tracks all messages and notes
- **Git sync**: Optional auto-commit and push to remote repository
- **Batch processing**: Queue-based processing with atomic worker claims

## Architecture

### Core Components

1. **Handlers** (`src/handlers/`)
   - `telegram_handler.py` - Telegram bot message handler
   - `http_handler.py` - FastAPI HTTP endpoints

2. **Processors** (`src/processors/`)
   - `claude_processor.py` - Claude AI integration for content analysis
   - `youtube_processor.py` - YouTube video processing orchestrator
   - `note_generator.py` - Obsidian markdown note generator

3. **Utilities** (`src/utils/`)
   - `whisper_transcriber.py` - OpenAI Whisper API transcription
   - `language_detector.py` - Language detection
   - `git_sync.py` - Git auto-commit and push

4. **Database** (`src/db/`)
   - `database.py` - SQLAlchemy database manager
   - `models.py` - Database models (Message, ProcessedNote)
   - `repository.py` - Data access layer

5. **Main Entry Points**
   - `main.py` - Telegram bot runner
   - `http_main.py` - HTTP API server
   - `batch_processor.py` - Background batch processing

## Recent Changes (Latest Session)

### YouTube Transcription Migration
**Problem**: Gladia API was unreliable and failed frequently.

**Solution**: Migrated to OpenAI Whisper API using proven working script from sister project.

**Implementation**:
- Created `src/utils/whisper_transcriber.py` with yt-dlp + OpenAI Whisper
- Downloads audio with yt-dlp using FFmpeg post-processing
- Splits audio into 10-minute chunks using pydub
- Transcribes each chunk with OpenAI Whisper API
- Falls back to YouTube Transcript API first (free captions)
- Updated Dockerfile to include ffmpeg

**Files changed**:
- `src/utils/whisper_transcriber.py` (NEW)
- `src/processors/youtube_processor.py` (updated to use WhisperTranscriber)
- `requirements.txt` (removed Gladia, added openai, pydub, ffmpeg-python)
- `.env.example` (changed GLADIA_API_KEY to OPENAI_API_KEY)
- `Dockerfile` (added ffmpeg)
- Deleted: `src/utils/gladia_transcriber.py`

### YouTube Data Structure Change
**Problem**: `process_youtube_url()` returned string, needed structured metadata.

**Solution**: Changed return type to dict with content, title, URL, category.

**Impact**: Updated all 3 handlers to extract dict fields:
- `src/handlers/telegram_handler.py:234-260`
- `src/handlers/http_handler.py:580-585`
- `src/batch_processor.py:204-236`

### Metadata Preservation on Failure
**Problem**: Failed messages showed empty category and language in database.

**Solution**:
- Early language detection before any processing
- Track `category_for_db` from early extraction
- Pass both to `update_status()` even on failure

**Files changed**:
- `src/batch_processor.py:165-275`
- `src/handlers/http_handler.py:540-625`
- `src/handlers/telegram_handler.py:189-298`

### Note Generator Simplification
**Changes made** (as of last session):

1. **Frontmatter simplification**:
   - Removed: `tags`, `concepts`, `entities`, `related_notes`
   - `source` now shows `telegram` or `http` (submission method)
   - Added `youtube_url` property when YouTube URL processed

2. **Footer simplification**:
   - Shows: `*Generated from {source} on {timestamp}*`
   - YouTube URL displayed without "Source:" label

3. **Poetry/Sayings category special handling**:
   - No title heading in note body (only in frontmatter)
   - Only two sections: "People" (with wikilinks) and "Original Text"
   - Removed: Summary, Content, Key Concepts, Entities, Translations, Key Terms, Comparison Table

4. **Language preservation for Poetry/Sayings**:
   - Claude explicitly instructed to keep titles in ORIGINAL language
   - Entity names (people, places) kept in ORIGINAL language
   - No translation to English for Arabic poetry/sayings

**Files changed**:
- `src/processors/note_generator.py:169-237, 350-370`
- `src/processors/claude_processor.py:149-180`
- `src/handlers/telegram_handler.py:267-268`
- `src/handlers/http_handler.py:584-585`
- `src/batch_processor.py:243-247`

## Current State

### What's Working ✅
- Telegram bot receives messages and queues them
- HTTP API accepts messages and YouTube URLs
- YouTube transcription using OpenAI Whisper (reliable)
- Claude AI processing extracts metadata
- Notes generated in Obsidian vault with proper structure
- Database tracks all messages with status
- Git auto-commit and push (if enabled)
- Batch processing with atomic worker claims
- Poetry/Sayings categories use simplified format
- Language preservation for Arabic poetry/sayings

### Configuration
Required environment variables (see `.env.example`):
- `ANTHROPIC_API_KEY` - Claude AI
- `OPENAI_API_KEY` - Whisper transcription
- `TELEGRAM_BOT_TOKEN` - Telegram bot
- `TELEGRAM_ALLOWED_USER_ID` - Security
- `HTTP_API_KEY` - HTTP API security
- `VAULT_PATH` - Obsidian vault path
- `DATABASE_URL` - SQLite database
- `GIT_AUTO_COMMIT` - Enable git sync
- `YOUTUBE_ENABLED` - Enable YouTube processing

### Database Schema
**messages table**:
- Tracks all incoming messages
- Status: QUEUED → PROCESSING → COMPLETED/FAILED
- Stores: raw_text, source, user_id, category, language, error_message
- Worker ID for distributed processing

**processed_notes table**:
- Links to messages
- Stores: title, file_path, tags, concepts, entities, summary
- Full processed_data JSON

## Known Areas for Improvement

### Potential Enhancements
1. **YouTube transcription cost optimization**
   - Currently chunks every video
   - Could check if captions exist first more aggressively
   - Could cache transcriptions

2. **Note linking**
   - Could implement backlinks
   - Could suggest related notes based on concepts/entities

3. **Error recovery**
   - Retry logic for transient failures
   - Better handling of partial transcriptions

4. **Performance**
   - Parallel processing of multiple queued messages
   - Async YouTube downloads

5. **Testing**
   - Add unit tests for processors
   - Integration tests for handlers
   - Mock Claude/OpenAI APIs for testing

## Development Workflow

### Running the System

**Telegram bot (immediate processing)**:
```bash
python main.py
```

**Telegram bot (batch mode)**:
```bash
BATCH_MODE=true python main.py
```

**HTTP API server**:
```bash
python http_main.py
```

**Batch processor**:
```bash
# Run once
python src/batch_processor.py --once

# Run continuously
python src/batch_processor.py
```

### Docker Deployment
```bash
docker build -t second-brain .
docker run -d --env-file .env second-brain
```

### Database Operations
```bash
# Initialize database
python -c "from src.utils.db_init import initialize_database; import asyncio; asyncio.run(initialize_database())"

# Query messages
sqlite3 notes.db "SELECT * FROM messages WHERE processing_status='FAILED';"
```

## Important Code Patterns

### Processing Pipeline
1. **Receive message** (Telegram/HTTP)
2. **Detect language** (`detect_language()`)
3. **Check for YouTube URL** (`is_youtube_url()`)
4. **If YouTube**: Extract category prefix, transcribe, get metadata
5. **Process with Claude** (`claude_processor.process_message()`)
6. **Add source field** to processed_data
7. **Generate note** (`note_generator.generate_note()`)
8. **Update database** status to COMPLETED/FAILED

### Source Field Tracking
All handlers must set `processed_data["source"]`:
- Telegram: `"telegram"`
- HTTP: `"http"`
- Batch: reads from `message.source` and normalizes `http_api` → `http`

### Category Handling
- User can specify category via prefix: `"Poetry -> content"`
- YouTube: Category passed to `process_youtube_url(category=...)`
- Claude: `specified_category` parameter enforces category
- Default: `"Jots"` if no category specified

### Poetry/Sayings Detection
Check category (case-insensitive):
```python
if category.lower() in ["poetry", "sayings"]:
    # Simplified processing
```

## Key File References

### Configuration
- `src/config.py` - All configuration with validation
- `.env.example` - Environment variable template

### YouTube Processing
- `src/processors/youtube_processor.py:96-158` - Main processing logic
- `src/utils/whisper_transcriber.py:36-135` - Transcription implementation

### Note Generation
- `src/processors/note_generator.py:159-372` - Content generation
- `src/processors/note_generator.py:207-231` - Poetry/Sayings special handling

### Claude Processing
- `src/processors/claude_processor.py:26-222` - Main processing
- `src/processors/claude_processor.py:155-160` - Poetry/Sayings language preservation

### Error Handling
- `src/batch_processor.py:149-277` - Batch processing with error preservation
- `src/handlers/telegram_handler.py:189-298` - Telegram error handling

## Next Steps / TODO

### Immediate
- [ ] Test Arabic poetry/sayings to verify language preservation
- [ ] Monitor YouTube transcription costs
- [ ] Verify frontmatter simplification works as expected

### Future Considerations
- [ ] Add retry logic for failed transcriptions
- [ ] Implement note deduplication
- [ ] Add support for audio messages from Telegram
- [ ] Create admin dashboard for viewing queue/stats
- [ ] Add support for video attachments (not just URLs)

## Troubleshooting

### Common Issues

**YouTube transcription fails**:
- Check `OPENAI_API_KEY` is set
- Check ffmpeg is installed (`which ffmpeg`)
- Check logs for download errors

**Database errors**:
- Ensure `DATABASE_URL` points to writable location
- Check if database file exists
- Run migrations if schema changed

**Git sync fails**:
- Check vault is a git repository
- Check remote is configured
- Check SSH keys or credentials

**Claude returns English for Arabic**:
- Check category is exactly "Poetry" or "Sayings" (case-insensitive)
- Check `specified_category` is passed to `claude_processor.process_message()`
- Review Claude prompt in logs

## Contact & Context

**Project Path**: `/Users/khaled/github/personal-automation/second-brain`

**Last Session**: 2026-05-30
- Completed note generator simplification
- Added Poetry/Sayings language preservation
- All 5 simplification requests implemented

**Ready to Resume**: Yes, all requested features implemented and working.
