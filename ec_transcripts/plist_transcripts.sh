#!/bin/bash
# Windows: plist_day.sh의 ec_transcripts 스텝 (매일 00:05 배치, plist_day.sh 안에서
# run_with_timeout "ec_transcripts" 로 직접 호출) — 별도 스케줄러 트리거 없음.
# (원래 macOS launchd 시절 매일 17:00 KST 단독 실행이었음. tmux 래퍼는 폐기됨.)
#
# 1) ec_cal/collectors/transcripts.py 실행 → earnings.json + EC 시트 F열 + newly_found.json
# 2) newly_found.json이 비어있지 않으면 Claude Code `/ec` 스킬 호출 (Obsidian 노트 생성)
# 3) ec_cal/collectors/obsidian_backfill.py 실행 → Obsidian YAML source URL → earnings.json + EC 시트 반영
# 4) adb1 repo로 변경사항 commit & push (Vercel 재배포)
set -uo pipefail

# Motley Fool rate-limit(429) 대응 — 티커당 URL 시도 횟수 축소 (기본 40 → 5).
# 40회 * 8초 sleep = 티커당 최대 5분+ 지연을 회피. 여전히 rate-limit 시 다음 티커로 fail-fast.
export TRANSCRIPT_FINDER_MAX_ATTEMPTS=5

ROOT="C:/Code_Local/2_Dash/ec_cal"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/ec_transcripts/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=python
CLAUDE=claude
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== ec_transcripts start ==="

cd "$ROOT" || { log "FATAL: $ROOT 없음"; exit 1; }

# 1) transcripts.py 실행
log "step1: collectors/transcripts.py"
"$PY" -m collectors.transcripts 2>&1 | tee -a "$LOG"
PY_EXIT=${PIPESTATUS[0]}
if [ "$PY_EXIT" -ne 0 ]; then
    log "ERROR: transcripts.py exit=$PY_EXIT"
fi

NEW_JSON="$ROOT/data/newly_found.json"

# 2) newly_found.json 이 비어있지 않으면 /ec 호출 (Obsidian 노트 생성)
log "step2: /ec 자동 호출 여부 판단"
if [ ! -f "$NEW_JSON" ]; then
    log "  → newly_found.json 없음, /ec 생략"
else
    # Windows Python 기본 cp949 → 한글 JSON UnicodeDecodeError. encoding='utf-8' 명시.
    COUNT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1], encoding='utf-8'))))" "$NEW_JSON" 2>>"$LOG")
    if [ -z "$COUNT" ]; then
        log "  → COUNT 계산 실패 (python 오류) — /ec 생략"
    elif [ "$COUNT" = "0" ]; then
        log "  → 신규 트랜스크립트 없음, /ec 생략"
    else
        log "  → 신규 $COUNT건 → /ec 스킬 호출"
        ARGS=$("$PY" -c '
import json, sys
items = json.load(open(sys.argv[1], encoding="utf-8"))
lines = []
for it in items:
    url = it.get("script_url") or "(URL 미확보 — Obsidian 노트 생성만)"
    lines.append(f"- {it[\"name\"]} ({it[\"ticker\"] or \"-\"}, {it[\"market\"]}, last={it[\"last_date\"]}) → {url}")
print("다음 신규 트랜스크립트들을 /ec 패턴으로 처리해줘. 각 종목별 노트를 Obsidian C:/Obsidian/Sync1/03 Sources/4 Earnings Call/ 에 저장. 이미 같은 파일이 존재하면 건너뛰기.\n\n" + "\n".join(lines))
' "$NEW_JSON" 2>>"$LOG")
        log "  → claude --dangerously-skip-permissions -p \"/ec ...\" 실행 (MSYS_NO_PATHCONV=1)"
        # Git Bash(MSYS)는 -p "/ec ..." 인자를 C:/Program Files/Git/ec로 경로 변환한다.
        # MSYS_NO_PATHCONV=1 로 이 명령 한 줄만 자동 변환 비활성화.
        MSYS_NO_PATHCONV=1 "$CLAUDE" --dangerously-skip-permissions -p "/ec $ARGS" 2>&1 | tee -a "$LOG"
        EC_EXIT=${PIPESTATUS[0]}
        log "  → /ec exit=$EC_EXIT"
    fi
fi

# 3) Obsidian → earnings.json + EC 시트 backfill (실제 트랜스크립트 URL 은 YAML source 에서)
log "step3: Obsidian backfill"
"$PY" -m collectors.obsidian_backfill 2>&1 | tee -a "$LOG"
BF_EXIT=${PIPESTATUS[0]}
log "  → backfill exit=$BF_EXIT"

# 4) adb1 repo로 sync & push (Vercel 재배포)
log "step4: adb1 repo sync"
mkdir -p "$ADB1_REPO/ec_cal/data"
cp "$ROOT/data/earnings.json" "$ADB1_REPO/ec_cal/data/earnings.json"

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
# 이전 실행이 중단되어 rebase-merge 잔재가 있으면 정리 (그대로 두면 다음 pull 실패).
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
    log "  → 이전 rebase 잔재 감지 → git rebase --abort"
    git rebase --abort 2>&1 | tee -a "$LOG" || true
fi
if ! git diff --quiet -- ec_cal/data/earnings.json 2>/dev/null; then
    log "  → earnings.json 변경 감지, commit & push"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        add ec_cal/data/earnings.json
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(ec_cal): daily transcript URLs $(date +%Y-%m-%d)" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
        2>&1 | tee -a "$LOG"
    log "  → git pull --rebase origin main"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        pull --rebase origin main 2>&1 | tee -a "$LOG"
    git push origin main 2>&1 | tee -a "$LOG"
else
    log "  → earnings.json 변경 없음, push 생략"
fi

log "=== ec_transcripts done ==="
exit 0
