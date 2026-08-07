#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting blog_listing..."

# 기본: 어제 하루. 인자 그대로 넘김 (예: --month 2026-07, --since ...)
python C:/Code_Local/1_Daily_Code/blog_listing/main.py "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
