"""
Facebook 프로필 피드 스크래퍼.

원본 Claude Code 스킬의 `fetch_feed.py` 동작을 그대로 이식했다.
차이점:
  - 구조화된 STDOUT이 아니라 `list[dict]`를 반환한다.
  - 각 포스트의 permalink(있을 경우)를 함께 저장해 dedupe 키로 쓸 수 있게 했다.
  - KST 타임존, 시간 추출 로직, 스크롤 루프는 동일.
"""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from config import (
    KST,
    MAX_SCROLLS,
    NAV_TIMEOUT_MS,
    POST_PAGE_TIMEOUT_MS,
    PROFILE_URL,
    SCROLL_DELAY_MS,
    SESSION_FILE,
    USER_AGENT,
    VIEWPORT,
)


def _normalize_text_head(text: str, length: int = 40) -> str:
    """텍스트의 앞 `length` 글자를 dedupe 키용으로 정규화한다.

    - 모든 공백(공백/탭/개행)을 단일 스페이스로 치환한 뒤 strip.
    - 정규화된 문자열의 앞 `length` 문자를 돌려준다.
    """
    import re as _re

    normalized = _re.sub(r"\s+", " ", text or "").strip()
    return normalized[:length]


@dataclass
class Post:
    """수집된 포스트 한 건."""

    text: str
    time_str: str  # "HH:MM" 또는 "??:??"
    post_date: Optional[date] = None
    url: str = ""
    key: str = ""  # 본문 앞 40자(중복 방지용 로컬 키)

    def fingerprint(self) -> str:
        """월별 노트 내 중복 방지용 고유 키.

        시간(time_str)은 키에 넣지 않는다 — 페북이 옛 글을 새 활동(댓글 등)으로
        다시 피드에 띄우면 같은 글이 다른 시각으로 재수집될 수 있는데, 시각을
        키에 넣으면 동일 본문이 '새 글'로 잡혀 중복 저장된다. 따라서 본문 앞
        80자(공백 정규화)만으로 식별한다. note_writer._existing_fingerprints 와
        반드시 동일한 규칙을 유지할 것.
        """
        return _normalize_text_head(self.text, 80)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "time_str": self.time_str,
            "post_date": self.post_date.isoformat() if self.post_date else None,
            "url": self.url,
            "key": self.key,
        }


def _parse_tooltip(tooltip: Optional[str]) -> tuple[Optional[date], str]:
    """`'Thursday, March 19, 2026 at 2:27 PM'` → `(date, 'HH:MM')`."""
    if not tooltip:
        return None, "??:??"
    normalized = tooltip.replace("\u202f", " ").strip()
    m = re.search(
        r"(\w+ \d+, \d{4}) at (\d+:\d+\s*[AP]M)", normalized, re.IGNORECASE
    )
    if not m:
        return None, "??:??"
    try:
        dt = datetime.strptime(
            f"{m.group(1)} {m.group(2).strip()}", "%B %d, %Y %I:%M %p"
        )
        return dt.date(), dt.strftime("%H:%M")
    except Exception:
        return None, "??:??"


def _rel_to_expected_date(rel_time: str) -> Optional[date]:
    """상대시간 라벨(`1d`, `3h`, ...) → 예상 날짜(KST 기준)."""
    now = datetime.now(KST)
    m = re.match(r"^(\d+)([wdhm])$", rel_time, re.IGNORECASE)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit == "d":
        return (now - timedelta(days=n)).date()
    if unit == "w":
        return (now - timedelta(weeks=n)).date()
    if unit == "h":
        return (now - timedelta(hours=n)).date()
    if unit == "m":
        return now.date()
    return None


async def _hover_get_tooltip(page, element) -> Optional[str]:
    try:
        await page.mouse.move(640, 450)
        await page.wait_for_timeout(300)
        await element.scroll_into_view_if_needed()
        await element.hover()
        await page.wait_for_timeout(1500)
        return await page.evaluate(
            r"""
            () => {
                const portals = document.querySelectorAll('.__fb-light-mode [id^="_r_"], body > div[class]');
                for (const p of portals) {
                    const t = p.innerText ? p.innerText.trim() : '';
                    if (t.match(/\w+ \d+.*\d+:\d+/)) return t;
                }
                for (const t of document.querySelectorAll('[role="tooltip"]')) {
                    if (t.innerText) return t.innerText.trim();
                }
                return null;
            }
            """
        )
    except Exception:
        return None


async def _get_creation_time_from_post_page(
    page, post_url: str, expected_date: date
) -> tuple[Optional[date], str]:
    """코멘트 링크만 노출된 경우 포스트 페이지로 이동하여 creation_time 추출."""
    try:
        await page.goto(
            post_url, wait_until="domcontentloaded", timeout=POST_PAGE_TIMEOUT_MS
        )
        await page.wait_for_timeout(3500)

        timestamps = await page.evaluate(
            r"""
            () => {
                const results = [];
                const seen = new Set();
                for (const s of document.querySelectorAll('script')) {
                    const c = s.textContent || '';
                    const re = /"creation_time":(\d{10})/g;
                    let m;
                    while ((m = re.exec(c)) !== null) {
                        const ts = parseInt(m[1]);
                        if (!seen.has(ts)) { seen.add(ts); results.push(ts); }
                    }
                }
                return results.sort();
            }
            """
        )

        matching = []
        for ts in timestamps:
            dt = datetime.fromtimestamp(ts, tz=KST)
            if dt.date() == expected_date:
                matching.append(dt)

        if matching:
            best = min(matching)
            return best.date(), best.strftime("%H:%M")
    except Exception as exc:  # pragma: no cover — Playwright side effects
        print(f"  [get_creation_time] error: {exc}", file=sys.stderr)

    return None, "??:??"


async def _collect(target_date: date) -> list[Post]:
    """target_date(KST) 포스트를 반환한다."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=str(SESSION_FILE),
            viewport=VIEWPORT,
            user_agent=USER_AGENT,
        )
        page = await context.new_page()
        await page.goto(
            PROFILE_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS
        )
        await page.wait_for_timeout(5000)

        seen_keys: set[str] = set()
        all_posts: list[Post] = []

        for scroll_n in range(MAX_SCROLLS):
            result = await page.evaluate(
                r"""
                () => {
                    const stories = document.querySelectorAll('[data-ad-rendering-role="story_message"]');
                    const posts = [];
                    stories.forEach(story => {
                        const seeMoreBtn = story.querySelector('div[role="button"]');
                        if (seeMoreBtn) {
                            const btnText = seeMoreBtn.innerText ? seeMoreBtn.innerText.trim() : '';
                            if (btnText === 'See more' || btnText === '더 보기') {
                                seeMoreBtn.click();
                            }
                        }
                        const text = story.innerText ? story.innerText.trim() : '';
                        const key = text.substring(0, 40);
                        let card = story;
                        let timeInfo = null;
                        for (let i = 0; i < 25; i++) {
                            card = card.parentElement;
                            if (!card) break;
                            for (const a of card.querySelectorAll('a')) {
                                const t = a.innerText ? a.innerText.trim() : '';
                                if (/^\d+[wdhm]$/i.test(t)) {
                                    timeInfo = { text: t, href: a.href, hasCommentId: a.href.includes('comment_id') };
                                    break;
                                }
                            }
                            if (timeInfo) break;
                        }
                        posts.push({ key, text, timeInfo });
                    });
                    return posts;
                }
                """
            )

            await page.wait_for_timeout(800)

            stories_els = await page.query_selector_all(
                '[data-ad-rendering-role="story_message"]'
            )
            expanded: dict[str, str] = {}
            for el in stories_els:
                t = await el.inner_text()
                if t:
                    t = t.strip()
                    for r in result:
                        if r["key"][:20] in t:
                            expanded[r["key"]] = t
                            break

            found_older = False
            for pi in result:
                if pi["key"] in seen_keys or not pi["text"]:
                    continue
                seen_keys.add(pi["key"])

                text = expanded.get(pi["key"], pi["text"])
                ti = pi.get("timeInfo") or {}
                rel_time = ti.get("text") or ""
                has_comment_id = ti.get("hasCommentId", False)
                href = ti.get("href") or ""

                expected_date = (
                    _rel_to_expected_date(rel_time) if rel_time else None
                )

                if expected_date and expected_date < target_date:
                    found_older = True
                    continue

                post_date: Optional[date] = None
                time_str = "??:??"
                permalink = href.split("?")[0] if href else ""

                if has_comment_id and expected_date and href:
                    base_url = href.split("?")[0]
                    print(
                        "  [comment_id link] fetching post page...",
                        file=sys.stderr,
                    )
                    post_date, time_str = await _get_creation_time_from_post_page(
                        page, base_url, expected_date
                    )
                    await page.goto(
                        PROFILE_URL,
                        wait_until="domcontentloaded",
                        timeout=NAV_TIMEOUT_MS,
                    )
                    await page.wait_for_timeout(3000)
                    seen_keys.discard(pi["key"])
                    if post_date:
                        all_posts.append(
                            Post(
                                text=text,
                                time_str=time_str,
                                post_date=post_date,
                                url=base_url,
                                key=pi["key"],
                            )
                        )
                        seen_keys.add(pi["key"])
                    break  # 페이지 이동 후 DOM이 초기화되었으니 루프 재시작
                else:
                    for el in stories_els:
                        el_t = await el.inner_text()
                        if el_t and pi["key"][:20] in el_t.strip():
                            time_a = await el.evaluate_handle(
                                r"""
                                el => {
                                    let card = el;
                                    for (let i = 0; i < 25; i++) {
                                        card = card.parentElement;
                                        if (!card) break;
                                        for (const a of card.querySelectorAll('a')) {
                                            const t = a.innerText ? a.innerText.trim() : '';
                                            if (/^\d+[wdhm]$/i.test(t)) return a;
                                        }
                                    }
                                    return null;
                                }
                                """
                            )
                            is_null = await time_a.evaluate(
                                "el => el === null"
                            )
                            if not is_null:
                                tooltip = await _hover_get_tooltip(
                                    page, time_a
                                )
                                post_date, time_str = _parse_tooltip(tooltip)
                            break

                    all_posts.append(
                        Post(
                            text=text,
                            time_str=time_str,
                            post_date=post_date,
                            url=permalink,
                            key=pi["key"],
                        )
                    )

            dates = [p.post_date for p in all_posts if p.post_date]
            oldest = min(dates) if dates else None
            print(
                f"SCROLL:{scroll_n} TOTAL:{len(all_posts)} OLDEST:{oldest}",
                file=sys.stderr,
            )

            if found_older:
                print(
                    "Found posts older than target date, stopping",
                    file=sys.stderr,
                )
                break

            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(SCROLL_DELAY_MS)

        await browser.close()
        return all_posts


def fetch_posts_for(target_date: date) -> list[Post]:
    """`target_date`(KST 기준)에 올라온 포스트만 반환한다.

    시간순(오름차순)으로 정렬된다. `??:??`는 뒤로 밀린다.
    """
    raw = asyncio.run(_collect(target_date))
    filtered = [p for p in raw if p.post_date == target_date]

    def sort_key(post: Post) -> tuple[int, str]:
        # `??:??` 를 가장 뒤로
        return (0 if post.time_str != "??:??" else 1, post.time_str)

    filtered.sort(key=sort_key)
    return filtered
