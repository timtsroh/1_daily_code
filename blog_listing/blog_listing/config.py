"""blog_listing 전역 설정."""

from datetime import timedelta, timezone

# ── 시간대 ────────────────────────────────────────────
KST = timezone(timedelta(hours=9))

# ── Google Sheets ────────────────────────────────────
SHEET_ID = "1jhIf2aTKP5uYl-imT9nRCnLiZ_q1dV94FeVRfXWfGLE"
BLOG_TAB = "blog"
# blog 시트 Destination 컬럼 값 → 저장할 시트 이름
DEST_TABS = {
    "article": "article",
    "deals": "deals",
    "llm": "LLM",
}
DEFAULT_DEST = "article"

# ── 인증 ──────────────────────────────────────────────
KEY_FILE = "C:/Code_Local/gcp-oauth.keys2.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── HTTP ──────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) blog_listing/1.0"
HTTP_TIMEOUT = 20
