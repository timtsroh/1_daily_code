"""
Obsidian '01 Work/0 inbox' 폴더 노트 정리.
- 프런트매터 없는 파일에 파일명 기반 프런트매터 자동 추가
- call_ / call2_ / meeting_ / meeting2_ 접두사 파일을 각 대상 폴더로 이동

매일 00:05 plist_day.sh 에서 실행.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from datetime import datetime

VAULT = Path(r"C:\Obsidian\Sync1")
INBOX = VAULT / "01 Work" / "0 inbox"

MOVE_MAP = {
    # 접두사 → 대상 폴더 (긴 것부터 매칭해야 하므로 dict 순서 주의; 아래에서 sorted로 처리)
    "call2_":    VAULT / "01 Work" / "A3 call2",
    "meeting2_": VAULT / "01 Work" / "A4 meeting2",
    "call_":     VAULT / "01 Work" / "A1 call",
    "meeting_":  VAULT / "01 Work" / "A2 meeting",
}

FIELD_ORDER = ["title", "date", "type", "speaker", "company", "source", "tags"]


# ─── 파일명 → 프런트매터 추출 ─────────────────────────────────────────────

# 타입 결정용: (판별 함수, 타입명) 순차 매칭. 접두사 + 키워드.
def infer_type(stem: str) -> str:
    # 등대 시리즈는 접두사(call/meeting)보다 우선 — 이전 분류 컨벤션과 일치
    if "등대_" in stem or "_등대" in stem or stem.startswith("등대_"):
        return "등대"
    if stem.startswith("call2_"):    return "콜"
    if stem.startswith("meeting2_"): return "미팅"
    if stem.startswith("call_"):     return "콜"
    if stem.startswith("meeting_"):  return "미팅"
    if stem.startswith("강의_"):     return "강의"
    if stem.startswith("보도자료_"): return "보도자료"
    if stem.startswith("Code_"):     return "코드"
    if stem.startswith("DR_"):       return "DR"
    if stem.startswith("todo_"):     return "투두"
    if stem.startswith("news_"):     return "뉴스"
    if stem.startswith("daily_"):    return "데일리"
    if "_컨콜" in stem:              return "컨콜"
    if "_실적발표" in stem:          return "실적발표"
    if "_뉴스" in stem:              return "뉴스"
    if "_기사" in stem:              return "기사"
    if "_종토" in stem:              return "종토"
    if "_펀드리뷰" in stem:          return "펀드리뷰"
    if "_IR" in stem:                return "IR"
    if "블로그" in stem:              return "블로그"
    if "_발표" in stem:              return "발표"
    return "메모"


# 소스 (LLM/매체 등) 판별
SOURCE_SUFFIXES = [
    ("_GPT Pro", "GPT Pro"),
    ("_GPT",     "GPT"),
    ("_Claude",  "Claude"),
    ("_word",    "word"),
    ("_Text",    "Text"),
]


def infer_source(stem: str) -> str | None:
    for suffix, name in SOURCE_SUFFIXES:
        if stem.endswith(suffix):
            return name
    return None


# 날짜 정규식은 아래 parse_date 함수 근처에서 정의


DATE_SEARCH_FULL = re.compile(r"(?<!\d)(\d{6})(?!\d)")
DATE_SEARCH_YM   = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def parse_date(stem: str) -> tuple[str | None, str]:
    """
    파일명(카테고리 접두사 제거 후) 어디에서든 YYMMDD 또는 YYMM 을 찾아 날짜로 파싱.
    발견하면 (날짜문자열, 해당 토큰 제거된 나머지) 리턴.
    """
    # 우선 YYMMDD (6자리, 순수 숫자 토큰)
    for m in DATE_SEARCH_FULL.finditer(stem):
        yymmdd = m.group(1)
        try:
            dt = datetime.strptime(yymmdd, "%y%m%d")
        except ValueError:
            continue
        # 합리적 연도 범위 (2020~2030)
        if not (2020 <= dt.year <= 2030):
            continue
        rest = (stem[: m.start()] + stem[m.end():]).strip("_ ")
        rest = re.sub(r"_+", "_", rest)
        return dt.strftime("%Y-%m-%d"), rest
    # YYMM (4자리) fallback
    for m in DATE_SEARCH_YM.finditer(stem):
        yymm = m.group(1)
        try:
            dt = datetime.strptime(yymm, "%y%m")
        except ValueError:
            continue
        if not (2020 <= dt.year <= 2030):
            continue
        rest = (stem[: m.start()] + stem[m.end():]).strip("_ ")
        rest = re.sub(r"_+", "_", rest)
        return dt.strftime("%Y-%m"), rest
    return None, stem


CATEGORY_PREFIXES = [
    "call2_", "meeting2_", "call_", "meeting_",
    "강의_", "보도자료_", "Code_", "DR_",
    "todo_", "news_", "daily_",
]


def strip_prefix(stem: str) -> str:
    for p in CATEGORY_PREFIXES:
        if stem.startswith(p):
            return stem[len(p):]
    return stem


def strip_source_suffix(stem: str) -> str:
    for suffix, _ in SOURCE_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def clean_title(stem: str) -> str:
    s = strip_prefix(stem)
    # 카테고리 뒤 날짜도 벗기기 (있으면)
    _, s = parse_date(s)
    s = strip_source_suffix(s)
    s = s.replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s or stem


TOKEN_SPLIT_RE = re.compile(r"[_\s,;·]+")
STOP_TAGS = {"", "-", "vs.", "vs", "on", "of", "the", "a", "an"}


def extract_tags(stem: str, typ: str) -> list[str]:
    s = strip_prefix(stem)
    _, s = parse_date(s)
    s = strip_source_suffix(s)
    raw = TOKEN_SPLIT_RE.split(s)
    tags: list[str] = []
    seen: set[str] = set()
    for t in raw:
        t = t.strip("()[]")
        if not t or t in STOP_TAGS:
            continue
        # 순수 숫자(예: '1') 는 스킵. 단 26Q1 같은 건 살림.
        if t.isdigit():
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(t)
    # 타입도 태그로 (중복 방지)
    if typ not in tags:
        tags.append(typ)
    return tags


def build_frontmatter(filename: str) -> dict:
    stem = filename[:-3] if filename.endswith(".md") else filename
    typ = infer_type(stem)
    # 날짜: 카테고리 접두사 있으면 벗긴 후 파싱
    working = strip_prefix(stem)
    date_val, _ = parse_date(working)
    source = infer_source(stem)
    title = clean_title(stem)
    tags = extract_tags(stem, typ)

    meta: dict = {"title": title, "type": typ, "tags": tags}
    if date_val:
        meta["date"] = date_val
    if source:
        meta["source"] = source
    return meta


def render_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key in FIELD_ORDER:
        if key not in meta or meta[key] is None:
            continue
        val = meta[key]
        if isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("중요도: false")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ─── 프런트매터 추가 ─────────────────────────────────────────────────────

def add_frontmatter_to_file(path: Path) -> str:
    """
    Returns: 'added' | 'has_fm' | 'empty'
    """
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return "empty"
    if raw.startswith("---\n") or raw.startswith("---\r\n"):
        return "has_fm"
    meta = build_frontmatter(path.name)
    fm = render_frontmatter(meta)
    body = raw.lstrip("\n").lstrip("\r\n")
    path.write_text(fm + "\n" + body, encoding="utf-8")
    return "added"


# ─── 파일 이동 ────────────────────────────────────────────────────────────

def move_file(src: Path, dst_folder: Path) -> str:
    """
    Returns: 'moved' | 'collision'
    같은 이름 파일이 대상에 있으면 이동 스킵.
    """
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst = dst_folder / src.name
    if dst.exists():
        return "collision"
    shutil.move(str(src), str(dst))
    return "moved"


def match_move_prefix(name: str) -> Path | None:
    # 긴 접두사(call2_/meeting2_)를 먼저 매칭
    for prefix in sorted(MOVE_MAP.keys(), key=len, reverse=True):
        if name.startswith(prefix):
            return MOVE_MAP[prefix]
    return None


# ─── 메인 ─────────────────────────────────────────────────────────────────

def main():
    if not INBOX.exists():
        print(f"[ERR] inbox not found: {INBOX}", file=sys.stderr)
        sys.exit(1)

    files = sorted(p for p in INBOX.iterdir() if p.is_file() and p.suffix == ".md")

    added = has_fm = empty = 0
    moved = collision = 0
    log_lines: list[str] = []

    # 1. 프런트매터 추가 (이동 전에)
    for p in files:
        result = add_frontmatter_to_file(p)
        if result == "added":
            added += 1
            log_lines.append(f"  + FM   {p.name}")
        elif result == "empty":
            empty += 1

    # 2. 이동 (프런트매터 붙은 후 이동해야 target 폴더에서도 FM 유지)
    files_after = sorted(p for p in INBOX.iterdir() if p.is_file() and p.suffix == ".md")
    for p in files_after:
        target = match_move_prefix(p.name)
        if target is None:
            continue
        result = move_file(p, target)
        if result == "moved":
            moved += 1
            log_lines.append(f"  → MOVE {p.name}  →  {target.name}")
        else:
            collision += 1
            log_lines.append(f"  ! SKIP {p.name}  (collision in {target.name})")

    print(f"[inbox_sort] scanned={len(files)}  FM_added={added}  FM_exists={has_fm}  empty={empty}")
    print(f"[inbox_sort] moved={moved}  collision={collision}")
    for line in log_lines:
        print(line)


if __name__ == "__main__":
    main()
