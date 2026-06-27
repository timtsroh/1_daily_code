#!/usr/bin/env python3
"""
reauth.py — Telethon 세션 재인증.

세션 파일(/Users/tealeaf/.claude/tg_session.session)이 없거나 만료되었을 때
최초 1회 전화번호 인증을 수행한다.

    python3 reauth.py
"""

from telethon.sync import TelegramClient

from fetch_feed import API_HASH, API_ID, SESSION_FILE


def main() -> None:
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    client.start()
    print(f"인증 완료: {SESSION_FILE}.session")
    client.disconnect()


if __name__ == "__main__":
    main()
