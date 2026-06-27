"""핵심 스캔 로직 — 채널별로 RSS 수집 → Shorts 필터 → 중복 제거."""

from datetime import date
from typing import Dict, List, Set, Tuple

from .config import MIN_DURATION
from .duration import format_length, get_duration
from .rss import get_channel_id, get_rss_videos


def scan_channel(
    source: str,
    url: str,
    start_date: date,
    end_date: date,
    existing_ids: Set[str],
) -> Tuple[List[dict], Dict[str, int], str]:
    """단일 채널 스캔.

    Returns:
        (added_videos, stats, error_message)
        stats keys: total, filtered, duped, added
        error_message: 실패 시 사유 문자열, 정상이면 ''.
    """
    stats = {"total": 0, "filtered": 0, "duped": 0, "added": 0}
    added: List[dict] = []

    cid = get_channel_id(url)
    if not cid:
        return added, stats, "channel_id 추출 실패"

    videos = get_rss_videos(cid, start_date, end_date)
    stats["total"] = len(videos)

    for v in videos:
        if v["id"] in existing_ids:
            stats["duped"] += 1
            print(f"  skip(중복): {v['title'][:50]}")
            continue

        dur = get_duration(v["id"])
        if dur <= MIN_DURATION:
            stats["filtered"] += 1
            print(f"  제외({dur}s): {v['title'][:50]}")
            continue

        v["duration"] = dur
        v["length"] = format_length(dur)
        v["source"] = source
        added.append(v)
        existing_ids.add(v["id"])  # 같은 배치 내 중복 방지
        stats["added"] += 1
        print(f"  추가: {v['published']} | {v['length']:>8s} | {v['title'][:50]}")

    return added, stats, ""
