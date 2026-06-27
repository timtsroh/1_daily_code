"""
포스트 본문에서 5단어 이내의 한국어 요약을 heuristic으로 추출한다.

원본 Claude Code 스킬은 LLM으로 요약했지만, 본 포팅은 순수 Python이므로
LLM 호출 대신 본문 첫 유의미한 라인에서 앞부분을 잘라 간이 요약을 만든다.
실제 이벤트 발생 시 사람이 노트에서 수동으로 다듬을 수 있다.
"""

from __future__ import annotations

import re

# 괄호(한글/영문) 처리: 본문 앞머리의 출처 표기(예: "(무역풍 오늘 기사)")를 제거.
_LEADING_PAREN_RE = re.compile(r"^\s*[\(（][^\)）]{0,40}[\)）]\s*")
# 흔한 조사·어미 — 필요시 앞에서 잘라낼 때 붙어 남으면 삭제.
_TAIL_PARTICLES = ("의", "이", "가", "을", "를", "은", "는", "에", "와", "과", "도", "로")


def _strip_leading_parenthetical(text: str) -> str:
    stripped = text
    while True:
        new = _LEADING_PAREN_RE.sub("", stripped)
        if new == stripped:
            return new
        stripped = new


def summarize(body: str, max_tokens: int = 5) -> str:
    """본문을 5단어 이내 한국어 요약 문자열로 변환."""
    if not body:
        return ""

    # 줄 단위로 첫 유의미한 라인을 뽑는다.
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = _strip_leading_parenthetical(line)
        # URL만 있는 라인은 스킵.
        if line.startswith("http") and " " not in line:
            continue
        # 특수문자/구분선 성격 라인은 스킵.
        if set(line) <= {".", "-", "_", "=", "·", "•", "*"}:
            continue
        # 문장부호/따옴표 제거.
        line = re.sub(r"[\"'`“”‘’]", "", line)
        line = re.sub(r"[.!?]+$", "", line).strip()

        if not line:
            continue

        # 공백 기준 앞에서 max_tokens 단어만 추출.
        tokens = line.split()
        if not tokens:
            continue
        short = tokens[:max_tokens]
        # 마지막 단어 뒤에 조사가 붙은 채 잘리면 어색하므로 제거 시도.
        if len(short) == max_tokens and short[-1][-1] in _TAIL_PARTICLES:
            short[-1] = short[-1].rstrip("".join(_TAIL_PARTICLES))
            if not short[-1]:
                short = short[:-1]
        summary = " ".join(short).strip()
        # 너무 긴 경우 글자 수로 한 번 더 안전하게 자른다.
        if len(summary) > 30:
            summary = summary[:30].rstrip()
        return summary

    return ""
