# Dockerfile for Notes Taking Processor
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# - git: for vault cloning and git sync
# - ffmpeg: for audio processing (yt-dlp + pydub)
# - ca-certificates: for SSL/TLS connections
RUN apt-get update && apt-get install -y \
    git \
    ca-certificates \
    ffmpeg \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
# - vault: for Obsidian vault storage
# - logs: for application logs
# - /tmp: ensure temp directory exists for audio processing
RUN mkdir -p vault logs /tmp && \
    chmod 1777 /tmp

# Configure git (will be overridden by env vars if needed)
RUN git config --global user.name "Notes System Bot" && \
    git config --global user.email "bot@notes-system.local"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Ensure temp directory is available for audio processing
ENV TMPDIR=/tmp

# Health check - verify application can import successfully
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from src.config import validate_config; sys.exit(0)"

# Run the application
CMD ["python", "-m", "src.main"]
