#!/usr/bin/env python3
"""
extract_meta.py
블로그·뉴스 URL에서 제목·작성일(YYMMDD)·작성자/매체를 추출한다.

사용법:
    python3 extract_meta.py URL [URL ...]

출력 (한 줄 = 한 URL):
    URL\\tTITLE\\tDATE\\tSOURCE
"""

import re
import subprocess
import sys
from urllib.parse import urlparse

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"


def fetch(url: str) -> str:
    """curl로 페이지를 가져온다 (시스템 cert 사용)."""
    try:
        out = subprocess.run(
            ["curl", "-sL", "-A", UA, "--max-time", "20", url],
            capture_output=True, text=True, errors="replace",
        )
        return out.stdout
    except Exception:
        return ""


def first(patterns, html):
    for p in patterns:
        m = re.search(p, html, re.S | re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


def to_yymmdd(date_str: str) -> str:
    if not date_str:
        return ""
    digits = re.findall(r"\d+", date_str)
    if len(digits) >= 3 and len(digits[0]) == 4:
        return f"{digits[0][2:]}{int(digits[1]):02d}{int(digits[2]):02d}"
    return ""


def extract_naver_blog(url: str, html: str) -> dict:
    """네이버 블로그 (m.blog.naver.com 또는 PostView.naver)."""
    title = first([
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r'<meta\s+name="title"\s+content="([^"]+)"',
        r'<title>([^<]+)</title>',
    ], html)
    if title:
        title = re.sub(r"\s*:\s*네이버\s*블로그\s*$", "", title)
    nick = first([
        r'<meta\s+property="naverblog:nickname"\s+content="([^"]+)"',
        r'class="nick"[^>]*>([^<]+)<',
        r'"nickName"\s*:\s*"([^"]+)"',
        r'"blogName"\s*:\s*"([^"]+)"',
    ], html)
    raw_date = first([
        r'class="se_publishDate[^"]*"[^>]*>([^<]+)<',
        r'class="blog_date"[^>]*>([^<]+)<',
        r'class="se_date"[^>]*>([^<]+)<',
        r'"publishDate"\s*:\s*"([^"]+)"',
        r'<meta\s+property="(?:article:published_time|og:published_time)"\s+content="([^"]+)"',
    ], html)
    blog_id_match = re.search(r"blogId=([^&]+)", url) or re.search(r"naver\.com/([^/]+)/", url)
    blog_id = blog_id_match.group(1) if blog_id_match else ""
    return {
        "title": title or "",
        "date": to_yymmdd(raw_date),
        "source": nick or blog_id,
    }


def extract_news(url: str, html: str) -> dict:
    """일반 뉴스 사이트 (Daum, einfomax, etc.)."""
    title = first([
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r'<title>([^<]+)</title>',
    ], html)
    src = first([
        r'<meta\s+property="og:site_name"\s+content="([^"]+)"',
    ], html)
    raw_date = first([
        r'<meta\s+property="article:published_time"\s+content="([^"]+)"',
        r'<meta\s+name="article:published_time"\s+content="([^"]+)"',
        r'<meta\s+property="og:published_time"\s+content="([^"]+)"',
        r'class="info-text"[^>]*>([^<]+)',
        r'datetime="([0-9-]+)',
    ], html)
    yymmdd = to_yymmdd(raw_date)
    # daum URL의 경로에 YYYYMMDD가 들어가는 경우 fallback
    if not yymmdd:
        m = re.search(r"/v/(\d{8})", url)
        if m:
            y = m.group(1)
            yymmdd = f"{y[2:4]}{y[4:6]}{y[6:8]}"
    # source 정리: "Daum | 에너지경제" → "에너지경제"
    if src and "|" in src:
        src = src.split("|")[-1].strip()
    return {"title": title or "", "date": yymmdd, "source": src or ""}


def extract(url: str) -> dict:
    html = fetch(url)
    if not html:
        return {"title": "", "date": "", "source": ""}
    host = urlparse(url).netloc
    if "naver.com" in host:
        # blog.naver.com은 자바스크립트 redirect → m.blog.naver.com/PostView.naver
        if re.search(r'top\.location\.replace\(\s*[\'"]([^\'"]+)[\'"]', html):
            real = re.search(r'top\.location\.replace\(\s*[\'"]([^\'"]+)[\'"]', html).group(1)
            real = real.replace("\\/", "/")
            html = fetch(real)
        return extract_naver_blog(url, html)
    return extract_news(url, html)


def main():
    urls = sys.argv[1:]
    for url in urls:
        m = extract(url)
        print(f"{url}\t{m['title']}\t{m['date']}\t{m['source']}")


if __name__ == "__main__":
    main()
