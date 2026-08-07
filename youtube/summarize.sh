#!/bin/bash
# Youtube 대시보드의 [요약] 큐를 처리하는 로컬 워커.
#
# 흐름:
#   1) https://adb1.vercel.app/api/config → config.youtube.pending 배열 읽기
#   2) videos.json 에서 대상 URL 들에 "요약대상": "Y" 마킹 (진행 전)
#   3) 각 URL 에 대해 claude -p "/yt <url>" 실행
#   4) 성공한 URL 은 videos.json 에 "요약완료": "Y" + "요약완료_at" 마킹
#   5) KV pending 제거
#   6) Google Sheets yt2 시트 H열(Obisidan) 에 "v" 마킹 (URL → row 자동 매칭)
#   7) videos.json 을 adb1 repo 로 push (Vercel 재배포 → 대시보드 (완료) 표시)
set -uo pipefail
export PYTHONIOENCODING=utf-8  # Windows cp949 대비: 한글 print() 예외 방지

ROOT="C:/Code_Local/2_Dash"
ADB1_REPO="C:/Code_Local/GitHub/adb1"
LOG_DIR="C:/Code_Local/1_Daily_Code/youtube/logs"
LOG="$LOG_DIR/summarize_$(date +%Y%m%d).log"
PY=python
CONFIG_URL="https://adb1.vercel.app/api/config"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== youtube_summarize start ==="

# 1) KV 에서 pending URL 목록 읽기
PENDING_JSON=$("$PY" -c "
import sys, json, urllib.request
try:
    with urllib.request.urlopen('$CONFIG_URL', timeout=10) as r:
        j = json.load(r)
    if not j.get('configured'):
        print('[]'); sys.exit(0)
    y = (j.get('config') or {}).get('youtube') or {}
    print(json.dumps(y.get('pending') or []))
except Exception as e:
    print('[]', file=sys.stderr)
    print(f'KV read failed: {e}', file=sys.stderr)
    sys.exit(0)
" 2>>"$LOG")

COUNT=$("$PY" -c "import json; print(len(json.loads('''$PENDING_JSON''')))" 2>/dev/null || echo 0)
if [ "$COUNT" = "0" ]; then
    log "  → 대기 중인 URL 없음, 종료"
    log "=== youtube_summarize done ==="
    exit 0
fi
log "  → 대기 URL: ${COUNT}개"

# 2-4) videos.json 요약대상 마킹 + /yt 실행 + 요약완료 마킹
# PROCESSED marker 는 stdout parsing 대신 임시 파일로 전달 (cp949·pipe 이슈 회피)
# 주의: Git Bash mktemp 은 /tmp/... POSIX 경로를 리턴하는데, heredoc 안에 interpolate 되면
# path 변환이 안 되어 Windows Python 이 C:\tmp\... 로 resolve 함. LOG_DIR 밑 Windows-native 경로 사용.
PROCESSED_FILE="$LOG_DIR/.processed_$$.json"
: > "$PROCESSED_FILE"
"$PY" << PYEOF 2>&1 | tee -a "$LOG"
import json, subprocess, sys, os
from datetime import date
from pathlib import Path

pending = json.loads('''$PENDING_JSON''')
videos_path = Path(r"$ROOT/youtube/data/videos.json")
payload = json.loads(videos_path.read_text(encoding='utf-8'))
videos = payload.get('videos') or []
url_to_video = {v['url']: v for v in videos if v.get('url')}

# 진행 전: 요약대상 = "Y" 일괄 마킹
for url in pending:
    if url in url_to_video:
        url_to_video[url]['요약대상'] = 'Y'
videos_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[mark] 요약대상=Y x {sum(1 for u in pending if u in url_to_video)}', flush=True)

processed_urls = []
today = date.today().isoformat()

def flush_marker():
    with open(r"$PROCESSED_FILE", 'w', encoding='utf-8') as f:
        json.dump(processed_urls, f)

# 중간 예외 대비: 시작 시점에도 빈 배열 미리 기록
flush_marker()

for url in pending:
    print(f'[yt] {url}', flush=True)
    r = subprocess.run(
        ['claude', '--dangerously-skip-permissions', '-p', f'/yt {url}'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1200
    )
    if r.stdout:
        sys.stdout.write(r.stdout[:500] + '\n')
        sys.stdout.flush()
    if r.returncode != 0:
        print(f'  -> /yt exit={r.returncode}, stderr={(r.stderr or "")[:200]}', flush=True)
        continue
    if url in url_to_video:
        url_to_video[url]['요약완료'] = 'Y'
        url_to_video[url]['요약완료_at'] = today
        # 각 성공마다 즉시 저장 (중간 실패에도 진행분 보존)
        videos_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    processed_urls.append(url)
    # 각 성공 즉시 marker 갱신 (중단되어도 완료분 보존)
    flush_marker()

flush_marker()
print(f'[done] processed={len(processed_urls)}', flush=True)
PYEOF

PROCESSED=$(cat "$PROCESSED_FILE" 2>/dev/null || echo '[]')
rm -f "$PROCESSED_FILE"
if [ -z "$PROCESSED" ]; then PROCESSED="[]"; fi
PROCESSED_COUNT=$("$PY" -c "import json; print(len(json.loads('''$PROCESSED''')))" 2>/dev/null || echo 0)
log "  → 처리 완료: ${PROCESSED_COUNT}개"

if [ "$PROCESSED_COUNT" = "0" ]; then
    log "=== youtube_summarize done (no changes) ==="
    exit 0
fi

# 5) KV pending 에서 처리 완료 URL 제거
"$PY" << PYEOF 2>&1 | tee -a "$LOG"
import json, urllib.request

processed = set(json.loads('''$PROCESSED'''))
try:
    with urllib.request.urlopen('$CONFIG_URL', timeout=10) as r:
        j = json.load(r)
    if not j.get('configured'):
        print('KV not configured, skip clear')
        raise SystemExit(0)
    y = (j.get('config') or {}).get('youtube') or {}
    new_pending = [u for u in (y.get('pending') or []) if u not in processed]
    y['pending'] = new_pending
    req = urllib.request.Request(
        '$CONFIG_URL',
        data=json.dumps({'section': 'youtube', 'data': y}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
    print(f'KV pending updated: {len(new_pending)} remaining')
except Exception as e:
    print(f'KV clear failed: {e}')
PYEOF

# 6) Google Sheets yt2!H 마킹 — 처리 완료된 URL 들에 "v" 표시
log "  → yt2 시트 H열 마킹"
echo "$PROCESSED" | "$PY" C:/Users/DELL/.claude/skills/tech_yt_script/scripts/mark_done_by_url.py 2>&1 | tee -a "$LOG"

# 7) videos.json 을 adb1 repo 로 복사 + commit + push
mkdir -p "$ADB1_REPO/youtube/data"
cp "$ROOT/youtube/data/videos.json" "$ADB1_REPO/youtube/data/videos.json"

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- youtube/data/videos.json 2>/dev/null; then
    log "  → videos.json 변경 없음, push 생략"
else
    log "  → videos.json 변경 감지, commit & push"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        add youtube/data/videos.json
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(youtube): mark ${PROCESSED_COUNT} videos summarized $(date +%Y-%m-%d)" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
        2>&1 | tee -a "$LOG"
    git push origin main 2>&1 | tee -a "$LOG"
fi

log "=== youtube_summarize done (processed=${PROCESSED_COUNT}) ==="
exit 0
