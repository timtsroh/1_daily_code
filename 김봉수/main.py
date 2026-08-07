#!/usr/bin/env python
"""
김봉수 페이스북 피드 일일 수집 파이프라인.

`python main.py` 한 번 실행 → 어제(KST) 포스트를 Playwright로 긁어
Obsidian 월별 노트에 저장한다.

종료 코드:
  0: 정상 (신규 글 없음도 포함)
  1: 치명적 오류 (세션 파일 없음, Playwright 실패 등)
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date, datetime, timedelta

from config import KST, PROFILE_NAME, PROFILE_URL, SESSION_FILE
from note_writer import WriteResult, note_path_for, write_monthly_note
from scraper import Post, fetch_posts_for
from session import SessionMissingError, ensure_session


def _yesterday_kst() -> date:
    return (datetime.now(KST) - timedelta(days=1)).date()


def _parse_date(s: str) -> date:
    """YYYY-MM-DD 또는 YYMMDD 형식을 받는다."""
    for fmt in ("%Y-%m-%d", "%y%m%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"날짜 형식이 잘못됐습니다: {s!r} (예: 2026-04-19 또는 260419)"
    )


def _print_summary(
    target_date: date, posts: list[Post], result: WriteResult
) -> None:
    print()
    print(f"=== {PROFILE_NAME} 피드 수집 결과 ===")
    print(f"프로필        : {PROFILE_URL}")
    print(f"대상 날짜     : {target_date.isoformat()} (KST)")
    print(f"수집된 글     : {len(posts)}건")
    print(f"노트 파일     : {result.path}")
    print(
        f"상태          : "
        + ("신규 생성" if result.created else "기존 파일")
        + f" / 추가 {result.appended}건"
        + (f" / 중복 스킵 {result.skipped_duplicates}건"
           if result.skipped_duplicates else "")
    )
    if posts:
        print("\n미리보기:")
        for p in posts:
            preview = p.text.strip().splitlines()[0] if p.text.strip() else ""
            if len(preview) > 60:
                preview = preview[:60] + "..."
            print(f"  - {p.time_str}  {preview}")
    else:
        print("\n어제 올라온 글 없음.")


def run(target_date: date) -> int:
    # 세션 확인
    try:
        ensure_session()
    except SessionMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # 수집
    try:
        posts = fetch_posts_for(target_date)
    except Exception as exc:  # pragma: no cover — Playwright 런타임 실패 대응
        print(
            f"[fatal] Playwright 수집 실패: {exc}",
            file=sys.stderr,
        )
        traceback.print_exc()
        return 1

    # 저장
    try:
        result = write_monthly_note(posts, target_date)
    except Exception as exc:
        print(f"[fatal] 노트 저장 실패: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    _print_summary(target_date, posts, result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"{PROFILE_NAME} 페이스북 피드 일일 수집기",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        help="수집할 날짜 (기본: 어제 KST). 형식: YYYY-MM-DD 또는 YYMMDD",
    )
    parser.add_argument(
        "--session",
        default=str(SESSION_FILE),
        help="Facebook 세션 파일 경로(환경변수 FB_SESSION_FILE로도 설정 가능)",
    )
    args = parser.parse_args()

    target = args.date or _yesterday_kst()
    # argparse로 넘어온 --session 은 config 레벨에서 이미 환경변수로 주입하도록 안내.
    # 여기서는 기본 경로 그대로 사용한다.
    return run(target)


if __name__ == "__main__":
    sys.exit(main())
