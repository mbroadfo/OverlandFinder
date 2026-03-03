"""
Deal Evaluator — Batch Processor with MongoDB Checkpoint Pattern

Fetches pending listings from raw_listings, enriches them with detail page
data (mileage, description), scores them, and writes deals to MongoDB.
"""
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.database import Database
from dotenv import load_dotenv
import os

from src.evaluator.value_evaluator import ValueEvaluator, VehicleListing, DealEvaluation
from src.data.vehicle_database import get_vehicle_profile

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BATCH_SIZE          = 20    # Listings to evaluate per run (stay under 10 min)
MIN_SCORE_TO_SAVE   = 30    # Skip saving obvious junk deals
REQUEST_DELAY       = 1.5   # Seconds between detail-page fetches
MAX_BUDGET          = 30_000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Mileage patterns in listing body text
MILEAGE_RE = re.compile(
    r"(?:odometer|mileage|miles?)[:\s]*([0-9]{1,3}(?:,?[0-9]{3})*)\s*(?:mi|miles?)?",
    re.IGNORECASE,
)


class DealEvaluator:
    """
    Reads pending raw_listings, enriches + scores them, writes to deals.
    Uses status field on raw_listing as natural resumption checkpoint — 
    never re-processes listings that are already 'evaluated' or 'error'.
    """

    def __init__(self):
        self.db: Database = self._connect_db()
        self.evaluator = ValueEvaluator(max_budget=MAX_BUDGET)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # DB connection
    # ------------------------------------------------------------------

    def _connect_db(self) -> Database:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set")
        client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
        client.admin.command("ping")
        logger.info("[evaluator] Connected to MongoDB Atlas")
        return client["overland_finder"]

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

        logger.info(f"[evaluator] Processing {len(pending)} pending listings")

        evaluated = 0
        deals_saved = 0
        errors = 0

        for raw in pending:
            listing_id = raw["_id"]
            url = raw.get("url", "")

            try:
                # Mark as in-progress so parallel runs skip it
                self.db.raw_listings.update_one(
                    {"_id": listing_id},
                    {"$set": {"status": "processing"}}
                )

                # Enrich with detail page (best-effort)
                enriched = self._enrich_from_detail(raw)

                # Build VehicleListing for the evaluator
                listing_obj = self._to_vehicle_listing(enriched)

                if listing_obj is None:
                    # Can't map to a known platform — mark and skip
                    self.db.raw_listings.update_one(
                        {"_id": listing_id},
                        {"$set": {"status": "skipped", "skip_reason": "unknown_platform"}}
                    )
                    continue

                # Run scoring
                evaluation: DealEvaluation = self.evaluator.evaluate_listing(listing_obj)
                evaluated += 1

                # Only persist worthwhile deals
                if evaluation.value_score >= MIN_SCORE_TO_SAVE:
                    self._save_deal(raw, enriched, evaluation)
                    deals_saved += 1
                    logger.info(
                        f"[evaluator] 💾 Deal saved: '{enriched.get('title')}' "
                        f"${enriched.get('price'):,} | score={evaluation.value_score:.1f} "
                        f"| {evaluation.recommended_action}"
                    )
                else:
                    logger.debug(
                        f"[evaluator] Skipped low-score listing: "
                        f"'{enriched.get('title')}' score={evaluation.value_score:.1f}"
                    )

                # Mark as evaluated
                self.db.raw_listings.update_one(
                    {"_id": listing_id},
                    {"$set": {
                        "status": "evaluated",
                        "evaluated_at": datetime.now(timezone.utc),
                        "value_score": evaluation.value_score,
                        "recommended_action": evaluation.recommended_action,
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
                # Remove the "QR code" notice if present
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

            # Condition, title status from attribute groups
            attrs = self._extract_attr_groups(soup)
            enriched["condition"]     = attrs.get("condition")
            enriched["title_status"]  = attrs.get("title status")
            enriched["odometer"]      = attrs.get("odometer")

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
        """Extract key-value pairs from Craigslist attribute spans."""
        attrs = {}
        for group in soup.select(".attrgroup"):
            for span in group.select("span"):
                text = span.get_text(" ", strip=True).lower()
                if ":" in text:
                    k, _, v = text.partition(":")
                    attrs[k.strip()] = v.strip()
                elif text:
                    # Single-word attributes like "4wd"
                    attrs[text] = True
        return attrs

    @staticmethod
    def _extract_mileage_from_attrs(soup) -> Optional[int]:
        """Look for odometer reading in Craigslist attribute groups."""
        for span in soup.select(".attrgroup span"):
            text = span.get_text(" ", strip=True).lower()
            if "odometer" in text or "mileage" in text:
                digits = re.sub(r"[^\d]", "", text)
                if digits:
                    return int(digits)
        return None

    @staticmethod
    def _extract_mileage_from_text(text: str) -> Optional[int]:
        """Extract mileage from free-text description."""
        m = MILEAGE_RE.search(text)
        if m:
            return int(m.group(1).replace(",", ""))
        return None

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    # ------------------------------------------------------------------
    # VehicleListing construction
    # ------------------------------------------------------------------

    def _to_vehicle_listing(self, enriched: dict) -> Optional[VehicleListing]:
        """
        Map an enriched raw listing dict → VehicleListing dataclass.
        Returns None if we can't identify the vehicle platform.
        """
        title    = enriched.get("title", "")
        price    = enriched.get("price") or 0
        year     = enriched.get("year")
        location = enriched.get("location", "")
        desc     = enriched.get("description", "")
        mileage  = enriched.get("mileage") or 150_000  # default if unknown
        url      = enriched.get("url", "")

        if not year or not price:
            return None

        # Parse make/model from title and search query
        make, model = self._infer_make_model(title, enriched.get("search_query", ""))
        if not make or not model:
            return None

        # Confirm vehicle is in our database
        profile = get_vehicle_profile(make, model, year)
        if not profile:
            # Try with nearby years (+/- 2)
            for dy in [1, -1, 2, -2]:
                profile = get_vehicle_profile(make, model, year + dy)
                if profile:
                    break
        if not profile:
            return None

        return VehicleListing(
            url=url,
            title=title,
            make=make,
            model=model,
            year=year,
            price=price,
            mileage=mileage,
            location=location,
            description=desc,
            title_status=enriched.get("title_status"),
        )

    @staticmethod
    def _infer_make_model(title: str, search_query: str) -> tuple[str, str]:
        """
        Infer make + model from the listing title ONLY.
        The search query is intentionally NOT used — a Craigslist search for
        'wrangler' can return unrelated listings (e.g. Honda Pilot), and
        classifying those by search term causes false positives.
        Returns ("", "") if no confident match.
        """
        title_lower = title.lower()

        MAPPINGS = [
            ("toyota",    "4runner",      ["4runner", "4-runner"]),
            ("toyota",    "tacoma",       ["tacoma"]),
            ("toyota",    "fj cruiser",   ["fj cruiser", "fjcruiser"]),
            ("toyota",    "land cruiser", ["land cruiser", "landcruiser"]),
            ("lexus",     "gx470",        ["gx470", "gx 470"]),
            ("lexus",     "gx460",        ["gx460", "gx 460"]),
            ("jeep",      "wrangler",     ["wrangler"]),
            ("jeep",      "cherokee",     ["cherokee xj", "cherokee kj", "grand cherokee"]),
            ("nissan",    "xterra",       ["xterra"]),
            ("nissan",    "frontier",     ["frontier"]),
            ("ford",      "bronco",       ["bronco"]),
            ("chevrolet", "colorado",     ["colorado zr2", "colorado z71"]),
        ]

        for make, model, keywords in MAPPINGS:
            if any(kw in title_lower for kw in keywords):
                return make.capitalize(), model.title()

        return "", ""

    # ------------------------------------------------------------------
    # Deal persistence
    # ------------------------------------------------------------------

    def _save_deal(self, raw: dict, enriched: dict, evaluation: DealEvaluation) -> None:
        """Upsert deal into the deals collection."""
        listing = evaluation.listing
        self.db.deals.update_one(
            {"url": listing.url},
            {"$set": {
                "url":               listing.url,
                "title":             listing.title,
                "make":              listing.make,
                "model":             listing.model,
                "year":              listing.year,
                "price":             listing.price,
                "mileage":           listing.mileage,
                "location":          listing.location,
                "description":       listing.description[:2000] if listing.description else "",
                "title_status":      listing.title_status,

                "value_score":       evaluation.value_score,
                "recommended_action":evaluation.recommended_action,
                "market_value_est":  evaluation.market_value_estimate,
                "discount_percent":  evaluation.discount_percent,
                "platform_score":    evaluation.platform_score,
                "pros":              evaluation.pros,
                "cons":              evaluation.cons,
                "red_flags":         evaluation.red_flags,
                "analysis":          evaluation.analysis,
                "upgrade_costs":     evaluation.estimated_upgrade_costs,

                "region":            raw.get("region"),
                "search_query":      raw.get("search_query"),
                "source":            raw.get("source", "craigslist_scraper"),
                "scraped_at":        raw.get("scraped_at"),
                "evaluated_at":      datetime.now(timezone.utc),
                "notified":          False,
            }},
            upsert=True,
        )


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
    result = evaluator.run()
    print(f"\n✅ Finished: {result}")
