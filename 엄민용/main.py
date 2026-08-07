#!/usr/bin/env python
"""
엄민용 — 신한투자증권 제약/바이오 텔레그램 채널(t.me/bio_shinhan) 리포트 자동 수집.

흐름:
  1. last_run.log 읽어 수집 시작일 결정 (없으면 최근 30일).
  2. Telethon으로 CHANNEL의 메시지를 시작일까지 역순 스캔.
  3. 각 메시지에서 bbs2.shinhansec.com PDF URL을 추출, attachmentId 중복 제거.
  4. 『...』 제목에서 기업명·제목 분리, 분류(기업/산업) 판정.
     - 티커 패턴((숫자.KQ), (숫자,KS) 등)이 있으면 기업분석.
     - 없으면 SECTOR_KEYWORDS에 포함될 때만 산업분석, 그 외는 스킵(모호).
  5. 부분 파일명 glob으로 중복 확인 → 신규만 다운로드.
  6. PDF 다운로드 후 /Type /Page 카운트로 페이지수 추출.
  7. 파일명 확정해 Google Drive inbox로 이동.
  8. 포스트 원문을 Obsidian 월별 노트(엄민용_YYMM.md)에 append.
  9. 모든 단계 성공 시 last_run.log 갱신.

종료 코드: 0 (성공, 신규 0건 포함) / 1 (오류).

의존성: telethon. 표준 라이브러리 나머지 전부 stdlib.
"""

from __future__ import annotations

import asyncio
import glob
import os
import re
import ssl
import sys
import tempfile
import traceback
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient

# ─── 설정 ──────────────────────────────────────────────────────────────────
API_ID = 32844347
API_HASH = "432b3c2ca6b5e925320031c3e234ac58"
# 다른 텔레그램 스킬(전종현 등)과 세션 파일을 공유한다.
SESSION_FILE = "C:/Users/DELL/.claude/tg_session"
CHANNEL = "bio_shinhan"
FETCH_LIMIT = 500  # 1개월 범위 스캔을 커버하는 여유값

# 마지막 실행일 로그 — launchd run.sh 와 호환되도록 기존 스킬 경로를 유지한다.
LAST_RUN_LOG = Path("C:/Users/DELL/.claude/skills/엄민용/last_run.log")

# PDF 저장 경로 (Google Drive Inbox)
PDF_DIR = Path("G:/내 드라이브/02 주식/02 자료/0 Inbox")

# 피드 노트 (Obsidian 3 큐레이션/)
NOTE_DIR = Path("C:/Obsidian/Sync1/03 Sources/3 큐레이션")

BROKER_TAG = "신한"

# 수집 대상 URL 패턴
URL_RE = re.compile(
    r"https?://bbs2\.shinhansec\.com/board/message/file\.pdf\.do\?attachmentId=\d+",
    re.IGNORECASE,
)
ATTACHMENT_ID_RE = re.compile(r"attachmentId=(\d+)", re.IGNORECASE)

# 제목 괄호 『 U+300E ... 』 U+300F
TITLE_RE = re.compile(r"『([^』]+)』")

# 종목 티커 — (358570.KQ), (068270,KS), (005930 KS) 등 폭넓게 허용
TICKER_PAREN_RE = re.compile(
    r"\(\s*\d{5,6}\s*[\.,\s]\s*[A-Z]{1,3}\s*\)"
)

# 『』 제목 내부의 구분자: 일반 하이픈 또는 em/en dash
TITLE_SEP_RE = re.compile(r"\s+[-–—]\s+")

# 산업분석으로 허용할 섹터 키워드 (제목 앞단어가 이 중 하나일 때만 산업분석으로 확정).
# 제약/바이오 채널 특성상 범위를 좁게 유지해 모호한 케이스를 스킵한다.
SECTOR_KEYWORDS = {
    "바이오",
    "제약",
    "헬스케어",
    "바이오헬스케어",
    "바이오시밀러",
    "제약바이오",
    "바이오/제약",
    "제약/바이오",
    "CDMO",
    "신약",
}

# 파일명 금지 문자 (Windows/Obsidian 호환). 공백으로 치환.
FORBIDDEN_CHARS_RE = re.compile(r'[\\/:*?"<>|]')

KST = timezone(timedelta(hours=9))


# ─── 데이터 구조 ────────────────────────────────────────────────────────────
@dataclass
class ReportLink:
    """한 메시지에서 뽑아낸 개별 PDF 링크."""
    attachment_id: str
    url: str


@dataclass
class ParsedTitle:
    """『...』 제목을 분해한 결과."""
    category: str        # "기업" | "산업" | "" (스킵)
    subject: str         # 기업명 또는 산업명
    title: str           # 제목 본문
    ticker_paren: str    # 노트 헤더에 붙이는 "(코드.KS)" 표기 (없으면 "")


@dataclass
class Post:
    """채널 메시지 1건을 정규화한 구조."""
    msg_id: int
    dt_kst: datetime
    raw_text: str                               # 마크다운 렌더링 없는 원본 텍스트
    links: List[ReportLink] = field(default_factory=list)
    parsed: Optional[ParsedTitle] = None


# ─── last_run 유틸 ─────────────────────────────────────────────────────────
def read_last_run() -> Optional[date]:
    if not LAST_RUN_LOG.exists():
        return None
    text = LAST_RUN_LOG.read_text(encoding="utf-8").strip()
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d").date()


def write_last_run(d: date) -> None:
    LAST_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_LOG.write_text(f"last_run: {d.strftime('%Y-%m-%d')}\n", encoding="utf-8")


def determine_start_date(today_kst: date) -> date:
    last = read_last_run()
    if last is None:
        return today_kst - timedelta(days=30)
    # PRD 규칙: last_run - 1일부터 재수집 (오류 재시도 대비)
    return last - timedelta(days=1)


# ─── 제목 파싱 / 분류 ───────────────────────────────────────────────────────
def strip_markdown_asterisks(text: str) -> str:
    """Telegram `**bold**` 마크다운을 텍스트에서 제거한다. 단순 치환."""
    return text.replace("**", "")


def parse_title(raw_text: str) -> ParsedTitle:
    """메시지 텍스트에서 『...』 제목을 추출·분해한다.

    스킵 조건:
      - 『』 없음.
      - 내부에 티커 괄호도 없고 선두어가 SECTOR_KEYWORDS 에 없음.
    """
    text = strip_markdown_asterisks(raw_text)
    m = TITLE_RE.search(text)
    if not m:
        return ParsedTitle(category="", subject="", title="", ticker_paren="")

    inner = m.group(1).strip()

    # 케이스 A: 기업분석 — 티커 괄호가 있음.
    ticker_m = TICKER_PAREN_RE.search(inner)
    if ticker_m:
        ticker_paren = ticker_m.group(0).strip()
        before = inner[: ticker_m.start()].strip()
        after = inner[ticker_m.end():].strip()
        # after 는 보통 " - 제목본문". 구분자 제거.
        title = TITLE_SEP_RE.sub("", after, count=1) if after else after
        title = title.lstrip(" -–—").strip()
        subject = before.strip()
        if subject and title:
            return ParsedTitle(
                category="기업",
                subject=subject,
                title=title,
                ticker_paren=ticker_paren,
            )
        # subject/title 둘 중 하나라도 비면 포맷 파괴로 간주 → 스킵.
        return ParsedTitle(category="", subject="", title="", ticker_paren="")

    # 케이스 B: 산업분석 후보 — 티커 없음. 선두 토큰 검사.
    # 구분자 " - " 로 분리. 없으면 전체를 subject+title 공유 불가 → 스킵.
    parts = TITLE_SEP_RE.split(inner, maxsplit=1)
    if len(parts) == 2:
        head, title = parts[0].strip(), parts[1].strip()
    else:
        head, title = inner.strip(), inner.strip()

    # head 첫 단어(공백/슬래시 기준) 가 섹터 키워드인지 확인.
    head_key = head.split()[0] if head else ""
    if head in SECTOR_KEYWORDS or head_key in SECTOR_KEYWORDS:
        return ParsedTitle(
            category="산업",
            subject=head if head in SECTOR_KEYWORDS else head_key,
            title=title,
            ticker_paren="",
        )

    # 그 외 — 모호하면 스킵.
    return ParsedTitle(category="", subject="", title="", ticker_paren="")


# ─── URL 추출 ──────────────────────────────────────────────────────────────
def extract_links(text: str) -> List[ReportLink]:
    """메시지 텍스트에서 bbs2 PDF URL 을 뽑아 attachmentId 중복 제거."""
    seen: set = set()
    out: List[ReportLink] = []
    for url in URL_RE.findall(text):
        aid_m = ATTACHMENT_ID_RE.search(url)
        if not aid_m:
            continue
        aid = aid_m.group(1)
        if aid in seen:
            continue
        seen.add(aid)
        out.append(ReportLink(attachment_id=aid, url=url))
    return out


# ─── 파일명 유틸 ───────────────────────────────────────────────────────────
def sanitize_for_filename(s: str) -> str:
    """Windows/Obsidian 호환을 위해 금지문자 제거 및 연속 공백 정리."""
    s = FORBIDDEN_CHARS_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def partial_filename(subject: str, yy_mmdd: str, title: str) -> str:
    """페이지수 제외 부분 파일명."""
    return f"{sanitize_for_filename(subject)}_{yy_mmdd}_{BROKER_TAG}_{sanitize_for_filename(title)}"


def final_filename(subject: str, yy_mmdd: str, title: str, pages: Optional[int]) -> str:
    p = f"p{pages}" if pages else "p?"
    return f"{partial_filename(subject, yy_mmdd, title)}_{p}.pdf"


# ─── PDF 다운로드 / 페이지수 ────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()
# bbs2 서버 인증서 체인이 간헐적으로 끊기는 사례 대비 (PRD 도 curl -sL 권장).
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def download_pdf(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as r:
        ct = (r.headers.get("Content-Type") or "").lower()
        data = r.read()
    if "pdf" not in ct and not data.startswith(b"%PDF"):
        raise RuntimeError(f"PDF 아님 (Content-Type={ct}, head={data[:8]!r})")
    dest.write_bytes(data)


def count_pages(pdf_path: Path) -> Optional[int]:
    try:
        data = pdf_path.read_bytes()
    except OSError:
        return None
    # /Pages 오브젝트 제외하고 /Type /Page 만 카운트.
    matches = re.findall(rb"/Type\s*/Page(?!s)", data)
    return len(matches) if matches else None


# ─── 중복 파일 검사 ────────────────────────────────────────────────────────
def find_existing(partial: str) -> List[str]:
    if not PDF_DIR.exists():
        return []
    safe_partial = glob.escape(partial)
    return sorted(glob.glob(str(PDF_DIR / f"{safe_partial}*.pdf")))


# ─── 피드 노트 ─────────────────────────────────────────────────────────────
def note_path_for(dt_kst: datetime) -> Path:
    return NOTE_DIR / f"엄민용_{dt_kst.strftime('%y%m')}.md"


def note_header(post: Post) -> str:
    """'## MMDD 기업명 (코드.KS) - 제목' 형식."""
    assert post.parsed is not None
    p = post.parsed
    mmdd = post.dt_kst.strftime("%m%d")
    if p.category == "기업" and p.ticker_paren:
        return f"## {mmdd} {p.subject} {p.ticker_paren} - {p.title}"
    return f"## {mmdd} {p.subject} - {p.title}"


def note_entry_already_present(note_file: Path, header: str) -> bool:
    if not note_file.exists():
        return False
    return header in note_file.read_text(encoding="utf-8")


def append_note_entry(
    note_file: Path,
    header: str,
    raw_text: str,
    saved_filenames: List[str],
) -> None:
    """월별 노트 끝에 엔트리 추가. 노트가 없으면 새로 생성."""
    body_lines = [header]

    # 원문 중 첫 줄(= 제목줄) 은 헤더와 중복되므로 제거.
    cleaned = strip_markdown_asterisks(raw_text).strip()
    lines = cleaned.splitlines()
    # 『...』 로 시작하는 선두줄(제목) 제거
    while lines and (not lines[0].strip() or lines[0].strip().startswith("『")):
        lines.pop(0)
    body_lines.extend(lines)

    for fn in saved_filenames:
        body_lines.append(f"→ 저장: {fn}")

    block = "\n".join(body_lines).rstrip() + "\n"

    note_file.parent.mkdir(parents=True, exist_ok=True)
    if note_file.exists() and note_file.stat().st_size > 0:
        prev = note_file.read_text(encoding="utf-8").rstrip() + "\n\n"
        note_file.write_text(prev + block, encoding="utf-8")
    else:
        note_file.write_text(block, encoding="utf-8")


# ─── Telegram fetch ───────────────────────────────────────────────────────
async def _fetch_posts(start_date: date) -> List[Post]:
    """start_date 이상의 채널 메시지를 수집한다."""
    posts: List[Post] = []
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                f"Telethon 세션 미인증: {SESSION_FILE}.session. 재인증이 필요하다."
            )

        async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT):
            msg_date = msg.date.astimezone(KST).date()
            if msg_date < start_date:
                break
            if not msg.text:
                continue
            if "bbs2.shinhansec.com" not in msg.text:
                continue

            links = extract_links(msg.text)
            if not links:
                continue

            posts.append(
                Post(
                    msg_id=msg.id,
                    dt_kst=msg.date.astimezone(KST),
                    raw_text=msg.text,
                    links=links,
                )
            )
    finally:
        await client.disconnect()

    posts.reverse()  # 오래된 포스트가 먼저 오도록 정렬
    return posts


# ─── 메인 처리 ─────────────────────────────────────────────────────────────
@dataclass
class RunStats:
    downloaded: int = 0
    skipped_existing: int = 0
    skipped_ambiguous: int = 0
    notes_appended: int = 0
    errors: int = 0
    saved_files: List[str] = field(default_factory=list)


def process_post(post: Post, stats: RunStats) -> None:
    """1개 포스트에 대해 분류·다운로드·파일명·피드 노트 반영."""
    post.parsed = parse_title(post.raw_text)
    if not post.parsed.category:
        # 모호한 포스트는 스킵. PDF 도 받지 않고 노트도 쓰지 않음.
        stats.skipped_ambiguous += 1
        print(f"  [skip-ambiguous] msg {post.msg_id} — 제목 파싱 실패/모호")
        return

    yy_mmdd = post.dt_kst.strftime("%y%m%d")
    subject = post.parsed.subject
    title = post.parsed.title

    partial = partial_filename(subject, yy_mmdd, title)
    saved_filenames: List[str] = []

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    for link in post.links:
        existing = find_existing(partial)
        if existing:
            # 이미 저장된 파일명을 노트에도 기록 (재실행 일관성).
            for path in existing:
                name = os.path.basename(path)
                if name not in saved_filenames:
                    saved_filenames.append(name)
            stats.skipped_existing += 1
            print(f"  [skip-existing] {partial}* 이미 존재")
            continue

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", prefix="eommy_"
        ) as tmp:
            tmp_path = Path(tmp.name)

        try:
            print(f"  [download] {link.url}")
            download_pdf(link.url, tmp_path)
            pages = count_pages(tmp_path)
            final_name = final_filename(subject, yy_mmdd, title, pages)
            final_path = PDF_DIR / final_name

            # 최종 경로 충돌 방지 (같은 페이지수·제목 우연 충돌)
            if final_path.exists():
                tmp_path.unlink(missing_ok=True)
                stats.skipped_existing += 1
                print(f"  [skip-existing] {final_name} 이미 존재")
                saved_filenames.append(final_name)
                continue

            os.replace(tmp_path, final_path)
            stats.downloaded += 1
            stats.saved_files.append(final_name)
            saved_filenames.append(final_name)
            print(f"  [saved] {final_name}")
        except Exception as exc:
            stats.errors += 1
            print(f"  [error] download/save 실패: {exc}")
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    # 노트 반영 — 이 포스트에 대해 새로 받은 게 있든 없든, 헤더가 없으면 추가.
    header = note_header(post)
    note_file = note_path_for(post.dt_kst)
    if not note_entry_already_present(note_file, header):
        append_note_entry(note_file, header, post.raw_text, saved_filenames)
        stats.notes_appended += 1
        print(f"  [note] appended → {note_file.name}")


def main() -> int:
    today_kst = datetime.now(KST).date()
    start_date = determine_start_date(today_kst)

    print(f"[엄민용] today_kst={today_kst} start_date={start_date}")
    print(f"[엄민용] channel={CHANNEL} session={SESSION_FILE}")

    try:
        posts = asyncio.run(_fetch_posts(start_date))
    except Exception as exc:
        traceback.print_exc()
        print(f"[엄민용] Telegram fetch 실패: {exc}", file=sys.stderr)
        return 1

    print(f"[엄민용] bbs2 포함 포스트 {len(posts)}건 수집")

    stats = RunStats()
    had_fatal = False
    for post in posts:
        try:
            process_post(post, stats)
        except Exception as exc:
            had_fatal = True
            stats.errors += 1
            traceback.print_exc()
            print(f"[엄민용] 포스트 처리 실패 msg_id={post.msg_id}: {exc}", file=sys.stderr)

    # 결과 요약
    print("[엄민용] ─── 결과 ───")
    print(f"  downloaded        : {stats.downloaded}")
    print(f"  skipped_existing  : {stats.skipped_existing}")
    print(f"  skipped_ambiguous : {stats.skipped_ambiguous}")
    print(f"  notes_appended    : {stats.notes_appended}")
    print(f"  errors            : {stats.errors}")
    for fn in stats.saved_files:
        print(f"  saved: {fn}")

    if had_fatal or stats.errors > 0:
        print("[엄민용] 에러 발생 — last_run.log 갱신 안 함")
        return 1

    write_last_run(today_kst)
    print(f"[엄민용] last_run.log 갱신: {today_kst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
