#!/usr/bin/env python
"""
main.py
최광식 스킬 — 순수 Python 포팅판.

역할:
  1. last_run.log 읽어 조회 시작일 결정 (없으면 최근 1개월).
  2. Telethon으로 t.me/HI_GS 포스트 수집 (bit.ly 링크 포함분만).
  3. 각 bit.ly 링크를 resolve → PDF 다운로드 (HTML·광고페이지 스킵).
  4. 포스트 텍스트에서 기업명/산업명·제목·날짜 추출 → 파일명 구성.
  5. 부분 파일명(페이지수 제외)으로 Google Drive 0 Inbox 폴더 중복 확인.
  6. 신규 파일만 최종 경로로 이동. 페이지 수로 최종 파일명 확정.
  7. 모든 단계가 오류 없이 끝나면 last_run.log에 오늘 날짜 기록.

이 스크립트는 Claude/LLM을 호출하지 않는다. 피드 노트 작성·리포트 요약 노트는
Claude 스킬이 담당하므로 여기서는 건드리지 않는다.

종료 코드:
  0 — 성공 (0건 처리 포함)
  1 — 치명적 오류 (세션 미인증, 폴더 없음 등)
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

from config import (
    LAST_RUN_LOG,
    GDRIVE_INBOX,
    INITIAL_LOOKBACK_DAYS,
    LAST_RUN_BUFFER_DAYS,
    BROKER_LABEL,
)
from telegram_client import Post, fetch_posts_since, KST
from post_parser import PostMeta, parse_post
from pdf_downloader import PdfDownloadResult, resolve_and_download


# ── 결과 집계 ─────────────────────────────────────────────────────────────


@dataclass
class RunStats:
    posts_scanned: int = 0
    urls_scanned: int = 0
    downloaded: List[str] = None
    skipped_duplicate: int = 0
    skipped_not_pdf: int = 0
    skipped_unparseable: int = 0
    skipped_http_error: int = 0

    def __post_init__(self):
        if self.downloaded is None:
            self.downloaded = []


# ── last_run.log ──────────────────────────────────────────────────────────


def read_last_run(path: Path) -> Optional[date]:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    # 형식: "last_run: YYYY-MM-DD"
    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith("last_run:"):
            iso = line.split(":", 1)[1].strip()
            try:
                return datetime.strptime(iso, "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def write_last_run(path: Path, d: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"last_run: {d.strftime('%Y-%m-%d')}\n", encoding="utf-8")


def compute_start_date(today_kst: date) -> date:
    last = read_last_run(LAST_RUN_LOG)
    if last is None:
        return today_kst - timedelta(days=INITIAL_LOOKBACK_DAYS)
    # -1일 buffer (이전 실행 도중 실패 대비)
    return last - timedelta(days=LAST_RUN_BUFFER_DAYS)


# ── 파일명 규칙 ────────────────────────────────────────────────────────────


def build_partial_filename(meta: PostMeta) -> str:
    """페이지 수 제외한 부분 파일명. 중복 확인용 glob 패턴의 prefix."""
    return f"{meta.entity}_{meta.yymmdd}_{BROKER_LABEL}_{meta.title}"


def build_full_filename(meta: PostMeta, page_count: Optional[int]) -> str:
    p = f"p{page_count}" if page_count else "p?"
    return f"{build_partial_filename(meta)}_{p}.pdf"


def is_duplicate(inbox: Path, meta: PostMeta) -> bool:
    """부분 파일명 prefix로 이미 다운로드된 파일이 있는지 확인.

    Inbox 폴더에는 과거 수동 저장된 파일 중 `:` 가 그대로 포함된 것, `-`로 치환된 것
    등 여러 표기가 섞여 있다. 따라서 단순 glob 매칭이 아니라 **정규화된 prefix**로
    비교한다 — 파일명에서 `post_parser._FILENAME_FORBIDDEN` 에 해당하는 문자를
    공백으로 치환한 뒤 startswith 비교.
    """
    from post_parser import _FILENAME_FORBIDDEN  # noqa: WPS433

    partial = build_partial_filename(meta)  # 이미 forbidden 문자가 정규화된 상태

    def _norm(name: str) -> str:
        s = _FILENAME_FORBIDDEN.sub(" ", name)
        import re as _re
        s = _re.sub(r"\s+", " ", s).strip()
        return s

    norm_prefix = _norm(partial)
    try:
        # `{기업명}_{YYMMDD}_다올_` 로 시작하는 것만 먼저 거른 뒤 정규화 비교
        narrow = f"{meta.entity}_{meta.yymmdd}_{BROKER_LABEL}_*.pdf"
        for p in inbox.glob(narrow):
            if _norm(p.name).startswith(norm_prefix):
                return True
    except OSError:
        return False
    return False


# ── 단일 포스트 처리 ───────────────────────────────────────────────────────


def process_post(post: Post, stats: RunStats, inbox: Path) -> None:
    meta = parse_post(post.text, post.datetime_kst)
    if meta is None:
        stats.skipped_unparseable += 1
        print(
            f"[SKIP unparseable] msg={post.message_id} "
            f"date={post.date_kst} "
            f"(해시태그도 없고 산업명도 추출 불가)",
            flush=True,
        )
        return

    for url in post.bitly_urls:
        stats.urls_scanned += 1

        # 중복 확인 먼저 (네트워크 I/O 회피)
        if is_duplicate(inbox, meta):
            stats.skipped_duplicate += 1
            print(
                f"[SKIP dup] {build_partial_filename(meta)}*.pdf "
                f"(이미 존재) msg={post.message_id}",
                flush=True,
            )
            continue

        print(
            f"[FETCH] {url}  → category={meta.category} "
            f"entity={meta.entity!r} title={meta.title!r}",
            flush=True,
        )
        result = resolve_and_download(url)
        if not result.ok:
            if result.reason.startswith("http"):
                stats.skipped_http_error += 1
            else:
                stats.skipped_not_pdf += 1
            print(
                f"[SKIP {result.reason}] {url} "
                f"(final={result.final_url} ctype={result.content_type})",
                flush=True,
            )
            continue

        # 성공 — 최종 경로로 이동
        final_name = build_full_filename(meta, result.page_count)
        dest = inbox / final_name

        # 경쟁 상태(같은 실행 중 방금 다운로드 완료)에 대비해 한 번 더 확인
        if dest.exists():
            stats.skipped_duplicate += 1
            if result.temp_path and result.temp_path.exists():
                result.temp_path.unlink(missing_ok=True)
            print(f"[SKIP dup-race] {final_name}", flush=True)
            continue

        try:
            shutil.move(str(result.temp_path), str(dest))
        except OSError as e:
            # 폴백: copy2 + unlink
            try:
                shutil.copy2(str(result.temp_path), str(dest))
                result.temp_path.unlink(missing_ok=True)
            except OSError as e2:
                print(f"[ERROR move] {dest}: {e2}", flush=True)
                continue

        stats.downloaded.append(final_name)
        print(
            f"[OK] {final_name}  (pages={result.page_count} "
            f"ctype={result.content_type})",
            flush=True,
        )


# ── 엔트리포인트 ───────────────────────────────────────────────────────────


async def run() -> int:
    today_kst = datetime.now(KST).date()
    start_date = compute_start_date(today_kst)

    print(f"[config] today(KST)={today_kst} start_date={start_date}")
    print(f"[config] inbox={GDRIVE_INBOX}")

    if not GDRIVE_INBOX.exists():
        print(f"[FATAL] Google Drive inbox 폴더가 존재하지 않음: {GDRIVE_INBOX}")
        return 1

    try:
        posts = await fetch_posts_since(start_date)
    except RuntimeError as e:
        print(f"[FATAL] {e}")
        return 1
    except Exception as e:
        print(f"[FATAL] Telegram fetch 실패: {e.__class__.__name__}: {e}")
        return 1

    stats = RunStats()
    stats.posts_scanned = len(posts)

    if not posts:
        print(f"[INFO] {start_date} 이후 bit.ly 포스트 없음.")
        write_last_run(LAST_RUN_LOG, today_kst)
        return 0

    for post in posts:
        process_post(post, stats, GDRIVE_INBOX)

    # 요약
    print()
    print("─" * 60)
    print(f"posts_scanned        : {stats.posts_scanned}")
    print(f"urls_scanned         : {stats.urls_scanned}")
    print(f"downloaded           : {len(stats.downloaded)}")
    print(f"skipped_duplicate    : {stats.skipped_duplicate}")
    print(f"skipped_not_pdf      : {stats.skipped_not_pdf}")
    print(f"skipped_http_error   : {stats.skipped_http_error}")
    print(f"skipped_unparseable  : {stats.skipped_unparseable}")
    if stats.downloaded:
        print()
        print("신규 저장 파일:")
        for name in stats.downloaded:
            print(f"  - {name}")
    print("─" * 60)

    # 모든 단계가 치명적 오류 없이 끝났다면 last_run.log 갱신
    write_last_run(LAST_RUN_LOG, today_kst)
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        print("[INTERRUPTED]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
