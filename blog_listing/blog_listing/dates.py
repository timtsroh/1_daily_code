"""인자 → 날짜 범위 변환."""

from datetime import date, datetime, timedelta
from typing import List, Tuple

from .config import KST


def _parse_ymd(s: str) -> date:
    """'YYYY-MM-DD' → date."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def _month_range(year: int, month: int) -> Tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def resolve_dates(args: List[str]) -> Tuple[date, date]:
    """CLI 인자를 (start, end) 날짜로 해석.

    - 인자 없음                            → 어제 하루 (Asia/Seoul)
    - 'YYYY-MM-DD'                         → 해당 날짜 하루
    - 'YYYY-MM-DD YYYY-MM-DD'              → 범위
    - '--month YYYY-MM'                    → 해당 월 전체
    - '--since YYYY-MM-DD --until YYYY-MM-DD' → 범위
    - '--since YYYY-MM-DD'                 → since ~ 오늘
    """
    today = datetime.now(KST).date()

    if not args:
        y = today - timedelta(days=1)
        return y, y

    # --month YYYY-MM
    if args[0] == "--month" and len(args) >= 2:
        y, m = args[1].split("-")
        return _month_range(int(y), int(m))

    # --since / --until
    since = until = None
    it = iter(args)
    for a in it:
        if a == "--since":
            since = _parse_ymd(next(it))
        elif a == "--until":
            until = _parse_ymd(next(it))
    if since is not None:
        return since, (until or today)

    # positional forms
    if len(args) == 1:
        d = _parse_ymd(args[0])
        return d, d
    if len(args) == 2:
        return _parse_ymd(args[0]), _parse_ymd(args[1])

    raise ValueError(f"인자 해석 실패: {args}")
