#!/usr/bin/env python3
"""Facebook 로그인 후 세션을 저장하는 스크립트.

포팅 원본: /Users/tealeaf/.claude/skills/노정석/scripts/fb_login.py
세션 파일 경로는 원본과 동일하게 유지한다.
"""

import asyncio

from playwright.async_api import async_playwright

SESSION_FILE = '/Users/tealeaf/.claude/fb_session.json'


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        page = await context.new_page()
        await page.goto('https://www.facebook.com/login', wait_until='domcontentloaded')
        print('\n=== Facebook 로그인 페이지가 열렸습니다 ===')
        print('브라우저에서 로그인을 완료한 후, 여기서 Enter를 누르세요.')
        input('\n>> Enter를 누르면 세션을 저장합니다... ')
        await context.storage_state(path=SESSION_FILE)
        print(f'\n세션 저장 완료: {SESSION_FILE}')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
