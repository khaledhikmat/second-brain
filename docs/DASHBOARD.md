# Dashboard Guide

Web-based monitoring dashboard for Second Brain with real-time analytics using HTMX.

---

## Overview

The dashboard provides a clean, real-time view of your Second Brain system with:

- **Summary Statistics**: Total messages, success rate, queue size, failed messages
- **Processing Status**: Visual breakdown of message statuses
- **Category Distribution**: See which categories are most used
- **Queue Monitor**: View messages waiting to be processed
- **Auto-Refresh**: Updates every 30 seconds automatically using HTMX

---

## Setup

### 1. Configure Environment Variables

Add to your `.env` file:

```env
# Dashboard Configuration
DASHBOARD_ENABLED=true
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your_secure_password_here
```

**Security Notes:**
- Use a strong, unique password
- Change the default username from `admin`
- Never commit credentials to git

### 2. Ensure HTTP API is Running

The dashboard is integrated into the HTTP API server. Start it with:

```bash
# Local deployment
python3 -m src.main

# The dashboard runs alongside the HTTP API on the same port (8080)
```

### 3. Access the Dashboard

Open your browser and navigate to:

```
http://localhost:8080/dashboard
```

Or on Railway:
```
https://your-app.up.railway.app/dashboard
```

---

## Using the Dashboard

### Login

1. Navigate to `/dashboard`
2. You'll be redirected to `/dashboard/login`
3. Enter your username and password from env vars
4. You'll be logged in for 24 hours

### Dashboard Views

**Summary Cards** (Top Row):
- **Total Messages**: All messages ever processed
- **Success Rate**: Percentage of successfully processed messages
- **Queued**: Messages waiting in queue
- **Failed**: Messages that failed processing

**Processing Status** (Left Panel):
- Visual breakdown of all message statuses
- Progress bars show percentage distribution
- Color-coded status badges:
  - 🟢 Green = Completed
  - 🔵 Blue = Processing
  - 🟡 Yellow = Queued
  - 🔴 Red = Failed

**Categories** (Right Panel):
- Distribution of messages by category
- Shows count and percentage for each
- Gradient progress bars

**Queue Table** (Bottom):
- First 10 messages in queue
- Shows: ID, timestamp, status, preview
- Real-time updates as queue changes

### Auto-Refresh

The dashboard automatically refreshes every 30 seconds using HTMX. No page reload needed!

**You'll see:**
- Smooth transitions when data updates
- Timestamp in header showing last update time
- Slight opacity change during refresh

### Logout

Click "Logout" in the top right corner.

---

## Features

### Server-Side Rendering

- Fast, lightweight pages
- No heavy JavaScript frameworks
- Renders on server, sends HTML to browser

### HTMX Integration

- Partial page updates
- Auto-refresh without full reload
- Smooth transitions
- Minimal JavaScript

### Authentication

- Session-based auth (cookies)
- 24-hour session lifetime
- HttpOnly cookies for security
- Configurable credentials via env vars

### Real-Time Monitoring

Dashboard shows:
- `/api/v1/analytics/summary` - Overall stats
- `/api/v1/analytics/categories` - Category breakdown
- `/api/v1/queue` - Current queue status

---

## Security

### Session Management

- Sessions stored in-memory (resets on restart)
- HttpOnly cookies prevent XSS attacks
- SameSite=Lax prevents CSRF
- 24-hour expiration

**Production Recommendations:**
- Use strong passwords (20+ characters)
- Rotate credentials regularly
- Use HTTPS in production (Railway provides this)
- Consider Redis for persistent sessions

### Access Control

- Dashboard requires authentication
- Separate from HTTP API key
- No public access without credentials

### Environment Variables

Never commit these to git:
```env
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=change_this_secure_password
```

Add to `.gitignore`:
```
.env
.env.local
.env.*.local
```

---

## Customization

### Change Refresh Interval

Edit `templates/dashboard.html`:

```html
<!-- Change from 30s to 60s -->
<div hx-get="/dashboard/refresh" hx-trigger="every 60s" hx-swap="outerHTML">
```

### Change Session Timeout

Edit `src/handlers/dashboard_handler.py`:

```python
response.set_cookie(
    key="session",
    value=token,
    httponly=True,
    max_age=172800,  # Changed from 86400 (24h) to 172800 (48h)
    samesite="lax"
)
```

### Customize Styling

Templates use Tailwind CSS via CDN. Edit `templates/dashboard.html` to modify:
- Colors (change `bg-blue-500` to `bg-purple-500`, etc.)
- Layout (change grid columns, spacing)
- Card styles (shadows, borders, padding)

---

## Troubleshooting

### Can't Access Dashboard

**Check:**
1. `DASHBOARD_ENABLED=true` in `.env`
2. HTTP API is running
3. Correct URL (http://localhost:8080/dashboard)

**Fix:**
```bash
# Check config
python3 -m src.config

# Restart with dashboard enabled
DASHBOARD_ENABLED=true python3 -m src.main
```

### "Dashboard is disabled" Error

**Cause:** `DASHBOARD_ENABLED=false` or not set

**Fix:**
```env
DASHBOARD_ENABLED=true
```

Restart the service.

### "Not authenticated" Error

**Cause:** Session expired or invalid

**Fix:**
- Go to `/dashboard/login`
- Log in again
- Clear cookies if still failing

### Login Fails

**Check:**
1. Credentials in `.env` match what you're entering
2. `DASHBOARD_PASSWORD` is set (not empty)
3. No trailing spaces in env vars

**Fix:**
```env
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=my_secure_password
```

Restart and try again.

### Dashboard Shows No Data

**Check:**
1. Database is connected (PostgreSQL or SQLite)
2. Messages exist in database
3. Check browser console for errors

**Fix:**
```bash
# Check database connection
railway run psql -c "SELECT COUNT(*) FROM messages;"

# Or for SQLite
sqlite3 notes.db "SELECT COUNT(*) FROM messages;"
```

### HTMX Not Refreshing

**Check:**
1. Browser dev tools → Network tab
2. Look for requests to `/dashboard/refresh` every 30s
3. Check for JavaScript errors

**Fix:**
- Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
- Clear browser cache
- Try different browser

---

## API Endpoints Used

The dashboard consumes these internal endpoints:

```
GET /dashboard              - Redirects to login or dashboard
GET /dashboard/login        - Login page
POST /dashboard/login       - Handle login
POST /dashboard/logout      - Handle logout
GET /dashboard/view         - Main dashboard view (requires auth)
GET /dashboard/refresh      - HTMX refresh endpoint (requires auth)
```

These endpoints use the same analytics APIs:
- `/api/v1/analytics/summary`
- `/api/v1/analytics/categories`
- `/api/v1/queue`

---

## Railway Deployment

### Environment Variables

In Railway dashboard → Variables, add:

```env
DASHBOARD_ENABLED=true
DASHBOARD_USERNAME=your_username
DASHBOARD_PASSWORD=your_secure_password
```

### Access URL

Railway automatically provides HTTPS:

```
https://your-app.up.railway.app/dashboard
```

### Production Checklist

- [ ] Strong password set (20+ characters)
- [ ] Username changed from default `admin`
- [ ] HTTPS enabled (automatic on Railway)
- [ ] Credentials NOT in git repository
- [ ] Dashboard accessible via Railway URL
- [ ] Session cookies working (test login/logout)

---

## Technical Details

### Stack

- **Backend**: FastAPI
- **Templates**: Jinja2
- **Frontend**: HTMX + Tailwind CSS (CDN)
- **Auth**: Session-based (cookies)
- **Database**: PostgreSQL (shared with main app)

### File Structure

```
templates/
├── base.html          # Base template with navbar
├── dashboard.html     # Main dashboard view
└── login.html         # Login page

src/handlers/
└── dashboard_handler.py  # Routes and auth logic
```

### Session Storage

Currently uses in-memory set (resets on restart):

```python
SESSIONS = set()  # In src/handlers/dashboard_handler.py
```

**For production persistence:**
- Use Redis
- Use database table
- Use JWT tokens

---

## Examples

### Testing Locally

```bash
# 1. Set environment variables
cat >> .env << EOF
DASHBOARD_ENABLED=true
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=test123
EOF

# 2. Start server
python3 -m src.main

# 3. Open browser
open http://localhost:8080/dashboard

# 4. Login with:
#    Username: admin
#    Password: test123
```

### Using with Railway

```bash
# 1. Set Railway env vars
railway variables set DASHBOARD_ENABLED=true
railway variables set DASHBOARD_USERNAME=admin
railway variables set DASHBOARD_PASSWORD=$(openssl rand -base64 32)

# 2. Deploy
git push

# 3. Access dashboard
railway open /dashboard
```

---

## Summary

✅ **Features:**
- Real-time monitoring with auto-refresh
- Clean, responsive UI
- Session-based authentication
- Server-side rendering with HTMX
- Minimal dependencies

✅ **Security:**
- HttpOnly cookies
- Password-protected
- HTTPS in production
- No public access

✅ **Performance:**
- Lightweight (no heavy JS frameworks)
- Fast server-side rendering
- Efficient partial updates with HTMX
- Auto-refresh every 30 seconds

**Your monitoring dashboard is ready!** 📊
