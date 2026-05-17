"""
Deal Expiry Checker — removes deals whose source listings have been taken down.

For each deal in the database, checks whether the original listing URL is still live.
Expired deals are deleted from both `deals` and `raw_listings` so they never resurface.

Checking is rate-limited and capped per run so it can run as part of the regular
scraper job without adding significant wall-clock time.
"""
import os
import re
import time
import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.database import Database
from dotenv import load_dotenv

from src.enrichment.ebay_detail import EbayDetailFetcher

load_dotenv()
logger = logging.getLogger(__name__)

REQUEST_DELAY = 1.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
EBAY_ITEM_RE = re.compile(r"/itm/(\d+)")
CL_REMOVED_PHRASES = [
    "this posting has been deleted",
    "this posting has expired",
    "this posting has been flagged for removal",
    "this posting has been removed",
]


class DealExpiryChecker:
    """
    Verifies that stored deal URLs are still live; removes expired ones.
    Processes up to max_checks deals per run, oldest-checked first, so
    the full collection cycles through naturally across daily runs.
    """

    def __init__(self):
        self.db: Database = self._connect_db()
        self.ebay_detail = EbayDetailFetcher()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _connect_db(self) -> Database:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set")
        client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
        client.admin.command("ping")
        logger.info("[expiry] Connected to MongoDB")
        return client["overland_finder"]

    def run(self, max_checks: int = 50) -> dict:
        """
        Check up to max_checks deals, prioritising those not checked recently.
        Returns counts for logging.
        """
        deals = list(
            self.db.deals.find(
                {},
                {"url": 1, "source": 1, "title": 1, "ebay_item_id": 1, "last_checked_at": 1},
            )
            .sort("last_checked_at", 1)
            .limit(max_checks)
        )

        if not deals:
            logger.info("[expiry] No deals to check")
            return {"checked": 0, "alive": 0, "expired": 0}

        logger.info(f"[expiry] Checking {len(deals)} deals")
        checked = alive = expired = 0

        for deal in deals:
            url = deal.get("url", "")
            source = (deal.get("source") or "craigslist").lower()
            title = deal.get("title", "?")

            is_alive = self._check_listing(url, source, deal)
            checked += 1

            if is_alive:
                alive += 1
                self.db.deals.update_one(
                    {"_id": deal["_id"]},
                    {"$set": {"last_checked_at": datetime.now(timezone.utc)}},
                )
            else:
                expired += 1
                logger.info(f"[expiry] Expired — removing: {title[:70]}")
                self._remove_expired(deal)

            time.sleep(REQUEST_DELAY)

        logger.info(f"[expiry] Done — {checked} checked, {alive} alive, {expired} expired")
        return {"checked": checked, "alive": alive, "expired": expired}

    # ------------------------------------------------------------------
    # Source-specific liveness checks
    # ------------------------------------------------------------------

    def _check_listing(self, url: str, source: str, deal: dict) -> bool:
        if "facebook" in source or "facebook" in url:
            return True  # Can't verify without Playwright + auth cookies
        if "ebay" in source or "ebay.com" in url:
            return self._check_ebay(url, deal)
        return self._check_craigslist(url)

    def _check_craigslist(self, url: str) -> bool:
        if not url:
            return False
        try:
            resp = self.session.get(url, timeout=12, allow_redirects=True)
            if resp.status_code == 404:
                return False
            # Removed CL listings redirect to the site root
            if resp.url.rstrip("/") in ("https://www.craigslist.org", "https://craigslist.org"):
                return False
            lower = resp.text.lower()
            if any(phrase in lower for phrase in CL_REMOVED_PHRASES):
                return False
            soup = BeautifulSoup(resp.text, "html.parser")
            if not soup.select_one("#postingbody"):
                return False
            return True
        except Exception:
            return True  # Network error — assume alive, retry next run

    def _check_ebay(self, url: str, deal: dict) -> bool:
        item_id = deal.get("ebay_item_id") or self._extract_ebay_item_id(url)
        if not item_id:
            return True  # Can't verify without item ID
        return self.ebay_detail.exists(item_id)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _remove_expired(self, deal: dict) -> None:
        url = deal.get("url", "")
        self.db.deals.delete_one({"_id": deal["_id"]})
        if url:
            self.db.raw_listings.update_many(
                {"url": url},
                {"$set": {"status": "skipped", "skip_reason": "listing_removed"}},
            )

    @staticmethod
    def _extract_ebay_item_id(url: str) -> str | None:
        m = EBAY_ITEM_RE.search(url or "")
        return m.group(1) if m else None


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
    checker = DealExpiryChecker()
    result = checker.run(max_checks=200)
    print(f"\nDone: {result}")
