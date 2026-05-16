"""
eBay Motors Scraper — Nationwide Overlanding Vehicles
Searches eBay Motors (Cars & Trucks, category 6001) via the Browse API,
saves raw listings to MongoDB using the same checkpoint pattern as CraigslistScraper.

Requires env vars: EBAY_APP_ID, EBAY_CERT_ID
"""
import os
import re
import json
import time
import base64
import logging
from pathlib import Path
from typing import Optional

import requests

from src.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MOTORS_CATEGORY = "6001"   # eBay Motors > Cars & Trucks
PAGE_LIMIT      = 50       # Items per page (max 200)
REQUEST_DELAY   = 1.0      # Seconds between pages

TOKEN_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

YEAR_RE = re.compile(r"\b(19[89]\d|20[012]\d)\b")


def _load_search_terms() -> list[dict]:
    wish_list_path = Path(__file__).parent.parent.parent / "wish_list.json"
    try:
        with open(wish_list_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[ebay] Could not load wish_list.json: {e}")
        return []


SEARCH_TERMS = _load_search_terms()


class EbayScraper(BaseScraper):
    """Scrape eBay Motors Cars & Trucks listings for overlanding vehicles."""

    def __init__(self):
        super().__init__("ebay_scraper")
        self.app_id  = os.getenv("EBAY_APP_ID", "")
        self.cert_id = os.getenv("EBAY_CERT_ID", "")
        self._token: Optional[str] = None
        self._token_expires: float = 0.0

    # ------------------------------------------------------------------
    # OAuth — client credentials grant, no user login required
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Return a valid application access token, refreshing when near expiry."""
        cached = self._token
        if cached and time.time() < self._token_expires - 60:
            return cached

        if not self.app_id or not self.cert_id:
            raise RuntimeError("EBAY_APP_ID and EBAY_CERT_ID must be set")

        credentials = base64.b64encode(f"{self.app_id}:{self.cert_id}".encode()).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        self._token = token
        self._token_expires = time.time() + data.get("expires_in", 7200)
        logger.info("[ebay] OAuth token refreshed")
        return token

    # ------------------------------------------------------------------
    # Core scrape loop
    # ------------------------------------------------------------------

    def scrape(self) -> tuple[int, int]:
        """Search eBay Motors for all wish list items and store new listings."""
        new_count  = 0
        total_seen = 0

        for term_cfg in SEARCH_TERMS:
            name      = term_cfg["name"]
            query     = term_cfg["query"]
            min_price = term_cfg["min_price"]
            max_price = term_cfg["max_price"]

            logger.info(f"[ebay] item='{name}' query='{query}' ${min_price}–${max_price}")

            offset = 0
            while True:
                listings = self._fetch_page(query, min_price, max_price, offset)

                if not listings:
                    logger.info(f"[ebay] No results at offset {offset} — moving on")
                    break

                total_seen += len(listings)
                for listing in listings:
                    if not self._is_relevant(listing.get("title", ""), term_cfg):
                        continue
                    listing["wish_list_name"] = name
                    if self.upsert_listing(listing):
                        new_count += 1

                logger.info(
                    f"[ebay] offset={offset} → {len(listings)} listings (+{new_count} new so far)"
                )

                if len(listings) < PAGE_LIMIT:
                    break

                offset += PAGE_LIMIT
                time.sleep(REQUEST_DELAY)

        return new_count, total_seen

    # ------------------------------------------------------------------
    # API fetch + parse
    # ------------------------------------------------------------------

    def _fetch_page(self, query: str, min_price: int, max_price: int, offset: int) -> list[dict]:
        """Fetch one page of eBay Motors search results via Browse API."""
        try:
            token = self._get_token()
            params = {
                "q":            query,
                "category_ids": MOTORS_CATEGORY,
                "filter":       f"price:[{min_price}..{max_price}],buyingOptions:{{FIXED_PRICE|BEST_OFFER}}",
                "limit":        PAGE_LIMIT,
                "offset":       offset,
            }
            resp = requests.get(
                SEARCH_URL,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params=params,
                timeout=15,
            )

            if resp.status_code == 429:
                logger.warning("[ebay] Rate limited — sleeping 30s")
                time.sleep(30)
                return self._fetch_page(query, min_price, max_price, offset)

            resp.raise_for_status()
            return [self._parse_item(i) for i in resp.json().get("itemSummaries", [])]

        except requests.RequestException as e:
            logger.warning(f"[ebay] Fetch error for '{query}' offset={offset}: {e}")
            return []

    def _parse_item(self, item: dict) -> dict:
        """Convert an eBay itemSummary to our standard listing format."""
        title = item.get("title", "")

        price_obj = item.get("price", {})
        try:
            price = int(float(price_obj.get("value", 0))) if price_obj else None
        except (ValueError, TypeError):
            price = None

        loc_obj  = item.get("itemLocation", {})
        location = ", ".join(filter(None, [
            loc_obj.get("city", ""),
            loc_obj.get("stateOrProvince", ""),
        ]))

        # VIN and mileage sometimes appear in localizedAspects on summary results
        vin     = None
        mileage = None
        for aspect in item.get("localizedAspects", []):
            key = aspect.get("name", "").lower()
            val = aspect.get("value", "")
            if key == "vin":
                vin = val
            elif key in ("mileage", "odometer"):
                digits = re.sub(r"[^\d]", "", val)
                mileage = int(digits) if digits else None

        return {
            "url":          item.get("itemWebUrl", ""),
            "title":        title,
            "price":        price,
            "location":     location,
            "year":         self._extract_year(title),
            "vin":          vin,
            "mileage":      mileage,
            "ebay_item_id": item.get("itemId"),
            "source":       "ebay",
            "region":       "nationwide",
            "posted_at":    item.get("itemCreationDate"),
            "search_query": "",
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _is_relevant(title: str, term_cfg: dict) -> bool:
        """Return True if any query keyword appears in the title (case-insensitive)."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in term_cfg["query"].lower().split())

    @staticmethod
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
    scraper = EbayScraper()
    result  = scraper.run()
    print(f"\n✅ Finished: {result['new']} new listings / {result['total_seen']} seen")
