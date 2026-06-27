#!/bin/bash
set -euo pipefail

# todo 수집 — fetch_feed.py + write_note.py 순차 실행
# 텔레그램 @atomtodo 어제 메시지 → 0 inbox/todo_YYYYMM.md 월별 노트의
# `# YYYY-MM-DD` 섹션으로 누적 (해당 날짜 섹션이 이미 있으면 덮어쓴다)
#
# 사용:
#   bash todo/run.sh              # 어제(KST) 기준
#   bash todo/run.sh 260424       # 특정 날짜
#
# plist_day.sh의 todo 작업으로 매일 자동 실행됨 (compile_day보다 먼저)

SCRIPTS="/Users/tealeaf/Code_Local/1_Daily_Code/todo"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting todo fetch..."
/usr/local/bin/python3 "$SCRIPTS/fetch_feed.py" "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting todo write..."
/usr/local/bin/python3 "$SCRIPTS/write_note.py"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] todo done."
