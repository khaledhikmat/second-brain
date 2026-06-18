# Bulk YouTube URL Submission Guide

## Overview

The `submit-youtube-urls.sh` script automates bulk submission of YouTube URLs from a markdown file to your Second Brain HTTP API.

## Features

✅ **Auto-category detection** - Parses markdown headers (## Islam, ## History, etc.)
✅ **Duplicate detection** - Skips URLs already submitted in the same run
✅ **Progress tracking** - Shows success/failure for each URL
✅ **Dry-run mode** - Test without actually submitting
✅ **Configurable delays** - Control rate limiting
✅ **Error handling** - Continues on failure, reports summary
✅ **API key from .env** - Automatically reads HTTP_API_KEY

## Quick Start

### 1. Basic Usage (Auto-detect API key from .env)

```bash
./submit-youtube-urls.sh
```

This will:
- Read `youtube-urls.md`
- Use API key from `.env` file
- Submit to `http://localhost:8080/api/v1/youtube`
- Wait 2 seconds between requests

### 2. Dry Run (Test First!)

```bash
./submit-youtube-urls.sh --dry-run
```

**Recommended**: Always test with `--dry-run` first to verify:
- Categories are parsed correctly
- URLs are extracted properly
- Duplicates are detected
- Commands look correct

### 3. Custom API Key

```bash
./submit-youtube-urls.sh --api-key "your-api-key-here"
```

### 4. Custom File

```bash
./submit-youtube-urls.sh --file my-videos.md
```

## File Format

Your markdown file should follow this format:

```markdown
## Category Name

- https://www.youtube.com/watch?v=VIDEO_ID
- https://youtu.be/VIDEO_ID

## Another Category

- https://www.youtube.com/watch?v=VIDEO_ID
```

**Example** (`youtube-urls.md`):

```markdown
## Islam
- https://www.youtube.com/watch?v=nFOZCTPsFyw
- https://www.youtube.com/watch?v=7KXw1IfArp4

## History
- https://www.youtube.com/watch?v=f1pN3cDjpoI

## Strategy
- https://www.youtube.com/watch?v=W8lwryTz6Vw
```

**Notes**:
- Headers can use `#` or `##` (both work)
- URLs can be anywhere in the line (bullet points optional)
- Blank lines are ignored
- Comments are not supported

## Command Line Options

### Basic Options

```bash
--file FILE              # Path to markdown file (default: youtube-urls.md)
--endpoint URL           # API endpoint (default: http://localhost:8080/api/v1/youtube)
--api-key KEY            # API key (default: from .env or prompt)
--delay SECONDS          # Delay between requests (default: 2)
```

### Control Options

```bash
--dry-run                # Show what would be submitted without actually doing it
--skip-duplicates        # Skip duplicate URLs (default: enabled)
--no-skip-duplicates     # Allow duplicate URLs
--help                   # Show help message
```

## Usage Examples

### Example 1: Submit to Production

```bash
./submit-youtube-urls.sh \
  --endpoint "https://your-app.railway.app/api/v1/youtube" \
  --api-key "your-production-key" \
  --delay 3
```

### Example 2: Test Locally First

```bash
# 1. Dry run to verify
./submit-youtube-urls.sh --dry-run

# 2. Submit to local server
./submit-youtube-urls.sh

# 3. Check logs
tail -f logs/http_main.log
```

### Example 3: Process Large Batch Carefully

```bash
# Longer delay to avoid overwhelming the server
./submit-youtube-urls.sh --delay 5
```

### Example 4: Allow Duplicates (Reprocess)

```bash
./submit-youtube-urls.sh --no-skip-duplicates
```

**Note**: Server-side deduplication will still prevent actual reprocessing if you have that feature enabled.

## Output Explained

### During Execution

```
========================================
YouTube URL Bulk Submission
========================================
File:     youtube-urls.md
Endpoint: http://localhost:8080/api/v1/youtube
Delay:    2s
Dry run:  false
========================================

Found category: Islam
Submitting [Islam]: https://www.youtube.com/watch?v=nFOZCTPsFyw
✓ Success

Submitting [Islam]: https://www.youtube.com/watch?v=7KXw1IfArp4
✓ Success

⊘ Duplicate: https://www.youtube.com/watch?v=nFOZCTPsFyw (already submitted in category: Islam)

Found category: History
Submitting [History]: https://www.youtube.com/watch?v=f1pN3cDjpoI
✓ Success
```

### Summary

```
========================================
Summary
========================================
Total URLs found:    30
Successfully sent:   29
Duplicates skipped:  1
Other skipped:       0
Failed:              0
========================================
```

## Troubleshooting

### Issue 1: "File not found: youtube-urls.md"

**Solution**: Create the file or specify path:
```bash
./submit-youtube-urls.sh --file /path/to/your/file.md
```

### Issue 2: "API key is required"

**Solutions**:
1. Add to `.env`: `HTTP_API_KEY=your-key-here`
2. Pass via command line: `--api-key "your-key"`
3. Script will prompt you to enter it

### Issue 3: Connection refused

**Check**:
```bash
# Is the server running?
curl http://localhost:8080/health

# Start the server
python http_main.py
```

### Issue 4: All requests fail with 401

**Cause**: Invalid API key

**Solution**: Verify API key matches what's in your server's `.env`:
```bash
grep HTTP_API_KEY .env
```

### Issue 5: Some URLs show as duplicates but shouldn't be

**Cause**: URL appears multiple times in the file

**Check**:
```bash
# Find duplicate URLs
sort youtube-urls.md | uniq -d
```

**Solution**:
- Clean up the file to remove duplicates, or
- Use `--no-skip-duplicates` flag

## Best Practices

### 1. Always Test First

```bash
# Test with dry-run
./submit-youtube-urls.sh --dry-run

# Check output looks correct
# Then run for real
./submit-youtube-urls.sh
```

### 2. Monitor Server Logs

```bash
# In another terminal
tail -f logs/http_main.log
```

### 3. Start Small

```bash
# Test with just a few URLs first
head -10 youtube-urls.md > test-urls.md
./submit-youtube-urls.sh --file test-urls.md
```

### 4. Use Appropriate Delays

- **Local development**: `--delay 1` (fast)
- **Remote server**: `--delay 2-3` (default, safe)
- **Rate-limited API**: `--delay 5-10` (conservative)

### 5. Keep Backup

```bash
# Backup your URLs before editing
cp youtube-urls.md youtube-urls.md.backup
```

## Integration with Second Brain

### Workflow

1. **Collect URLs** → Add to `youtube-urls.md` with categories
2. **Review** → Check categories are correct
3. **Test** → `./submit-youtube-urls.sh --dry-run`
4. **Submit** → `./submit-youtube-urls.sh`
5. **Monitor** → Watch batch processor logs
6. **Verify** → Check notes created in vault

### Check Processing Status

```bash
# Count queued messages
sqlite3 notes.db "SELECT COUNT(*) FROM messages WHERE processing_status='queued';"

# Count completed
sqlite3 notes.db "SELECT COUNT(*) FROM messages WHERE processing_status='completed';"

# Count ignored (duplicates)
sqlite3 notes.db "SELECT COUNT(*) FROM messages WHERE processing_status='ignored';"

# View recent submissions
sqlite3 notes.db "SELECT id, category, processing_status, created_at FROM messages ORDER BY created_at DESC LIMIT 10;"
```

### Start Batch Processing

```bash
# Process the queue
python src/batch_processor.py --once

# Or run continuously
python src/batch_processor.py
```

## Advanced Usage

### Submit URLs Without Category Prefix

If you want to submit URLs directly without the category prefix format:

**Your file**:
```markdown
## Islam
- https://www.youtube.com/watch?v=VIDEO_ID
```

**Script sends**:
```json
{"url": "https://www.youtube.com/watch?v=VIDEO_ID", "category": "Islam"}
```

The server will process this correctly without needing `Islam -> URL` format.

### Custom Endpoint for Different Environments

```bash
# Development
./submit-youtube-urls.sh --endpoint "http://localhost:8080/api/v1/youtube"

# Staging
./submit-youtube-urls.sh --endpoint "https://staging.example.com/api/v1/youtube"

# Production
./submit-youtube-urls.sh --endpoint "https://api.example.com/api/v1/youtube"
```

### Combine with Other Tools

```bash
# Extract URLs from browser bookmarks and format
# (Assuming you have a bookmarks.html file)
grep -o 'https://www.youtube.com/watch[^"]*' bookmarks.html | \
  awk '{print "- " $0}' > extracted-urls.md

# Then submit
./submit-youtube-urls.sh --file extracted-urls.md
```

## Summary

The bulk submission script makes it easy to process large numbers of YouTube videos:

✅ Automatic category detection from markdown headers
✅ Built-in duplicate detection
✅ Dry-run mode for safety
✅ Detailed progress and error reporting
✅ Configurable delays and endpoints
✅ Works with both local development and production

**Quick Commands**:
```bash
# Test first
./submit-youtube-urls.sh --dry-run

# Submit for real
./submit-youtube-urls.sh

# Monitor progress
tail -f logs/http_main.log
```
