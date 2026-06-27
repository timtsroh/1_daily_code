#!/usr/bin/env python3
"""
write_note.py
수집된 텔레그램 피드를 Obsidian 월별 노트에 병합·저장한다.

- 파일 없음 → 신규 생성
- 파일 있음 → 날짜·시간순으로 기존 내용에 병합 (중복 건너뜀)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

# ── Obsidian 경로 / 파일명 규칙 ────────────────────────────────────────────
VAULT = "/Users/tealeaf/Obsidian/Sync1/03 Sources/3 큐레이션"
PERSON = "전종현"
CHANNEL_URL = "https://t.me/chunjonghyun"
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class WriteResult:
    filepath: str
    created: bool              # True=신규 생성, False=기존 파일 업데이트
    added: int                 # 실제로 새로 추가된 항목 수
    skipped: int               # 중복으로 건너뛴 항목 수


def note_filepath(year_month: str) -> str:
    """yymm → 전종현_yymm.md 절대경로."""
    return os.path.join(VAULT, f"{PERSON}_{year_month}.md")


def _entry_block(time: str, forwarded: str, body: str) -> str:
    """
    단일 피드 항목 마크다운 블록을 생성한다.

    헤더는 `#### HH:MM` 만 사용 (요약은 LLM이 채우던 자리라 비워둠).
    """
    lines = [f"#### {time}"]
    if forwarded:
        name, url = (forwarded.split("|", 1) + [""])[:2]
        if url:
            lines.append(f"> Forwarded from [{name}]({url})")
        else:
            lines.append(f"> Forwarded from {name}")
        lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _new_note(year_month: str, date_iso: str, entry_blocks: List[str]) -> str:
    """새 월별 노트 전체 내용을 생성한다."""
    yyyy_mm = f"20{year_month[:2]}-{year_month[2:]}"
    entries_md = "\n\n---\n\n".join(entry_blocks)
    return f"""---
tags: [{PERSON}, 텔레그램, 산업분석]
date: {yyyy_mm}
source: {CHANNEL_URL}
---

# {PERSON} {year_month}

---
## {date_iso}

{entries_md}

---
"""


def _merge(
    existing: str,
    date_iso: str,
    entry_blocks: List[Tuple[str, str]],
) -> Tuple[str, int, int]:
    """
    기존 노트에 새 항목을 병합한다.

    entry_blocks: [(time_str, block_markdown), ...] (시간순 오름차순 가정)
    반환: (updated_content, added_count, skipped_count)
    """
    date_header = f"## {date_iso}"

    if date_header in existing:
        # 해당 날짜 섹션이 이미 있음 → 섹션 경계 찾기
        section_start = existing.index(date_header)
        after = existing[section_start + len(date_header):]
        next_section = re.search(r"\n## ", after)
        if next_section:
            section_end = section_start + len(date_header) + next_section.start()
        else:
            section_end = len(existing)

        section = existing[section_start:section_end]

        added_blocks: List[str] = []
        added = 0
        skipped = 0
        for time_str, block in entry_blocks:
            # 중복 체크: 동일 #### HH:MM 헤더가 이미 존재?
            if re.search(rf"^#### {re.escape(time_str)}\b", section, re.MULTILINE):
                skipped += 1
                continue
            added_blocks.append(block)
            added += 1

        if not added_blocks:
            return existing, 0, skipped

        addition = "\n\n---\n\n" + "\n\n---\n\n".join(added_blocks)
        updated = (
            existing[:section_end].rstrip()
            + addition
            + "\n"
            + existing[section_end:]
        )
        return updated, added, skipped

    # 해당 날짜 섹션 없음 → 날짜순에 맞는 위치에 삽입
    blocks_only = [b for _, b in entry_blocks]
    new_section = (
        f"## {date_iso}\n\n" + "\n\n---\n\n".join(blocks_only) + "\n\n---"
    )

    date_sections = list(re.finditer(r"\n## (\d{4}-\d{2}-\d{2})", existing))
    insert_pos = len(existing)
    for m in date_sections:
        if m.group(1) > date_iso:
            insert_pos = m.start()
            break

    updated = (
        existing[:insert_pos].rstrip()
        + f"\n\n---\n{new_section}\n"
        + existing[insert_pos:].lstrip()
    )
    return updated, len(blocks_only), 0


def write_entries(
    year_month: str,
    date_iso: str,
    entries: Iterable,
) -> WriteResult:
    """
    entries: FeedEntry 혹은 {"time","body","forwarded"} dict 이터러블.
    시간순 오름차순으로 정렬 후 노트를 생성/병합한다.
    """
    os.makedirs(VAULT, exist_ok=True)
    filepath = note_filepath(year_month)

    # 통일된 (time, forwarded, body) 튜플로 변환
    items: List[Tuple[str, str, str]] = []
    for e in entries:
        if hasattr(e, "time"):
            items.append((e.time, getattr(e, "forwarded", "") or "", e.body))
        else:
            items.append((e["time"], e.get("forwarded", "") or "", e["body"]))

    items.sort(key=lambda x: x[0])  # HH:MM 사전순 = 시간순
    blocks: List[Tuple[str, str]] = [
        (t, _entry_block(t, f, b)) for (t, f, b) in items
    ]

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = f.read()
        updated, added, skipped = _merge(existing, date_iso, blocks)
        if added > 0:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(updated)
        return WriteResult(
            filepath=filepath, created=False, added=added, skipped=skipped
        )

    # 신규 파일
    content = _new_note(year_month, date_iso, [b for _, b in blocks])
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return WriteResult(
        filepath=filepath, created=True, added=len(blocks), skipped=0
    )
