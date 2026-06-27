#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting 노정석 skill..."

/usr/local/bin/python3 /Users/tealeaf/Code_Local/1_Daily_Code/노정석/main.py

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
