# Railway Deployment Guide - Dual Service Architecture

Complete guide to deploy Second Brain to Railway using a production-ready dual service architecture with shared PostgreSQL database.

---

## Architecture Overview

This deployment creates three Railway services in a single project:

```
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│  Telegram Bot       │      │  Batch Processor    │      │  PostgreSQL DB      │
│  (Always Running)   │─────▶│  (Cron: Every 3min) │◄────▶│  (Shared Queue)     │
│  Queues messages    │      │  Processes queue    │      │  Messages & Notes   │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
         │                            │
         └────────────────────────────┴─────── Git Sync ──────────▶ GitHub Vault
                                                                            │
                                                                            ▼
                                                                    Obsidian (Local)
```

### Why Dual Service?

**Benefits:**
- Bot always responsive (no blocking during YouTube processing)
- Queue-based processing with automatic retries
- Batch processor runs on cron schedule (cost-effective)
- Shared PostgreSQL database prevents race conditions
- Can scale bot and processor independently

**How it works:**
1. User sends message to Telegram bot
2. Bot saves message to database with status `queued`
3. Bot responds immediately: "Message queued"
4. Batch processor runs every 3 minutes (configurable)
5. Processor claims queued messages, processes them
6. Notes pushed to GitHub vault
7. Obsidian syncs from GitHub

---

## Prerequisites

Before starting, gather these:

### 1. Railway Account
- Sign up at https://railway.app
- Free tier includes $5 credit/month
- Credit card required (won't be charged on free tier)

### 2. GitHub Repositories

**Vault Repository (Private):**
- Create at https://github.com/new
- Name: `obsidian-vault` (or your preference)
- **Must be Private**
- Do NOT initialize with README

**Bot Code Repository:**
- Your Second Brain code must be in GitHub
- Can be private or public

### 3. GitHub Personal Access Token

For Railway to push notes to your vault:

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `Railway Second Brain`
4. Scope: Select **only** `repo` (full control of private repositories)
5. Generate and **copy the token** (you won't see it again)
6. Format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 4. API Keys

**Required:**
- Telegram Bot Token (from @BotFather)
- Telegram User ID (from @userinfobot)
- Anthropic API Key (from https://console.anthropic.com)

**Optional (for YouTube):**
- OpenAI API Key (from https://platform.openai.com)

---

## Deployment Steps

### Step 1: Create Railway Project

1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Authorize Railway to access your GitHub
4. Select your `second-brain` repository
5. Railway creates a new project

### Step 2: Add PostgreSQL Database

**In the same Railway project:**

1. Click "New" → "Database" → "Add PostgreSQL"
2. Railway provisions a database (takes ~30 seconds)
3. Note: Railway automatically creates `DATABASE_URL` variable

**Important:** Don't configure anything yet. We'll reference this in the services.

### Step 3: Configure Telegram Bot Service

This is the service Railway created automatically from your repo.

#### 3.1 Rename Service (Optional)

1. Click the service → Settings → scroll to "Service Name"
2. Rename to: `telegram-bot`

#### 3.2 Add Environment Variables

Click "Variables" tab and add:

**Core Configuration:**
```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_USER_ID=your_numeric_user_id
ANTHROPIC_API_KEY=sk-ant-xxxxx
BATCH_MODE=true
```

**Database (Reference Railway PostgreSQL):**
```env
DATABASE_ENABLED=true
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**Vault & Git Sync:**
```env
VAULT_PATH=/app/vault
GIT_AUTO_COMMIT=true
GIT_AUTO_PUSH=true
GIT_REMOTE_NAME=origin
GIT_BRANCH_NAME=main
VAULT_REPO_URL=https://YOUR_GITHUB_TOKEN@github.com/YOUR_USERNAME/obsidian-vault.git
```

**Categories:**
```env
PREDEFINED_CATEGORIES=Sayings,Poetry,Jots,Islam,History,Strategy,Definitions,Path
LANGUAGE_FOLDERS={"ar": "arabic", "en": "english"}
```

**YouTube (Optional but Recommended):**
```env
YOUTUBE_ENABLED=true
YOUTUBE_TRANSCRIPT_LANGUAGES=en,ar
OPENAI_API_KEY=sk-xxxxx
```

**Replace these values:**
- `YOUR_GITHUB_TOKEN` - Token from Prerequisites Step 3
- `YOUR_USERNAME` - Your GitHub username
- `obsidian-vault` - Your vault repository name

**Example VAULT_REPO_URL:**
```env
VAULT_REPO_URL=https://ghp_abc123xyz789@github.com/johndoe/obsidian-vault.git
```

#### 3.3 Deploy Bot Service

Railway automatically deploys when you add variables. Monitor the logs:

```
Settings → Deployments → View Logs
```

**Expected output:**
```
Database initialized successfully: postgresql+asyncpg://...
Vault is ready
Batch mode enabled - messages will be queued
Starting Telegram bot polling...
Bot is running in batch mode
```

### Step 4: Add Batch Processor Service

**In the same Railway project:**

#### 4.1 Create New Service

1. Click "New" → "Empty Service"
2. Name it: `batch-processor`
3. Settings → Source → Connect to GitHub
4. Select same repository as telegram-bot
5. Select same branch (usually `main`)

#### 4.2 Copy Variables from Bot Service

1. Go to `telegram-bot` service → Variables
2. Click "Copy Variables" button (or manually copy all)
3. Go to `batch-processor` service → Variables
4. Paste all variables

**Important:** All variables should be identical between both services.

#### 4.3 Configure Start Command

In `batch-processor` service:

1. Settings → Deploy
2. Custom Start Command:
   ```bash
   python -m src.batch_processor --once
   ```

This makes it run once and exit (perfect for cron).

#### 4.4 Configure Cron Schedule

In `batch-processor` service:

1. Settings → Cron Schedule
2. Add cron expression:
   ```
   */3 * * * *
   ```

**This runs every 3 minutes.** Other options:
- Every 5 minutes: `*/5 * * * *`
- Every 10 minutes: `*/10 * * * *`
- Every 30 minutes: `*/30 * * * *`

#### 4.5 Deploy Batch Processor

Click "Deploy" and monitor logs:

```
Settings → Deployments → View Logs
```

**Expected output (every 3 minutes):**
```
Database initialized successfully
Worker {worker-id} claimed 2 messages (PostgreSQL)
Worker {worker-id} processing 2 claimed messages...
Created note: vault/arabic/strategy/...
Batch processing complete. Success: 2, Failed: 0
```

### Step 5: Verify Deployment

#### 5.1 Check All Services Running

In Railway dashboard, you should see:

```
✓ telegram-bot       (Active - Always Running)
✓ batch-processor    (Scheduled - Runs every 3 min)
✓ Postgres           (Active)
```

#### 5.2 Test Message Flow

1. Open Telegram and message your bot:
   ```
   Jots -> Testing Railway deployment with dual service architecture
   ```

2. Bot should respond immediately:
   ```
   ✓ Message queued for processing
   ```

3. Wait up to 3 minutes (next cron run)

4. Check batch processor logs for:
   ```
   Processing message 1: Testing Railway deployment...
   Created note: vault/english/jots/20260614_xxxxx_testing_railway_deployment.md
   ```

#### 5.3 Verify GitHub Vault

1. Go to `https://github.com/YOUR_USERNAME/obsidian-vault`
2. You should see:
   - New folders: `arabic/`, `english/`
   - Subfolders: `jots/`, `poetry/`, `strategy/`, etc.
   - New note file with timestamp
   - Git commit: "Add note: Testing Railway deployment..."

#### 5.4 Test YouTube Processing (if enabled)

Send a YouTube URL:
```
History -> https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Wait for next cron run and check logs for transcription.

#### 5.5 Check Database

Connect to PostgreSQL to inspect queue:

```bash
# Install Railway CLI: https://docs.railway.app/develop/cli
railway login
railway link  # Select your project
railway run psql

# Then in psql:
SELECT id, source, category, language, processing_status
FROM messages
ORDER BY id DESC
LIMIT 10;
```

**Expected:**
```
 id | source   | category | language | processing_status
----+----------+----------+----------+------------------
  1 | telegram | Jots     | en       | completed
```

---

## Connect Obsidian

Now sync your GitHub vault to Obsidian locally.

### Install Obsidian Git Plugin

1. Open Obsidian
2. Settings → Community Plugins → Browse
3. Search "Obsidian Git"
4. Install and Enable

### Clone Vault to Obsidian

**Option A: Create New Vault**

1. Create a new vault in Obsidian
2. Note the vault location (e.g., `/Users/you/Documents/ObsidianVault`)
3. Open terminal in that location:
   ```bash
   cd /Users/you/Documents/ObsidianVault
   rm -rf .obsidian  # Remove Obsidian's default folder
   git clone https://YOUR_GITHUB_TOKEN@github.com/YOUR_USERNAME/obsidian-vault.git .
   ```
4. Restart Obsidian and open this vault

**Option B: Use Existing Vault**

1. Open your vault folder in terminal
2. Initialize Git and pull:
   ```bash
   cd /path/to/your/vault
   git init
   git remote add origin https://YOUR_GITHUB_TOKEN@github.com/YOUR_USERNAME/obsidian-vault.git
   git pull origin main
   ```

### Configure Auto-Sync

In Obsidian → Settings → Obsidian Git:

```
✓ Enable automatic pull on startup
✓ Pull updates on startup
  Pull interval: 3 minutes (match your cron schedule)
✓ Disable push (Railway pushes, Obsidian only pulls)
```

**Test it:**
- Send message to Telegram bot
- Wait 3 minutes
- Obsidian should auto-pull and show new note

---

## Monitoring and Maintenance

### View Logs

**Telegram Bot Logs:**
```
Railway Dashboard → telegram-bot → Deployments → View Logs
```

Filter by level:
- Errors: Look for `ERROR` or `Failed`
- Activity: Look for `INFO`

**Batch Processor Logs:**
```
Railway Dashboard → batch-processor → Deployments → View Logs
```

Should show activity every 3 minutes.

**PostgreSQL Metrics:**
```
Railway Dashboard → Postgres → Metrics
```

Monitor:
- Database size (should grow slowly)
- Connection count (should be low, <5)
- Query performance

### Check Queue Status

Using Railway CLI:

```bash
railway run psql -c "
  SELECT processing_status, COUNT(*)
  FROM messages
  GROUP BY processing_status;
"
```

**Healthy output:**
```
 processing_status | count
-------------------+-------
 completed         |    45
 queued            |     2
```

**Unhealthy (stuck messages):**
```
 processing_status | count
-------------------+-------
 processing        |    10  ← Bad! Stuck messages
 failed            |     5  ← Check error_message
```

**Fix stuck messages:**
```bash
railway run psql -c "
  UPDATE messages
  SET processing_status = 'queued'
  WHERE processing_status = 'processing';
"
```

### Restart Services

**Restart Bot:**
```
Railway Dashboard → telegram-bot → Settings → Restart
```

**Restart Batch Processor (force run now):**
```
Railway Dashboard → batch-processor → Settings → Restart
```

**Restart Database:**
```
Railway Dashboard → Postgres → Settings → Restart
```

### Update Environment Variables

1. Go to service → Variables
2. Update any variable
3. Click "Update Variables"
4. Service automatically restarts

**Note:** If you update variables in one service, update in both (bot and batch processor should have identical variables).

### Deploy Code Changes

1. Make changes locally
2. Test: `python -m src.main` (bot) and `python -m src.batch_processor --once` (batch)
3. Commit and push to GitHub:
   ```bash
   git add .
   git commit -m "Fix: Updated batch processor commit timing"
   git push
   ```
4. Railway automatically redeploys both services!

### View Git Commits

Monitor notes being created:

```
https://github.com/YOUR_USERNAME/obsidian-vault/commits/main
```

Each note creates a commit like:
```
Add note: مصير العالم الإسلامي والوعي الاستراتيجي للنخب
```

---

## Troubleshooting

### Issue: Bot not responding

**Check:**
1. `telegram-bot` service is running (Railway dashboard)
2. Environment variables are set correctly
3. `TELEGRAM_BOT_TOKEN` is valid

**View logs:**
```
Railway Dashboard → telegram-bot → View Logs
```

**Look for:**
- `Unauthorized` - Invalid bot token
- `Database is not available` - PostgreSQL connection issue
- `Failed to clone vault repository` - Git sync issue

### Issue: Messages stuck in "queued"

**Symptoms:** Messages queued but never processed

**Check:**
1. Batch processor cron is running:
   ```
   Railway Dashboard → batch-processor → Settings → Cron Schedule
   ```
2. Check last deployment time (should run every 3 min)
3. View batch processor logs for errors

**Common causes:**
- Cron not configured
- Start command incorrect (should be `python -m src.batch_processor --once`)
- Database connection error
- Worker claiming messages but process crashing

**Fix:**
```bash
# Check queue
railway run psql -c "SELECT id, processing_status, error_message FROM messages WHERE processing_status != 'completed' ORDER BY id DESC LIMIT 10;"

# Reset stuck messages
railway run psql -c "UPDATE messages SET processing_status = 'queued', worker_id = NULL WHERE processing_status = 'processing';"
```

### Issue: Duplicate processing

**Symptoms:** Same message processed twice

**Cause:** Both services are processing messages (not in batch mode)

**Fix:**
- Ensure `BATCH_MODE=true` in **both** services
- Restart both services
- Check logs: bot should say "batch mode enabled"

### Issue: Notes not in GitHub

**Check:**
1. `VAULT_REPO_URL` format is correct
2. GitHub token has `repo` scope
3. Repository exists and is accessible
4. `GIT_AUTO_COMMIT=true` and `GIT_AUTO_PUSH=true`

**Test manually:**
```bash
# In Railway CLI
railway shell

# Inside container
cd /app/vault
git status
git remote -v  # Should show your GitHub repo
git push  # Test push manually
```

**Common errors:**
- `Authentication failed` - Invalid GitHub token
- `Repository not found` - Wrong URL or private repo without token
- `Permission denied` - Token lacks `repo` scope

**Fix:**
1. Regenerate GitHub token: https://github.com/settings/tokens
2. Update `VAULT_REPO_URL` in both services
3. Restart services

### Issue: Obsidian not syncing

**Check:**
1. Obsidian Git plugin is installed and enabled
2. Git remote is configured:
   ```bash
   cd /path/to/vault
   git remote -v
   ```
3. Can pull manually:
   ```bash
   git pull origin main
   ```

**Fix:**
- Obsidian → Settings → Obsidian Git → Enable auto-pull
- Set pull interval to 3 minutes
- Restart Obsidian

### Issue: PostgreSQL connection errors

**Symptoms:**
```
Failed to connect to database
asyncpg.exceptions.InvalidPasswordError
```

**Check:**
1. PostgreSQL service is running
2. `DATABASE_URL` variable references correct service:
   ```env
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```
3. Both services have same database reference

**Fix:**
1. Go to Postgres service → Connect → Copy `DATABASE_URL`
2. Update in both services (or use variable reference)
3. Restart services

### Issue: YouTube transcription fails

**Check:**
1. `YOUTUBE_ENABLED=true`
2. `OPENAI_API_KEY` is set (if using Whisper API)
3. Railway has enough memory (check Metrics)

**Common errors:**
- `No module named 'yt_dlp'` - Dependency issue, redeploy
- `ffmpeg not found` - Dockerfile missing ffmpeg (should have it)
- `OpenAI API error` - Invalid API key or rate limit

**View detailed logs:**
```
Railway Dashboard → batch-processor → View Logs → Filter: "youtube"
```

### Issue: Out of memory

**Symptoms:**
- Service crashes during processing
- Logs show `OOMKilled` or `Killed`

**Cause:** YouTube processing or large transcripts

**Solutions:**
1. **Use OpenAI Whisper API** (recommended):
   ```env
   OPENAI_API_KEY=sk-xxxxx
   ```
2. **Upgrade Railway plan** (more RAM)
3. **Optimize batch size:**
   ```env
   BATCH_PROCESS_LIMIT=1  # Process 1 message at a time
   ```

---

## Cost Analysis

### Monthly Costs (Estimated)

**Railway Services:**
| Service | Type | Cost |
|---------|------|------|
| Telegram Bot | Always-on (512MB RAM) | $5-7 |
| Batch Processor | Cron (every 3 min, ~30s runtime) | $0.50-1 |
| PostgreSQL | Database (1GB storage) | $5 |
| **Total Railway** | | **$10.50-13** |

**API Costs:**
| API | Usage | Cost |
|-----|-------|------|
| Anthropic Claude | ~$0.01-0.05 per note | $1-5/month (for 100 notes) |
| OpenAI Whisper | ~$0.006 per minute | $1-3/month (for videos) |
| **Total APIs** | | **$2-8** |

**Total Monthly Cost:** ~$12-21

### Cost Optimization Tips

1. **Increase cron interval** to reduce batch processor runs:
   ```
   */5 * * * *  # Every 5 min instead of 3
   ```
   Saves: ~$0.20/month

2. **Use Railway free tier** ($5 credit/month):
   - Disable batch processor (use single service)
   - Or reduce cron frequency
   - Or pause services when not in use

3. **Optimize YouTube processing:**
   - Use Whisper API (faster = less Railway CPU time)
   - Disable YouTube if not needed
   - Set `YOUTUBE_ENABLED=false`

4. **Database optimization:**
   - Regularly clean old messages:
     ```sql
     DELETE FROM messages WHERE created_at < NOW() - INTERVAL '30 days';
     ```

---

## Security Best Practices

### 1. Never Commit Secrets

Ensure `.env` is in `.gitignore`:

```bash
cd /Users/khaled/github/personal-automation/second-brain
cat .gitignore | grep env  # Should show .env
git ls-files | grep env     # Should be empty
```

### 2. Rotate Tokens Every 3-6 Months

**GitHub Token:**
1. Generate new token: https://github.com/settings/tokens
2. Update `VAULT_REPO_URL` in Railway
3. Delete old token from GitHub

**API Keys:**
- Anthropic: https://console.anthropic.com/settings/keys
- OpenAI: https://platform.openai.com/api-keys

### 3. Use Minimal Token Scopes

GitHub token should **only** have:
- ✓ `repo` (for private repository access)
- ✗ Everything else unchecked

### 4. Keep Repositories Private

Both your bot code and vault should be **Private** on GitHub.

### 5. Monitor Database Access

Regularly check PostgreSQL logs for unauthorized access:

```
Railway Dashboard → Postgres → Metrics → Connection count
```

Should be low (2-5 connections from your services).

---

## Backup Strategy

### Automatic Backups (Built-in)

✓ **Every note is committed to GitHub** - Full version history
✓ **Railway backs up PostgreSQL** - Automatic daily snapshots
✓ **Database tracks all messages** - Can replay if needed

### Manual Backup (Monthly Recommended)

**Backup vault:**
```bash
git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/obsidian-vault.git backup-$(date +%Y%m)
# Creates: backup-202606/
```

**Backup database:**
```bash
railway run pg_dump > backup-$(date +%Y%m%d).sql
```

### Restore from Backup

**Restore vault to specific commit:**
```bash
cd vault
git log  # Find commit hash
git checkout COMMIT_HASH
```

**Restore database:**
```bash
railway run psql < backup-20260614.sql
```

---

## Advanced Configuration

### Custom Commit Messages

Edit `.env`:
```env
GIT_COMMIT_MESSAGE_TEMPLATE=Add note: {title}
```

Available placeholders:
- `{title}` - Note title
- `{category}` - Category name
- `{language}` - Detected language

### Change Processing Frequency

**Faster (every 1 minute):**
```
*/1 * * * *
```

**Slower (every hour):**
```
0 * * * *
```

**Specific times (every day at 9 AM and 5 PM):**
```
0 9,17 * * *
```

### Enable HTTP API (Optional)

Add to both services:
```env
HTTP_API_ENABLED=true
HTTP_API_KEY=your_secure_random_key_here
```

Railway will expose port 8080 automatically.

**Test:**
```bash
curl https://your-app.up.railway.app/health
curl -X POST https://your-app.up.railway.app/api/v1/notes \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test from API"}'
```

### Multiple Workers (Scale Batch Processor)

For high volume, add more batch processor instances:

1. Duplicate `batch-processor` service
2. Name it `batch-processor-2`
3. Same environment variables
4. Same cron schedule

Both will safely process different messages (PostgreSQL row locking prevents conflicts).

---

## Purging Vault Notes

If you need to delete all notes and start fresh (while keeping the folder structure):

### Step 1: Stop Railway Services

Prevent new notes from being created during the purge:

```
Railway Dashboard → telegram-bot → Settings → Stop
Railway Dashboard → batch-processor → Settings → Stop (or pause cron)
```

**Wait 30 seconds** to ensure all processes are stopped.

### Step 2: Delete Notes from GitHub Vault

**Option A: Local Clone (Recommended)**

```bash
cd ~/Desktop  # or any temp location
git clone https://YOUR_GITHUB_TOKEN@github.com/YOUR_USERNAME/obsidian-vault.git temp-vault
cd temp-vault

# Keep folder structure, delete only .md files
find arabic english -name "*.md" -delete

# Verify what's left
ls -R

# Commit and push
git add .
git commit -m "Purge all notes - clean start"
git push

# Clean up
cd ..
rm -rf temp-vault
```

**Replace:**
- `YOUR_GITHUB_TOKEN` - Your GitHub personal access token
- `YOUR_USERNAME` - Your GitHub username

**Option B: GitHub Web Interface**

1. Go to your vault repository on GitHub
2. Navigate into `arabic/` and `english/` folders
3. Delete `.md` files (keep folders intact)
4. Commit changes directly on GitHub

### Step 3: Clear Database (Optional but Recommended)

Remove processing history from PostgreSQL:

```bash
# Using Railway CLI
railway login
railway link  # Select your project

# Clear processed notes and messages tables
railway run psql -c "DELETE FROM processed_notes;"
railway run psql -c "DELETE FROM messages;"

# Verify clean state
railway run psql -c "SELECT COUNT(*) FROM messages;"
```

**Expected output:** `count = 0`

### Step 4: Restart Railway Services

```
Railway Dashboard → telegram-bot → Settings → Restart
Railway Dashboard → batch-processor → Settings → Restart
```

### Step 5: Verify Clean State

**Check GitHub vault:**
- Should have folders: `arabic/`, `english/`
- Each has subfolders: `jots/`, `poetry/`, `strategy/`, etc.
- **No `.md` files**

**Check Obsidian (if connected):**
- Settings → Obsidian Git → Pull
- Vault should be empty (only folder structure)
- Ready for new notes

**Check Railway logs:**
```
Bot is running in batch mode
Worker claimed 0 messages
```

### Quick One-Liner Script

If you want to purge quickly:

```bash
# Stop services in Railway Dashboard first, then:
cd ~/Desktop && \
git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/obsidian-vault.git temp-vault && \
cd temp-vault && \
find arabic english -name "*.md" -delete && \
git add . && \
git commit -m "Purge all notes - clean start" && \
git push && \
cd .. && \
rm -rf temp-vault
```

Then restart Railway services manually.

---

## Summary

**You now have:**
- ✓ Telegram bot queuing messages (always responsive)
- ✓ Batch processor running every 3 minutes
- ✓ PostgreSQL database (shared queue, no race conditions)
- ✓ Git sync to GitHub vault
- ✓ Obsidian auto-syncing from GitHub
- ✓ Production-ready architecture

**Next steps:**
1. Test with various message types
2. Monitor costs in Railway dashboard
3. Set up Obsidian templates for categories
4. Create dataview queries to explore notes

**Your Second Brain is live!** 🧠🚀
