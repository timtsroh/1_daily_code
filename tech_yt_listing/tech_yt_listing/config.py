"""프로젝트 전역 설정."""

import ssl
from datetime import timedelta, timezone

import certifi

# ── 시간대 ────────────────────────────────────────────
KST = timezone(timedelta(hours=9))

# ── Google Sheets ────────────────────────────────────
SHEET_ID = "1jhIf2aTKP5uYl-imT9nRCnLiZ_q1dV94FeVRfXWfGLE"
YT1_TAB = "yt1"
YT2_TAB = "yt2"

# ── 인증 ──────────────────────────────────────────────
# CLAUDE.md에 명시된 GCP 서비스 계정 키 경로
KEY_FILE = "/Users/tealeaf/Code_Local/gcp-oauth.keys2.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── 필터 ──────────────────────────────────────────────
MIN_DURATION = 120  # 120초(2분) 이하는 Shorts/클립으로 간주하여 제외

# ── HTTP ──────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) tech_yt_listing/1.0"
HTTP_TIMEOUT = 15  # seconds
SSL_CTX = ssl.create_default_context(cafile=certifi.where())
