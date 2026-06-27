"""영상 길이 조회 — yt-dlp로 duration(초) 추출.

RSS 피드에는 영상 길이가 없으므로 Shorts 판별을 위해 별도 조회가 필요하다.
yt-dlp는 YouTube Data API 키 없이 동작하며, 오픈 공개 영상이면 대부분 성공한다.
"""

from typing import Optional

import yt_dlp


def get_duration(vid_id: str) -> int:
    """video ID → duration(초). 실패 시 0 반환."""
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://youtu.be/{vid_id}", download=False)
            return int(info.get("duration") or 0)
    except Exception:
        return 0


def format_length(seconds: Optional[int]) -> str:
    """초 → 'H:MM:SS' 또는 'M:SS'."""
    s = int(seconds or 0)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
