#!/usr/bin/env python3
"""tech_yt_listing — 엔트리 포인트.

사용법:
    python3 main.py                # 이번 주(월~오늘, KST) 수집
    python3 main.py 260406         # 해당 날짜 ~ 오늘
    python3 main.py 260406-260411  # 범위
    python3 main.py 260406 260411  # 범위 (공백 구분)

Exit code:
    0 → 정상 종료 (개별 채널 에러가 있어도 전체 파이프라인이 진행되었으면 0)
    1 → 복구 불가 오류 (인자 파싱 실패, Sheets 접근 실패 등)
"""

import sys
import traceback
from datetime import datetime

from tech_yt_listing.config import KST
from tech_yt_listing.dates import resolve_dates
from tech_yt_listing.report import print_summary
from tech_yt_listing.scan import scan_channel
from tech_yt_listing.sheets import (
    insert_rows_yt2,
    load_channels,
    load_existing_yt2,
)


def main() -> int:
    # 1) 인자 → 날짜 범위
    try:
        start_date, end_date = resolve_dates(sys.argv[1:])
    except Exception as ex:
        print(f"[FATAL] 인자 파싱 실패: {ex}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 1

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    print(f"기간: {start_date} ~ {end_date} (today={today_str})")

    # 2) yt1 채널 목록 + yt2 기존 URL 로딩
    try:
        channels = load_channels()
        print(f"채널: {len(channels)}개")

        yt2_ws, existing_ids = load_existing_yt2()
        print(f"기존 yt2: {len(existing_ids)}개 URL")
    except Exception as ex:
        print(f"[FATAL] Google Sheets 접근 실패: {ex}", file=sys.stderr)
        traceback.print_exc()
        return 1

    # 3) 채널별 스캔
    all_videos = []
    stats = {}
    for ch in channels:
        source = ch["source"]
        print(f"\n--- {source} ---")
        try:
            added, ch_stats, err = scan_channel(
                source=source,
                url=ch["url"],
                start_date=start_date,
                end_date=end_date,
                existing_ids=existing_ids,
            )
            if err:
                # 채널 단위 경고 — 전체는 계속 진행
                print(f"  WARN: {err}")
                ch_stats["error"] = err
            all_videos.extend(added)
            stats[source] = ch_stats
        except Exception as ex:
            # HTTP 500, 네트워크 오류 등은 경고 취급
            print(f"  WARN: {ex}")
            stats[source] = {
                "total": 0, "filtered": 0, "duped": 0, "added": 0,
                "error": str(ex),
            }

    # 4) 최신순 정렬 후 yt2에 삽입
    all_videos.sort(key=lambda v: v["published"], reverse=True)
    rows = [
        [today_str, v["source"], v["title"], v["url"], v["published"], v["length"], ""]
        for v in all_videos
    ]

    if rows:
        try:
            insert_rows_yt2(yt2_ws, rows)
            print(f"\nyt2 시트에 {len(rows)}행 삽입 완료")
        except Exception as ex:
            print(f"[FATAL] yt2 삽입 실패: {ex}", file=sys.stderr)
            traceback.print_exc()
            # 삽입 실패는 fatal 처리
            print_summary(stats)
            return 1
    else:
        print("\n삽입할 신규 영상 없음")

    # 5) 요약
    print_summary(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
