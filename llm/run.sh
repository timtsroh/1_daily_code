#!/bin/bash
# Daily step: rebuild llm/data/llm.json from Google Sheets (blog Category=LLM + LLM tab),
# then commit & push to the adb1 repo so Vercel redeploys.
set -uo pipefail

ROOT="C:/Code_Local/2_Dash"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/llm/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== llm start ==="

cd "$ROOT" || { log "FATAL: $ROOT 없음"; exit 1; }

log "step1: llm.collectors.build"
"$PY" -m llm.collectors.build 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: build.py exit=$PY_EXIT"
    log "=== llm done (build failed) ==="
    exit 0
fi

mkdir -p "$ADB1_REPO/llm/data"
cp "$ROOT/llm/data/llm.json" "$ADB1_REPO/llm/data/llm.json"

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- llm/data/llm.json 2>/dev/null; then
    log "  → llm.json 변경 없음, push 생략"
    log "=== llm done ==="
    exit 0
fi

log "  → llm.json 변경 감지, commit & push"
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    add llm/data/llm.json
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    commit -m "chore(llm): daily llm snapshot $(date +%Y-%m-%d)" \
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

log "=== llm done ==="
exit 0
