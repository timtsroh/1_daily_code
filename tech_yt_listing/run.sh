#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting tech_yt_listing skill..."

/usr/local/bin/python3 /Users/tealeaf/Code_Local/1_Daily_Code/tech_yt_listing/main.py

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
