"""
Craigslist Scraper — Overlanding Vehicles (Denver / Colorado)
Searches Craigslist cars+trucks by owner for target platforms,
saves raw listings to MongoDB, and uses checkpoint pattern for resumability.
"""
import json
import re
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import urllib.parse

import requests
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Search configuration
# ---------------------------------------------------------------------------

# Craigslist regions to cover (add more as needed)
REGIONS = [
    "denver",
    "boulder",
    "cosprings",
]


def _load_search_terms() -> list[dict]:
    """Load search terms from wish_list.json at project root."""
    wish_list_path = Path(__file__).parent.parent.parent / "wish_list.json"
    try:
        with open(wish_list_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[craigslist] Could not load wish_list.json: {e}")
        return []


SEARCH_TERMS = _load_search_terms()

RESULTS_PER_PAGE = 120
REQUEST_DELAY_SECONDS = 2.5  # Be polite to Craigslist servers

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Regex to find a 4-digit year in a listing title
YEAR_RE = re.compile(r"\b(19[89]\d|20[012]\d)\b")


class CraigslistScraper(BaseScraper):
    """Scrape Craigslist cars+trucks-by-owner listings for overlanding vehicles."""

    def __init__(self):
        super().__init__("craigslist_scraper")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # Core scrape loop
    # ------------------------------------------------------------------

    def scrape(self) -> tuple[int, int]:
        """
        Iterate over regions × search terms × pages.
        Checkpoint stores (region_idx, term_idx, page_offset) so we can
        resume exactly where we left off after any interruption.
        """
        checkpoint = self.load_checkpoint()
        start_region = checkpoint.get("region_idx", 0)
        start_term   = checkpoint.get("term_idx", 0)
        start_offset = checkpoint.get("page_offset", 0)

        new_count  = 0
        total_seen = 0

        for r_idx, region in enumerate(REGIONS):
            if r_idx < start_region:
                continue  # Already processed

            for t_idx, term_cfg in enumerate(SEARCH_TERMS):
                if r_idx == start_region and t_idx < start_term:
                    continue  # Already processed

                name      = term_cfg["name"]
                query     = term_cfg["query"]
                min_price = term_cfg["min_price"]
                max_price = term_cfg["max_price"]

                logger.info(
                    f"[craigslist] region={region} item='{name}' query='{query}' "
                    f"${min_price}–${max_price}"
                )

                offset = start_offset if (r_idx == start_region and t_idx == start_term) else 0

                while True:
                    listings = self._fetch_page(region, query, min_price, max_price, offset)

                    if not listings:
                        logger.info(
                            f"[craigslist] No results at offset {offset} — moving on"
                        )
                        break

                    total_seen += len(listings)
                    for listing in listings:
                        if not self._is_relevant(listing.get("title", ""), term_cfg):
                            continue
                        listing["wish_list_name"] = name
                        if self.upsert_listing(listing):
                            new_count += 1

                    logger.info(
                        f"[craigslist] Page offset={offset} → "
                        f"{len(listings)} listings (+{new_count} new so far)"
                    )

                    # Save checkpoint after each page
                    self.save_checkpoint({
                        "region_idx":     r_idx,
                        "term_idx":       t_idx,
                        "page_offset":    offset + RESULTS_PER_PAGE,
                        "region":         region,
                        "wish_list_name": name,
                        "search_term":    query,
                    })

                    if len(listings) < RESULTS_PER_PAGE:
                        break  # Last page

                    offset += RESULTS_PER_PAGE
                    time.sleep(REQUEST_DELAY_SECONDS)

            # Reset offset when moving to the next search term
            start_offset = 0

        self.clear_checkpoint()
        return new_count, total_seen

    # ------------------------------------------------------------------
    # HTTP + HTML parsing
    # ------------------------------------------------------------------

    def _fetch_page(
        self,
        region: str,
        query: str,
        min_price: int,
        max_price: int,
        offset: int,
    ) -> list[dict]:
        """Fetch one search results page and return a list of raw listing dicts."""
        url = (
            f"https://{region}.craigslist.org/search/cto"
            f"?query={urllib.parse.quote(query)}"
            f"&min_price={min_price}"
            f"&max_price={max_price}"
            f"&s={offset}"
        )

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[craigslist] Fetch error for {url}: {e}")
            return []

        return self._parse_listings(resp.text, region, query)

    def _parse_listings(self, html: str, region: str, query: str) -> list[dict]:
        """Parse Craigslist search results HTML into listing dicts."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Craigslist serves static content in <li class="cl-static-search-result">
        items = soup.select("li.cl-static-search-result")

        for item in items:
            listing = self._parse_listing_item(item, region, query)
            if listing:
                results.append(listing)

        return results

    def _parse_listing_item(self, item, region: str, query: str) -> Optional[dict]:
        """Extract fields from a single <li class='cl-static-search-result'> element."""
        try:
            # Title from li[title] attribute (most reliable)
            title = item.get("title", "").strip()
            if not title:
                title_el = item.select_one("div.title")
                title = title_el.get_text(strip=True) if title_el else ""

            # URL
            anchor = item.select_one("a")
            if not anchor:
                return None
            listing_url = anchor.get("href", "")
            if not listing_url.startswith("http"):
                listing_url = f"https://{region}.craigslist.org{listing_url}"

            if not title or not listing_url:
                return None

            # Price
            price_el = item.select_one("div.price")
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = self._parse_price(price_text)

            # Location
            location_el = item.select_one("div.location")
            location = location_el.get_text(strip=True) if location_el else region

            # Infer year from title
            year = self._extract_year(title)

            return {
                "url":          listing_url,
                "title":        title,
                "price":        price,
                "location":     location,
                "year":         year,
                "posted_at":    None,  # Not in static HTML; fetchable from detail page
                "search_query": query,
                "region":       region,
            }

        except Exception as e:
            logger.debug(f"[craigslist] Parse error on item: {e}")
            return None

    # ------------------------------------------------------------------
    # Utility parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_relevant(title: str, term_cfg: dict) -> bool:
        """Return True if any query keyword appears in the title (case-insensitive)."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in term_cfg["query"].lower().split())

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        """'$22,500' → 22500, returns None if unparseable."""
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    @staticmethod
    def _extract_year(title: str) -> Optional[int]:
        """Pull a 4-digit year (1980-2029) from listing title."""
        m = YEAR_RE.search(title)
        return int(m.group(1)) if m else None

    @staticmethod
    def _parse_date(dt_str: str) -> Optional[datetime]:
        """Parse ISO 8601 or common Craigslist date strings."""
        if not dt_str:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(dt_str[:19], fmt)
            except ValueError:
                continue
        return None


# ---------------------------------------------------------------------------
# Local runner — python -m src.scrapers.craigslist_scraper
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    scraper = CraigslistScraper()
    result = scraper.run()
    print(f"\n✅ Finished: {result['new']} new listings / {result['total_seen']} seen")
