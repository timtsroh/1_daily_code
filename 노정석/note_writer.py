#!/usr/bin/env python3
"""Obsidian 월별 노트 쓰기/append 로직.

파일 경로: {VAULT}/3 큐레이션/노정석_YYMM.md
파일 없으면 frontmatter + 제목 포함하여 신규 생성.
파일 있으면 끝에 `---` 구분선과 함께 append.

Idempotent: 동일한 `#### MM/DD HH:MM` 헤더 + 동일한 본문 첫 줄이 이미 있으면 스킵.
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import List


VAULT_ROOT = '/Users/tealeaf/Obsidian/Sync1'
INBOX_DIR = os.path.join(VAULT_ROOT, '3 큐레이션')


def month_note_path(yesterday: date) -> str:
    filename = f'노정석_{yesterday.strftime("%y%m")}.md'
    return os.path.join(INBOX_DIR, filename)


def _frontmatter(yesterday: date) -> str:
    ym = yesterday.strftime('%Y-%m')
    return (
        '---\n'
        'type: curation\n'
        'person: 노정석\n'
        f'month: {ym}\n'
        'source: https://www.facebook.com/chester.roh\n'
        'tags:\n'
        '  - 노정석\n'
        '  - 큐레이션\n'
        '---\n'
        '\n'
        f'# 노정석 {yesterday.strftime("%y%m")}\n'
    )


def _short_preview(text: str, max_words: int = 5) -> str:
    """본문 첫 줄을 '5단어 이내' 요약 대용으로 사용.
    LLM이 없으므로 원문 첫 줄을 자연스럽게 잘라 헤더에 부착한다.
    """
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), '')
    if not first:
        return ''
    # 불필요한 URL은 제거
    first = re.sub(r'https?://\S+', '', first).strip()
    if not first:
        return ''
    # 공백 기준 어절 분리 (한/영 혼합 허용)
    words = first.split()
    preview = ' '.join(words[:max_words])
    # 긴 문장 컷
    if len(preview) > 40:
        preview = preview[:40].rstrip() + '…'
    return preview


def _post_block(post: dict, yesterday: date) -> str:
    mmdd = yesterday.strftime('%m/%d')
    hhmm = post['time_str']
    preview = _short_preview(post['text'])
    header = f'#### {mmdd} {hhmm} {preview}'.rstrip()
    body = post['text'].strip()
    return f'{header}\n\n{body}\n'


def _extract_existing_keys(content: str) -> set:
    """기존 노트의 (HH:MM, 본문첫줄) 튜플 집합을 추출해 중복 판정에 사용."""
    keys = set()
    lines = content.splitlines()
    i = 0
    header_re = re.compile(r'^####\s+\d{2}/\d{2}\s+(\d{2}:\d{2}|\?\?:\?\?)')
    while i < len(lines):
        m = header_re.match(lines[i])
        if m:
            hhmm = m.group(1)
            # 다음 non-empty, non-separator 줄이 본문 첫 줄
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].strip() == '---'):
                j += 1
            first_body = lines[j].strip() if j < len(lines) else ''
            keys.add((hhmm, first_body[:40]))
        i += 1
    return keys


def _post_key(post: dict) -> tuple:
    first = next((ln.strip() for ln in post['text'].splitlines() if ln.strip()), '')
    return (post['time_str'], first[:40])


def write_posts(posts: List[dict], yesterday: date) -> dict:
    """포스트 리스트를 월별 노트에 저장.

    반환: { 'path': str, 'created': bool, 'appended': int, 'skipped': int }
    """
    os.makedirs(INBOX_DIR, exist_ok=True)
    path = month_note_path(yesterday)

    file_exists = os.path.exists(path)
    existing_keys: set = set()
    if file_exists:
        with open(path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        existing_keys = _extract_existing_keys(existing_content)
    else:
        existing_content = ''

    new_blocks: List[str] = []
    appended = 0
    skipped = 0
    for post in posts:
        k = _post_key(post)
        if k in existing_keys:
            skipped += 1
            continue
        new_blocks.append(_post_block(post, yesterday))
        existing_keys.add(k)
        appended += 1

    if not file_exists:
        # 신규 파일 — 포스트가 0개여도 헤더까지는 생성하지 않고, 0이면 파일 자체를 만들지 않음
        if not new_blocks:
            return {'path': path, 'created': False, 'appended': 0, 'skipped': skipped}
        body = _frontmatter(yesterday) + '\n---\n\n' + '\n---\n\n'.join(new_blocks)
        if not body.endswith('\n'):
            body += '\n'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        return {'path': path, 'created': True, 'appended': appended, 'skipped': skipped}

    if not new_blocks:
        return {'path': path, 'created': False, 'appended': 0, 'skipped': skipped}

    suffix = existing_content
    if not suffix.endswith('\n'):
        suffix += '\n'
    append_chunk = '\n---\n\n' + '\n---\n\n'.join(new_blocks)
    if not append_chunk.endswith('\n'):
        append_chunk += '\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(suffix + append_chunk)
    return {'path': path, 'created': False, 'appended': appended, 'skipped': skipped}
