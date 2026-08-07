"""Facebook 로그인 세션 관리.

- `ensure_session()`: 세션 파일이 없으면 안내 메시지와 함께 에러를 발생시킨다.
- `refresh_session()`: 대화형으로 브라우저를 띄워 로그인한 뒤 세션을 저장한다.
  CLI에서 `python session.py` 로 직접 호출할 수 있다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from config import SESSION_FILE, USER_AGENT, VIEWPORT


class SessionMissingError(RuntimeError):
    """세션 파일이 없을 때 발생한다."""


def ensure_session(path: Path = SESSION_FILE) -> Path:
    """세션 파일이 존재하는지 확인한다."""
    if not path.exists():
        raise SessionMissingError(
            f"Facebook 세션 파일이 없습니다: {path}\n"
            f"다음 명령으로 로그인 후 세션을 저장하세요:\n"
            f"  python {Path(__file__).resolve().parent / 'session.py'}"
        )
    return path


async def _refresh(path: Path) -> None:
    from playwright.async_api import async_playwright

    path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport=VIEWPORT,
            user_agent=USER_AGENT,
        )
        page = await context.new_page()
        await page.goto(
            "https://www.facebook.com/login", wait_until="domcontentloaded"
        )
        print("\n=== Facebook 로그인 페이지가 열렸습니다 ===")
        print("브라우저에서 로그인을 완료한 후, 여기서 Enter를 누르세요.")
        input("\n>> Enter를 누르면 세션을 저장합니다... ")
        await context.storage_state(path=str(path))
        print(f"\n세션 저장 완료: {path}")
        await browser.close()


def refresh_session(path: Path = SESSION_FILE) -> None:
    """대화형 재로그인."""
    asyncio.run(_refresh(path))


if __name__ == "__main__":
    try:
        refresh_session()
    except KeyboardInterrupt:
        print("\n중단됨", file=sys.stderr)
        sys.exit(1)
