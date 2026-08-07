#!/bin/bash
set -euo pipefail

# inbox_sort — Obsidian 0 inbox 정리
#   1) 프런트매터 없는 노트에 파일명 기반 프런트매터 추가
#   2) call_ / call2_ / meeting_ / meeting2_ 접두사 파일을
#      01 Work/A1 call · A3 call2 · A2 meeting · A4 meeting2 폴더로 이동
#
# plist_day.sh 에서 매일 00:05 자동 실행.

SCRIPT_DIR="C:/Code_Local/1_Daily_Code/inbox_sort"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting inbox_sort..."
python "$SCRIPT_DIR/sort_inbox.py"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] inbox_sort done."
