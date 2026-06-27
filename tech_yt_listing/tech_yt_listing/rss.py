"""YouTube 채널 ID 추출 + RSS 피드 파서."""

import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import List, Optional

from .config import HTTP_TIMEOUT, KST, SSL_CTX, USER_AGENT

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=SSL_CTX) as resp:
        return resp.read()


def get_channel_id(handle_url: str) -> Optional[str]:
    """YouTube @handle URL에서 channel_id(UC...)를 추출한다.

    /videos 경로가 붙어 있어도 자동으로 처리한다.
    """
    url = handle_url.rstrip("/")
    if url.endswith("/videos"):
        url = url[: -len("/videos")]

    html = _fetch(url).decode("utf-8", errors="replace")
    m = re.search(r'"externalId":"(UC[^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r"channel_id=([^\"&]+)", html)
    if m:
        return m.group(1)
    return None


def get_rss_videos(channel_id: str, start_date: date, end_date: date) -> List[dict]:
    """채널 RSS 피드에서 [start_date, end_date] 범위 영상 목록을 반환한다.

    Returns: [{"title", "id", "url", "published"}] (published는 'YYYY-MM-DD' 문자열)
    """
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    xml_data = _fetch(url)
    root = ET.fromstring(xml_data)

    videos: List[dict] = []
    for entry in root.findall("atom:entry", _NS):
        title_el = entry.find("atom:title", _NS)
        vid_el = entry.find("yt:videoId", _NS)
        pub_el = entry.find("atom:published", _NS)
        if title_el is None or vid_el is None or pub_el is None:
            continue

        title = title_el.text or ""
        vid_id = vid_el.text or ""
        published_raw = pub_el.text or ""

        try:
            pub_date = datetime.fromisoformat(published_raw).astimezone(KST).date()
        except ValueError:
            continue

        if pub_date < start_date or pub_date > end_date:
            continue

        videos.append({
            "title": title,
            "id": vid_id,
            "url": f"https://youtu.be/{vid_id}",
            "published": str(pub_date),
        })
    return videos
