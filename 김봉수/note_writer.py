"""
Obsidian 월별 노트 writer.

- 노트 파일이 없으면 frontmatter + 제목을 포함해 신규 생성.
- 이미 있으면 본문 끝에 `---` 구분선과 함께 append.
- 동일한 포스트(fingerprint 동일)는 다시 쓰지 않는다 — idempotent.
- 각 포스트 헤더는 `#### MMDD HH:MM <요약>`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from config import NOTE_DIR, NOTE_FILENAME_TEMPLATE, PROFILE_URL
from scraper import Post, _normalize_text_head
from summary import summarize


FRONTMATTER_TEMPLATE = """---
type: curation
person: 김봉수
month: {year}-{month:02d}
source: {source}
tags:
  - 김봉수
  - 큐레이션
  - 조선
---

# 김봉수 {yymm}
"""


@dataclass
class WriteResult:
    path: Path
    created: bool
    appended: int
    skipped_duplicates: int


def note_path_for(target_date: date) -> Path:
    yymm = target_date.strftime("%y%m")
    return NOTE_DIR / NOTE_FILENAME_TEMPLATE.format(yymm=yymm)


def _render_frontmatter(target_date: date) -> str:
    yymm = target_date.strftime("%y%m")
    return FRONTMATTER_TEMPLATE.format(
        year=target_date.year,
        month=target_date.month,
        yymm=yymm,
        source=PROFILE_URL,
    )


def _render_post(post: Post, target_date: date) -> str:
    header_date = target_date.strftime("%m%d")
    summary = summarize(post.text)
    if summary:
        header = f"#### {header_date} {post.time_str} {summary}"
    else:
        header = f"#### {header_date} {post.time_str}"
    body = post.text.rstrip()
    return f"{header}\n\n{body}\n"


def _existing_fingerprints(content: str) -> set[str]:
    """기존 노트에 이미 기록된 포스트의 fingerprint 집합을 추출.

    각 `#### MMDD HH:MM ...` 블록의 본문에서 `정규화_앞80자` fingerprint를
    만든다. 시각(HH:MM)은 키에 넣지 않는다 — `Post.fingerprint` 와 동일하게
    본문만으로 식별해, 같은 글이 다른 시각으로 재수집돼도 중복으로 잡는다.
    """
    fingerprints: set[str] = set()

    # 각 포스트 블록: 헤더 → 빈 줄 → 본문 → (다음 ---/#### 또는 문서 끝)
    block_re = re.compile(
        r"^####\s+\d{4}\s+(?:\d{2}:\d{2}|\?\?:\?\?)[^\n]*\n\n(.*?)(?=\n\s*---\s*\n|\n####\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for m in block_re.finditer(content):
        body = m.group(1).strip()
        fingerprints.add(_normalize_text_head(body, 80))
    return fingerprints


def write_monthly_note(posts: Iterable[Post], target_date: date) -> WriteResult:
    """월별 노트에 포스트들을 기록한다.

    posts 는 시간순으로 이미 정렬되어 있다고 가정한다(scraper.fetch_posts_for가 보장).
    """
    posts = list(posts)
    path = note_path_for(target_date)
    path.parent.mkdir(parents=True, exist_ok=True)

    created = False
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        existing = _render_frontmatter(target_date)
        created = True

    existing_fps = _existing_fingerprints(existing)

    new_blocks: list[str] = []
    skipped = 0
    for post in posts:
        fp = post.fingerprint()
        if fp in existing_fps:
            skipped += 1
            continue
        new_blocks.append(_render_post(post, target_date))
        existing_fps.add(fp)

    if not new_blocks and not created:
        # 추가할 것도 없고 새 파일도 아니면 I/O 생략.
        return WriteResult(path=path, created=False, appended=0, skipped_duplicates=skipped)

    # 조립.
    body_parts: list[str] = [existing.rstrip()]
    for block in new_blocks:
        body_parts.append("---")
        body_parts.append(block.rstrip())
    final_text = "\n\n".join(body_parts) + "\n"

    path.write_text(final_text, encoding="utf-8")

    return WriteResult(
        path=path,
        created=created,
        appended=len(new_blocks),
        skipped_duplicates=skipped,
    )
