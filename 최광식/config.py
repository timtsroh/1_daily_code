#!/usr/bin/env python3
"""
config.py
최광식 스킬 포팅 — 공용 상수.

- 전종현 스킬의 Telegram 세션·API 키를 재사용한다.
- last_run.log는 Claude 스킬과 동일한 경로를 그대로 공유한다.
"""

from pathlib import Path

# ── Telegram ───────────────────────────────────────────────────────────────
API_ID = 32844347
API_HASH = "432b3c2ca6b5e925320031c3e234ac58"
SESSION_FILE = "/Users/tealeaf/.claude/tg_session"  # 전종현과 공유
CHANNEL = "HI_GS"  # https://t.me/HI_GS

# ── 경로 ────────────────────────────────────────────────────────────────────
LAST_RUN_LOG = Path("/Users/tealeaf/.claude/skills/최광식/last_run.log")

GDRIVE_INBOX = Path(
    "/Users/tealeaf/Library/CloudStorage/"
    "GoogleDrive-taeseungg@gmail.com/My Drive/02 주식/02 자료/0 Inbox"
)

# ── 동작 파라미터 ───────────────────────────────────────────────────────────
# 최초 실행 시 조회 범위 (일)
INITIAL_LOOKBACK_DAYS = 30
# last_run.log가 있으면 해당 날짜 -1일부터 조회
LAST_RUN_BUFFER_DAYS = 1
# Telethon 한 번에 가져올 메시지 수 (충분히 크게)
FETCH_LIMIT = 500

# bit.ly 링크 식별자
BITLY_HOSTS = ("bit.ly", "bitly.com")

# 증권사 레이블 (파일명)
BROKER_LABEL = "다올"
