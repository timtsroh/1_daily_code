#!/bin/bash
# Daily step: rebuild news/data/news.json from Google Sheets news tab + RSS/Google News,
# then commit & push to the adb1 repo so Vercel redeploys.
#
# news 는 llm 과 달리 2_Dash 사본이 없고 adb1 안의 collectors 를 그대로 사용한다
# (build 산출물 news.json 이 이미 adb1/news/data/news.json 이므로 copy 단계 불필요).
set -uo pipefail
export PYTHONIOENCODING=utf-8

ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/news/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== news start ==="

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }

log "step1: news.collectors.build"
"$PY" -m news.collectors.build 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: build.py exit=$PY_EXIT"
    log "=== news done (build failed) ==="
    exit 0
fi

if git diff --quiet -- news/data/news.json 2>/dev/null; then
    log "  → news.json 변경 없음, push 생략"
    log "=== news done ==="
    exit 0
fi

log "  → news.json 변경 감지, commit & push"
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    add news/data/news.json
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    commit -m "chore(news): daily news snapshot $(date +%Y-%m-%d)" \
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

log "=== news done ==="
exit 0
