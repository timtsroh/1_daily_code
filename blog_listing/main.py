#!/usr/bin/env python
"""blog_listing — Google Sheet article/deals 시트 갱신 엔트리 포인트.

사용법:
    python main.py                                    # 어제 하루
    python main.py 2026-07-15                         # 해당 날짜 하루
    python main.py 2026-07-01 2026-07-15              # 범위
    python main.py --month 2026-07                    # 해당 월 전체
    python main.py --since 2026-07-01 --until 2026-07-15

동작:
    1) blog 시트 소스 목록 로드 (Destination 컬럼 포함)
    2) 각 소스에서 기간 내 신규 글 수집 (Substack API / RSS / HTML 파싱)
    3) 기존 article + deals 시트 전체 URL 과 dedupe
    4) Posted desc 정렬 후 각 소스의 Destination 시트 2행부터 insert (최근 글이 위)

Exit code:
    0 → 정상 종료 (개별 소스 에러가 있어도 진행되었으면 0)
    1 → 인자 파싱 실패, Google Sheets 접근 실패 등 복구 불가 오류
"""

import sys
import traceback
from datetime import datetime

# Windows 콘솔 cp949 인코딩에서 em-dash 등 다국어 문자로 크래시하지 않도록.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from blog_listing.config import DEST_TABS, KST
from blog_listing.dates import resolve_dates
from blog_listing.sheets import (
    insert_rows,
    load_blog_sources,
    load_existing_urls_by_dest,
)
from blog_listing.sources import fetch_source


def main() -> int:
    # 1) 인자 → 날짜 범위
    try:
        start_date, end_date = resolve_dates(sys.argv[1:])
    except Exception as ex:
        print(f"[FATAL] 인자 파싱 실패: {ex}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 1

    today = datetime.now(KST).date()
    today_str = today.isoformat()
    print(f"기간: {start_date} ~ {end_date} (today={today_str})")

    # 2) 소스 목록 + 기존 URL 집합 (article + deals 통합)
    try:
        sources = load_blog_sources()
        ws_by_dest, existing_urls = load_existing_urls_by_dest()
        dest_summary = ", ".join(f"{d}={ws_by_dest[d].title}" for d in ws_by_dest)
        print(f"소스: {len(sources)}개, 기존 URL: {len(existing_urls)}개 ({dest_summary})")
    except Exception as ex:
        print(f"[FATAL] Google Sheets 접근 실패: {ex}", file=sys.stderr)
        traceback.print_exc()
        return 1

    # 3) 소스별 수집 → destination 별 버킷
    posts_by_dest = {d: [] for d in DEST_TABS}
    stats = []  # (name, dest, total, dup, added, err)

    for src in sources:
        name = src["Name"]
        dest = src["Destination"]
        print(f"\n--- {name} ({src['Format']}, dest={dest}) ---")
        err = ""
        try:
            posts = fetch_source(src, start_date, end_date)
        except Exception as ex:
            posts = []
            err = str(ex)
            print(f"  ERR: {ex}")

        total = len(posts)
        added = 0
        dup = 0
        for p in posts:
            if p["URL"] in existing_urls:
                dup += 1
                continue
            existing_urls.add(p["URL"])  # 같은 세션 안 중복도 방지
            posts_by_dest[dest].append(p)
            added += 1

        stats.append((name, dest, total, dup, added, err))
        print(f"  fetched={total} dup={dup} added={added}")

    # 4) destination 별로 Posted desc 정렬 후 insert
    inserted_total = 0
    for dest, posts in posts_by_dest.items():
        if not posts:
            continue
        posts.sort(key=lambda p: p["Posted"], reverse=True)
        rows = [
            [today_str, p["Format"], p["Writer"], p["Posted"], p["URL"], p["Title"]]
            for p in posts
        ]
        ws = ws_by_dest[dest]
        try:
            insert_rows(ws, rows)
            print(f"\n[{dest}] inserted {len(rows)} rows at row 2.")
            inserted_total += len(rows)
        except Exception as ex:
            print(f"[FATAL] {dest} insert 실패: {ex}", file=sys.stderr)
            traceback.print_exc()
            return 1

    if inserted_total == 0:
        print("\n신규 글 없음.")

    # 5) 요약
    print("\n" + "=" * 70)
    print(f"{'Source':22s} {'dest':>8s} {'fetched':>8s} {'dup':>5s} {'added':>6s}  err")
    print("-" * 70)
    for name, dest, tot, du, add, er in stats:
        print(f"{name:22s} {dest:>8s} {tot:>8d} {du:>5d} {add:>6d}  {er}")
    print(f"{'TOTAL':22s} {'':>8s} {sum(s[2] for s in stats):>8d} "
          f"{sum(s[3] for s in stats):>5d} {sum(s[4] for s in stats):>6d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
