#!/usr/bin/env python
"""
fetch_feed.py
@atomtodo 텔레그램 채널에서 지정 날짜(또는 날짜 범위) 메시지를 수집하고
첨부 미디어를 다운로드한다.

사용법:
    python fetch_feed.py                    # 어제(KST) 단일 일자
    python fetch_feed.py 260406             # 특정 YYMMDD
    python fetch_feed.py 260401 260405      # 시작-종료 범위 (포함)

출력:
    /tmp/todo_feed.json — 일자별 메시지 목록 (텍스트, grouped_id, 다운로드된 미디어 경로 포함)
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.tl.types import (
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityItalic,
    MessageEntityPre,
    MessageEntityTextUrl,
    MessageEntityUnderline,
    MessageEntityUrl,
)

# ── 설정 (references/channel_info.md 참조) ──────────────────────────────────
API_ID = 32844347
API_HASH = "432b3c2ca6b5e925320031c3e234ac58"
SESSION_FILE = "C:/Users/DELL/.claude/tg_session"
CHANNEL = "atomtodo"
INBOX = "C:/Obsidian/Sync1/02 Daily/1 day"
IMG_DIR = "C:/Obsidian/Sync1/A3 Assets/1 IMG"
OUT_JSON = "/tmp/todo_feed.json"
FETCH_LIMIT = 1000
# ────────────────────────────────────────────────────────────────────────────

KST = timezone(timedelta(hours=9))


def parse_args(argv):
    """인자 파싱: 없음 / YYMMDD / YYMMDD YYMMDD.

    Returns:
        (start, end, mode)
        - mode="24h": start/end는 datetime (최근 24시간), 오늘 날짜로 노트 저장
        - mode="date": start/end는 date (날짜 단위 필터)
    """
    now = datetime.now(KST)
    if len(argv) == 0:
        return now - timedelta(hours=24), now, "24h"
    if len(argv) == 1:
        d = datetime.strptime(argv[0], "%y%m%d").date()
        return d, d, "date"
    if len(argv) >= 2:
        s = datetime.strptime(argv[0], "%y%m%d").date()
        e = datetime.strptime(argv[1], "%y%m%d").date()
        if s > e:
            s, e = e, s
        return s, e, "date"


def build_markdown(text: str, entities) -> str:
    """Telegram entities → 마크다운."""
    if not entities:
        return text
    sorted_ents = sorted(entities, key=lambda e: e.offset)
    out = ""
    prev = 0
    for ent in sorted_ents:
        start, end = ent.offset, ent.offset + ent.length
        chunk = text[start:end]
        out += text[prev:start]
        if isinstance(ent, MessageEntityTextUrl):
            out += f"[{chunk}]({ent.url})"
        elif isinstance(ent, MessageEntityUrl):
            out += f"[{chunk}]({chunk})"
        elif isinstance(ent, (MessageEntityBold, MessageEntityUnderline)):
            out += f"**{chunk}**"
        elif isinstance(ent, MessageEntityItalic):
            out += f"*{chunk}*"
        elif isinstance(ent, (MessageEntityCode, MessageEntityPre)):
            out += f"`{chunk}`"
        else:
            out += chunk
        prev = end
    out += text[prev:]
    return out


async def main():
    start, end, mode = parse_args(sys.argv[1:])
    print(f"MODE={mode}")
    print(f"START={start.isoformat()}")
    print(f"END={end.isoformat()}")

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    # 1) 메시지 수집
    raw_by_date = {}  # date_iso → [msg, ...]
    if mode == "24h":
        # 최근 24시간 메시지 → 오늘 날짜 키로 통합
        today_iso = datetime.now(KST).date().isoformat()
        async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT):
            msg_dt = msg.date.astimezone(KST)
            if msg_dt < start:
                break
            if start <= msg_dt <= end:
                raw_by_date.setdefault(today_iso, []).append(msg)
    else:
        # 날짜 단위 필터 (기존 동작)
        async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT):
            d = msg.date.astimezone(KST).date()
            if d < start:
                break
            if start <= d <= end:
                raw_by_date.setdefault(d.isoformat(), []).append(msg)

    # 2) 일자별로 그룹·미디어 처리
    result = {}
    for date_iso, msgs in raw_by_date.items():
        msgs.reverse()  # 시간 오름차순
        yymmdd = datetime.fromisoformat(date_iso).strftime("%y%m%d")

        # grouped_id로 묶기 (텍스트는 일반적으로 첫 메시지에만 존재)
        groups = []  # [{primary_msg, members:[msg,...]}]
        idx_by_group = {}
        for m in msgs:
            gid = m.grouped_id
            if gid is None:
                groups.append({"primary": m, "members": [m]})
            else:
                if gid in idx_by_group:
                    groups[idx_by_group[gid]]["members"].append(m)
                else:
                    idx_by_group[gid] = len(groups)
                    groups.append({"primary": m, "members": [m]})
        # 각 그룹의 primary는 텍스트 있는 첫 메시지로 갱신
        for g in groups:
            for mm in g["members"]:
                if mm.text:
                    g["primary"] = mm
                    break

        items = []
        for g in groups:
            primary = g["primary"]
            time_str = primary.date.astimezone(KST).strftime("%H%M")
            text_md = build_markdown(primary.text or "", primary.entities) if primary.text else ""

            # 미디어 다운로드 (해당 그룹의 모든 멤버) → 9 IMG 폴더
            os.makedirs(IMG_DIR, exist_ok=True)
            media_paths = []
            media_msgs = [m for m in g["members"] if m.media]
            for i, mm in enumerate(media_msgs, 1):
                base = f"todo_{yymmdd}_{time_str}_{i}"
                path = await mm.download_media(file=os.path.join(IMG_DIR, base))
                if path:
                    media_paths.append(os.path.basename(path))

            items.append({
                "id": primary.id,
                "time": primary.date.astimezone(KST).strftime("%H:%M"),
                "text": text_md,
                "media": media_paths,
            })

        result[date_iso] = items
        print(f"{date_iso}: {len(items)}건 (미디어 {sum(len(i['media']) for i in items)}개)")

    with open(OUT_JSON, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"WROTE {OUT_JSON}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
