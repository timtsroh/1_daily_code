"""요약 테이블 출력."""

from typing import Dict


def print_summary(stats: Dict[str, Dict]) -> None:
    """채널별 스캔 통계를 표 형식으로 출력한다.

    stats[source] = {total, filtered, duped, added, error?}
    """
    print("\n=== 결과 요약 ===")
    total_added = 0
    total_filtered = 0
    total_duped = 0
    total_rss = 0
    for source, s in stats.items():
        err = f" (ERROR: {s['error']})" if s.get("error") else ""
        print(
            f"  {source}: RSS {s['total']}건, 추가 {s['added']}건, "
            f"Shorts제외 {s['filtered']}건, 중복 {s['duped']}건{err}"
        )
        total_rss += s["total"]
        total_added += s["added"]
        total_filtered += s["filtered"]
        total_duped += s["duped"]
    print(
        f"  합계: RSS {total_rss}건, 추가 {total_added}건, "
        f"Shorts제외 {total_filtered}건, 중복 {total_duped}건"
    )
