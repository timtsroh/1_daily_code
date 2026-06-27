#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting tech_yt_listing skill..."

/Users/tealeaf/.local/bin/claude --dangerously-skip-permissions -p "/tech_yt_listing"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
