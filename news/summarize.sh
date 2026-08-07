#!/bin/bash
# News 대시보드의 [요약] 큐를 처리하는 로컬 워커.
#
# 흐름:
#   1) https://adb1.vercel.app/api/config → config.news.pending 배열 읽기
#   2) news.json 에서 대상 URL 들에 "요약대상": "Y" 마킹 (진행 전)
#   3) 각 URL 에 대해 claude -p "..." 실행:
#      /tech_blog 스킬의 요약·번역 규칙(3-bullet 한글 요약 + 본문 완역)을
#      뉴스 기사에 적용하되, 저장 폴더만 03 Sources/7 Tech News 로 지정
#   4) 성공한 URL 은 news.json 에 "요약완료": "Y" + "요약완료_at" 마킹
#   5) KV pending 제거
#   6) news.json 을 adb1 repo 로 push (Vercel 재배포 → 대시보드 (완료) 표시)
set -uo pipefail
export PYTHONIOENCODING=utf-8  # Windows cp949 대비: 한글 print() 예외 방지

ADB1_REPO="C:/Code_Local/GitHub/adb1"
NEWS_JSON="$ADB1_REPO/news/data/news.json"
LOG_DIR="C:/Code_Local/1_Daily_Code/news/logs"
LOG="$LOG_DIR/summarize_$(date +%Y%m%d).log"
PY=python
CONFIG_URL="https://adb1.vercel.app/api/config"
OBSIDIAN_FOLDER="C:/Obsidian/Sync1/03 Sources/7 Tech News"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== news_summarize start ==="

# 1) KV 에서 pending URL 목록 읽기
PENDING_JSON=$("$PY" -c "
import sys, json, urllib.request
try:
    with urllib.request.urlopen('$CONFIG_URL', timeout=10) as r:
        j = json.load(r)
    if not j.get('configured'):
        print('[]'); sys.exit(0)
    n = (j.get('config') or {}).get('news') or {}
    print(json.dumps(n.get('pending') or []))
except Exception as e:
    print('[]', file=sys.stderr)
    print(f'KV read failed: {e}', file=sys.stderr)
    sys.exit(0)
" 2>>"$LOG")

COUNT=$("$PY" -c "import json; print(len(json.loads('''$PENDING_JSON''')))" 2>/dev/null || echo 0)
if [ "$COUNT" = "0" ]; then
    log "  → 대기 중인 URL 없음, 종료"
    log "=== news_summarize done ==="
    exit 0
fi
log "  → 대기 URL: ${COUNT}개"

# 2-4) news.json 요약대상 마킹 + /tech_blog 규칙 적용 실행 + 요약완료 마킹
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
news_path = Path(r"$NEWS_JSON")
payload = json.loads(news_path.read_text(encoding='utf-8'))
articles = payload.get('articles') or []
url_to_article = {a['url']: a for a in articles if a.get('url')}

# 진행 전: 요약대상 = "Y" 일괄 마킹
for url in pending:
    if url in url_to_article:
        url_to_article[url]['요약대상'] = 'Y'
news_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[mark] 요약대상=Y x {sum(1 for u in pending if u in url_to_article)}', flush=True)

processed_urls = []
today = date.today().isoformat()

def flush_marker():
    with open(r"$PROCESSED_FILE", 'w', encoding='utf-8') as f:
        json.dump(processed_urls, f)

# 중간 예외 대비: 시작 시점에도 빈 배열 미리 기록
flush_marker()

for url in pending:
    art = url_to_article.get(url) or {}
    source = art.get('source') or '뉴스'
    title = art.get('title') or ''
    posted = art.get('posted') or today
    yymmdd = posted.replace('-', '')[2:8]  # YYYY-MM-DD → YYMMDD

    prompt = (
        f"아래 뉴스 기사에 /tech_blog 스킬의 요약·번역 규칙(한국어 3-bullet 요약 + 본문 한글 완역)을 "
        f"적용해서 Obsidian 노트로 저장해라.\n\n"
        f"[대상 기사]\n"
        f"- URL: {url}\n"
        f"- 매체: {source}\n"
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
        f"- paywall(FT/NYT/WSJ) 이면 접근 가능한 부분까지 처리하고 하단에 '(이하 유료 콘텐츠)' 표시\n"
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
        news_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
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
    log "=== news_summarize done (no changes) ==="
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
    n = (j.get('config') or {}).get('news') or {}
    new_pending = [u for u in (n.get('pending') or []) if u not in processed]
    n['pending'] = new_pending
    req = urllib.request.Request(
        '$CONFIG_URL',
        data=json.dumps({'section': 'news', 'data': n}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
    print(f'KV pending updated: {len(new_pending)} remaining')
except Exception as e:
    print(f'KV clear failed: {e}')
PYEOF

# 6) news.json 을 adb1 repo 로 commit + push (이미 $NEWS_JSON 이 adb1 안에 있음)
cd "$ADB1_REPO" || { log "FATAL: $ADB1_REPO 없음"; exit 1; }
if git diff --quiet -- news/data/news.json 2>/dev/null; then
    log "  → news.json 변경 없음, push 생략"
else
    log "  → news.json 변경 감지, commit & push"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        add news/data/news.json
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(news): mark ${PROCESSED_COUNT} articles summarized $(date +%Y-%m-%d)" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>" \
        2>&1 | tee -a "$LOG"
    git push origin main 2>&1 | tee -a "$LOG"
fi

log "=== news_summarize done (processed=${PROCESSED_COUNT}) ==="
exit 0
