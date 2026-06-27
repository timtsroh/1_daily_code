#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

MODE="${1:-start}"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting log skill (mode=$MODE)..."

/usr/local/bin/python3 /Users/tealeaf/.claude/skills/log/scripts/log.py "$MODE"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
