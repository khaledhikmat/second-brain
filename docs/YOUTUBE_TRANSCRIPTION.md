# YouTube Transcription Guide

## Overview

The system supports three methods for transcribing YouTube videos:

1. **YouTube Captions** (Fastest, Free) ✅
2. **Local Whisper** (Slow, Free) ⚠️
3. **OpenAI Whisper API** (Fast, Paid) ⚡

## Method Comparison

### 1. YouTube Captions (Primary Method)

**When:** Video has captions/subtitles available

**Speed:** Instant (~1-2 seconds)

**Cost:** Free

**Accuracy:** Depends on video creator

**How it works:**
- Fetches existing captions from YouTube
- Supports multiple languages (en, ar, etc.)
- No audio download needed

### 2. Local Whisper (Fallback #1)

**When:** No captions available + `WHISPER_METHOD=local`

**Speed:** **VERY SLOW**
- Short video (5 min): ~60-90 seconds
- Medium video (15 min): ~3-5 minutes
- Long video (1 hour): ~15-30 minutes

**Cost:** Free

**Accuracy:** Good to excellent (depending on model)

**Requirements:**
- FFmpeg installed
- Significant CPU/RAM
- Disk space for model (~150MB for `base`)

**Models:**
| Model | Speed | Accuracy | Size | RAM |
|-------|-------|----------|------|-----|
| tiny | Fastest | Basic | 75 MB | ~1 GB |
| base | Fast | Good | 150 MB | ~1 GB |
| small | Medium | Better | 500 MB | ~2 GB |
| medium | Slow | Great | 1.5 GB | ~5 GB |
| large | Very Slow | Best | 3 GB | ~10 GB |

### 3. OpenAI Whisper API (Fallback #2)

**When:** No captions available + `WHISPER_METHOD=api`

**Speed:** **FAST**
- Short video (5 min): ~5-10 seconds
- Medium video (15 min): ~15-30 seconds
- Long video (1 hour): ~1-2 minutes

**Cost:** **$0.006 per minute of audio**
- 5 min video: $0.03
- 15 min video: $0.09
- 60 min video: $0.36

**Accuracy:** Excellent

**Requirements:**
- OpenAI API key
- Active OpenAI account with credits

## Configuration

### Enable YouTube Transcription

In your `.env`:

```env
YOUTUBE_ENABLED=true
YOUTUBE_TRANSCRIPT_LANGUAGES=en,ar
```

### Choose Whisper Method

#### Option A: Local Whisper (Free, Slow)

```env
WHISPER_METHOD=local
WHISPER_MODEL=base  # Options: tiny, base, small, medium, large
```

**Best for:**
- Occasional use
- Short videos
- No budget constraints
- Don't mind waiting

#### Option B: OpenAI Whisper API (Paid, Fast)

```env
WHISPER_METHOD=api
OPENAI_API_KEY=sk-...  # Get from https://platform.openai.com/api-keys
```

**Best for:**
- Frequent use
- Long videos
- Need fast results
- Have budget (~$0.006/min)

## Cost Analysis

### Scenario 1: Light Usage
- 10 videos/month
- Average 10 minutes each
- **Local:** Free (but takes ~15 minutes total processing time)
- **API:** $0.60/month (processes in ~3 minutes total)

### Scenario 2: Medium Usage
- 50 videos/month
- Average 15 minutes each
- **Local:** Free (but takes ~2.5 hours total processing time)
- **API:** $4.50/month (processes in ~15 minutes total)

### Scenario 3: Heavy Usage
- 200 videos/month
- Average 20 minutes each
- **Local:** Free (but takes ~15+ hours total processing time)
- **API:** $24/month (processes in ~1 hour total)

## Performance Comparison (Real Example)

From your test (5-minute video):

| Method | Time | Cost |
|--------|------|------|
| YouTube Captions | 1-2 sec | Free |
| Local Whisper (base) | 68 sec | Free |
| OpenAI Whisper API | ~10 sec | $0.03 |

**For longer videos, the difference is even more dramatic:**

20-minute video:
- YouTube Captions: 2 sec (if available) ✅
- Local Whisper: ~5 minutes ⚠️
- OpenAI API: ~20 seconds ⚡

## Recommendations

### For Local Development/Testing:
```env
WHISPER_METHOD=local
WHISPER_MODEL=tiny  # Fastest for testing
```

### For Production (Railway):
```env
WHISPER_METHOD=api
OPENAI_API_KEY=sk-...
```

**Why API for production:**
1. Railway charges for CPU time - slow processing = higher costs
2. API is actually cheaper than running Whisper on Railway for most videos
3. Much better user experience (faster responses)
4. More predictable costs

### Cost Comparison: Railway CPU vs OpenAI API

**Railway CPU time cost:**
- $0.000463 per CPU minute
- Whisper processing: ~68 seconds for 5-min video
- Railway cost: ~$0.00053 per video

**OpenAI API cost:**
- $0.006 per minute of audio
- 5-min video: $0.03

**However:**
- Railway processing is SLOW (bad UX)
- Railway CPU is shared (variable performance)
- OpenAI is FAST and consistent
- For longer videos, Railway CPU cost increases (more processing time)

**Recommendation:** Use OpenAI API for Railway deployment unless you process < 20 videos/month.

## Setup Instructions

### Local Whisper Setup (macOS)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install SSL certificates:
```bash
/Applications/Python\ 3.11/Install\ Certificates.command
```

3. Configure `.env`:
```env
WHISPER_METHOD=local
WHISPER_MODEL=base
```

### OpenAI Whisper API Setup

1. Get API key:
   - Go to https://platform.openai.com/api-keys
   - Create new secret key
   - Copy it (starts with `sk-...`)

2. Add credits to account:
   - Go to https://platform.openai.com/account/billing
   - Add payment method
   - Add credits ($5 minimum)

3. Configure `.env`:
```env
WHISPER_METHOD=api
OPENAI_API_KEY=sk-...
```

4. Install OpenAI package:
```bash
pip install openai>=1.0.0
```

## Testing

### Test with captions (fast):
```bash
curl -X POST http://localhost:8080/api/v1/youtube \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "category": "History"}'
```

### Test without captions (uses Whisper):
Find a video without captions and try it - you'll see the difference in speed between local and API!

## Troubleshooting

### Local Whisper Issues

**Problem:** SSL Certificate Error
```
Solution: Run certificate installer (see LOCAL_TESTING.md)
```

**Problem:** Very slow processing
```
Solution:
1. Use smaller model (tiny instead of base)
2. Or switch to API method
```

**Problem:** Out of memory
```
Solution: Use smaller model or reduce batch size
```

### OpenAI API Issues

**Problem:** Authentication failed
```
Solution: Check API key is correct and starts with sk-
```

**Problem:** Insufficient credits
```
Solution: Add credits at platform.openai.com/account/billing
```

**Problem:** Rate limit exceeded
```
Solution: Wait a minute and retry, or upgrade account tier
```

## Railway Deployment

For Railway, the Dockerfile is already configured with:
- FFmpeg (required for audio processing)
- SSL certificates (for Whisper model downloads)
- Both local and API Whisper support

Just set environment variables in Railway dashboard:
```
YOUTUBE_ENABLED=true
WHISPER_METHOD=api
OPENAI_API_KEY=sk-...
```

## Summary

**Best Practice:**
1. Always try YouTube captions first (automatic, instant, free)
2. Fallback to Whisper only when captions unavailable
3. Use **local Whisper** for development/testing
4. Use **OpenAI API** for production (better UX, often cheaper on Railway)

**Cost-Effective Strategy:**
- Development: Local Whisper (`WHISPER_METHOD=local`)
- Production: OpenAI API (`WHISPER_METHOD=api`)
- Budget conscious: Local Whisper + faster model (`WHISPER_MODEL=tiny`)
