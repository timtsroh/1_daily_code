"""
김봉수 페이스북 피드 수집기 공통 설정.

환경변수로 override 가능하지만 기본값은 기존 Claude Code 스킬과 호환된다.
"""

from __future__ import annotations

import os
from datetime import timedelta, timezone
from pathlib import Path

# ---- 대상 프로필 ----------------------------------------------------------
PROFILE_HANDLE = "bongsoo2"
PROFILE_NAME = "김봉수"
PROFILE_URL = f"https://www.facebook.com/{PROFILE_HANDLE}"

# ---- 세션 ----------------------------------------------------------------
# 기존 Claude 스킬과 동일한 경로를 그대로 사용한다. (이동 금지)
SESSION_FILE = Path(
    os.environ.get("FB_SESSION_FILE", "/Users/tealeaf/.claude/fb_session.json")
)

# ---- 타임존 ---------------------------------------------------------------
KST = timezone(timedelta(hours=9))

# ---- Obsidian 저장 -------------------------------------------------------
VAULT_ROOT = Path(
    os.environ.get("OBSIDIAN_VAULT", "/Users/tealeaf/Obsidian/Sync1")
)
# CLAUDE.md 규칙: 피드 월별 노트는 3 큐레이션 아래에 저장한다.
NOTE_DIR = VAULT_ROOT / "03 Sources" / "3 큐레이션"
NOTE_FILENAME_TEMPLATE = "김봉수_{yymm}.md"

# ---- 스크래핑 파라미터 ---------------------------------------------------
MAX_SCROLLS = 25
SCROLL_DELAY_MS = 2500
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1280, "height": 900}
NAV_TIMEOUT_MS = 60000
POST_PAGE_TIMEOUT_MS = 30000
