"""
Deal Evaluator — Batch Processor with MongoDB Checkpoint Pattern

Reads pending listings from raw_listings, enriches them with detail page
data, scores them with Claude (Haiku), and writes deals to MongoDB.
Also records price_observations to build market knowledge over time.
"""
import json
import re
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from dotenv import load_dotenv
import os

from src.evaluator.claude_evaluator import ClaudeEvaluator

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BATCH_SIZE        = 50    # Listings per batch (loops until all pending are done)
MIN_SCORE_TO_SAVE = 50    # Only save FAIR and above (50+) to keep deals collection clean
REQUEST_DELAY     = 1.5   # Seconds between detail-page fetches

# Keywords that disqualify a listing before hitting Claude — saves API calls + DB space.
# Checked against both the raw title (before detail fetch) and the full description (after).
SKIP_KEYWORDS = [
    "salvage title", "rebuilt title", "reconstructed title",
    "flood title", "flood damage", "flood car",
    "frame damage", "bent frame", "structural damage",
    "airbag deployed", "airbags deployed", "no airbags",
    "for parts", "parts only", "parts car",
    "blown head gasket", "seized engine", "locked engine",
    "no title",
]

# Craigslist structured title_status values that disqualify a listing
SALVAGE_TITLE_STATUSES = {"salvage", "rebuilt", "reconstructed", "parts only", "lemon"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MILEAGE_RE = re.compile(
    r"(?:odometer|mileage|miles?)[:\s]*([0-9]{1,3}(?:,?[0-9]{3})*)\s*(?:mi|miles?)?",
    re.IGNORECASE,
)

VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")


class DealEvaluator:
    """
    Reads pending raw_listings, enriches + scores them with Claude, writes to deals.
    Uses status field on raw_listing as natural resumption checkpoint.
    """

    def __init__(self):
        self.db: Database = self._connect_db()
        self._ensure_indexes()
        self.evaluator = ClaudeEvaluator()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._wish_list_map = self._load_wish_list()

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _connect_db(self) -> Database:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set")
        client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
        client.admin.command("ping")
        logger.info("[evaluator] Connected to MongoDB Atlas")
        return client["overland_finder"]

    def _ensure_indexes(self) -> None:
        # Sparse unique index on VIN: enforces uniqueness only when VIN is present,
        # so multiple null-VIN documents (Craigslist) don't conflict.
        try:
            self.db.deals.drop_index("vin_unique")
        except Exception:
            pass  # Didn't exist yet — fine
        self.db.deals.create_index(
            [("vin", ASCENDING)],
            unique=True,
            sparse=True,
            name="vin_unique",
        )

    def _load_wish_list(self) -> dict:
        """Load wish_list.json and index by item name for fast lookup."""
        wish_list_path = Path(__file__).parent.parent.parent / "wish_list.json"
        try:
            with open(wish_list_path, encoding="utf-8") as f:
                items = json.load(f)
            logger.info(f"[evaluator] Loaded {len(items)} items from wish_list.json")
            return {item["name"]: item for item in items}
        except Exception as e:
            logger.warning(f"[evaluator] Could not load wish_list.json: {e}")
            return {}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """
        Process up to BATCH_SIZE pending listings.
        Returns counts for logging/job history.
        """
        pending = list(
            self.db.raw_listings
            .find({"status": "pending"})
            .limit(BATCH_SIZE)
        )

        if not pending:
            logger.info("[evaluator] No pending listings — nothing to do")
            return {"evaluated": 0, "deals_saved": 0, "errors": 0}

        batch_size = len(pending)
        logger.info(f"[evaluator] Processing {batch_size} pending listings")

        evaluated = 0
        deals_saved = 0
        errors = 0

        for idx, raw in enumerate(pending, start=1):
            listing_id = raw["_id"]
            url = raw.get("url", "")

            try:
                # Mark as in-progress so parallel runs skip it
                self.db.raw_listings.update_one(
                    {"_id": listing_id},
                    {"$set": {"status": "processing"}}
                )

                # Skip if no price
                if not raw.get("price"):
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": "no_price"}}
                    )
                    continue

                # Quick keyword check on raw title — avoids fetching detail page for obvious junk
                raw_title_lower = raw.get("title", "").lower()
                if any(kw in raw_title_lower for kw in SKIP_KEYWORDS):
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped (title keyword): '{raw.get('title')}'"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": "keyword_title"}}
                    )
                    continue

                # Enrich with detail page (best-effort)
                enriched = self._enrich_from_detail(raw)

                # Structured title_status check (Craigslist attrgroup field)
                title_status = (enriched.get("title_status") or "").lower()
                if title_status in SALVAGE_TITLE_STATUSES:
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped (title status '{title_status}'): "
                        f"'{enriched.get('title')}'"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": f"title_status_{title_status}"}}
                    )
                    continue

                # Full description keyword check after detail fetch
                description_lower = (enriched.get("description") or "").lower()
                if any(kw in description_lower for kw in SKIP_KEYWORDS):
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped (description keyword): "
                        f"'{enriched.get('title')}'"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": "keyword_description"}}
                    )
                    continue

                # Look up wish_list context
                wish_list_name = raw.get("wish_list_name") or raw.get("search_query", "")
                item = self._wish_list_map.get(wish_list_name, {})
                evaluation_notes = item.get("evaluation_notes", "")

                # Skip if mileage exceeds item's max (skip only when mileage is known)
                max_mileage = item.get("max_mileage")
                mileage = enriched.get("mileage")
                if max_mileage and mileage and mileage > max_mileage:
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped high mileage: "
                        f"'{enriched.get('title')}' {mileage:,} mi > {max_mileage:,} limit"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": f"mileage_{mileage}"}}
                    )
                    continue

                # Skip if year is outside item's [min_year, max_year] window
                year = enriched.get("year")
                min_year = item.get("min_year")
                max_year = item.get("max_year")
                if min_year and year and year < min_year:
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped old vehicle: "
                        f"'{enriched.get('title')}' {year} < {min_year} min year"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": f"year_{year}"}}
                    )
                    continue
                if max_year and year and year > max_year:
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped new vehicle: "
                        f"'{enriched.get('title')}' {year} > {max_year} max year"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": f"year_{year}"}}
                    )
                    continue

                # Duplicate check — same title + price already in deals (e.g. dealer listing twice on eBay)
                if self.db.deals.find_one({"title": enriched.get("title"), "price": enriched.get("price")}):
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped (duplicate): '{enriched.get('title')}' "
                        f"${enriched.get('price', 0):,}"
                    )
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": "duplicate"}}
                    )
                    continue

                # Score with Claude
                evaluation = self.evaluator.evaluate(enriched, wish_list_name, evaluation_notes)
                evaluated += 1

                # Record price observation for market knowledge
                self._record_price_observation(enriched, wish_list_name, evaluation)

                score = evaluation.get("value_score", 0)
                action = evaluation.get("recommended_action", "PASS")

                if score >= MIN_SCORE_TO_SAVE:
                    self._save_deal(raw, enriched, evaluation, wish_list_name)
                    deals_saved += 1
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Deal saved: '{enriched.get('title')}' "
                        f"${enriched.get('price', 0):,} | score={score:.1f} | {action} | {url}"
                    )
                else:
                    logger.info(
                        f"[evaluator] [{idx}/{batch_size}] Skipped: '{enriched.get('title')}' "
                        f"score={score:.1f} | {action} | {url}"
                    )

                self.db.raw_listings.update_one(
                    {"_id": listing_id},
                    {"$set": {
                        "status": "evaluated",
                        "evaluated_at": datetime.now(timezone.utc),
                        "value_score": score,
                        "recommended_action": action,
                    }}
                )

            except Exception as e:
                errors += 1
                logger.exception(f"[evaluator] Error on {url}: {e}")
                self.db.raw_listings.update_one(
                    {"_id": listing_id},
                    {"$set": {"status": "error", "error": str(e)}}
                )

            time.sleep(REQUEST_DELAY)

        logger.info(
            f"[evaluator] Done — {evaluated} evaluated, "
            f"{deals_saved} deals saved, {errors} errors"
        )
        return {"evaluated": evaluated, "deals_saved": deals_saved, "errors": errors}

    # ------------------------------------------------------------------
    # Detail page enrichment
    # ------------------------------------------------------------------

    def _enrich_from_detail(self, raw: dict) -> dict:
        """
        Fetch the individual Craigslist listing page to extract mileage,
        description, and post date. Falls back to raw data on errors.
        """
        enriched = dict(raw)
        url = raw.get("url", "")

        if not url:
            return enriched

        try:
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Description
            body_el = soup.select_one("#postingbody") or soup.select_one(".body")
            if body_el:
                for tag in body_el.select(".print-qrcode-container"):
                    tag.decompose()
                enriched["description"] = body_el.get_text(" ", strip=True)
            else:
                enriched["description"] = ""

            # Mileage — check attribute groups first, then description
            mileage = self._extract_mileage_from_attrs(soup)
            if mileage is None and enriched.get("description"):
                mileage = self._extract_mileage_from_text(enriched["description"])
            enriched["mileage"] = mileage

            # Condition, title status, VIN from attribute groups
            attrs = self._extract_attr_groups(soup)
            enriched["condition"]    = attrs.get("condition")
            enriched["title_status"] = attrs.get("title status")
            enriched["odometer"]     = attrs.get("odometer")

            # VIN — attrs first, then regex fallback on description
            vin = attrs.get("vin")
            if not vin and enriched.get("description"):
                m = VIN_RE.search(enriched["description"])
                vin = m.group(1) if m else None
            enriched["vin"] = vin

            # More-accurate price from detail page
            price_el = soup.select_one("span.price") or soup.select_one(".price")
            if price_el:
                enriched["price"] = self._parse_price(price_el.get_text(strip=True)) or raw.get("price")

            # Post date
            time_el = soup.select_one("time.date") or soup.select_one("time[datetime]")
            if time_el:
                enriched["posted_at"] = time_el.get("datetime")

        except Exception as e:
            logger.debug(f"[evaluator] Detail fetch failed for {url}: {e}")

        return enriched

    @staticmethod
    def _extract_attr_groups(soup) -> dict:
        attrs = {}
        for group in soup.select(".attrgroup"):
            for span in group.select("span"):
                text = span.get_text(" ", strip=True).lower()
                if ":" in text:
                    k, _, v = text.partition(":")
                    attrs[k.strip()] = v.strip()
                elif text:
                    attrs[text] = True
        return attrs

    @staticmethod
    def _extract_mileage_from_attrs(soup) -> Optional[int]:
        for span in soup.select(".attrgroup span"):
            text = span.get_text(" ", strip=True).lower()
            if "odometer" in text or "mileage" in text:
                digits = re.sub(r"[^\d]", "", text)
                if digits:
                    return int(digits)
        return None

    @staticmethod
    def _extract_mileage_from_text(text: str) -> Optional[int]:
        m = MILEAGE_RE.search(text)
        if m:
            return int(m.group(1).replace(",", ""))
        return None

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    # ------------------------------------------------------------------
    # Deal persistence
    # ------------------------------------------------------------------

    def _save_deal(self, raw: dict, enriched: dict, evaluation: dict, wish_list_name: str) -> None:
        """Upsert deal into the deals collection."""
        price = enriched.get("price", 0) or 0
        market_val = evaluation.get("estimated_market_value", 0) or 0
        discount = ((market_val - price) / market_val * 100) if market_val > 0 and price > 0 else 0

        # Derive make/model from wish_list_name for SMS digest compatibility
        parts = wish_list_name.split(" ", 1) if wish_list_name else []
        make = parts[0] if parts else ""
        model = parts[1] if len(parts) > 1 else wish_list_name

        vin = enriched.get("vin")
        update: dict = {"$set": {
            "url":                enriched.get("url", ""),
            "title":              enriched.get("title", ""),
            "make":               make,
            "model":              model,
            "wish_list_name":     wish_list_name,
            "year":               enriched.get("year"),
            "price":              price,
            "mileage":            enriched.get("mileage"),
            "location":           enriched.get("location", ""),
            "description":        (enriched.get("description") or "")[:2000],
            "title_status":       enriched.get("title_status"),
            "source":             raw.get("source", "craigslist"),

            "value_score":        evaluation.get("value_score", 0),
            "recommended_action": evaluation.get("recommended_action", "PASS"),
            "market_value_est":   market_val,
            "discount_percent":   discount,
            "pros":               evaluation.get("pros", []),
            "cons":               evaluation.get("cons", []),
            "red_flags":          evaluation.get("red_flags", []),
            "analysis":           evaluation.get("analysis", ""),

            "region":             raw.get("region"),
            "search_query":       raw.get("search_query"),
            "source":             raw.get("source", "craigslist_scraper"),
            "scraped_at":         raw.get("scraped_at"),
            "evaluated_at":       datetime.now(timezone.utc),
            "notified":           False,
        }}
        # Only store vin when present — sparse unique index skips absent fields,
        # but indexes vin:null as a value, so null-VIN docs would conflict.
        if vin:
            update["$set"]["vin"] = vin
        else:
            update["$unset"] = {"vin": ""}

        self.db.deals.update_one(
            {"url": enriched.get("url", "")},
            update,
            upsert=True,
        )

    def _record_price_observation(self, enriched: dict, wish_list_name: str, evaluation: dict) -> None:
        """Record price data point for building market knowledge over time."""
        price = enriched.get("price")
        market_est = evaluation.get("estimated_market_value")
        if not price or not market_est:
            return

        self.db.price_observations.insert_one({
            "wish_list_name":    wish_list_name,
            "title":             enriched.get("title", ""),
            "price":             price,
            "year":              enriched.get("year"),
            "mileage":           enriched.get("mileage"),
            "location":          enriched.get("location", ""),
            "claude_market_est": market_est,
            "value_score":       evaluation.get("value_score"),
            "observed_at":       datetime.now(timezone.utc),
        })


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
    evaluator = DealEvaluator()
    totals = {"evaluated": 0, "deals_saved": 0, "errors": 0}
    while True:
        result = evaluator.run()
        for k in totals:
            totals[k] += result[k]
        if result["evaluated"] == 0:
            break
    print(f"\nFinished: {totals}")
