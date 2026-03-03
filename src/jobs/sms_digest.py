"""
Daily SMS Digest — Sends top overlanding deals via Verizon email-to-SMS gateway.

Flow:
  1. Query MongoDB for top unnotified deals (last 24h, score >= 40)
  2. Format compact SMS message
  3. Send via SMTP → Verizon NUMBER@vtext.com gateway
  4. Mark deals as notified in MongoDB

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
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Optional

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOP_N              = 3    # Deals to include in digest
MIN_SCORE          = 40   # Only include deals at or above this score
LOOKBACK_HOURS     = 48   # Consider deals evaluated in the last N hours
MAX_SMS_CHARS      = 300  # Keep message short; some carriers accept 300+
GOOD_DEAL_SCORE    = 65   # Above this = "GOOD DEAL", below = "FAIR DEAL"


class SMSDigest:
    """Queries MongoDB for top deals and sends a daily SMS digest."""

    def __init__(self):
        self.db = self._connect_db()
        self.recipient    = os.getenv("SMS_RECIPIENT", "")
        self.smtp_server  = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port    = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user    = os.getenv("SMTP_USERNAME", "")
        self.smtp_pass    = os.getenv("SMTP_PASSWORD", "")

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
        """Query deals, format message, send SMS."""
        deals = self._get_top_deals()

        if not deals:
            logger.info("[sms_digest] No qualifying deals to send")
            return {"sent": False, "deals": 0, "reason": "no_deals"}

        if not self.recipient:
            logger.error("[sms_digest] SMS_RECIPIENT not configured in .env")
            return {"sent": False, "deals": len(deals), "reason": "no_recipient"}

        message = self._format_message(deals)
        logger.info(f"[sms_digest] Sending {len(deals)} deals to {self.recipient}")
        logger.info(f"[sms_digest] Message ({len(message)} chars):\n{message}")

        sent = self._send_sms(message)

        if sent:
            self._mark_notified(deals)
            logger.info(f"[sms_digest] ✅ SMS sent, {len(deals)} deals marked as notified")
        else:
            logger.error("[sms_digest] ❌ SMS send failed")

        return {"sent": sent, "deals": len(deals)}

    # ------------------------------------------------------------------
    # Deal fetching
    # ------------------------------------------------------------------

    def _get_top_deals(self) -> list[dict]:
        """
        Get the top N unnotified deals from the last LOOKBACK_HOURS.
        Excludes RED FLAG listings and already-notified deals.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

        deals = list(
            self.db.deals.find(
                {
                    "value_score": {"$gte": MIN_SCORE},
                    "notified":    False,
                    "evaluated_at": {"$gte": cutoff},
                    # Exclude definite red flags — those contain "🚫" or "RED FLAG"
                    "recommended_action": {"$not": {"$regex": "RED FLAG|🚫"}},
                },
                {
                    "title": 1, "price": 1, "year": 1, "make": 1, "model": 1,
                    "value_score": 1, "recommended_action": 1, "url": 1,
                    "location": 1, "mileage": 1,
                }
            )
            .sort("value_score", -1)
            .limit(TOP_N)
        )

        return deals

    # ------------------------------------------------------------------
    # Message formatting
    # ------------------------------------------------------------------

    def _format_message(self, deals: list[dict]) -> str:
        """
        Format deals into a compact SMS-friendly string.
        Example output:
          OverlandFinder 3 deals:
          1. '15 Tacoma $13.7k (61) Aurora
          2. '13 4Runner $13k (60) Denver
          3. '18 Wrangler $16.5k (55) Erie
        """
        lines = [f"OverlandFinder — {len(deals)} deal{'s' if len(deals) != 1 else ''} today:"]

        for i, deal in enumerate(deals, 1):
            year  = str(deal.get("year", ""))[-2:]   # "2015" → "15"
            model = deal.get("model", "?")
            price = deal.get("price", 0)
            score = int(deal.get("value_score", 0))
            loc   = deal.get("location", "")[:12]    # Truncate long city names

            # Format price: $13700 → "$13.7k", $8800 → "$8.8k"
            price_str = f"${price/1000:.1f}k" if price >= 1000 else f"${price}"

            # Short label
            label = "🔥GREAT" if score >= GOOD_DEAL_SCORE else "👍FAIR"

            lines.append(f"{i}. '{year} {model} {price_str} ({score}) {loc} {label}")

        # Add a bare CL search link
        lines.append("Source: denver.craigslist.org/search/cto")

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
            {"$set": {"notified": True, "notified_at": datetime.now(timezone.utc)}}
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
        deals = digest._get_top_deals()
        if deals:
            msg = digest._format_message(deals)
            print(f"\n📱 DRY RUN — message that would be sent ({len(msg)} chars):\n")
            print("─" * 50)
            print(msg)
            print("─" * 50)
            print(f"\n{len(deals)} deal(s) found, NOT sent (dry run).")
        else:
            print("No qualifying deals found.")
        sys.exit(0)

    result = digest.run()
    if result["sent"]:
        print(f"\n✅ SMS sent with {result['deals']} deal(s)")
    else:
        print(f"\n⚠️  Not sent: {result.get('reason', result)}")
