#!/usr/bin/env python3
"""
telegram_client.py
Telethon으로 t.me/HI_GS 채널에서 지정 기간 이후의 포스트를 수집한다.

반환 항목:
    {
        "message_id": int,
        "date_kst": date,          # KST 기준 날짜
        "datetime_kst": datetime,  # KST 기준 일시
        "text": str,               # 본문 (엔티티 병합 X — 원본 텍스트)
        "bitly_urls": [str, ...],  # 본문·엔티티에서 추출한 bit.ly URL
    }

bit.ly만 취급한다. buly.kr 등은 제외.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List

from telethon import TelegramClient
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

from config import API_ID, API_HASH, SESSION_FILE, CHANNEL, FETCH_LIMIT, BITLY_HOSTS

KST = timezone(timedelta(hours=9))

_BITLY_RE = re.compile(
    r"https?://(?:bit\.ly|bitly\.com)/[A-Za-z0-9_\-]+",
    re.IGNORECASE,
)


@dataclass
class Post:
    message_id: int
    date_kst: date
    datetime_kst: datetime
    text: str
    bitly_urls: List[str] = field(default_factory=list)


def _extract_bitly_urls(text: str, entities) -> List[str]:
    urls: List[str] = []

    # 1) entities — MessageEntityTextUrl.url 필드와 MessageEntityUrl(본문 슬라이스)
    if entities:
        for ent in entities:
            if isinstance(ent, MessageEntityTextUrl) and ent.url:
                urls.append(ent.url)
            elif isinstance(ent, MessageEntityUrl):
                slice_ = text[ent.offset : ent.offset + ent.length]
                urls.append(slice_)

    # 2) 혹시 엔티티가 누락된 경우를 대비해 본문 정규식 스캔
    urls.extend(_BITLY_RE.findall(text or ""))

    # 엔티티 오프셋 오차로 `ttp://bit.ly/...` 같은 비정상 URL이 섞일 수 있으므로
    # 정규식으로 재추출한 것만 채택한다 (entity URL은 후보일 뿐).
    bitly_clean: List[str] = []
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        lower = u.lower()
        if "buly.kr" in lower:
            continue
        # bit.ly 정규식으로 실제 매치 추출 (앞뒤 잡음 제거)
        for m in _BITLY_RE.findall(u):
            bitly_clean.append(m)
        # 엔티티에서 넘어온 원본이 완전히 정규식 매치인 경우에도 추가
        if _BITLY_RE.fullmatch(u) is not None and u not in bitly_clean:
            bitly_clean.append(u)

    # 중복 제거 (삽입 순서 유지)
    seen = set()
    result: List[str] = []
    for u in bitly_clean:
        if u in seen:
            continue
        seen.add(u)
        result.append(u)
    return result


async def fetch_posts_since(start_date_kst: date) -> List[Post]:
    """start_date_kst 이후(포함) 포스트 중 bit.ly URL이 1개 이상 있는 것을 수집.

    KST 기준 날짜를 사용한다.
    """
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                f"Telegram 세션({SESSION_FILE}.session)이 인증되어 있지 않다. "
                "전종현 스킬의 reauth.py를 먼저 실행해 인증을 복구하라."
            )

        collected: List[Post] = []
        async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT):
            if not msg.date:
                continue
            dt_kst = msg.date.astimezone(KST)
            d_kst = dt_kst.date()

            # 조회 시작일 이전이면 종료 (오래된 것부터 올라오지는 않지만,
            # iter_messages는 최신→과거 순이므로 break 가능)
            if d_kst < start_date_kst:
                break

            text = msg.text or ""
            if not text:
                continue

            urls = _extract_bitly_urls(text, msg.entities)
            if not urls:
                continue

            collected.append(
                Post(
                    message_id=msg.id,
                    date_kst=d_kst,
                    datetime_kst=dt_kst,
                    text=text,
                    bitly_urls=urls,
                )
            )

        # 오래된 순으로 정렬 (월별 노트 append 편의)
        collected.sort(key=lambda p: p.datetime_kst)
        return collected
    finally:
        await client.disconnect()
