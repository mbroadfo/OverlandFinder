"""
Daily SMS Digest — Sends top overlanding deals via Verizon email-to-SMS gateway.

Flow:
  1. Query MongoDB for top unnotified deals (score >= 40, scraped within MAX_LISTING_AGE_DAYS)
  2. Verify each candidate listing is still live before sending
  3. Format compact SMS message
  4. Send via SMTP → Verizon NUMBER@vtext.com gateway
  5. Mark deals as notified in MongoDB

Required .env variables:
  SMS_RECIPIENT     — e.g. 7208399656@vtext.com
  SMTP_USERNAME     — your Gmail address
  SMTP_PASSWORD     — Gmail App Password (NOT your login password)
  SMTP_SERVER       — smtp.gmail.com (default)
  SMTP_PORT         — 587 (default)
"""
import os
import smtplib
import logging
import requests
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from bs4 import BeautifulSoup
from pymongo import MongoClient
from dotenv import load_dotenv

from src.enrichment.ebay_detail import EbayDetailFetcher

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOP_N                = 3    # Deals to include in digest
MIN_SCORE            = 40   # Only include deals at or above this score
REPEAT_AFTER_DAYS    = 4    # Re-notify about a deal after this many days
MAX_SMS_CHARS        = 300  # Keep message short; some carriers accept 300+
GOOD_DEAL_SCORE      = 65   # Above this = "GREAT", below = "FAIR"
MAX_LISTING_AGE_DAYS = 5    # Skip deals whose listing was scraped more than this many days ago
FETCH_CANDIDATES     = TOP_N * 3  # Over-fetch so we have fallbacks after liveness filtering

CL_REMOVED_PHRASES = [
    "this posting has been deleted",
    "this posting has expired",
    "this posting has been flagged for removal",
    "this posting has been removed",
]
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class SMSDigest:
    """Queries MongoDB for top deals and sends a daily SMS digest."""

    def __init__(self):
        self.db = self._connect_db()
        self.recipient    = os.getenv("SMS_RECIPIENT", "")
        self.smtp_server  = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port    = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user    = os.getenv("SMTP_USERNAME", "")
        self.smtp_pass    = os.getenv("SMTP_PASSWORD", "")
        self.ebay_detail  = EbayDetailFetcher()

    # ------------------------------------------------------------------
    # DB connection
    # ------------------------------------------------------------------

    def _connect_db(self):
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set")
        client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
        client.admin.command("ping")
        return client["overland_finder"]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Query deals, verify liveness, send one SMS per live deal."""
        candidates = self._get_top_deals()

        if not candidates:
            logger.info("[sms_digest] No qualifying deals to send")
            return {"sent": False, "deals": 0, "reason": "no_deals"}

        if not self.recipient:
            logger.error("[sms_digest] SMS_RECIPIENT not configured in .env")
            return {"sent": False, "deals": len(candidates), "reason": "no_recipient"}

        # Filter to live listings before sending
        live_deals = []
        for deal in candidates:
            if len(live_deals) >= TOP_N:
                break
            title = deal.get("title", "?")[:60]
            if self._is_still_live(deal):
                live_deals.append(deal)
                logger.info(f"[sms_digest] Live: {title}")
            else:
                logger.info(f"[sms_digest] Expired — removing from DB: {title}")
                self.db.deals.delete_one({"_id": deal["_id"]})

        if not live_deals:
            logger.info("[sms_digest] All candidates were expired — nothing to send")
            return {"sent": False, "deals": 0, "reason": "all_expired"}

        import time
        sent_count = 0
        for i, deal in enumerate(live_deals, 1):
            message = self._format_deal(deal, i, len(live_deals))
            logger.info(f"[sms_digest] Sending deal {i}/{len(live_deals)} ({len(message)} chars):\n{message}")
            if self._send_sms(message):
                self._mark_notified([deal])
                sent_count += 1
                logger.info(f"[sms_digest] Deal {i} sent and marked notified")
            else:
                logger.error(f"[sms_digest] Failed to send deal {i}")
            if i < len(live_deals):
                time.sleep(8)  # Pause between sends so gateway delivers as separate SMS

        return {"sent": sent_count > 0, "deals": sent_count}

    # ------------------------------------------------------------------
    # Deal fetching
    # ------------------------------------------------------------------

    def _get_top_deals(self) -> list[dict]:
        """
        Get up to FETCH_CANDIDATES deals eligible for notification, freshest-first.
        Caller will liveness-filter these down to TOP_N before sending.
        """
        repeat_cutoff   = datetime.now(timezone.utc) - timedelta(days=REPEAT_AFTER_DAYS)
        freshness_cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_LISTING_AGE_DAYS)

        deals = list(
            self.db.deals.find(
                {
                    "value_score": {"$gte": MIN_SCORE},
                    "scraped_at":  {"$gte": freshness_cutoff},
                    "$or": [
                        {"notified": False},
                        {"notified_at": {"$lt": repeat_cutoff}},
                    ],
                    "recommended_action": {"$not": {"$regex": "RED FLAG"}},
                },
                {
                    "title": 1, "price": 1, "year": 1, "make": 1, "model": 1,
                    "value_score": 1, "recommended_action": 1, "url": 1,
                    "location": 1, "mileage": 1, "source": 1, "scraped_at": 1, "ebay_item_id": 1,
                }
            )
            .sort([("value_score", -1), ("scraped_at", -1)])
            .limit(FETCH_CANDIDATES)
        )

        return deals

    def _is_still_live(self, deal: dict) -> bool:
        """
        Quick liveness check before sending SMS. Craigslist: HTTP probe.
        Facebook/eBay: optimistic (can't verify without auth/API in this workflow).
        """
        url    = deal.get("url", "")
        source = (deal.get("source") or "").lower()

        if not url:
            return False
        if "facebook" in source:
            return True
        if "ebay" in source or "ebay.com" in url:
            item_id = deal.get("ebay_item_id", "")
            return self.ebay_detail.exists(item_id)  # falls back to True if no creds

        # Craigslist
        try:
            resp = requests.get(url, timeout=12, allow_redirects=True, headers=_HTTP_HEADERS)
            if resp.status_code == 404:
                return False
            if resp.url.rstrip("/") in ("https://www.craigslist.org", "https://craigslist.org"):
                return False
            lower = resp.text.lower()
            if any(phrase in lower for phrase in CL_REMOVED_PHRASES):
                return False
            soup = BeautifulSoup(resp.text, "html.parser")
            return bool(soup.select_one("#postingbody"))
        except Exception:
            return True  # Network error — be optimistic, retry next run

    # ------------------------------------------------------------------
    # Message formatting
    # ------------------------------------------------------------------

    def _format_deal(self, deal: dict, i: int, total: int) -> str:
        """
        Format a single deal as a standalone SMS message.
        Example output:
          OverlandFinder deal 1/3 [CL] 🔥GREAT
          '15 Tacoma $13.7k (82) Aurora
          https://denver.craigslist.org/...
        """
        year    = str(deal["year"])[-2:] if deal.get("year") else "??"
        model   = deal.get("model", "?")
        price   = deal.get("price", 0)
        score   = int(deal.get("value_score", 0))
        loc     = deal.get("location", "")[:16]
        url     = deal.get("url", "").split("?")[0]  # Strip eBay tracking params
        source  = deal.get("source", "")
        if "facebook" in source:
            src_tag = "FB"
        elif "ebay" in source:
            src_tag = "eBay"
        else:
            src_tag = "CL"
        label   = "GREAT" if score >= GOOD_DEAL_SCORE else "FAIR"

        price_str = f"${price/1000:.1f}k" if price >= 1000 else f"${price}"

        lines = [
            f"OverlandFinder {i}/{total} [{src_tag}] {label}",
            f"'{year} {model} {price_str} ({score}) {loc}",
        ]
        if url:
            lines.append(url)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # SMTP send
    # ------------------------------------------------------------------

    def _send_sms(self, message: str) -> bool:
        """Send message via SMTP to the Verizon email-to-SMS gateway."""
        if not self.smtp_user or not self.smtp_pass:
            logger.warning(
                "[sms_digest] SMTP_USERNAME or SMTP_PASSWORD not set. "
                "Add Gmail app password to .env — see docs/SMS_SETUP.md"
            )
            return False

        try:
            msg = MIMEText(message, "plain")
            msg["From"]    = self.smtp_user
            msg["To"]      = self.recipient
            msg["Subject"] = ""  # Empty subject keeps SMS clean

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            return True

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "[sms_digest] Gmail authentication failed. "
                "Use a Gmail App Password, not your login password. "
                "See: https://myaccount.google.com/apppasswords"
            )
            return False

        except Exception as e:
            logger.exception(f"[sms_digest] SMTP error: {e}")
            return False

    # ------------------------------------------------------------------
    # Mark notified
    # ------------------------------------------------------------------

    def _mark_notified(self, deals: list[dict]) -> None:
        ids = [d["_id"] for d in deals]
        self.db.deals.update_many(
            {"_id": {"$in": ids}},
            {
                "$set": {"notified": True, "notified_at": datetime.now(timezone.utc)},
                "$inc": {"times_notified": 1},
            },
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

    digest = SMSDigest()

    # Dry-run mode: show what would be sent without actually sending
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        candidates = digest._get_top_deals()
        if candidates:
            print(f"\nDRY RUN -- checking {len(candidates)} candidates for liveness...\n")
            live, dead = [], []
            for deal in candidates:
                if digest._is_still_live(deal):
                    live.append(deal)
                else:
                    dead.append(deal)
            print(f"Live: {len(live)}  |  Expired: {len(dead)}\n")
            if dead:
                print("EXPIRED (would be deleted):")
                for d in dead:
                    print(f"  - {d.get('title','?')[:70]}")
                print()
            to_send = live[:TOP_N]
            if to_send:
                print(f"WOULD SEND ({len(to_send)}):")
                for i, deal in enumerate(to_send, 1):
                    msg = digest._format_deal(deal, i, len(to_send))
                    print("-" * 50)
                    print(msg)
                print("-" * 50)
            else:
                print("No live deals found — nothing would be sent.")
        else:
            print("No qualifying deals found (check age filter or score threshold).")
        sys.exit(0)

    result = digest.run()
    if result["sent"]:
        print(f"\n✅ SMS sent with {result['deals']} deal(s)")
    else:
        print(f"\n⚠️  Not sent: {result.get('reason', result)}")
