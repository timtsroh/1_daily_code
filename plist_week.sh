#!/bin/bash
set -euo pipefail

# 매주 토요일 05:00 launchd 진입점 (com.tealeaf.saturday.plist)
# 1) move.sh: 0 inbox/ 의 2일 이상 지난 daily_*/news_*/todo_* → 8 moved/ 이동
# 2) /compile_week Claude 스킬: 이번 주(토~금) 신규 포스팅·작업 → 위클리 노트

LOG_DIR="/Users/tealeaf/Code_Local/1_Daily_Code/move/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting weekly run..."

/bin/bash /Users/tealeaf/Code_Local/1_Daily_Code/move/move.sh

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Running /compile_week skill..."

/Users/tealeaf/.local/bin/claude --dangerously-skip-permissions -p "/compile_week"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
