"""
Facebook Marketplace Scraper — Local Vehicle Listings
Uses Playwright (headless Chromium) with a stored authenticated session.

Authentication:
  Log in to Facebook once locally, export cookies via browser dev tools or
  a helper script, and store the JSON array as the FB_COOKIES GitHub secret
  (plain JSON or base64-encoded). The scraper injects those cookies before
  navigating so no interactive login is needed in CI.

Cookie export (one-time setup, repeat every ~90 days):
  1. Log in to facebook.com in Chrome
  2. Open DevTools → Application → Cookies → facebook.com
  3. Copy all cookies as JSON (EditThisCookie extension makes this easy)
  4. Store the JSON string as secret FB_COOKIES in GitHub repo settings

Search radius: 160 km (~100 miles) around the user's default location as set
in the Facebook account profile.
"""
import asyncio
import base64
import json
import logging
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from src.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

YEAR_RE = re.compile(r"\b(19[89]\d|20[012]\d)\b")
ITEM_ID_RE = re.compile(r"/marketplace/item/(\d+)/")
PRICE_RE = re.compile(r"\$[\d,]+")


def _load_search_terms() -> list[dict]:
    wish_list_path = Path(__file__).parent.parent.parent / "wish_list.json"
    try:
        with open(wish_list_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[facebook] Could not load wish_list.json: {e}")
        return []


SEARCH_TERMS = _load_search_terms()

SCROLL_PAUSE = 1.5   # Seconds between scroll steps
SCROLL_STEPS = 4     # How many times to scroll down per search page
PAGE_LOAD_WAIT = 3   # Seconds to wait after initial navigation


class FacebookScraper(BaseScraper):
    """
    Scrapes Facebook Marketplace vehicle listings using Playwright.
    Requires the FB_COOKIES environment variable (JSON array of cookie dicts).
    """

    def __init__(self):
        super().__init__("facebook_scraper")

    # ------------------------------------------------------------------
    # Cookie loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_cookies() -> list[dict]:
        raw = os.getenv("FB_COOKIES", "").strip()
        if not raw:
            raise RuntimeError(
                "FB_COOKIES env var is not set. "
                "Export your Facebook session cookies as JSON and store them as a secret."
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try base64-encoded JSON
            return json.loads(base64.b64decode(raw).decode())

    # ------------------------------------------------------------------
    # Core scrape loop (sync wrapper around async Playwright)
    # ------------------------------------------------------------------

    def scrape(self) -> tuple[int, int]:
        return asyncio.run(self._scrape_async())

    async def _scrape_async(self) -> tuple[int, int]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

        cookies = self._load_cookies()
        new_count = 0
        total_seen = 0

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            # Inject stored auth cookies
            await context.add_cookies(cookies)

            page = await context.new_page()

            for term_cfg in SEARCH_TERMS:
                name = term_cfg["name"]
                query = term_cfg["query"]
                min_price = term_cfg["min_price"]
                max_price = term_cfg["max_price"]

                logger.info(f"[facebook] Searching: '{name}' ${min_price}–${max_price}")

                listings = await self._search(page, query, min_price, max_price, name)
                total_seen += len(listings)

                for listing in listings:
                    if self.upsert_listing(listing):
                        new_count += 1

                logger.info(
                    f"[facebook] '{name}': {len(listings)} found (+{new_count} new total)"
                )
                time.sleep(1)

            await browser.close()

        return new_count, total_seen

    # ------------------------------------------------------------------
    # Per-search-term scraping
    # ------------------------------------------------------------------

    async def _search(
        self,
        page,
        query: str,
        min_price: int,
        max_price: int,
        wish_list_name: str,
    ) -> list[dict]:
        url = (
            "https://www.facebook.com/marketplace/vehicles/search/"
            f"?query={urllib.parse.quote(query)}"
            f"&minPrice={min_price}"
            f"&maxPrice={max_price}"
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(PAGE_LOAD_WAIT)
        except Exception as e:
            logger.warning(f"[facebook] Navigation failed for '{query}': {e}")
            return []

        # Detect login wall — if we land on login page our cookies are expired
        if "login" in page.url.lower() or "checkpoint" in page.url.lower():
            logger.error(
                "[facebook] Redirected to login page — FB_COOKIES are expired or invalid. "
                "Re-export cookies from a logged-in browser and update the secret."
            )
            return []

        # Scroll to load more listings
        for _ in range(SCROLL_STEPS):
            await page.keyboard.press("End")
            await asyncio.sleep(SCROLL_PAUSE)

        return await self._extract_listings(page, wish_list_name, query)

    # ------------------------------------------------------------------
    # Listing extraction
    # ------------------------------------------------------------------

    async def _extract_listings(
        self, page, wish_list_name: str, query: str
    ) -> list[dict]:
        listings = []
        seen_ids: set[str] = set()

        # Collect all links that point to marketplace item pages
        links = await page.query_selector_all('a[href*="/marketplace/item/"]')

        for link in links:
            try:
                href = await link.get_attribute("href") or ""
                m = ITEM_ID_RE.search(href)
                if not m:
                    continue
                item_id = m.group(1)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                text = (await link.inner_text()).strip()
                listing = self._parse_card_text(
                    text,
                    f"https://www.facebook.com/marketplace/item/{item_id}/",
                    wish_list_name,
                    query,
                )
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[facebook] Card parse error: {e}")

        return listings

    # ------------------------------------------------------------------
    # Text parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_card_text(
        text: str, url: str, wish_list_name: str, query: str
    ) -> Optional[dict]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None

        price: Optional[int] = None
        title: Optional[str] = None
        location: Optional[str] = None

        for line in lines:
            if price is None and PRICE_RE.match(line):
                digits = re.sub(r"[^\d]", "", line)
                price = int(digits) if digits else None
            elif title is None and len(line) > 4:
                title = line
            elif title and location is None and not PRICE_RE.match(line):
                location = line

        if not title:
            return None

        return {
            "url":            url,
            "title":          title,
            "price":          price,
            "location":       location or "",
            "year":           _extract_year(title),
            "source":         "facebook",
            "region":         "local",
            "search_query":   query,
            "wish_list_name": wish_list_name,
            "posted_at":      None,
        }


def _extract_year(title: str) -> Optional[int]:
    m = YEAR_RE.search(title)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Local runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    scraper = FacebookScraper()
    result = scraper.run()
    print(f"\nDone: {result['new']} new listings / {result['total_seen']} seen")
