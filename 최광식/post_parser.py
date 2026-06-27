#!/usr/bin/env python3
"""
post_parser.py
텔레그램 포스트 텍스트에서 파일명 구성 요소를 추출.

SKILL.md / PRD.md 규칙:

| 항목     | 추출 방법                                                               |
|----------|------------------------------------------------------------------------|
| 분류     | `#종목명` 해시태그 있으면 기업분석, 없으면 산업분석                     |
| 기업명   | 첫 번째 `#해시태그` 값 (`#대한조선` → `대한조선`)                       |
| 산업명   | `#해시태그` 없을 때 — 텍스트 내 `:` 앞의 명칭 (`다올 선박:` → `다올 선박`)|
| 제목     | `「」` 또는 `『』` 안의 텍스트; 없을 때는 포스트 텍스트 앞 30자          |

기업/산업 구별 heuristic:
  - 해시태그가 있으면 첫 해시태그 전체를 태그값으로 사용 → 기업분석
  - 없으면 산업분석으로 분류
  - 산업명 추출이 실패하면 None 반환 (호출부에서 skip)

HTML 엔티티(`&#33;`, `&amp;` 등)는 디코드한다.
컴플라이언스 문구는 본문에 남겨둔다 (노트 저장 시점에서 걸러낸다).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# 첫 번째 해시태그: 한글/영문/숫자 + 일부 특수문자 허용
# (`#대한조선`, `#HD현대중공업`, `#한화에어로스페이스` 등)
_HASHTAG_RE = re.compile(r"#([A-Za-z0-9가-힣_]+)")

# 「」 또는 『』 안의 문자열 (비탐욕)
_TITLE_RE = re.compile(r"[「『]([^」』]+)[」』]")

# `:` 또는 `：`(전각) 앞의 섹터/시리즈 명칭. 줄 단위로 먼저 찾는다.
# `://` (URL 스키마)는 건너뛴다.
_COLON_PREFIX_RE = re.compile(
    r"^\s*([^:\n：]+?)\s*[:：](?!//)",
    re.MULTILINE,
)

# URL/링크 마커로 시작하는 줄 — 산업명 추출 대상에서 제외
_LINK_LINE_RE = re.compile(
    r"^\s*(?:☞|▶️|https?://|www\.|#)",
    re.UNICODE,
)

# 파일명에서 금지되는 문자 (macOS + Windows 호환성)
_FILENAME_FORBIDDEN = re.compile(r'[\\/:*?"<>|\r\n\t]')


@dataclass
class PostMeta:
    category: str          # "기업분석" | "산업분석"
    entity: str            # 기업명 or 산업명
    title: str
    datetime_kst: datetime

    @property
    def yymmdd(self) -> str:
        return self.datetime_kst.strftime("%y%m%d")

    @property
    def mmdd(self) -> str:
        return self.datetime_kst.strftime("%m%d")


def _decode_html(s: str) -> str:
    return html.unescape(s or "")


def _clean_filename_piece(s: str) -> str:
    """파일명에 쓸 수 있도록 금지 문자만 제거. `_`는 구분기호이므로 텍스트 내
    기존 `_`는 그대로 둔다 (원문 존중). 제어문자·슬래시만 제거."""
    s = _decode_html(s).strip()
    s = _FILENAME_FORBIDDEN.sub(" ", s)
    # 연속 공백 축소
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_title(text: str) -> Optional[str]:
    text = _decode_html(text)
    m = _TITLE_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def _extract_first_hashtag(text: str) -> Optional[str]:
    text = _decode_html(text)
    m = _HASHTAG_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def _extract_sector_from_colon(text: str) -> Optional[str]:
    """해시태그가 없을 때 산업명 후보로 `:` 앞 명칭을 추출.

    다올 포스트 샘플:
        `🛳 신조선가지수 상승. 탱커와 가스선 발주와 LNG FID 계속`  ← `:` 없음
        `⛴ #조선 「…」`                                            ← 해시태그 있음
        `다올 선박: …`                                             ← `:` 있음

    `:` 앞 명칭을 그대로 쓰면 이모지/번호/불필요 기호가 섞이기 쉽다.
    첫 줄에서 추출하고, 앞쪽 비-한글/영문 문자는 제거한다. 결과가 너무
    길거나 비어있으면 None.
    """
    text = _decode_html(text).strip()
    if not text:
        return None

    # 첫 20줄 중에서 첫 `:` 매칭만 취한다 (포스트 후반의 본문 콜론은 잡지 말 것)
    # 실무적으로는 맨 처음 유의미한 줄의 `:` 만 사용.
    for raw in text.splitlines()[:5]:
        raw = raw.strip()
        if not raw:
            continue
        # URL·링크 마커 줄은 건너뛴다
        if _LINK_LINE_RE.match(raw):
            continue
        if ":" not in raw and "：" not in raw:
            continue
        m = _COLON_PREFIX_RE.match(raw)
        if not m:
            continue
        candidate = m.group(1).strip()
        # URL 조각이 들어왔다면 무시
        if "://" in candidate or candidate.lower() in ("http", "https", "ftp"):
            continue
        # 이모지·불필요한 선행 기호를 걷어내고 남은 한글/영문 구간을 취한다.
        candidate = re.sub(
            r"^[\s\W_]*",  # 선행 공백·기호 제거
            "",
            candidate,
            flags=re.UNICODE,
        )
        candidate = candidate.strip()
        if not candidate:
            continue
        # 길이 제한 (20자 이내) — 너무 길면 콜론 앞이 문장일 가능성
        if len(candidate) > 20:
            continue
        return candidate

    return None


def parse_post(text: str, datetime_kst: datetime) -> Optional[PostMeta]:
    """포스트 메타 추출. 분류 불가 시 None."""
    text = text or ""
    if not text.strip():
        return None

    hashtag = _extract_first_hashtag(text)
    title_raw = _extract_title(text)

    # 분류 결정
    if hashtag:
        category = "기업분석"
        # 단, 첫 해시태그가 섹터명("조선", "방산", "기계" 등)이면 산업분석으로
        # 재분류한다. 다올 포스트 관행: `#조선`은 섹터, `#대한조선`은 기업.
        if hashtag in _SECTOR_HASHTAGS:
            category = "산업분석"
        entity = hashtag
    else:
        sector = _extract_sector_from_colon(text)
        if not sector:
            return None
        category = "산업분석"
        entity = sector

    # 제목
    if title_raw:
        title = title_raw
    else:
        # fallback — 본문 앞 30자 (줄바꿈·연속 공백 정규화 후)
        flat = re.sub(r"\s+", " ", _decode_html(text)).strip()
        title = flat[:30]

    entity = _clean_filename_piece(entity)
    title = _clean_filename_piece(title)

    if not entity or not title:
        return None

    return PostMeta(
        category=category,
        entity=entity,
        title=title,
        datetime_kst=datetime_kst,
    )


# 다올 최광식 채널에서 섹터로 해시태그를 다는 경우의 키워드 목록.
# (기업명 해시태그와 구분하기 위해 보수적으로 유지)
_SECTOR_HASHTAGS = {
    "조선",
    "기계",
    "방산",
    "항공",
    "해양",
    "조선기자재",
    "건설기계",
    "중공업",
    "플랜트",
    "에너지",
    "LNG",
    "탱커",
    "벌크",
}
