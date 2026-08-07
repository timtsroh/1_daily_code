"""Google Sheets 읽기/쓰기 (gspread)."""

from typing import Dict, List, Set, Tuple

import gspread
from google.oauth2.service_account import Credentials

from .config import BLOG_TAB, DEFAULT_DEST, DEST_TABS, KEY_FILE, SCOPES, SHEET_ID


def _open_sheet():
    creds = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def load_blog_sources() -> List[dict]:
    """blog 시트에서 소스 목록을 읽는다.
    헤더: Category | Name | URL | API | Ref | Destination | Format
    URL이 http로 시작하는 행만 유효.
    """
    sh = _open_sheet()
    ws = sh.worksheet(BLOG_TAB)
    rows = ws.get_all_values()
    sources: List[dict] = []
    for r in rows[1:]:
        if len(r) < 7:
            # Destination/Format 이 없으면 스킵
            continue
        url = r[2].strip()
        if not url.startswith("http"):
            continue
        dest = (r[5].strip() or DEFAULT_DEST).lower()
        if dest not in DEST_TABS:
            print(f"  WARN unknown Destination='{dest}' for {r[1]!r}, using {DEFAULT_DEST}")
            dest = DEFAULT_DEST
        sources.append({
            "Category": r[0].strip(),
            "Name": r[1].strip(),
            "URL": url,
            "API": r[3].strip(),
            "Ref": r[4].strip(),
            "Destination": dest,
            "Format": r[6].strip(),
        })
    return sources


def load_existing_urls_by_dest() -> Tuple[Dict[str, object], Set[str]]:
    """각 destination 시트의 ws 객체 dict + 전체 dedup URL 집합 반환.

    dedup 은 destination 을 넘나들며 전역으로 (같은 URL 은 어느 시트에도 있으면 스킵).
    """
    sh = _open_sheet()
    ws_by_dest: Dict[str, object] = {}
    urls: Set[str] = set()
    for dest, tab in DEST_TABS.items():
        ws = sh.worksheet(tab)
        ws_by_dest[dest] = ws
        for r in ws.get_all_values()[1:]:
            if len(r) > 4 and r[4].strip():
                urls.add(r[4].strip())
    return ws_by_dest, urls


def insert_rows(ws, rows: List[List[str]]) -> None:
    """지정 시트 2행에 다수 행을 insert (기존 데이터는 아래로 밀림).
    rows 형식: [Today, Format, Writer, Posted, URL, Title]
    """
    if not rows:
        return
    ws.insert_rows(rows, row=2, value_input_option="USER_ENTERED")
