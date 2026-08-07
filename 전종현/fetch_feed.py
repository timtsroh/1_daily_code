#!/usr/bin/env python
"""
fetch_feed.py
텔레그램 채널 chunjonghyun에서 어제(KST) 날짜 메시지를 수집한다.

모듈로 import해서 사용하거나 단독 실행(디버깅)할 수 있다.

단독 실행 시 출력 형식:
    YESTERDAY_ISO:YYYY-MM-DD
    YEAR_MONTH:yymm
    COUNT:N
    ---MSG---
    TIME:HH:MM
    FORWARDED:채널명|URL   (해당 시)
    <마크다운 변환 본문>
    ...
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

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

# ── 설정 ───────────────────────────────────────────────────────────────────
API_ID = 32844347
API_HASH = "432b3c2ca6b5e925320031c3e234ac58"
SESSION_FILE = "C:/Users/DELL/.claude/tg_session"
CHANNEL = "chunjonghyun"
FETCH_LIMIT = 200
# ───────────────────────────────────────────────────────────────────────────

KST = timezone(timedelta(hours=9))


@dataclass
class FeedEntry:
    """단일 피드 메시지."""
    time: str                     # "HH:MM" (KST)
    body: str                     # 마크다운 본문
    forwarded: str = ""           # "채널명|URL" 형식 (없으면 빈 문자열)


@dataclass
class FeedResult:
    """fetch_yesterday() 반환 객체."""
    date_iso: str                 # YYYY-MM-DD
    year_month: str               # yymm
    entries: List[FeedEntry] = field(default_factory=list)


def yesterday_kst() -> date:
    """실행일 기준 전날(KST) 날짜 객체."""
    return datetime.now(KST).date() - timedelta(days=1)


def build_markdown(text: str, entities) -> str:
    """Telegram entities를 마크다운 텍스트로 변환한다."""
    if not entities:
        return text

    sorted_ents = sorted(entities, key=lambda e: e.offset)
    result = ""
    prev = 0
    for ent in sorted_ents:
        start = ent.offset
        end = ent.offset + ent.length
        chunk = text[start:end]
        result += text[prev:start]

        if isinstance(ent, MessageEntityTextUrl):
            result += f"[{chunk}]({ent.url})"
        elif isinstance(ent, MessageEntityUrl):
            result += f"[{chunk}]({chunk})"
        elif isinstance(ent, MessageEntityBold):
            result += f"**{chunk}**"
        elif isinstance(ent, MessageEntityItalic):
            result += f"*{chunk}*"
        elif isinstance(ent, MessageEntityUnderline):
            result += f"**{chunk}**"
        elif isinstance(ent, (MessageEntityCode, MessageEntityPre)):
            result += f"`{chunk}`"
        else:
            result += chunk

        prev = end
    result += text[prev:]
    return result


async def _fetch_async(target_date: date) -> FeedResult:
    """텔레그램에서 target_date의 메시지를 수집해 FeedResult를 반환한다."""
    result = FeedResult(
        date_iso=target_date.strftime("%Y-%m-%d"),
        year_month=target_date.strftime("%y%m"),
    )

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError(
            f"Telethon 세션 미인증: {SESSION_FILE}.session 이 없거나 만료됨. "
            f"reauth.py를 실행해 재인증하세요."
        )

    messages = []
    async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT):
        msg_date = msg.date.astimezone(KST).date()
        if msg_date == target_date:
            messages.append(msg)
        elif msg_date < target_date:
            break

    messages.reverse()  # 오래된 것부터 정렬 (시간순 오름차순)

    seen = set()
    for msg in messages:
        if not msg.text:
            continue

        key = msg.text[:30]
        if key in seen:
            continue
        seen.add(key)

        # Forwarded 처리
        forwarded = ""
        if msg.forward:
            fwd = msg.forward
            if hasattr(fwd, "channel_id") and fwd.channel_id:
                try:
                    fwd_entity = await client.get_entity(fwd.channel_id)
                    fwd_name = (
                        getattr(fwd_entity, "title", "")
                        or getattr(fwd_entity, "username", "")
                    )
                    fwd_username = getattr(fwd_entity, "username", "")
                    fwd_url = f"https://t.me/{fwd_username}" if fwd_username else ""
                    forwarded = f"{fwd_name}|{fwd_url}"
                except Exception:
                    forwarded = "Unknown|"
            elif hasattr(fwd, "from_name") and fwd.from_name:
                forwarded = f"{fwd.from_name}|"

        time_kst = msg.date.astimezone(KST).strftime("%H:%M")
        md_text = build_markdown(msg.text, msg.entities)

        result.entries.append(
            FeedEntry(time=time_kst, body=md_text, forwarded=forwarded)
        )

    await client.disconnect()
    return result


def fetch_yesterday(target: Optional[date] = None) -> FeedResult:
    """동기 래퍼: 어제(KST) 또는 주어진 날짜의 피드를 수집해 반환한다."""
    target_date = target or yesterday_kst()
    return asyncio.run(_fetch_async(target_date))


def _print_legacy(result: FeedResult) -> None:
    """레거시 스킬 출력 포맷 (디버깅·단독 실행용)."""
    print(f"YESTERDAY_ISO:{result.date_iso}")
    print(f"YEAR_MONTH:{result.year_month}")
    print(f"COUNT:{len(result.entries)}")
    for e in result.entries:
        print("---MSG---")
        print(f"TIME:{e.time}")
        if e.forwarded:
            print(f"FORWARDED:{e.forwarded}")
        print(e.body)


if __name__ == "__main__":
    res = fetch_yesterday()
    _print_legacy(res)
