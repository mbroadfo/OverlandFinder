"""
Smoke tests — verify imports and basic logic without hitting MongoDB or external APIs.
"""
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

def test_base_scraper_imports():
    from src.scrapers.base_scraper import BaseScraper
    assert BaseScraper is not None


def test_craigslist_scraper_imports():
    from src.scrapers.craigslist_scraper import CraigslistScraper, SEARCH_TERMS, REGIONS
    assert CraigslistScraper is not None
    assert len(SEARCH_TERMS) > 0
    assert "denver" in REGIONS


def test_claude_evaluator_imports():
    from src.evaluator.claude_evaluator import ClaudeEvaluator
    assert ClaudeEvaluator is not None


def test_sms_digest_imports():
    from src.jobs.sms_digest import SMSDigest, MIN_SCORE, TOP_N
    assert SMSDigest is not None
    assert MIN_SCORE >= 0
    assert TOP_N > 0


def test_function_app_imports():
    import function_app
    assert hasattr(function_app, "app")


# ---------------------------------------------------------------------------
# ClaudeEvaluator unit tests (no API calls)
# ---------------------------------------------------------------------------

def test_claude_evaluator_build_prompt_includes_key_fields():
    from src.evaluator.claude_evaluator import ClaudeEvaluator
    with patch("src.evaluator.claude_evaluator.anthropic.Anthropic"):
        ev = ClaudeEvaluator()

    listing = {
        "title": "2010 Toyota 4Runner SR5 4x4",
        "price": 8500,
        "year": 2010,
        "mileage": 130000,
        "location": "Denver, CO",
        "description": "Clean title, runs great, new tires",
    }
    prompt = ev._build_prompt(listing, "Toyota 4Runner", "Prefer clean title 4x4", [])
    assert "Toyota 4Runner" in prompt
    assert "8,500" in prompt
    assert "2010" in prompt
    assert "130,000" in prompt
    assert "Denver" in prompt


def test_claude_evaluator_tool_schema_has_required_fields():
    from src.evaluator.claude_evaluator import ClaudeEvaluator
    tool = ClaudeEvaluator._evaluation_tool()
    required = tool["input_schema"]["required"]
    for field in ("value_score", "recommended_action", "estimated_market_value",
                  "pros", "cons", "red_flags", "analysis"):
        assert field in required, f"Missing required field: {field}"


def test_claude_evaluator_evaluate_parses_tool_use_response():
    from src.evaluator.claude_evaluator import ClaudeEvaluator
    with patch("src.evaluator.claude_evaluator.anthropic.Anthropic"):
        ev = ClaudeEvaluator()

    expected = {
        "value_score": 75,
        "recommended_action": "GOOD DEAL",
        "estimated_market_value": 15000,
        "pros": ["Clean title", "Low miles for year"],
        "cons": [],
        "red_flags": [],
        "analysis": "Solid deal on a reliable 4Runner.",
    }
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_evaluation"
    mock_block.input = expected

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    ev.client.messages.create.return_value = mock_response

    listing = {"title": "2010 Toyota 4Runner", "price": 12000}
    result = ev.evaluate(listing, "Toyota 4Runner")

    assert result["value_score"] == 75
    assert result["recommended_action"] == "GOOD DEAL"
    assert isinstance(result["pros"], list)


# ---------------------------------------------------------------------------
# SMS formatting test (no SMTP connection)
# ---------------------------------------------------------------------------

def test_sms_format_message():
    from src.jobs.sms_digest import SMSDigest

    mock_db = MagicMock()
    with patch.object(SMSDigest, "_connect_db", return_value=mock_db):
        digest = SMSDigest()

    deal = {"year": 2015, "make": "Toyota", "model": "4Runner", "price": 13700,
            "value_score": 72, "location": "Aurora", "url": "https://cl.org/1",
            "source": "craigslist"}
    msg = digest._format_deal(deal, 1, 3)

    assert "OverlandFinder" in msg
    assert "4Runner" in msg
    assert len(msg) <= 200  # Single deal fits comfortably in one SMS
