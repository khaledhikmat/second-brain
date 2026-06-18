#!/bin/bash

# submit-youtube-urls.sh - Bulk submit YouTube URLs from markdown file to HTTP API
#
# Usage:
#   ./submit-youtube-urls.sh [options]
#
# Options:
#   --file FILE         Path to markdown file (default: youtube-urls.md)
#   --endpoint URL      API endpoint (default: http://localhost:8080/api/v1/youtube)
#   --api-key KEY       API key for authentication (default: from .env or prompt)
#   --delay SECONDS     Delay between requests (default: 2)
#   --dry-run           Print commands without executing
#   --skip-duplicates   Skip duplicate URLs (default: enabled)
#   --help              Show this help message

set -euo pipefail

# Default configuration
FILE="youtube-urls.md"
ENDPOINT="http://localhost:8080/api/v1/youtube"
API_KEY=""
DELAY=2
DRY_RUN=false
SKIP_DUPLICATES=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --file)
            FILE="$2"
            shift 2
            ;;
        --endpoint)
            ENDPOINT="$2"
            shift 2
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --delay)
            DELAY="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-duplicates)
            SKIP_DUPLICATES=true
            shift
            ;;
        --no-skip-duplicates)
            SKIP_DUPLICATES=false
            shift
            ;;
        --help)
            grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if file exists
if [[ ! -f "$FILE" ]]; then
    echo -e "${RED}Error: File not found: $FILE${NC}"
    exit 1
fi

# Get API key from .env if not provided
if [[ -z "$API_KEY" ]]; then
    if [[ -f ".env" ]]; then
        API_KEY=$(grep "^HTTP_API_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi
fi

# Prompt for API key if still not available
if [[ -z "$API_KEY" ]]; then
    echo -e "${YELLOW}API key not found in .env or command line${NC}"
    read -p "Enter API key: " API_KEY
fi

# Validate API key
if [[ -z "$API_KEY" ]]; then
    echo -e "${RED}Error: API key is required${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}YouTube URL Bulk Submission${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "File:     ${GREEN}$FILE${NC}"
echo -e "Endpoint: ${GREEN}$ENDPOINT${NC}"
echo -e "Delay:    ${GREEN}${DELAY}s${NC}"
echo -e "Dry run:  ${GREEN}$DRY_RUN${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Counters
total_urls=0
submitted=0
skipped=0
failed=0
duplicates=0

# Track submitted URLs to detect duplicates (using temp file for bash 3.x compatibility)
SEEN_URLS_FILE=$(mktemp)
trap "rm -f $SEEN_URLS_FILE" EXIT

# Current category
current_category=""

# Read file line by line
while IFS= read -r line; do
    # Skip empty lines
    [[ -z "$line" ]] && continue

    # Check if line is a category header (## Category or # Category)
    if [[ "$line" =~ ^#+ ]]; then
        # Extract category name (remove # and spaces)
        current_category=$(echo "$line" | sed 's/^#* *//' | sed 's/ *$//')
        echo -e "${BLUE}Found category: ${current_category}${NC}"
        continue
    fi

    # Check if line contains a YouTube URL
    if [[ "$line" =~ (https?://[^[:space:]]+) ]]; then
        url="${BASH_REMATCH[1]}"
        total_urls=$((total_urls + 1))

        # Check for duplicates
        if [[ "$SKIP_DUPLICATES" == true ]]; then
            prev_category=$(grep -F "$url" "$SEEN_URLS_FILE" 2>/dev/null | cut -d'|' -f2 || echo "")
            if [[ -n "$prev_category" ]]; then
                echo -e "${YELLOW}⊘ Duplicate: $url (already submitted in category: ${prev_category})${NC}"
                duplicates=$((duplicates + 1))
                skipped=$((skipped + 1))
                continue
            fi
        fi

        # Mark URL as seen
        echo "$url|$current_category" >> "$SEEN_URLS_FILE"

        # Skip if no category found
        if [[ -z "$current_category" ]]; then
            echo -e "${YELLOW}⚠ Skipping (no category): $url${NC}"
            skipped=$((skipped + 1))
            continue
        fi

        # Build JSON payload
        json_payload=$(cat <<EOF
{"url": "$url", "category": "$current_category"}
EOF
)

        # Build curl command
        curl_cmd=(
            curl -X POST "$ENDPOINT"
            -H "X-API-Key: $API_KEY"
            -H "Content-Type: application/json"
            -d "$json_payload"
            -w "\nHTTP Status: %{http_code}\n"
            -s
        )

        if [[ "$DRY_RUN" == true ]]; then
            echo -e "${BLUE}[DRY RUN]${NC} Category: ${GREEN}$current_category${NC}"
            echo -e "${BLUE}[DRY RUN]${NC} URL: $url"
            echo -e "${BLUE}[DRY RUN]${NC} Command: ${curl_cmd[*]}"
            echo ""
            submitted=$((submitted + 1))
        else
            echo -e "Submitting [${GREEN}$current_category${NC}]: $url"

            # Execute curl command
            response=$("${curl_cmd[@]}" 2>&1)
            exit_code=$?

            if [[ $exit_code -eq 0 ]] && [[ "$response" =~ "HTTP Status: 20"[0-9] ]]; then
                echo -e "${GREEN}✓ Success${NC}"
                submitted=$((submitted + 1))
            else
                echo -e "${RED}✗ Failed${NC}"
                echo -e "${RED}Response: $response${NC}"
                failed=$((failed + 1))
            fi

            # Delay between requests (except for last one)
            if [[ $total_urls -lt $(wc -l < "$FILE") ]]; then
                sleep "$DELAY"
            fi
        fi
    fi
done < "$FILE"

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total URLs found:    ${YELLOW}$total_urls${NC}"
echo -e "Successfully sent:   ${GREEN}$submitted${NC}"
echo -e "Duplicates skipped:  ${YELLOW}$duplicates${NC}"
echo -e "Other skipped:       ${YELLOW}$((skipped - duplicates))${NC}"
echo -e "Failed:              ${RED}$failed${NC}"
echo -e "${BLUE}========================================${NC}"

# Exit with appropriate code
if [[ $failed -gt 0 ]]; then
    exit 1
fi
