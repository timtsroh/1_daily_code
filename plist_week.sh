#!/bin/bash
set -euo pipefail

# 매주 토요일 05:00 launchd 진입점 (com.tealeaf.saturday.plist)
# 1) move.sh: 0 inbox/ 의 2일 이상 지난 daily_*/news_*/todo_* → 8 moved/ 이동
# 2) /compile_week Claude 스킬: 이번 주(토~금) 신규 포스팅·작업 → 위클리 노트
# 3) policy_dates: FOMC/BOK 금통위/Jackson Hole 일정 스크래핑 → ec_cal/data/policy_dates.json
# 4) lexicon learn: 사용자가 지난 주에 수정한 STT 노트를 학습 (high 자동, medium/low → #task 알림)
# 5) cleanup_snapshots: 30일 지난·미변경 스냅샷 삭제

LOG_DIR="C:/Code_Local/1_Daily_Code/move/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting weekly run..."

/bin/bash C:/Code_Local/1_Daily_Code/move/move.sh

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Running /compile_week skill..."

claude --dangerously-skip-permissions -p "/compile_week"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Running policy_dates (FOMC/BOK/Jackson Hole)..."
/bin/bash C:/Code_Local/1_Daily_Code/policy_dates/run.sh || \
  echo "[WARN] policy_dates 실패 (배치 계속)"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Running lexicon learn (--auto --report-discord)..."
# fail-safe: 실패해도 배치 전체가 죽지 않게 || true
python C:/Users/DELL/.claude/skills/lexicon/learn.py --auto --report-discord || \
  echo "[WARN] lexicon learn 실패 (배치 계속)"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Running cleanup_snapshots (30d)..."
python C:/Users/DELL/.claude/skills/_shared/cleanup_snapshots.py --days 30 || \
  echo "[WARN] cleanup_snapshots 실패 (배치 계속)"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
