#!/bin/bash
set -euo pipefail

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting 노정석 skill..."

claude --dangerously-skip-permissions -p "/노정석"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
