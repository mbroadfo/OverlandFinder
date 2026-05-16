"""
Base Scraper with MongoDB Checkpoint Pattern
All scrapers inherit from this to get resumability + job tracking.
"""
import os
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base class for all OverlandFinder scrapers.

    Provides:
    - MongoDB connection management
    - Checkpoint save/load (resume after interruption)
    - Job history tracking
    - Consistent logging
    """

    def __init__(self, scraper_name: str):
        self.scraper_name = scraper_name
        self.db: Database = self._connect_db()
        self.job_id = f"{scraper_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._job_start = datetime.utcnow()

    # ------------------------------------------------------------------
    # MongoDB helpers
    # ------------------------------------------------------------------

    def _connect_db(self) -> Database:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set in environment")
        client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
        client.admin.command("ping")  # Fail fast if unreachable
        logger.info(f"[{self.scraper_name}] Connected to MongoDB Atlas")
        return client["overland_finder"]

    # ------------------------------------------------------------------
    # Checkpoint pattern
    # ------------------------------------------------------------------

    def load_checkpoint(self) -> dict:
        """Load the last saved checkpoint for this scraper, or empty dict."""
        doc = self.db.batch_checkpoints.find_one({"_id": self.scraper_name})
        if doc:
            logger.info(f"[{self.scraper_name}] Resuming from checkpoint: {doc}")
        else:
            logger.info(f"[{self.scraper_name}] No checkpoint found — starting fresh")
        return doc or {}

    def save_checkpoint(self, state: dict) -> None:
        """Persist current scraper state so we can resume on failure."""
        state.update({"_id": self.scraper_name, "last_updated": datetime.utcnow()})
        self.db.batch_checkpoints.replace_one(
            {"_id": self.scraper_name}, state, upsert=True
        )

    def clear_checkpoint(self) -> None:
        """Remove checkpoint after a successful full run."""
        self.db.batch_checkpoints.delete_one({"_id": self.scraper_name})
        logger.info(f"[{self.scraper_name}] Checkpoint cleared (full run complete)")

    # ------------------------------------------------------------------
    # Listing storage
    # ------------------------------------------------------------------

    def upsert_listing(self, listing: dict) -> bool:
        """
        Insert listing if URL not already in DB. Returns True if new or re-queued.
        Uses $setOnInsert so existing listings are never overwritten.

        Price drop detection: if the same URL was previously evaluated and the new
        price is ≥5% lower, the listing is reset to "pending" so Claude re-scores it
        and the deal record gets updated with the new price.
        """
        listing.setdefault("scraped_at", datetime.utcnow())
        listing.setdefault("status", "pending")
        listing.setdefault("source", self.scraper_name)

        new_price = listing.get("price") or 0
        if new_price:
            existing = self.db.raw_listings.find_one(
                {"url": listing["url"], "status": "evaluated"},
                {"_id": 1, "price": 1},
            )
            if existing:
                old_price = existing.get("price") or 0
                if old_price > 0 and new_price < old_price * 0.95:
                    pct = (old_price - new_price) / old_price * 100
                    self.db.raw_listings.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {
                            "price":                    new_price,
                            "status":                   "pending",
                            "price_dropped_from":       old_price,
                            "price_drop_pct":           round(pct, 1),
                            "price_drop_detected_at":   datetime.utcnow(),
                        }},
                    )
                    logger.info(
                        f"[{self.scraper_name}] Price drop {pct:.0f}%: "
                        f"${old_price:,} → ${new_price:,} — re-queuing for eval"
                    )
                    return True  # Counts toward new_count so it appears in logs
                return False  # Exists, no significant change

        result = self.db.raw_listings.update_one(
            {"url": listing["url"]},
            {"$setOnInsert": listing},
            upsert=True,
        )
        return result.upserted_id is not None

    # ------------------------------------------------------------------
    # Job history
    # ------------------------------------------------------------------

    def _record_job_start(self) -> None:
        self.db.job_history.insert_one({
            "job_id": self.job_id,
            "function_name": self.scraper_name,
            "started_at": self._job_start,
            "status": "running",
        })

    def _record_job_end(self, new_count: int, total_seen: int, error: Optional[str] = None) -> None:
        self.db.job_history.update_one(
            {"job_id": self.job_id},
            {"$set": {
                "finished_at": datetime.utcnow(),
                "status": "error" if error else "success",
                "error": error,
                "new_listings": new_count,
                "total_seen": total_seen,
                "duration_seconds": (datetime.utcnow() - self._job_start).total_seconds(),
            }}
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Run the scraper, recording job history and handling errors."""
        self._record_job_start()
        new_count = 0
        total_seen = 0
        try:
            new_count, total_seen = self.scrape()
            self._record_job_end(new_count, total_seen)
            logger.info(
                f"[{self.scraper_name}] Done — {new_count} new / {total_seen} seen"
            )
        except Exception as e:
            logger.exception(f"[{self.scraper_name}] Fatal error: {e}")
            self._record_job_end(new_count, total_seen, error=str(e))
            raise
        return {"new": new_count, "total_seen": total_seen}

    @abstractmethod
    def scrape(self) -> tuple[int, int]:
        """
        Implement scraping logic here.
        Must return (new_listing_count, total_listings_seen).
        Use load_checkpoint() / save_checkpoint() for resumability.
        """
