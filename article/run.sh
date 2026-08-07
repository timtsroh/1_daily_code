#!/bin/bash
# Daily step: rebuild article/data/articles.json from Google Sheets (blog + article),
# then commit & push to the adb1 repo so Vercel redeploys.
#
# Runs AFTER blog_listing so `article` tab is already up to date.
#
# Pattern mirrors 1_Daily_Code/youtube/run.sh: collector lives in 2_Dash,
# commits are staged from a separate GitHub/adb1 checkout for author cleanliness.
set -uo pipefail

ROOT="C:/Code_Local/2_Dash"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/article/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== article start ==="

cd "$ROOT" || { log "FATAL: $ROOT 없음"; exit 1; }

# 1) Collector: blog + article 시트 → article/data/articles.json
log "step1: article.collectors.build"
"$PY" -m article.collectors.build 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: build.py exit=$PY_EXIT"
    log "=== article done (build failed) ==="
    exit 0  # 상위 plist_day.sh 는 continue-on-error
fi

# 2) 결과를 adb1 repo로 복사
mkdir -p "$ADB1_REPO/article/data"
cp "$ROOT/article/data/articles.json" "$ADB1_REPO/article/data/articles.json"

# 3) commit & push (변경 시에만)
cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- article/data/articles.json 2>/dev/null; then
    log "  → articles.json 변경 없음, push 생략"
    log "=== article done ==="
    exit 0
fi

log "  → articles.json 변경 감지, commit & push"
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    add article/data/articles.json
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    commit -m "chore(article): daily article snapshot $(date +%Y-%m-%d)" \
    --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
    2>&1 | tee -a "$LOG"
# 다른 대시보드 자동화가 origin 을 앞서가므로 push 전 rebase 로 동기화 (macro/dart_shiporder 와 동일 패턴)
# --autostash: user WIP 가 있어도 배치가 죽지 않음
git fetch origin -q
git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
    pull --rebase --autostash origin main 2>&1 | tee -a "$LOG"
git push origin main 2>&1 | tee -a "$LOG"
PUSH_EXIT=${PIPESTATUS[0]}
if [ "$PUSH_EXIT" -ne 0 ]; then
    log "ERROR: git push exit=$PUSH_EXIT"
fi

log "=== article done ==="
exit 0
