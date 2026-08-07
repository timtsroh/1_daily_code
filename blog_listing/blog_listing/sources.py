"""소스별 신규 글 수집.

각 fetcher 는 (start_date, end_date) 범위 내 글을 다음 형식 dict 로 반환:
    {"Format": str, "Writer": str, "Posted": "YYYY-MM-DD", "Title": str, "URL": str}
"""

import html
import json
import re
import urllib.request
from datetime import date, datetime
from typing import Dict, List

from .config import HTTP_TIMEOUT, USER_AGENT

_HDRS = {"User-Agent": USER_AGENT}


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=_HDRS)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read().decode("utf-8", errors="ignore")


def _in_range(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def _clean_title(s: str) -> str:
    """HTML 엔티티 unescape + 공백 정리."""
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ─────────────────────────────────────────────────────────
# Substack (Jamin, Apoorv, Sarah, Elad, ALAD, Dwarkesh, SemiAnalysis)
# ─────────────────────────────────────────────────────────
def fetch_substack(
    api_url: str, writer: str, start: date, end: date, format_label: str = "Substack"
) -> List[Dict]:
    """/api/v1/archive?limit=30&offset=N 을 순회하며 post_date 범위 필터.

    Substack API 는 limit 최대 30. 페이지의 최고령이 start 보다 오래되면 중단.
    """
    out: List[Dict] = []
    limit = 30
    offset = 0
    max_pages = 10  # safety (최대 300개 스캔)
    for _ in range(max_pages):
        try:
            raw = _fetch(f"{api_url}?limit={limit}&offset={offset}")
            data = json.loads(raw)
        except Exception as ex:
            print(f"  ERR substack fetch (offset={offset}): {ex}")
            break
        if not data:
            break

        oldest_pd = None
        for post in data:
            post_date = (post.get("post_date") or "")[:10]
            if not post_date:
                continue
            try:
                pd = datetime.strptime(post_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            if oldest_pd is None or pd < oldest_pd:
                oldest_pd = pd
            if not _in_range(pd, start, end):
                continue
            canonical = post.get("canonical_url", "") or ""
            url = canonical.replace("/p/", "/api/v1/p/", 1) if "/p/" in canonical else canonical
            title = post.get("title") or ""
            out.append({
                "Format": format_label,
                "Writer": writer,
                "Posted": post_date,
                "Title": _clean_title(title),
                "URL": url,
            })

        # 이 페이지의 가장 오래된 글이 start 이전이면 다음 페이지 필요 없음
        if oldest_pd is not None and oldest_pd < start:
            break
        if len(data) < limit:
            break
        offset += limit
    return out


# ─────────────────────────────────────────────────────────
# Stratechery (RSS feed)
# ─────────────────────────────────────────────────────────
_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _parse_rss_date(s: str) -> date:
    """RFC822 형식 'Thu, 15 Jul 2026 12:00:00 +0000' → date."""
    m = re.match(r"[A-Za-z]+, (\d{1,2}) ([A-Za-z]{3}) (\d{4})", s.strip())
    if not m:
        raise ValueError(s)
    day = int(m.group(1))
    mon = _MONTHS[m.group(2)]
    year = int(m.group(3))
    return date(year, mon, day)


def fetch_stratechery(start: date, end: date) -> List[Dict]:
    out: List[Dict] = []
    try:
        xml = _fetch("https://stratechery.com/feed/")
    except Exception as ex:
        print(f"  ERR stratechery: {ex}")
        return out

    for item in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
        l = re.search(r"<link>(.*?)</link>", item)
        p = re.search(r"<pubDate>(.*?)</pubDate>", item)
        if not (t and l and p):
            continue
        try:
            pd = _parse_rss_date(p.group(1))
        except Exception:
            continue
        if not _in_range(pd, start, end):
            continue
        out.append({
            "Format": "Stratechery",
            "Writer": "Ben Thompson",
            "Posted": pd.isoformat(),
            "Title": _clean_title(t.group(1)),
            "URL": l.group(1).strip(),
        })
    return out


# ─────────────────────────────────────────────────────────
# Sequoia (story-category 별 필터: perspective / spotlight / news / podcast)
# ─────────────────────────────────────────────────────────
def fetch_sequoia_category(category: str, format_label: str, start: date, end: date) -> List[Dict]:
    """/stories/?_story-category=<category> HTML 에서 URL 집합을 얻고,
    WP REST API 로 발행일 조회 후 교집합 → 범위 필터.

    Sequoia WP REST 는 story_category 커스텀 taxonomy 를 노출하지 않으므로
    HTML listing 을 category 필터로 대신 사용.
    """
    out: List[Dict] = []
    listing_url = f"https://www.sequoiacap.com/stories/?_story-category={category}"
    try:
        listing = _fetch(listing_url)
    except Exception as ex:
        print(f"  ERR sequoia listing ({category}): {ex}")
        return out

    urls = []
    seen = set()
    for m in re.finditer(r'href=["\']?(https://(?:www\.)?sequoiacap\.com/article/[a-z0-9-]+/?)', listing):
        u = m.group(1).rstrip("/") + "/"
        if u not in seen:
            seen.add(u)
            urls.append(u)

    if not urls:
        print(f"  WARN sequoia ({category}): 0 URLs")
        return out

    since_iso = start.strftime("%Y-%m-%dT00:00:00")
    until_iso = end.strftime("%Y-%m-%dT23:59:59")
    api = (
        "https://www.sequoiacap.com/wp-json/wp/v2/posts"
        f"?after={since_iso}&before={until_iso}&per_page=100"
        "&_fields=id,date,slug,link,title"
    )
    try:
        raw = _fetch(api)
        posts = json.loads(raw)
    except Exception as ex:
        print(f"  ERR sequoia WP API: {ex}")
        return out

    category_set = {u.rstrip("/") for u in urls}
    for p in posts:
        link = (p.get("link") or "").rstrip("/")
        if link not in category_set:
            continue
        try:
            pd = datetime.strptime(p["date"][:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if not _in_range(pd, start, end):
            continue
        title_raw = p.get("title", {}).get("rendered", "") if isinstance(p.get("title"), dict) else p.get("title", "")
        out.append({
            "Format": format_label,
            "Writer": "",
            "Posted": pd.isoformat(),
            "Title": _clean_title(title_raw),
            "URL": link + "/",
        })
    return out


def _sequoia_category_from_url(url: str) -> str:
    """blog 시트 URL 의 ?_story-category=<slug> 파라미터에서 category 추출."""
    m = re.search(r"[?&]_?story-category=([a-z0-9-]+)", url)
    return m.group(1) if m else "perspective"


# ─────────────────────────────────────────────────────────
# BVP News / Atlas — data-date 속성 파싱
# ─────────────────────────────────────────────────────────
def fetch_bvp(url: str, format_label: str, start: date, end: date) -> List[Dict]:
    """BVP News/Atlas HTML 에서 <article data-date=...> 파싱.
    페이지 안에서 같은 article 이 top-story slider + 리스트 등 여러 위치에 등장할 수 있어
    URL 로 dedupe.
    """
    out: List[Dict] = []
    try:
        html = _fetch(url)
    except Exception as ex:
        print(f"  ERR bvp {url}: {ex}")
        return out

    pattern = re.compile(
        r'<article[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*>\s*'
        r'<a[^>]*href="([^"]+)"[^>]*>.*?'
        r'<h2>(.*?)</h2>',
        re.DOTALL,
    )
    seen = set()
    for m in pattern.finditer(html):
        try:
            pd = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if not _in_range(pd, start, end):
            continue
        link = m.group(2).strip()
        if link.startswith("/"):
            link = "https://www.bvp.com" + link
        if link in seen:
            continue
        seen.add(link)
        title = _clean_title(re.sub(r"<[^>]+>", "", m.group(3)))
        out.append({
            "Format": format_label,
            "Writer": "",
            "Posted": pd.isoformat(),
            "Title": title,
            "URL": link,
        })
    return out


# ─────────────────────────────────────────────────────────
# Bill Evans (ben-evans.com/essays) — Squarespace
# ─────────────────────────────────────────────────────────
def fetch_ben_evans(start: date, end: date) -> List[Dict]:
    """ben-evans.com/essays — Squarespace 요약 페이지.

    HTML 에 essay 당 <time datetime> 태그가 above-title/below-title 2번 나와서
    date↔title regex 짝맞춤이 어긋난다. Bill Evans URL 경로에 이미 발행일
    (/benedictevans/YYYY/M/D/slug) 이 박혀 있으므로 URL 에서 직접 파싱한다.
    """
    out: List[Dict] = []
    try:
        html = _fetch("https://www.ben-evans.com/essays")
    except Exception as ex:
        print(f"  ERR ben-evans: {ex}")
        return out

    pattern = re.compile(
        r'<a[^>]*href="(/benedictevans/(\d{4})/(\d{1,2})/(\d{1,2})/[^"]+)"'
        r'[^>]*class="summary-title-link"[^>]*>\s*(.*?)\s*</a>',
        re.DOTALL,
    )
    seen = set()
    for m in pattern.finditer(html):
        try:
            pd = date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except ValueError:
            continue
        if not _in_range(pd, start, end):
            continue
        href = "https://www.ben-evans.com" + m.group(1)
        if href in seen:
            continue
        seen.add(href)
        out.append({
            "Format": "Bill Evans",
            "Writer": "Benedict Evans",
            "Posted": pd.isoformat(),
            "Title": _clean_title(m.group(5)),
            "URL": href,
        })
    return out


# ─────────────────────────────────────────────────────────
# 소스 → fetcher 라우팅
# ─────────────────────────────────────────────────────────
def fetch_source(src: Dict, start: date, end: date) -> List[Dict]:
    name = src["Name"]
    fmt = src["Format"]
    api = src["API"]
    url = src["URL"]
    ref = src["Ref"]

    # Substack API 소스
    if api and "/api/v1/archive" in api:
        # 기존 blog2 컨벤션: ALAD 는 인물명(Kevin Gee) 대신 발행처명 "A Letter A Day"
        writer = "A Letter A Day" if name == "ALAD" else (ref or name)
        return fetch_substack(api, writer, start, end)

    # 이름/도메인 기반 라우팅
    if name == "Stratechery" or "stratechery.com" in url:
        return fetch_stratechery(start, end)

    if "sequoiacap.com" in url:
        # URL 의 story-category 파라미터로 perspective / spotlight / news / podcast 구분
        cat = _sequoia_category_from_url(url)
        # Format 라벨: perspective→"Sequoia", 그 외에는 "Sequoia <Category>"
        label = "Sequoia" if cat == "perspective" else f"Sequoia {cat.title()}"
        return fetch_sequoia_category(cat, label, start, end)

    if name == "BVP News" or url.rstrip("/").endswith("bvp.com/news"):
        return fetch_bvp(url, "BVP News", start, end)

    if name == "BVP Atlas" or url.rstrip("/").endswith("bvp.com/atlas"):
        return fetch_bvp(url, "BVP Atlas", start, end)

    if "ben-evans.com" in url:
        return fetch_ben_evans(start, end)

    if "semianalysis" in url:
        return fetch_substack(
            "https://newsletter.semianalysis.com/api/v1/archive",
            "Dylan Patel",
            start,
            end,
            format_label="SemiAnalysis",
        )

    print(f"  SKIP unknown source: {name} ({fmt}) {url}")
    return []
