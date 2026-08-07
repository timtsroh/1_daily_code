#!/bin/bash
# Daily step: rebuild youtube/data/videos.json from Google Sheets (yt1 + yt2),
# then commit & push to the adb1 repo so Vercel redeploys with today's videos.
#
# Runs AFTER tech_yt_listing so yt2 is already up to date.
#
# Pattern mirrors ec_transcripts/plist_transcripts.sh: collector lives in
# 2_Dash, but commits are staged from a separate GitHub/adb1 checkout to keep
# push authorship (timtsroh) clean for Vercel.
set -uo pipefail

ROOT="C:/Code_Local/2_Dash"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/youtube/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== youtube start ==="

cd "$ROOT" || { log "FATAL: $ROOT 없음"; exit 1; }

# 1) Collector 실행: yt1 + yt2 → youtube/data/videos.json
log "step1: youtube.collectors.build"
"$PY" -m youtube.collectors.build 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: build.py exit=$PY_EXIT"
    log "=== youtube done (build failed) ==="
    exit 0  # 상위 plist_day.sh는 continue-on-error
fi

# 2) 결과를 adb1 repo로 복사
mkdir -p "$ADB1_REPO/youtube/data"
cp "$ROOT/youtube/data/videos.json" "$ADB1_REPO/youtube/data/videos.json"

# 3) commit & push (변경 시에만)
cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- youtube/data/videos.json 2>/dev/null; then
    log "  → videos.json 변경 없음, push 생략"
    log "=== youtube done ==="
    exit 0
fi

log "  → videos.json 변경 감지, commit & push"
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    add youtube/data/videos.json
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    commit -m "chore(youtube): daily yt2 snapshot $(date +%Y-%m-%d)" \
    --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
    2>&1 | tee -a "$LOG"
git push origin main 2>&1 | tee -a "$LOG"
PUSH_EXIT=${PIPESTATUS[0]}
if [ "$PUSH_EXIT" -ne 0 ]; then
    log "ERROR: git push exit=$PUSH_EXIT"
fi

log "=== youtube done ==="
exit 0
