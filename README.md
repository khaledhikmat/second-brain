# Notes Processor

An automated system that receives messages from Telegram or HTTP channels, processes them using AI models and generates structured Obsidian and OKF notes with proper categorization, tagging, and wikilinks.

## Database Management

### Connection to the database:

```bash
# Interactive mode
psql -h localhost -p 5433 -U second_brain_user -d second_brain
# Password: second_brain_password

# Or set PGPASSWORD to skip password prompt
export PGPASSWORD=second_brain_password
psql -h localhost -p 5433 -U second_brain_user -d second_brain
```

**Useful psql commands** (once connected):
```sql
\dt                 -- List all tables
\d messages         -- Describe messages table
\d processed_notes  -- Describe processed_notes table
\l                  -- List all databases
\du                 -- List all users
\q                  -- Quit

-- Query examples
SELECT * FROM messages LIMIT 10;
SELECT COUNT(*) FROM messages;
SELECT processing_status, COUNT(*) FROM messages GROUP BY processing_status;
```

### Common Database Operations

Set password environment variable for easier access:
```bash
export PGPASSWORD=second_brain_password
```

**View all messages:**
```bash
psql -h localhost -p 5433 -U second_brain_user -d second_brain -c \
  "SELECT id, processing_status, category, language FROM messages ORDER BY created_at DESC LIMIT 10;"
```

**Check failed messages:**
```bash
psql -h localhost -p 5433 -U second_brain_user -d second_brain -c \
  "SELECT id, category, error_message FROM messages WHERE processing_status = 'FAILED';"
```

**Count messages by status:**
```bash
psql -h localhost -p 5433 -U second_brain_user -d second_brain -c \
  "SELECT processing_status, COUNT(*) as count FROM messages GROUP BY processing_status;"
```

**Reset database (delete all data):**
```bash
# Stop the app first, then:
docker compose down -v
docker compose up -d postgres
# Tables will be recreated when you restart the app
```

## Local Setup

### Step 1: Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example config
cp .env.example .env.local

# Adjust and add credentials as needed
```

### Step 3: Start the database

Start a new terminal:

```bash
# Start the database
docker compose up -d postgres

# Check if it's running
docker compose ps

# View logs
docker compose logs -f postgres
```

### Step 4: Start Main Locally

Start a new terminal:

```bash
source .venv/bin/activate
python3 src/main.py
```

### Step 5: Start Batch Locally

Start a new terminal:

```bash
source .venv/bin/activate
python3 src/batch.py
```

### Step 6: Dashboard

```bash
http://localhost:8080/dashboard
```

## Telegram

- Set all environment variables
- Update `TELEGRAM_WEBHOOK_URL` to Railway URL

Make sure the Telegram bot's webhook is registerd properly:

```bash
curl https://api.telegram.org/<telegram-token>/getWebhookInfo
```

If not, register Telegram bot's webhook manually:

```bash
curl -X POST "https://api.telegram.org/<telegram-token>/setWebhook?url=https://<railwat-base-url>/webhook/telegram"
```

## Railway Setup

Please refer to [Railway Deploymemnt](./docs/RAILWAY-DEPLOYMENT.md) for details.

## Usage Examples

**Notes via Telegram:**

```bash
/sayings Knowledge is power
```

```bash
/islam الصلاة عمود الدين
```

**Notes via HTTP API (programmatic):**

```bash
curl -X POST http://localhost:8080/api/v1/notes \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Knowledge is power", "category": "sayings"}'
```

```bash
curl -X POST http://localhost:8080/api/v1/notes \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "يبدو ان الصراع التاريخيّ بين القوى البرية الكبرى والقوة البحرية الكبرى يدخل منعطفاً جديداً في هذه الأيام، وهو صراع تتحكم فيه معادلة العلاقة بين القوى الصاعدة والقوى السائدة . وأبرز مظاهر هذا الصراع اليوم هو الصعود المطرد للشرق الآسيوي - الأوراسي بقيادة الصين وحليفتها روسيا على حساب الغرب الأطلسي بقيادة الولايات المتحدة الأمريكية مع حلفائها الأوروبيين.", "category": "strategy"}'
```

**YouTube via HTTP API:**

```bash
curl -X POST http://localhost:8080/api/v1/notes \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "https://youtube.com/watch?v=xxxxx", "category": "history", "language": "Arabic"}'
```

**PDF via HTTP API:**

```bash
curl -X POST http://localhost:8080/api/v1/notes \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "./book1.pdf", "category": "history", "language": "Arabic"}'
```

## License

MIT
