#!/bin/bash
# Daily step: rebuild report/data/reports.json from Google Sheets nrd tab + Naver Finance,
# then commit & push to the adb1 repo so Vercel redeploys.
set -uo pipefail
export PYTHONIOENCODING=utf-8

ROOT="C:/Code_Local/2_Dash"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/report/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== report start ==="

cd "$ROOT" || { log "FATAL: $ROOT 없음"; exit 1; }

log "step1: report.collectors.build"
"$PY" -m report.collectors.build 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: build.py exit=$PY_EXIT"
    log "=== report done (build failed) ==="
    exit 0
fi

mkdir -p "$ADB1_REPO/report/data"
cp "$ROOT/report/data/reports.json" "$ADB1_REPO/report/data/reports.json"

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- report/data/reports.json 2>/dev/null; then
    log "  → reports.json 변경 없음, push 생략"
    log "=== report done ==="
    exit 0
fi

log "  → reports.json 변경 감지, commit & push"
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    add report/data/reports.json
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    commit -m "chore(report): daily report snapshot $(date +%Y-%m-%d)" \
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

log "=== report done ==="
exit 0
