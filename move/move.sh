#!/bin/bash
set -euo pipefail

# 02 Daily/1 day/ 에서 5일 이상 지난 daily_*, news_*, todo_* 파일을 02 Daily/3 moved/ 로 이동
# 매주 토요일 05:00 launchd로 실행 (plist_week.sh에서 호출)

VAULT="C:/Users/DELL/Obsidian/Sync1"
INBOX="$VAULT/02 Daily/1 day"
MOVED_DIR="$VAULT/02 Daily/3 moved"
LOG="C:/Code_Local/launchd_output.log"

mkdir -p "$MOVED_DIR"

# 파일명에서 날짜(YYMMDD)를 추출하여 5일 이상 경과 여부 판단
# mtime 기반이 아닌 파일명 기반으로 판단 (Sync 시 mtime이 변경될 수 있음)
CUTOFF=$(date -v-5d +%y%m%d)

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === weekly === Starting inbox archive (cutoff: $CUTOFF)" >> "$LOG"

MOVED=0

for f in "$INBOX"/daily_*.md "$INBOX"/news_*.md "$INBOX"/todo_*.md; do
    [ -f "$f" ] || continue

    # 파일명에서 YYMMDD 추출 (예: daily_260403.md → 260403)
    basename=$(basename "$f")
    file_date=$(echo "$basename" | grep -oE '[0-9]{6}' | head -1)

    [ -z "$file_date" ] && continue

    # YYMMDD 비교 (문자열 비교로 충분)
    if [ "$file_date" -lt "$CUTOFF" ] 2>/dev/null; then
        mv "$f" "$MOVED_DIR/"
        echo "  moved: $basename" >> "$LOG"
        MOVED=$((MOVED + 1))
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === weekly === Done. $MOVED files moved to 02 Daily/3 moved/" >> "$LOG"
