"""인자 → 날짜 범위 변환."""

from datetime import date, datetime, timedelta
from typing import List, Tuple

from .config import KST


def parse_yymmdd(s: str) -> date:
    """'YYMMDD' → date."""
    return datetime.strptime(s, "%y%m%d").date()


def resolve_dates(args: List[str]) -> Tuple[date, date]:
    """CLI 인자 리스트를 (start, end) 날짜 쌍으로 해석한다.

    - 인자 없음        → 이번 주 월요일 ~ 오늘 (KST)
    - 'YYMMDD'         → 해당 날짜 ~ 오늘
    - 'YYMMDD-YYMMDD'  → 범위
    - 'YYMMDD YYMMDD'  → 범위 (공백 구분)
    """
    today = datetime.now(KST).date()

    if not args:
        monday = today - timedelta(days=today.weekday())
        return monday, today

    if len(args) == 1:
        arg = args[0]
        if "-" in arg:
            a, b = arg.split("-", 1)
            return parse_yymmdd(a), parse_yymmdd(b)
        return parse_yymmdd(arg), today

    return parse_yymmdd(args[0]), parse_yymmdd(args[1])
