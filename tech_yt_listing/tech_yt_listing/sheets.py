"""Google Sheets 읽기/쓰기 래퍼 (gspread 기반)."""

from typing import List, Set, Tuple

import gspread
from google.oauth2.service_account import Credentials

from .config import KEY_FILE, SCOPES, SHEET_ID, YT1_TAB, YT2_TAB


def _open_sheet():
    creds = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def load_channels() -> List[dict]:
    """yt1 시트에서 채널 목록을 읽는다.
    B열=Source, C열=URL (URL이 https://www.youtube.com/ 으로 시작해야 포함).
    """
    sh = _open_sheet()
    ws = sh.worksheet(YT1_TAB)
    rows = ws.get_all_values()
    channels: List[dict] = []
    for row in rows[1:]:  # 헤더 스킵
        if len(row) >= 3 and row[2].startswith("https://www.youtube.com/"):
            channels.append({"source": row[1], "url": row[2]})
    return channels


def load_existing_yt2() -> Tuple[object, Set[str]]:
    """yt2 시트 객체와 기존 video_id 집합을 반환한다."""
    sh = _open_sheet()
    ws = sh.worksheet(YT2_TAB)
    existing = ws.get_all_values()
    ids: Set[str] = set()
    for r in existing[1:]:
        if len(r) > 3 and r[3]:
            vid_id = r[3].split("/")[-1].split("?")[0]
            if vid_id:
                ids.add(vid_id)
    return ws, ids


def insert_rows_yt2(ws, rows: List[List[str]]) -> None:
    """2행에 다수 행을 삽입 (기존 데이터는 아래로 밀림)."""
    if not rows:
        return
    ws.insert_rows(rows, row=2)
