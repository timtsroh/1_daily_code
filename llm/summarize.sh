#!/bin/bash
# LLM 대시보드의 [요약] 큐를 처리하는 로컬 워커.
#
# 흐름:
#   1) https://adb1.vercel.app/api/config → config.llm.pending 배열 읽기
#   2) llm.json 에서 대상 URL 들에 "요약대상": "Y" 마킹 (진행 전)
#   3) 각 URL 에 대해 claude -p "..." 실행 (/tech_blog 스킬 규칙 적용)
#   4) 성공한 URL 은 llm.json 에 "요약완료": "Y" + "요약완료_at" 마킹
#   5) KV pending 제거
#   6) llm.json 을 adb1 repo 로 push
set -uo pipefail
export PYTHONIOENCODING=utf-8

ADB1_REPO="C:/Code_Local/GitHub/adb1"
LLM_JSON="$ADB1_REPO/llm/data/llm.json"
LOG_DIR="C:/Code_Local/1_Daily_Code/llm/logs"
LOG="$LOG_DIR/summarize_$(date +%Y%m%d).log"
PY=python
CONFIG_URL="https://adb1.vercel.app/api/config"
OBSIDIAN_FOLDER="C:/Obsidian/Sync1/03 Sources/6 Tech Blog"
SECTION="llm"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== llm_summarize start ==="

PENDING_JSON=$("$PY" -c "
import sys, json, urllib.request
try:
    with urllib.request.urlopen('$CONFIG_URL', timeout=10) as r:
        j = json.load(r)
    if not j.get('configured'):
        print('[]'); sys.exit(0)
    n = (j.get('config') or {}).get('$SECTION') or {}
    print(json.dumps(n.get('pending') or []))
except Exception as e:
    print('[]', file=sys.stderr)
    print(f'KV read failed: {e}', file=sys.stderr)
    sys.exit(0)
" 2>>"$LOG")

COUNT=$("$PY" -c "import json; print(len(json.loads('''$PENDING_JSON''')))" 2>/dev/null || echo 0)
if [ "$COUNT" = "0" ]; then
    log "  → 대기 중인 URL 없음, 종료"
    log "=== llm_summarize done ==="
    exit 0
fi
log "  → 대기 URL: ${COUNT}개"

PROCESSED_FILE="$LOG_DIR/.processed_$$.json"
: > "$PROCESSED_FILE"
"$PY" << PYEOF 2>&1 | tee -a "$LOG"
import json, subprocess, sys, os
from datetime import date
from pathlib import Path

pending = json.loads('''$PENDING_JSON''')
llm_path = Path(r"$LLM_JSON")
payload = json.loads(llm_path.read_text(encoding='utf-8'))
articles = payload.get('articles') or []
url_to_article = {a['url']: a for a in articles if a.get('url')}

for url in pending:
    if url in url_to_article:
        url_to_article[url]['요약대상'] = 'Y'
llm_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[mark] 요약대상=Y x {sum(1 for u in pending if u in url_to_article)}', flush=True)

processed_urls = []
today = date.today().isoformat()

def flush_marker():
    with open(r"$PROCESSED_FILE", 'w', encoding='utf-8') as f:
        json.dump(processed_urls, f)

flush_marker()

for url in pending:
    art = url_to_article.get(url) or {}
    source = art.get('source') or 'LLM'
    title = art.get('title') or ''
    posted = art.get('posted') or today
    yymmdd = posted.replace('-', '')[2:8]

    prompt = (
        f"아래 AI/LLM 리서치 노트에 /tech_blog 스킬의 요약·번역 규칙(한국어 3-bullet 요약 + 본문 한글 완역)을 "
        f"적용해서 Obsidian 노트로 저장해라.\n\n"
        f"[대상 아티클]\n"
        f"- URL: {url}\n"
        f"- 소스: {source}\n"
        f"- 원문 제목: {title}\n"
        f"- 발행일: {posted}\n\n"
        f"[저장 경로 - 반드시 이 폴더]\n"
        f"  {r'$OBSIDIAN_FOLDER'}/\n"
        f"[파일명 형식]\n"
        f"  {yymmdd}_{source}_<제목>.md\n"
        f"  * 제목의 특수문자(: ? / \\\\ | < > \" *) 제거\n\n"
        f"[노트 구성 - /tech_blog 스킬 SKILL.md 형식 그대로]\n"
        f"- YAML 프런트매터 (title/author/source/url/date/노트생성일자/tags)\n"
        f"- ## 요약 (한국어 3불릿)\n"
        f"- ## 본문 (한글 번역, 전문 완역, 문단·소제목·리스트 구조 유지)\n\n"
        f"[규칙]\n"
        f"- 달러 표기: \$Xbn / \$Xmn / \$Xtn (한글식 억/조 금지)\n"
        f"- WebFetch 로 본문 확보 → 곧바로 Write 도구로 노트 저장.\n"
    )
    print(f'[tech_blog] {url}', flush=True)
    r = subprocess.run(
        ['claude', '--dangerously-skip-permissions', '-p', prompt],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1500
    )
    if r.stdout:
        sys.stdout.write(r.stdout[:500] + '\n')
        sys.stdout.flush()
    if r.returncode != 0:
        print(f'  -> tech_blog exit={r.returncode}, stderr={(r.stderr or "")[:200]}', flush=True)
        continue
    if url in url_to_article:
        url_to_article[url]['요약완료'] = 'Y'
        url_to_article[url]['요약완료_at'] = today
        llm_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    processed_urls.append(url)
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
    log "=== llm_summarize done (no changes) ==="
    exit 0
fi

"$PY" << PYEOF 2>&1 | tee -a "$LOG"
import json, urllib.request

processed = set(json.loads('''$PROCESSED'''))
try:
    with urllib.request.urlopen('$CONFIG_URL', timeout=10) as r:
        j = json.load(r)
    if not j.get('configured'):
        print('KV not configured, skip clear')
        raise SystemExit(0)
    n = (j.get('config') or {}).get('$SECTION') or {}
    new_pending = [u for u in (n.get('pending') or []) if u not in processed]
    n['pending'] = new_pending
    req = urllib.request.Request(
        '$CONFIG_URL',
        data=json.dumps({'section': '$SECTION', 'data': n}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
    print(f'KV pending updated: {len(new_pending)} remaining')
except Exception as e:
    print(f'KV clear failed: {e}')
PYEOF

cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- llm/data/llm.json 2>/dev/null; then
    log "  → llm.json 변경 없음, push 생략"
else
    log "  → llm.json 변경 감지, commit & push"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        add llm/data/llm.json
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(llm): mark ${PROCESSED_COUNT} notes summarized $(date +%Y-%m-%d)" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
        2>&1 | tee -a "$LOG"
    git push origin main 2>&1 | tee -a "$LOG"
fi

log "=== llm_summarize done (processed=${PROCESSED_COUNT}) ==="
exit 0
