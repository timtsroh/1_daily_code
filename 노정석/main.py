#!/usr/bin/env python
"""노정석 일일 파이프라인 엔트리포인트.

실행:  python main.py

흐름:
  1. KST 어제 날짜 계산
  2. Facebook 세션 파일 확인 (없으면 안내 후 exit 1)
  3. Playwright로 chester.roh 프로필 스크랩 → 어제 날짜 포스트 필터
  4. Obsidian `0 inbox/노정석_YYMM.md` 파일에 시간순 저장 (신규 or append, 중복 스킵)
  5. 요약 출력 후 exit 0 (포스트가 0건이어도 정상 종료)

치명 오류(세션 만료, Playwright 미설치 등)는 exit 1.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SESSION_FILE = 'C:/Users/DELL/.claude/fb_session.json'


def main() -> int:
    try:
        from fetch_feed import fetch_yesterday_posts
    except ImportError as e:
        print(f'[FATAL] Playwright 또는 의존성이 설치되지 않았습니다: {e}', file=sys.stderr)
        print('설치:  python -m pip install -r requirements.txt', file=sys.stderr)
        print('       python -m playwright install chromium', file=sys.stderr)
        return 1

    from note_writer import write_posts, month_note_path

    today = datetime.now(KST).date()
    yesterday = today - timedelta(days=1)
    yyyy_mm_dd = yesterday.strftime('%Y-%m-%d')
    yymm = yesterday.strftime('%y%m')

    print(f'[노정석] yesterday(KST) = {yyyy_mm_dd} (month: {yymm})')

    if not os.path.exists(SESSION_FILE):
        print(f'[FATAL] Facebook 세션 파일이 없습니다: {SESSION_FILE}', file=sys.stderr)
        print(f'터미널에서 다음 명령을 실행해 로그인하세요:', file=sys.stderr)
        print(f'  python {os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_login.py")}', file=sys.stderr)
        return 1

    try:
        posts = fetch_yesterday_posts(yesterday)
    except FileNotFoundError as e:
        print(f'[FATAL] {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'[FATAL] Playwright 스크랩 실패: {e}', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    print(f'[노정석] 수집된 포스트: {len(posts)}건')

    if not posts:
        print('[노정석] 어제 올라온 글 없음')
        # 파일을 만들지 않음 — path만 안내
        print(f'[노정석] 대상 노트 경로(미생성): {month_note_path(yesterday)}')
        return 0

    try:
        result = write_posts(posts, yesterday)
    except Exception as e:
        print(f'[FATAL] 노트 저장 실패: {e}', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    status = '신규 생성' if result['created'] else '기존 파일 업데이트'
    print(f'[노정석] {status}: {result["path"]}')
    print(f'[노정석]  - append: {result["appended"]}건')
    print(f'[노정석]  - skip(중복): {result["skipped"]}건')

    print('[노정석] --- preview ---')
    for p in posts:
        first_line = next((ln.strip() for ln in p['text'].splitlines() if ln.strip()), '')
        preview = first_line[:60] + ('…' if len(first_line) > 60 else '')
        print(f'  {p["time_str"]}  {preview}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
