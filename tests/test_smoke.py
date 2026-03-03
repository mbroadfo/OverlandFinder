"""
Smoke tests — verify imports and basic logic without hitting MongoDB or external APIs.
"""
import pytest


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

def test_base_scraper_imports():
    from src.scrapers.base_scraper import BaseScraper
    assert BaseScraper is not None


def test_craigslist_scraper_imports():
    from src.scrapers.craigslist_scraper import CraigslistScraper, SEARCH_TERMS, REGIONS
    assert len(SEARCH_TERMS) > 0
    assert "denver" in REGIONS


def test_value_evaluator_imports():
    from src.evaluator.value_evaluator import ValueEvaluator, VehicleListing
    assert ValueEvaluator is not None


def test_sms_digest_imports():
    from src.jobs.sms_digest import SMSDigest, MIN_SCORE, TOP_N
    assert MIN_SCORE >= 0
    assert TOP_N > 0


def test_function_app_imports():
    import function_app
    assert hasattr(function_app, "app")


# ---------------------------------------------------------------------------
# Value evaluator unit tests (pure logic, no I/O)
# ---------------------------------------------------------------------------

def test_value_score_great_deal():
    from src.evaluator.value_evaluator import ValueEvaluator, VehicleListing
    ev = ValueEvaluator(max_budget=15_000)
    listing = VehicleListing(
        title="2010 Toyota 4Runner SR5 4x4",
        price=8_500,
        year=2010,
        make="Toyota",
        model="4Runner",
        mileage=130_000,
        location="Denver, CO",
        url="https://denver.craigslist.org/test/1",
        description="Clean title, runs great, new tires",
    )
    result = ev.evaluate_listing(listing)
    # A well-priced 4Runner should score above the minimum threshold
    assert result.value_score >= 30, f"Expected score >= 30, got {result.value_score}"


def test_value_score_over_budget():
    from src.evaluator.value_evaluator import ValueEvaluator, VehicleListing
    ev = ValueEvaluator(max_budget=15_000)
    listing = VehicleListing(
        title="2023 Toyota 4Runner TRD Pro",
        price=55_000,
        year=2023,
        make="Toyota",
        model="4Runner",
        mileage=5_000,
        location="Denver, CO",
        url="https://denver.craigslist.org/test/2",
        description="Brand new, fully loaded",
    )
    result = ev.evaluate_listing(listing)
    # Way over budget — score should be penalised heavily
    assert result.value_score < 50, f"Expected low score for over-budget listing, got {result.value_score}"


# ---------------------------------------------------------------------------
# SMS formatting test (no SMTP connection)
# ---------------------------------------------------------------------------

def test_sms_format_message():
    from src.jobs.sms_digest import SMSDigest
    from unittest.mock import patch, MagicMock

    mock_db = MagicMock()
    with patch.object(SMSDigest, "_connect_db", return_value=mock_db):
        digest = SMSDigest()

    fake_deals = [
        {"year": 2015, "make": "Toyota", "model": "4Runner", "price": 13700,
         "value_score": 72, "location": "Aurora", "url": "https://cl.org/1"},
        {"year": 2013, "make": "Toyota", "model": "4Runner", "price": 13000,
         "value_score": 61, "location": "Denver", "url": "https://cl.org/2"},
    ]
    msg = digest._format_message(fake_deals)

    assert "OverlandFinder" in msg
    assert "4Runner" in msg
    assert len(msg) <= 400  # Must fit in a couple of SMS segments
