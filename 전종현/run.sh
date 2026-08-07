#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting 전종현 skill..."

python C:/Code_Local/1_Daily_Code/전종현/main.py

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
