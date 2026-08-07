#!/usr/bin/env python
"""
write_note.py
fetch_feed.py가 만든 /tmp/todo_feed.json을 읽어 Obsidian 월별 노트로 저장한다.

저장 위치: `0 inbox/todo_YYYYMM.md` (월별 누적). 일자별 항목은 파일 안에서
`# YYYY-MM-DD` 섹션(h1)으로 구분되며, 같은 날짜 섹션이 이미 있으면 덮어쓴다.
같은 월의 다른 날짜 섹션은 보존된다.

분류 규칙:
- 캡션 한 줄 + URL 또는 URL만 있음 → URL의 실제 제목/일자/출처를 가져와
  `## 제목 (YYMMDD, 출처)` 헤더로 변환
- 본문 ≥ 5줄 (리포트 등) → 본문 첫 줄을 헤더로, 나머지는 본문 (헤더와 중복되는
  첫 줄은 본문에서 제거)
- 짧은 텍스트 (URL 없음) → 텍스트 첫 줄을 헤더로
- 미디어만 (텍스트 없음) → 직전 그룹에 병합 (fetch 단계에서 grouped_id로 처리됨)

텔레그램 t.me 링크는 본문/헤더에서 모두 제거한다.
"""

import json
import os
import re
import subprocess
import sys

INBOX = "C:/Obsidian/Sync1/02 Daily/1 day"
IN_JSON = "/tmp/todo_feed.json"
EXTRACT_META = os.path.join(os.path.dirname(__file__), "extract_meta.py")

URL_PATTERN = re.compile(r"https?://[^\s)\]]+")
TME_PATTERN = re.compile(r"https?://t\.me/[^\s)\]]+")
MD_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")


def find_external_urls(text: str) -> list:
    """본문에서 t.me/, bit.ly 외 외부 블로그/뉴스 URL 추출."""
    found = []
    for m in MD_LINK_PATTERN.finditer(text):
        url = m.group(2)
        if "t.me/" in url or "bit.ly" in url or "n.nhsec.com" in url:
            continue
        found.append(url)
    if not found:
        for m in URL_PATTERN.finditer(text):
            url = m.group(0).rstrip(".,)")
            if "t.me/" in url or "bit.ly" in url:
                continue
            found.append(url)
    return found


def strip_telegram_links(text: str) -> str:
    """본문에서 t.me 마크다운 링크와 bare URL 제거."""
    text = re.sub(r"\[([^\]]*)\]\(https?://t\.me/[^)]+\)", r"\1", text)
    lines = text.split("\n")
    out = [ln for ln in lines if not re.match(r"^\s*https?://t\.me/\S+\s*$", ln)]
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_meta(url: str) -> dict:
    """extract_meta.py 한 URL 호출."""
    try:
        out = subprocess.run(
            ["python", EXTRACT_META, url],
            capture_output=True, text=True, timeout=30,
        )
        line = out.stdout.strip().split("\n")[0]
        parts = line.split("\t")
        if len(parts) >= 4:
            return {"title": parts[1], "date": parts[2], "source": parts[3]}
    except Exception:
        pass
    return {"title": "", "date": "", "source": ""}


def format_link_header(meta: dict) -> str:
    """제목 (YYMMDD, 출처) 형식. 일부 필드가 비어도 우아하게."""
    title = meta.get("title") or "(제목 없음)"
    parts = []
    if meta.get("date"):
        parts.append(meta["date"])
    if meta.get("source"):
        parts.append(meta["source"])
    suffix = f" ({', '.join(parts)})" if parts else ""
    return f"{title}{suffix}"


def strip_body_headers(text: str) -> str:
    """본문에서 마크다운 헤더(#, ##, ### 등)를 일반 텍스트로 변환."""
    return re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)


def classify_and_render(item: dict) -> str:
    """단일 메시지 → 마크다운 섹션."""
    text = strip_telegram_links(item.get("text", "") or "")
    media = item.get("media", [])

    # 미디어만 있고 텍스트 없는 경우 (드물게 grouped_id 묶음에서 분리됨)
    if not text and media:
        body = "\n".join(f"![[{m}]]" for m in media)
        return f"## (이미지)\n\n{body}\n"

    if not text:
        return ""

    lines = [ln for ln in text.split("\n") if ln.strip()]
    urls = find_external_urls(text)

    # 헤더는 LLM 후처리로 5단어 이내 요약됨 → 원문은 반드시 본문에 유지

    # 케이스 1: 짧은 메시지(≤2줄, URL 없음)
    if len(lines) <= 2 and not urls:
        header = lines[0]
        body_parts = [strip_body_headers(text)]
        if media:
            body_parts.append("\n".join(f"![[{m}]]" for m in media))
        return f"## {header}\n\n" + "\n\n".join(body_parts) + "\n"

    # 케이스 2: 캡션+URL 또는 URL만 있는 메시지 (≤4줄)
    if urls and len(lines) <= 4:
        meta = fetch_meta(urls[0])
        header = format_link_header(meta)
        link_md = f"[{urls[0]}]({urls[0]})"
        # 캡션 텍스트에서 URL(bare/마크다운 링크) 줄을 제거한 나머지를 본문으로 유지
        caption_lines = []
        for ln in lines:
            stripped = ln.strip()
            # bare URL 줄 제거
            if URL_PATTERN.fullmatch(stripped):
                continue
            # 마크다운 링크만 있는 줄 제거 (예: [url](url))
            if MD_LINK_PATTERN.fullmatch(stripped):
                continue
            caption_lines.append(ln)
        body_parts = []
        if caption_lines:
            body_parts.append(strip_body_headers("\n".join(caption_lines)))
        body_parts.append(link_md)
        if media:
            body_parts.append("\n".join(f"![[{m}]]" for m in media))
        return f"## {header}\n\n" + "\n\n".join(body_parts) + "\n"

    # 케이스 3: 긴 본문 메시지 → 첫 줄 헤더, 전체 본문 유지
    header = lines[0]
    body = text.strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = strip_body_headers(body)

    parts = [body]
    if media:
        parts.append("\n".join(f"![[{m}]]" for m in media))
    return f"## {header}\n\n" + "\n\n".join(parts) + "\n"


DAY_HEADER_RE = re.compile(r"^# (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


def render_day_section(date_iso: str, items: list) -> str:
    """단일 일자 섹션을 렌더링: `# YYYY-MM-DD` h1 헤더 + 본문 항목들."""
    body_blocks = []
    for it in items:
        block = classify_and_render(it).strip()
        if block:
            body_blocks.append(block)
    if not body_blocks:
        return ""
    return f"# {date_iso}\n\n" + "\n\n---\n\n".join(body_blocks) + "\n"


def build_monthly_frontmatter(yyyymm: str) -> str:
    """yyyymm = '202605' → 월별 프런트매터."""
    return (
        "---\n"
        '채널: "@atomtodo"\n'
        f"월: {yyyymm[:4]}-{yyyymm[4:]}\n"
        "---\n\n"
    )


def parse_monthly(content: str):
    """기존 월별 파일을 (frontmatter, {date_iso: section_text}) 로 분해."""
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            frontmatter = content[: end + len("\n---\n")]
            body = content[end + len("\n---\n") :].lstrip("\n")
        else:
            frontmatter = ""
            body = content
    else:
        frontmatter = ""
        body = content

    matches = list(DAY_HEADER_RE.finditer(body))
    sections = {}
    for i, m in enumerate(matches):
        date = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[date] = body[start:end].rstrip() + "\n"
    return frontmatter, sections


def update_monthly_note(date_iso: str, items: list):
    """date_iso 일자 섹션을 해당 월의 파일에 upsert."""
    yyyymm = date_iso[:7].replace("-", "")  # '2026-05-01' → '202605'
    path = os.path.join(INBOX, f"todo_{yyyymm}.md")
    new_section = render_day_section(date_iso, items)
    if not new_section:
        return None

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        frontmatter, sections = parse_monthly(content)
        if not frontmatter:
            frontmatter = build_monthly_frontmatter(yyyymm)
    else:
        frontmatter = build_monthly_frontmatter(yyyymm)
        sections = {}

    sections[date_iso] = new_section
    body = "\n".join(sections[d].rstrip() + "\n" for d in sorted(sections.keys()))
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)
    return path


def main():
    with open(IN_JSON) as f:
        data = json.load(f)

    written = []
    for date_iso in sorted(data.keys()):
        items = data[date_iso]
        if not items:
            print(f"{date_iso}: 메시지 없음, 스킵")
            continue
        path = update_monthly_note(date_iso, items)
        if path:
            written.append((path, date_iso, len(items)))
            print(f"WROTE {path} ({date_iso}: {len(items)}건)")

    print(f"DONE: {len(written)}개 일자 섹션 갱신")


if __name__ == "__main__":
    main()
