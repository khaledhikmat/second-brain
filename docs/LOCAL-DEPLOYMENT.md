# Local Deployment Guide

Complete guide for running Second Brain locally while connecting to Railway PostgreSQL database.

---

## Architecture

This setup runs services on your local machine while using Railway's PostgreSQL database:

```
┌─────────────────────────────────┐
│   Local Machine                 │
│                                 │
│  ┌─────────────────────┐       │      ┌──────────────────────┐
│  │  Telegram Bot       │       │      │  Railway PostgreSQL  │
│  │  (localhost)        │───────┼─────▶│  (Cloud Database)    │
│  └─────────────────────┘       │      └──────────────────────┘
│                                 │
│  ┌─────────────────────┐       │
│  │  Batch Processor    │       │
│  │  (localhost)        │───────┼──────┘
│  └─────────────────────┘       │
│                                 │
└─────────────────────────────────┘
         │
         └────── Git Sync ──────▶ GitHub Vault
                                         │
                                         ▼
                                  Obsidian (Local)
```

**Why this setup?**
- Test with production database (same data as Railway deployment)
- Faster development (no deploy wait time)
- Full debugging capabilities (local logs, breakpoints)
- Shared database state across local and Railway

---

## Prerequisites

### 1. Railway PostgreSQL Database

You need a Railway PostgreSQL database already set up. If you haven't created one:

1. Go to https://railway.app
2. Create a new project or use existing
3. Click "New" → "Database" → "Add PostgreSQL"
4. Copy the `DATABASE_URL` from Railway dashboard

### 2. Get Your Credentials

**Telegram Bot:**
1. Open Telegram, search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Save your bot token (looks like: `123456789:ABCdef...`)

**Your Telegram User ID:**
1. Search for `@userinfobot` on Telegram
2. Send `/start`
3. Save your user ID (a number like `123456789`)

**Claude API Key:**
1. Go to https://console.anthropic.com/
2. Create/get your API key (starts with `sk-ant-`)

**OpenAI API Key (Optional, for YouTube):**
1. Go to https://platform.openai.com
2. Create/get your API key (starts with `sk-`)

**GitHub Personal Access Token (Optional, for Git sync):**
1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Scope: Select only `repo`
4. Copy token (starts with `ghp_`)

---

## Setup

### Step 1: Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# macOS ONLY: Fix SSL certificates (required for YouTube transcription)
# Find your Python version and run:
/Applications/Python\ 3.11/Install\ Certificates.command
# Or for other versions:
# /Applications/Python\ 3.12/Install\ Certificates.command
```

### Step 2: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your credentials
nano .env  # or use VS Code/your editor
```

**Add your values:**

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_USER_ID=your_numeric_user_id

# AI API Keys
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx  # Optional, for YouTube transcription

# Database (Railway PostgreSQL)
DATABASE_ENABLED=true
DATABASE_URL=postgresql+asyncpg://postgres:xxxxx@xxxx.proxy.rlwy.net:xxxxx/railway

# Vault Path (local)
VAULT_PATH=./vault

# Git Sync (Optional)
GIT_AUTO_COMMIT=false  # Set to true if you want auto-commit locally
GIT_AUTO_PUSH=false    # Usually false for local development
GIT_REMOTE_NAME=origin
GIT_BRANCH_NAME=main
# VAULT_REPO_URL=https://ghp_xxxxx@github.com/username/obsidian-vault.git

# Categories
PREDEFINED_CATEGORIES=Sayings,Poetry,Jots,Islam,History,Strategy,Definitions,Path
LANGUAGE_FOLDERS={"ar": "arabic", "en": "english"}

# YouTube Transcription (Optional)
YOUTUBE_ENABLED=true
YOUTUBE_TRANSCRIPT_LANGUAGES=en,ar

# Batch Mode
BATCH_MODE=true  # true for queue-based processing, false for immediate
BATCH_INTERVAL_MINUTES=3  # For continuous batch processor

# HTTP API (Optional)
HTTP_API_ENABLED=true
HTTP_API_KEY=your_secret_api_key_here
```

**Getting Railway DATABASE_URL:**

```bash
# Option 1: Railway CLI
railway login
railway link  # Select your project
railway variables | grep DATABASE_URL

# Option 2: Railway Dashboard
# Go to Postgres service → Connect → Copy DATABASE_URL
```

**Important:** Change `postgresql://` to `postgresql+asyncpg://` for async support.

### Step 3: Validate Configuration

```bash
python3 -m src.config
```

You should see: `Configuration is valid!`

### Step 4: Verify Database Connection

```bash
# Test database connection
python3 -c "
import asyncio
from src.db.database import DatabaseManager

async def test():
    db = DatabaseManager('YOUR_DATABASE_URL_HERE')
    if await db.initialize():
        print('✅ Connected to Railway PostgreSQL')
    else:
        print('❌ Connection failed')
    await db.close()

asyncio.run(test())
"
```

**Or using Railway CLI:**

```bash
railway run psql -c "SELECT version();"
```

---

## Running Services

### Option 1: Immediate Mode (No Queue)

Best for: Testing, quick iterations, text-only messages

```bash
# Ensure BATCH_MODE=false in .env
python3 -m src.main
```

**Expected output:**
```
Database initialized successfully: postgresql+asyncpg://...
Vault is ready
Starting Telegram bot polling...
Bot is running in immediate mode
```

**Test it:**
1. Open Telegram
2. Message your bot: `Poetry -> The night is dark and full of stars`
3. Bot processes immediately and creates note

### Option 2: Batch Mode (Recommended)

Best for: YouTube videos, development workflow, testing queue system

#### Start Bot (Queues Messages)

```bash
# Ensure BATCH_MODE=true in .env
python3 -m src.main
```

**Expected output:**
```
Database initialized successfully: postgresql+asyncpg://...
Vault is ready
Batch mode enabled - messages will be queued
Starting Telegram bot polling...
Bot is running in batch mode
```

#### Start Batch Processor (Processes Queue)

**Terminal 2:**

```bash
# Process once and exit
python3 -m src.batch_processor --once

# Or run continuously (checks every 3 minutes)
python3 -m src.batch_processor
```

**Expected output:**
```
Database initialized successfully
Worker laptop-1234-a3f2b claimed 2 messages (PostgreSQL)
Worker laptop-1234-a3f2b processing 2 claimed messages...
Created note: vault/english/poetry/...
Batch processing complete. Success: 2, Failed: 0
```

---

## Testing

### Test 1: Basic Message Processing

**Send via Telegram:**
```
Jots -> Testing local deployment with Railway PostgreSQL
```

**Batch mode:** Bot responds "✓ Message queued"
**Immediate mode:** Bot processes and creates note instantly

### Test 2: YouTube Processing

**Send via Telegram:**
```
History -> https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Wait for batch processor to run (or trigger manually).

### Test 3: Arabic Content

**Send via Telegram:**
```
Islam -> الصلاة عمود الدين
```

Should create note in `vault/arabic/islam/`

### Test 4: HTTP API (if enabled)

```bash
# Health check
curl http://localhost:8080/health

# Create note
curl -X POST http://localhost:8080/api/v1/notes \
  -H "X-API-Key: your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"message": "Sayings -> Testing HTTP API", "category": "Sayings"}'

# Process YouTube video
curl -X POST http://localhost:8080/api/v1/youtube \
  -H "X-API-Key: your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "category": "History"}'
```

---

## Database Operations

### Connect to Railway PostgreSQL

**Using Railway CLI:**
```bash
railway login
railway link  # Select your project
railway run psql
```

**Using psql directly:**
```bash
psql "postgresql://postgres:xxxxx@xxxx.proxy.rlwy.net:xxxxx/railway"
```

### Common Queries

**Check queue status:**
```sql
SELECT processing_status, COUNT(*)
FROM messages
GROUP BY processing_status;
```

**View recent messages:**
```sql
SELECT id, timestamp, category, language, processing_status
FROM messages
ORDER BY timestamp DESC
LIMIT 10;
```

**View queued messages:**
```sql
SELECT id, timestamp, LEFT(raw_text, 50) as preview, processing_status
FROM messages
WHERE processing_status = 'queued'
ORDER BY timestamp ASC;
```

**Check worker activity:**
```sql
SELECT worker_id, COUNT(*) as processing_count
FROM messages
WHERE processing_status = 'processing'
GROUP BY worker_id;
```

**View failed messages:**
```sql
SELECT id, timestamp, error_message, LEFT(raw_text, 50)
FROM messages
WHERE processing_status = 'failed'
ORDER BY timestamp DESC;
```

**Reset stuck messages:**
```sql
UPDATE messages
SET processing_status = 'queued',
    worker_id = NULL
WHERE processing_status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

**Clean old completed messages:**
```sql
DELETE FROM messages
WHERE processing_status = 'completed'
  AND created_at < NOW() - INTERVAL '30 days';
```

### Using Python for Queries

```bash
# Quick query
python3 -c "
import asyncio
from src.db.database import get_db_manager
from sqlalchemy import text

async def query():
    db_manager = get_db_manager()
    async with db_manager.get_session() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM messages'))
        count = result.scalar()
        print(f'Total messages: {count}')

asyncio.run(query())
"
```

---

## Monitoring

### View Logs

```bash
# Main bot logs
tail -f logs/app.log

# Batch processor logs
tail -f logs/batch_processor.log

# Both logs together
tail -f logs/*.log
```

### Check Database Metrics (Railway Dashboard)

1. Go to Railway dashboard
2. Click on Postgres service
3. View Metrics:
   - Connection count (should be low, 1-3)
   - Database size
   - Query performance

### Monitor Queue in Real-Time

```bash
# Watch queue status (updates every 2 seconds)
watch -n 2 "railway run psql -c \"SELECT processing_status, COUNT(*) FROM messages GROUP BY processing_status;\""
```

---

## Development Workflow

### Typical Development Session

**Terminal 1: Bot (queuing messages)**
```bash
source .venv/bin/activate
export BATCH_MODE=true
python3 -m src.main
```

**Terminal 2: Batch Processor (processing in background)**
```bash
source .venv/bin/activate
python3 -m src.batch_processor
```

**Terminal 3: Logs**
```bash
tail -f logs/*.log
```

**Terminal 4: Database queries**
```bash
railway run psql
```

### Testing Code Changes

1. **Make changes** to code
2. **Stop bot** (Ctrl+C in Terminal 1)
3. **Restart bot**:
   ```bash
   python3 -m src.main
   ```
4. **Test** via Telegram
5. **Check logs** for errors
6. **Query database** to verify behavior

### Testing Batch Processor Changes

1. **Make changes** to `src/batch_processor.py`
2. **Stop batch processor** (Ctrl+C in Terminal 2)
3. **Queue test messages** via Telegram
4. **Run batch processor once**:
   ```bash
   python3 -m src.batch_processor --once
   ```
5. **Check logs** and database

---

## Troubleshooting

### Database Connection Errors

**Error:** `connection refused` or `could not connect`

**Check:**
1. DATABASE_URL is correct in `.env`
2. Railway PostgreSQL service is running (check Railway dashboard)
3. Your IP is not blocked (Railway allows all IPs by default)

**Fix:**
```bash
# Test connection
railway run psql -c "SELECT 1;"

# Verify DATABASE_URL format
grep DATABASE_URL .env
# Should be: postgresql+asyncpg://postgres:xxxxx@xxxx.proxy.rlwy.net:xxxxx/railway
```

### Messages Stuck in Queue

**Symptom:** Messages queued but never processed

**Check:**
```sql
SELECT id, processing_status, worker_id, updated_at
FROM messages
WHERE processing_status = 'processing'
ORDER BY updated_at ASC;
```

**Fix:**
```sql
-- Reset stuck messages
UPDATE messages
SET processing_status = 'queued',
    worker_id = NULL
WHERE processing_status = 'processing';
```

Then restart batch processor.

### Bot Not Responding

**Check:**
1. Bot is running (`python3 -m src.main` active)
2. TELEGRAM_ALLOWED_USER_ID matches your actual ID
3. No errors in logs

**Fix:**
```bash
# Get your user ID from @userinfobot
# Update .env
TELEGRAM_ALLOWED_USER_ID=123456789

# Restart bot
Ctrl+C
python3 -m src.main
```

### YouTube Transcription Fails

**Common Issues:**

**"No module named 'yt_dlp'":**
```bash
pip install --upgrade yt-dlp
```

**"ffmpeg not found":**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

**"SSL certificate error" (macOS):**
```bash
/Applications/Python\ 3.11/Install\ Certificates.command
```

### Notes Not Created

**Check:**
1. Vault directory exists (`ls vault/`)
2. Permissions allow writing
3. Claude API key is valid
4. Check logs for errors

**Fix:**
```bash
# Create vault structure manually
mkdir -p vault/arabic/{sayings,poetry,jots,islam,history,strategy,definitions,path}
mkdir -p vault/english/{sayings,poetry,jots,islam,history,strategy,definitions,path}

# Check Claude API key
python3 -c "
import os
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
print('✅ Claude API key is valid')
"
```

### Worker ID Conflicts

**Symptom:** Multiple batch processors claim same messages

**This shouldn't happen** - each worker gets unique ID based on hostname-pid-uuid.

**But if it does:**
```sql
-- View workers
SELECT worker_id, COUNT(*)
FROM messages
WHERE worker_id IS NOT NULL
GROUP BY worker_id;

-- Clear worker_id from old sessions
UPDATE messages
SET worker_id = NULL
WHERE processing_status = 'queued';
```

---

## Categories

Your notes are organized into these categories:

| Category | Use For |
|----------|---------|
| **Sayings** | Quotes, proverbs, wisdom |
| **Poetry** | Poems, verses, lyrical content |
| **Jots** | Quick notes, random thoughts (default) |
| **Kb** | Knowledge, teachings |
| **History** | Historical facts, events |
| **Strategy** | Strategic thinking, planning |
| **Definitions** | Concepts, explanations |
| **Path** | Path forward, guidance |

**Usage:**
```
Poetry -> Roses are red, violets are blue
Islam -> The five pillars of Islam are...
History -> World War II ended in 1945
```

**Default (no category specified):**
```
Just a random thought
```
→ Goes to `Jots`

---

## Language Detection

The system automatically detects:

- **Arabic** → `vault/arabic/category/`
- **English** → `vault/english/category/`

**Examples:**

```
Islam -> الصلاة عمود الدين
```
→ `vault/arabic/islam/note.md`

```
History -> World War II ended in 1945
```
→ `vault/english/history/note.md`

---

## What Gets Created

Each note includes:

### YAML Frontmatter
```yaml
id: "20260617123456"
title: "Note Title"
language: ar/en
category: Poetry
source: telegram  # or http
created: "2026-06-17T12:34:56"
youtube_url: "https://youtube.com/..."  # if YouTube video
```

### Content Sections
- **Summary**: 1-2 sentence summary
- **Content**: AI-processed content with wikilinks
- **Key Concepts**: Top concepts extracted
- **Entities**: People, places, terms mentioned
- **Original Text**: Your original message (preserved)

**Special handling for Poetry/Sayings:**
- No title heading in body
- Only "People" and "Original Text" sections
- Minimal processing to preserve original

---

## Git Sync (Optional)

If you want notes auto-committed to GitHub:

1. **Create GitHub repository** for vault (private recommended)

2. **Generate GitHub token:**
   - https://github.com/settings/tokens
   - Scope: `repo` only
   - Copy token

3. **Update .env:**
   ```env
   GIT_AUTO_COMMIT=true
   GIT_AUTO_PUSH=true
   VAULT_REPO_URL=https://ghp_xxxxx@github.com/username/obsidian-vault.git
   ```

4. **Initialize vault git:**
   ```bash
   cd vault
   git init
   git remote add origin https://ghp_xxxxx@github.com/username/obsidian-vault.git
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

5. **Restart bot** - notes will auto-commit/push

---

## Connect Obsidian

### Option 1: Direct Vault Access

Point Obsidian directly to `vault/` folder:

1. Open Obsidian
2. Open folder as vault → Browse to `second-brain/vault`
3. Notes appear in Obsidian as they're created

### Option 2: Git Sync (if enabled)

Clone vault to separate location for Obsidian:

1. **Install Obsidian Git plugin:**
   - Settings → Community Plugins → Browse
   - Search "Obsidian Git"
   - Install and Enable

2. **Clone vault:**
   ```bash
   cd ~/Documents
   git clone https://ghp_xxxxx@github.com/username/obsidian-vault.git MyVault
   ```

3. **Open in Obsidian:**
   - Open folder as vault → `~/Documents/MyVault`

4. **Configure auto-pull:**
   - Settings → Obsidian Git
   - Enable "Pull updates on startup"
   - Pull interval: 3 minutes

---

## Testing Checklist

**Basic Functionality:**
- [ ] Bot starts without errors
- [ ] Can connect to Railway PostgreSQL
- [ ] Send message with category: `Poetry -> test`
- [ ] Send message without category: `test`
- [ ] Send Arabic message: `Islam -> الصلاة`
- [ ] Check vault folders for new notes
- [ ] Verify notes have proper frontmatter

**Batch Mode:**
- [ ] Messages queue in database
- [ ] Batch processor claims messages
- [ ] Notes created from queued messages
- [ ] Worker ID tracked correctly
- [ ] Failed messages have error_message

**YouTube (if enabled):**
- [ ] Send YouTube URL via Telegram
- [ ] Transcript extracted successfully
- [ ] Note created from transcript
- [ ] URL stored in processed_data

**HTTP API (if enabled):**
- [ ] Health endpoint works: `/health`
- [ ] Create note via API: `POST /api/v1/notes`
- [ ] API key authentication works
- [ ] YouTube processing via API works

---

## Commands Reference

```bash
# Start bot (immediate mode)
BATCH_MODE=false python3 -m src.main

# Start bot (batch mode)
BATCH_MODE=true python3 -m src.main

# Process queue once
python3 -m src.batch_processor --once

# Process queue continuously
python3 -m src.batch_processor

# Check configuration
python3 -m src.config

# View logs
tail -f logs/app.log
tail -f logs/batch_processor.log

# Connect to database
railway run psql

# Activate venv
source .venv/bin/activate
```

---

## File Locations

- **Notes**: `vault/arabic/` and `vault/english/`
- **Logs**: `logs/app.log`, `logs/batch_processor.log`
- **Config**: `.env`
- **Database**: Railway PostgreSQL (remote)
- **Virtual Environment**: `.venv/`

---

## Next Steps

Once local deployment works:

1. **Deploy to Railway** - See [RAILWAY-DEPLOYMENT.md](RAILWAY-DEPLOYMENT.md)
2. **Set up Obsidian** - View your notes in Obsidian
3. **Configure Git sync** - Auto-commit notes to GitHub
4. **Create templates** - Set up Obsidian templates for categories

---

**You're ready to develop and test locally with Railway PostgreSQL!** 🚀
