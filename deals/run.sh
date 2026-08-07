#!/bin/bash
# Daily step: rebuild deals/data/deals.json from Google Sheets (blog Destination=deals + deals tab),
# then commit & push to the adb1 repo so Vercel redeploys.
#
# Runs AFTER blog_listing so `deals` tab is already up to date.
# Pattern mirrors 1_Daily_Code/article/run.sh.
set -uo pipefail

ROOT="C:/Code_Local/2_Dash"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/deals/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== deals start ==="

cd "$ROOT" || { log "FATAL: $ROOT 없음"; exit 1; }

log "step1: deals.collectors.build"
"$PY" -m deals.collectors.build 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: build.py exit=$PY_EXIT"
    log "=== deals done (build failed) ==="
    exit 0
fi

mkdir -p "$ADB1_REPO/deals/data"
cp "$ROOT/deals/data/deals.json" "$ADB1_REPO/deals/data/deals.json"

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- deals/data/deals.json 2>/dev/null; then
    log "  → deals.json 변경 없음, push 생략"
    log "=== deals done ==="
    exit 0
fi

log "  → deals.json 변경 감지, commit & push"
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    add deals/data/deals.json
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    commit -m "chore(deals): daily deals snapshot $(date +%Y-%m-%d)" \
    --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
    2>&1 | tee -a "$LOG"
git fetch origin -q
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    pull --rebase --autostash origin main 2>&1 | tee -a "$LOG"
git push origin main 2>&1 | tee -a "$LOG"
PUSH_EXIT=${PIPESTATUS[0]}
if [ "$PUSH_EXIT" -ne 0 ]; then
    log "ERROR: git push exit=$PUSH_EXIT"
fi

log "=== deals done ==="
exit 0
