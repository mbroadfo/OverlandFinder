"""
OverlandFinder — Azure Functions v2 Entry Point

Functions:
  - scraper_job        : Timer trigger every 4h — Craigslist scrape + evaluate
  - daily_sms_digest   : Timer trigger daily 8AM MST — SMS top deals

Env vars / Key Vault references (set in Terraform app_settings):
  MONGODB_URI, SMTP_USERNAME, SMTP_PASSWORD, SMS_RECIPIENT
"""
import logging
import time

import azure.functions as func

app = func.FunctionApp()

# ---------------------------------------------------------------------------
# Scraper + Evaluator Job — every 4 hours
# ---------------------------------------------------------------------------


@app.timer_trigger(
    schedule="0 30 */4 * * *",  # :30 past every 4th hour (offset avoids cold-start rush)
    arg_name="scraper_timer",
    run_on_startup=False,
    use_monitor=True,
)
def scraper_job(scraper_timer: func.TimerRequest) -> None:
    """
    1. Run CraigslistScraper  → writes raw_listings to MongoDB
    2. Run DealEvaluator      → enriches raw_listings, writes deals to MongoDB
    """
    logger = logging.getLogger("scraper_job")

    if scraper_timer.past_due:
        logger.warning("Scraper job is past due — running now")

    logger.info("=== Scraper Job Started ===")
    t0 = time.monotonic()

    # --- Step 1: Scrape ---
    try:
        from src.scrapers.craigslist_scraper import CraigslistScraper

        scraper = CraigslistScraper()
        new_count, total_seen = scraper.scrape()
        logger.info(f"Scraper complete: {new_count} new raw_listings / {total_seen} total seen")
    except Exception:
        logger.exception("Scraper step failed — skipping evaluator this run")
        raise  # Re-raise so Functions marks the invocation as failed

    # --- Step 2: Evaluate ---
    try:
        from src.evaluator.deal_evaluator import DealEvaluator

        evaluator = DealEvaluator()
        result = evaluator.run()
        logger.info(f"Evaluator complete: {result}")
    except Exception:
        logger.exception("Evaluator step failed")
        raise

    elapsed = time.monotonic() - t0
    logger.info(f"=== Scraper Job Done in {elapsed:.1f}s ===")


# ---------------------------------------------------------------------------
# Daily SMS Digest — 8:00 AM MST (UTC-7 summer / UTC-6 winter)
# Use 14:00 UTC which = 8 AM MDT (good enough for summer; shifts 1h in winter)
# ---------------------------------------------------------------------------


@app.timer_trigger(
    schedule="0 0 14 * * *",  # Daily at 14:00 UTC = 8:00 AM MDT
    arg_name="sms_timer",
    run_on_startup=False,
    use_monitor=True,
)
def daily_sms_digest(sms_timer: func.TimerRequest) -> None:
    """
    Query MongoDB for top unnotified deals and send SMS via Gmail → Verizon gateway.
    Marks sent deals as notified so they aren't re-sent tomorrow.
    """
    logger = logging.getLogger("daily_sms_digest")

    if sms_timer.past_due:
        logger.warning("SMS digest is past due — running now")

    logger.info("=== Daily SMS Digest Started ===")

    try:
        from src.jobs.sms_digest import SMSDigest

        digest = SMSDigest()
        result = digest.run()
        logger.info(f"SMS digest result: {result}")
    except Exception:
        logger.exception("SMS digest failed")
        raise

    logger.info("=== Daily SMS Digest Complete ===")
