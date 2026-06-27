#!/usr/bin/env python3
"""
main.py — 전종현 텔레그램 채널 자동 수집 엔트리포인트.

실행 흐름:
  1. 텔레그램 채널 chunjonghyun에서 어제(KST) 메시지 수집
  2. Obsidian 월별 노트 (0 inbox/전종현_yymm.md) 에 시간순 병합 (중복 제거)
  3. 요약 출력

성공: exit 0, 하드 에러: exit 1.
"""

from __future__ import annotations

import sys
import traceback

from fetch_feed import fetch_yesterday
from write_note import write_entries


def main() -> int:
    try:
        feed = fetch_yesterday()
    except Exception as exc:
        print(f"[ERROR] 피드 수집 실패: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    print(f"[INFO] 날짜(KST): {feed.date_iso}")
    print(f"[INFO] 수집 메시지: {len(feed.entries)}건")

    if not feed.entries:
        print("[OK] 어제 올라온 글 없음.")
        return 0

    try:
        result = write_entries(feed.year_month, feed.date_iso, feed.entries)
    except Exception as exc:
        print(f"[ERROR] 노트 저장 실패: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    status = "CREATED" if result.created else "UPDATED"
    print(f"[{status}] {result.filepath}")
    print(f"[INFO] 추가: {result.added}건, 중복 건너뜀: {result.skipped}건")

    # 미리보기 (첫 줄, Forwarded 표시)
    print("[PREVIEW]")
    for e in feed.entries:
        first_line = e.body.split("\n", 1)[0][:80]
        fwd_tag = ""
        if e.forwarded:
            fwd_name = e.forwarded.split("|", 1)[0]
            fwd_tag = f" [fwd: {fwd_name}]"
        print(f"  {e.time}{fwd_tag}  {first_line}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
