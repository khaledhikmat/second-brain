# PostgreSQL Database Guide - Railway Production

Complete guide to using PostgreSQL database with Second Brain on Railway for production deployment.

---

## Overview

The Second Brain application uses PostgreSQL as the production database for:

- **Message Queue Management**: Database-backed queue for batch processing
- **Message History**: Store all incoming messages with metadata
- **Processing Lifecycle Tracking**: Monitor status from queued → processing → completed/failed
- **YouTube URL Deduplication**: Prevent duplicate video processing
- **Multi-Worker Coordination**: Atomic dequeue prevents race conditions
- **Analytics**: Query statistics by category, language, status

**Production Stack:**
- PostgreSQL 14+ on Railway
- Async driver: `asyncpg`
- Connection pooling: 5 connections + 10 overflow
- Row-level locking for parallel processing

---

## Database Schema

### Table: `messages`

Stores all incoming messages from any source (Telegram, HTTP API).

**Columns:**
```sql
id                  SERIAL PRIMARY KEY
timestamp           TIMESTAMP NOT NULL
user_id             VARCHAR(255)
source              VARCHAR(50) NOT NULL          -- 'telegram', 'http'
source_message_id   VARCHAR(255)
category            VARCHAR(100)
language            VARCHAR(10)                   -- 'ar', 'en'
raw_text            TEXT NOT NULL
processing_status   VARCHAR(20) NOT NULL          -- 'queued', 'processing', 'completed', 'failed', 'ignored'
worker_id           VARCHAR(100)                  -- Worker that claimed this message
error_message       TEXT
retry_count         INTEGER DEFAULT 0
created_at          TIMESTAMP DEFAULT NOW()
updated_at          TIMESTAMP DEFAULT NOW()
```

**Indexes:**
```sql
CREATE INDEX idx_messages_status ON messages(processing_status);
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX idx_messages_category ON messages(category);
CREATE INDEX idx_messages_language ON messages(language);
CREATE INDEX idx_messages_worker_id ON messages(worker_id);
```

### Table: `processed_notes`

Stores metadata for successfully created notes.

**Columns:**
```sql
id                  SERIAL PRIMARY KEY
message_id          INTEGER NOT NULL REFERENCES messages(id)
title               VARCHAR(500) NOT NULL
file_path           TEXT NOT NULL
tags                TEXT[]                        -- PostgreSQL array
concepts            TEXT[]
entities            JSONB                         -- {"people": [...], "places": [...]}
summary             TEXT
processed_data      JSONB NOT NULL                -- Full Claude output
created_at          TIMESTAMP DEFAULT NOW()
```

**Indexes:**
```sql
CREATE INDEX idx_processed_notes_message_id ON processed_notes(message_id);
CREATE INDEX idx_processed_notes_created_at ON processed_notes(created_at DESC);
CREATE INDEX idx_processed_data_url ON processed_notes USING GIN (processed_data);  -- For URL deduplication
```

---

## Message Lifecycle

### Successful Processing

```
1. QUEUED      → Message saved to database via Telegram/HTTP API
2. PROCESSING  → Batch processor claims message (atomic dequeue)
3. COMPLETED   → Note created, metadata stored in processed_notes
```

### Failed Processing

```
1. QUEUED      → Message saved to database
2. PROCESSING  → Batch processor claims message
3. FAILED      → Error stored, retry_count incremented
```

### YouTube Duplicate Detection

```
1. QUEUED      → YouTube URL message saved
2. PROCESSING  → Batch processor checks for duplicate URL
3. IGNORED     → Duplicate found, marked as ignored (no processing)
   OR
   COMPLETED   → First occurrence, process and store URL in processed_data
```

---

## PostgreSQL-Specific Optimizations

### 1. Atomic Dequeue with Row-Level Locking

**Location:** `src/db/repository.py:350-405`

Uses PostgreSQL's `SELECT FOR UPDATE SKIP LOCKED` for true parallel processing:

```sql
-- Step 1: Claim messages atomically
SELECT * FROM messages
WHERE processing_status = 'queued'
ORDER BY timestamp ASC
LIMIT 10
FOR UPDATE SKIP LOCKED;  -- Skip rows locked by other workers

-- Step 2: Update claimed messages
UPDATE messages
SET processing_status = 'processing',
    worker_id = 'railway-1234-a3f2b',
    updated_at = NOW()
WHERE id IN (...claimed message IDs...);
```

**Benefits:**
- ✅ Multiple workers process different messages in parallel
- ✅ No blocking between workers
- ✅ Prevents duplicate processing
- ✅ Optimal for high-throughput production

**Worker Identity:**
- Format: `{hostname}-{pid}-{short-uuid}`
- Example: `railway-batch-1234-a3f2b`
- Tracked in `worker_id` column

### 2. JSON Queries for YouTube Deduplication

**Location:** `src/db/repository.py:229-277`

Uses PostgreSQL's native JSONB operators:

```python
# Python (SQLAlchemy)
ProcessedNote.processed_data['url'].astext == youtube_url

# Equivalent SQL
SELECT * FROM processed_notes
WHERE processed_data->>'url' = 'https://www.youtube.com/watch?v=xxxxx';
```

**Performance:**
- GIN index on `processed_data` enables fast lookups
- O(log n) complexity for URL deduplication
- Handles thousands of videos efficiently

### 3. Connection Pooling

**Configuration:** `src/db/database.py:67-74`

```python
engine = create_async_engine(
    database_url,
    pool_size=5,           # 5 persistent connections
    max_overflow=10,       # Up to 15 total connections
    pool_pre_ping=True     # Verify connections before use
)
```

**Best for:**
- Telegram bot (1 connection)
- Batch processor (1-3 connections per worker)
- HTTP API (1-2 connections)

---

## Railway Setup

### Step 1: Add PostgreSQL to Railway Project

1. Go to your Railway project dashboard
2. Click "New" → "Database" → "Add PostgreSQL"
3. Railway provisions database (~30 seconds)
4. Railway automatically creates `DATABASE_URL` variable

### Step 2: Configure Services

**Environment Variable (both bot and batch processor):**
```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Railway automatically converts this to:
```env
DATABASE_URL=postgresql://postgres:xxxxx@postgres.railway.internal:5432/railway
```

**For asyncpg driver, ensure it's converted to:**
```env
DATABASE_URL=postgresql+asyncpg://postgres:xxxxx@postgres.railway.internal:5432/railway
```

### Step 3: Initialize Schema

Schema is automatically created on first deployment:

1. Railway builds your application
2. Service starts and runs `initialize_database()`
3. Tables are created automatically
4. Logs confirm: `Database initialized successfully: postgresql+asyncpg://...`

**Manual initialization (if needed):**
```bash
railway run python -c "
import asyncio
from src.utils.db_init import initialize_database
asyncio.run(initialize_database())
"
```

### Step 4: Verify Setup

```bash
# Using Railway CLI
railway login
railway link  # Select your project

# Connect to database
railway run psql

# Check tables
\dt

# Expected output:
# messages
# processed_notes
```

---

## Querying with psql

### Connect to Database

```bash
# Option 1: Railway CLI (recommended)
railway run psql

# Option 2: Direct connection
psql "postgresql://user:password@host:5432/railway"

# Option 3: From Railway dashboard
# Postgres service → Connect → Copy connection command
```

### Essential psql Commands

**Meta Commands:**
```bash
\l              # List all databases
\c dbname       # Connect to database
\dt             # List tables
\d messages     # Describe messages table
\d+ messages    # Describe with sizes and indexes
\du             # List users/roles
\q              # Quit psql
```

**Query Formatting:**
```bash
\x              # Toggle expanded display (vertical format)
\x auto         # Auto expand for wide results
\pset pager off # Disable pager for long output
\timing         # Show query execution time
```

**File Operations:**
```bash
\i script.sql        # Execute SQL from file
\o output.txt        # Send results to file
\o                   # Stop output to file
```

### Common Queries

**Queue Status:**
```sql
-- Check queue size
SELECT processing_status, COUNT(*)
FROM messages
GROUP BY processing_status;

-- View queued messages
SELECT id, timestamp, category, LEFT(raw_text, 50) as preview
FROM messages
WHERE processing_status = 'queued'
ORDER BY timestamp ASC;
```

**Worker Activity:**
```sql
-- Currently processing messages by worker
SELECT worker_id, COUNT(*) as processing_count
FROM messages
WHERE processing_status = 'processing'
GROUP BY worker_id;

-- Worker performance stats
SELECT
    worker_id,
    COUNT(*) as total,
    SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM messages
WHERE worker_id IS NOT NULL
GROUP BY worker_id
ORDER BY total DESC;
```

**Processing Statistics:**
```sql
-- Success rate
SELECT
    COUNT(*) as total_messages,
    SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM messages;

-- Messages per day
SELECT
    DATE(timestamp) as date,
    COUNT(*) as count
FROM messages
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- By category
SELECT category, COUNT(*) as count
FROM messages
WHERE category IS NOT NULL
GROUP BY category
ORDER BY count DESC;

-- By language
SELECT language, COUNT(*) as count
FROM messages
WHERE language IS NOT NULL
GROUP BY language
ORDER BY count DESC;
```

**Failed Messages:**
```sql
-- Recent failures
SELECT id, timestamp, category, error_message, retry_count
FROM messages
WHERE processing_status = 'failed'
ORDER BY timestamp DESC
LIMIT 10;

-- Failure reasons
SELECT error_message, COUNT(*) as count
FROM messages
WHERE processing_status = 'failed'
GROUP BY error_message
ORDER BY count DESC;
```

**YouTube Processing:**
```sql
-- YouTube URLs processed
SELECT COUNT(*) as total_youtube_videos
FROM processed_notes
WHERE processed_data->>'url' IS NOT NULL;

-- Ignored duplicates
SELECT COUNT(*) as duplicate_count
FROM messages
WHERE processing_status = 'ignored';

-- Find message by YouTube URL
SELECT m.id, m.timestamp, m.category, n.title
FROM messages m
JOIN processed_notes n ON m.id = n.message_id
WHERE n.processed_data->>'url' = 'https://www.youtube.com/watch?v=xxxxx';
```

**Notes Analysis:**
```sql
-- Notes by category
SELECT
    COALESCE(processed_data->>'category', 'unknown') as category,
    COUNT(*) as count
FROM processed_notes
GROUP BY category
ORDER BY count DESC;

-- Recent notes
SELECT
    id,
    title,
    processed_data->>'category' as category,
    created_at
FROM processed_notes
ORDER BY created_at DESC
LIMIT 10;

-- Search notes by title
SELECT id, title, file_path
FROM processed_notes
WHERE title ILIKE '%strategy%'
ORDER BY created_at DESC;
```

---

## Monitoring and Maintenance

### Database Health Checks

**Connection Count:**
```sql
SELECT count(*) as active_connections
FROM pg_stat_activity
WHERE datname = 'railway';
```

**Expected:** 2-5 connections (bot + batch processor)

**Database Size:**
```sql
SELECT
    pg_size_pretty(pg_database_size('railway')) as database_size;
```

**Table Sizes:**
```sql
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size('public.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.'||tablename) DESC;
```

**Index Usage:**
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### Cleanup Operations

**Delete Old Completed Messages (older than 30 days):**
```sql
DELETE FROM messages
WHERE processing_status = 'completed'
  AND created_at < NOW() - INTERVAL '30 days';
```

**Reset Stuck Processing Messages:**
```sql
-- Find stuck messages (processing > 1 hour)
SELECT id, timestamp, worker_id, raw_text
FROM messages
WHERE processing_status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';

-- Reset to queued
UPDATE messages
SET processing_status = 'queued',
    worker_id = NULL,
    updated_at = NOW()
WHERE processing_status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

**Vacuum and Analyze:**
```sql
-- Reclaim space and update statistics
VACUUM ANALYZE messages;
VACUUM ANALYZE processed_notes;

-- Or vacuum entire database
VACUUM ANALYZE;
```

### Performance Monitoring

**Slow Queries (requires pg_stat_statements extension):**
```sql
SELECT
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Table Bloat:**
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_dead_tup DESC;
```

---

## Backup and Recovery

### Railway Automatic Backups

Railway automatically backs up PostgreSQL databases:
- Daily snapshots
- 7-day retention on free tier
- Restore from Railway dashboard: Postgres → Backups

### Manual Backup

**Using Railway CLI:**
```bash
# Backup to file
railway run pg_dump > backup-$(date +%Y%m%d-%H%M%S).sql

# Compress backup
railway run pg_dump | gzip > backup-$(date +%Y%m%d).sql.gz
```

**Using psql directly:**
```bash
pg_dump "postgresql://user:pass@host/railway" > backup.sql
```

### Restore from Backup

```bash
# Using Railway CLI
railway run psql < backup.sql

# Or direct connection
psql "postgresql://user:pass@host/railway" < backup.sql
```

### Export Data for Analysis

**Export to CSV:**
```bash
railway run psql -c "\copy messages TO '/tmp/messages.csv' CSV HEADER"
railway run psql -c "\copy processed_notes TO '/tmp/notes.csv' CSV HEADER"
```

---

## Troubleshooting

### Connection Issues

**Error:** `connection refused` or `could not connect`

**Check:**
1. Database service is running (Railway dashboard → Postgres)
2. `DATABASE_URL` is correctly set in both services
3. Using `asyncpg` driver: `postgresql+asyncpg://...`

**Solution:**
```bash
# Test connection
railway run psql -c "SELECT version();"

# Check DATABASE_URL format
railway variables | grep DATABASE_URL
```

### Permission Errors

**Error:** `permission denied for table messages`

**Solution:**
```bash
railway run psql -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;"
railway run psql -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;"
```

### Stuck Messages in Processing

**Symptom:** Messages stuck in `processing` status

**Diagnosis:**
```sql
SELECT id, timestamp, worker_id, updated_at, LEFT(raw_text, 50)
FROM messages
WHERE processing_status = 'processing'
ORDER BY updated_at ASC;
```

**Solution:**
```sql
-- Reset messages stuck > 1 hour
UPDATE messages
SET processing_status = 'queued',
    worker_id = NULL
WHERE processing_status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

### High Connection Count

**Error:** `too many connections`

**Diagnosis:**
```sql
SELECT
    datname,
    usename,
    count(*) as connections
FROM pg_stat_activity
GROUP BY datname, usename;
```

**Solution:**
1. Check for connection leaks in code
2. Increase connection pool limits (Railway PostgreSQL settings)
3. Reduce `pool_size` in `src/db/database.py` if many workers

### Slow Queries

**Diagnosis:**
```sql
-- Current running queries
SELECT
    pid,
    now() - query_start as duration,
    query
FROM pg_stat_activity
WHERE state = 'active'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;
```

**Solution:**
1. Add missing indexes
2. Optimize query (use EXPLAIN ANALYZE)
3. Increase Railway plan for more resources

### Out of Disk Space

**Diagnosis:**
```sql
SELECT pg_size_pretty(pg_database_size('railway')) as size;
```

**Solution:**
1. Delete old completed messages (see Cleanup Operations)
2. Run `VACUUM FULL` to reclaim space
3. Upgrade Railway PostgreSQL plan

---

## Performance Optimization

### Recommended Indexes

Already created automatically:
```sql
CREATE INDEX idx_messages_status ON messages(processing_status);
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX idx_messages_worker_id ON messages(worker_id);
CREATE INDEX idx_processed_data_url ON processed_notes USING GIN (processed_data);
```

### Optional Indexes for Heavy Analytics

```sql
-- Composite index for status + category queries
CREATE INDEX idx_messages_status_category ON messages(processing_status, category);

-- Index for timestamp range queries
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);

-- Full-text search on titles
CREATE INDEX idx_notes_title_fts ON processed_notes USING GIN (to_tsvector('english', title));
```

### Query Optimization Tips

**Use EXPLAIN ANALYZE:**
```sql
EXPLAIN ANALYZE
SELECT * FROM messages WHERE processing_status = 'queued';
```

**Batch Updates:**
```sql
-- Good: Single update
UPDATE messages SET processing_status = 'queued'
WHERE id = ANY(ARRAY[1,2,3,4,5]);

-- Bad: Multiple updates
UPDATE messages SET processing_status = 'queued' WHERE id = 1;
UPDATE messages SET processing_status = 'queued' WHERE id = 2;
...
```

**Use Connection Pooling:**
- Already configured in `database.py`
- Don't create new connections for each query
- Reuse session from context manager

---

## Database Metrics

### Key Metrics to Monitor

**Queue Health:**
```sql
SELECT
    SUM(CASE WHEN processing_status = 'queued' THEN 1 ELSE 0 END) as queued,
    SUM(CASE WHEN processing_status = 'processing' THEN 1 ELSE 0 END) as processing,
    SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed
FROM messages
WHERE created_at > NOW() - INTERVAL '24 hours';
```

**Processing Throughput (last hour):**
```sql
SELECT
    COUNT(*) as messages_processed
FROM messages
WHERE processing_status = 'completed'
  AND updated_at > NOW() - INTERVAL '1 hour';
```

**Average Processing Time:**
```sql
SELECT
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_seconds
FROM messages
WHERE processing_status = 'completed';
```

**Failure Rate:**
```sql
SELECT
    ROUND(100.0 * SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) / COUNT(*), 2) as failure_rate
FROM messages
WHERE created_at > NOW() - INTERVAL '7 days';
```

---

## Production Checklist

### Initial Setup
- [x] PostgreSQL added to Railway project
- [x] `DATABASE_URL` configured in both services
- [x] `asyncpg` in `requirements.txt`
- [x] Schema initialized (tables created)
- [x] Indexes created automatically

### Monitoring
- [ ] Set up alerts for failed messages
- [ ] Monitor connection count
- [ ] Track database size growth
- [ ] Review slow queries weekly

### Maintenance
- [ ] Backup strategy in place (Railway auto-backup)
- [ ] Cleanup old messages monthly
- [ ] Run VACUUM quarterly
- [ ] Review and optimize indexes as needed

### Security
- [ ] Database URL never committed to git
- [ ] Connection uses SSL (Railway default)
- [ ] Minimal permissions for application user
- [ ] Regular security updates (Railway managed)

---

## Summary

✅ **Production-Ready PostgreSQL Setup:**
- Row-level locking prevents race conditions
- JSONB for efficient YouTube deduplication
- Connection pooling handles concurrent load
- Automatic schema initialization

✅ **Railway Integration:**
- Managed PostgreSQL service
- Automatic backups (7-day retention)
- Shared database between bot and batch processor
- Environment variable injection

✅ **Monitoring & Maintenance:**
- Comprehensive psql queries for diagnostics
- Cleanup scripts for old data
- Performance optimization guidelines
- Troubleshooting common issues

✅ **Multi-Worker Safety:**
- Atomic dequeue with `SELECT FOR UPDATE SKIP LOCKED`
- Worker identity tracking
- No duplicate processing
- Parallel execution support

**Your PostgreSQL database is production-ready on Railway!** 🚀
