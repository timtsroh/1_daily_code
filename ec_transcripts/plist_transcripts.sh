#!/bin/bash
# 매일 17:00 KST에 launchd가 실행하는 ec_transcripts 본체.
#
# 1) ec_cal/collectors/transcripts.py 실행 → earnings.json + EC 시트 F열 + newly_found.json
# 2) adb1 repo로 변경사항 commit & push (Vercel 재배포)
# 3) newly_found.json이 비어있지 않으면 Claude Code `/ec` 스킬 호출
set -uo pipefail

ROOT="/Users/tealeaf/Code_Local/2_Dash/ec_cal"
ADB1_REPO="/Users/tealeaf/Code_Local/GitHub/adb1"
LOG_DIR="/Users/tealeaf/Code_Local/1_Daily_Code/ec_transcripts/logs"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
PY=/usr/local/bin/python3
CLAUDE=/Users/tealeaf/.local/bin/claude
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

# 2) adb1 repo로 sync & push
log "step2: adb1 repo sync"
# 2_Dash → adb1 (earnings.json + newly_found.json)
mkdir -p "$ADB1_REPO/ec_cal/data"
cp "$ROOT/data/earnings.json" "$ADB1_REPO/ec_cal/data/earnings.json"

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if ! git diff --quiet -- ec_cal/data/earnings.json 2>/dev/null; then
    log "  → earnings.json 변경 감지, commit & push"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        add ec_cal/data/earnings.json
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(ec_cal): daily transcript URLs $(date +%Y-%m-%d)" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
        2>&1 | tee -a "$LOG"
    git push origin main 2>&1 | tee -a "$LOG"
else
    log "  → earnings.json 변경 없음, push 생략"
fi

# 3) newly_found.json이 비어있지 않으면 /ec 호출
log "step3: /ec 자동 호출 여부 판단"
cd "$ROOT" || exit 1
if [ ! -f "$NEW_JSON" ]; then
    log "  → newly_found.json 없음, /ec 생략"
    log "=== ec_transcripts done ==="
    exit 0
fi

COUNT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$NEW_JSON" 2>/dev/null || echo 0)
if [ "$COUNT" = "0" ]; then
    log "  → 신규 트랜스크립트 없음, /ec 생략"
    log "=== ec_transcripts done ==="
    exit 0
fi

log "  → 신규 $COUNT건 → /ec 스킬 호출"
# 신규 항목을 인자 문자열로 변환
ARGS=$("$PY" -c '
import json, sys
items = json.load(open(sys.argv[1]))
lines = []
for it in items:
    lines.append(f"- {it[\"name\"]} ({it[\"ticker\"] or \"-\"}, {it[\"market\"]}, last={it[\"last_date\"]}) → {it[\"script_url\"]}")
print("다음 신규 트랜스크립트들을 /ec 패턴으로 처리해줘. 각 종목별 노트를 Obsidian /Users/tealeaf/Obsidian/Sync1/03 Sources/4 Earnings Call/ 에 저장. 이미 같은 파일이 존재하면 건너뛰기.\n\n" + "\n".join(lines))
' "$NEW_JSON")

# claude -p에 인자 전달
log "  → claude --dangerously-skip-permissions -p \"/ec ...\" 실행"
"$CLAUDE" --dangerously-skip-permissions -p "/ec $ARGS" 2>&1 | tee -a "$LOG"
EC_EXIT=${PIPESTATUS[0]}
log "  → /ec exit=$EC_EXIT"

log "=== ec_transcripts done ==="
exit 0
