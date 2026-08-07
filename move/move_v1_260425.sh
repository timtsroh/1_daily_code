#!/bin/bash
set -euo pipefail

# 0 inbox/ 에서 7일 이상 지난 daily_*, news_*, todo_* 파일을 8 archive/ 로 이동
# 매주 일요일 01:00 launchd로 실행

VAULT="C:/Users/DELL/Obsidian/Sync1"
INBOX="$VAULT/0 inbox"
ARCHIVE="$VAULT/8 archive"
LOG="C:/Code_Local/launchd_output.log"

# 파일명에서 날짜(YYMMDD)를 추출하여 7일 이상 경과 여부 판단
# mtime 기반이 아닌 파일명 기반으로 판단 (iCloud 동기화 시 mtime이 변경될 수 있음)
TODAY=$(date +%y%m%d)
CUTOFF=$(date -v-7d +%y%m%d)

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === archive === Starting inbox archive (cutoff: $CUTOFF)" >> "$LOG"

MOVED=0

for f in "$INBOX"/daily_*.md "$INBOX"/news_*.md "$INBOX"/todo_*.md; do
    [ -f "$f" ] || continue

    # 파일명에서 YYMMDD 추출 (예: daily_260403.md → 260403)
    basename=$(basename "$f")
    file_date=$(echo "$basename" | grep -oE '[0-9]{6}' | head -1)

    [ -z "$file_date" ] && continue

    # YYMMDD 비교 (문자열 비교로 충분)
    if [ "$file_date" -lt "$CUTOFF" ] 2>/dev/null; then
        mv "$f" "$ARCHIVE/"
        echo "  moved: $basename" >> "$LOG"
        MOVED=$((MOVED + 1))
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === archive === Done. $MOVED files moved to 8 archive/" >> "$LOG"
