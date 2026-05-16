"""
Claude-based deal evaluator — replaces the rule-based ValueEvaluator.
Uses claude-haiku via the Anthropic SDK with tool_use for structured output
and prompt caching on the system prompt to reduce API costs across batch runs.
"""
import os
import logging

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert deal evaluator helping a buyer find exceptional bargains on used vehicles.
Your job is to identify listings priced significantly below what similar vehicles actually sell for.

## Step 1 — Establish estimated_market_value

This is the most critical step. estimated_market_value must reflect what this specific vehicle
(same year, trim, and mileage range) actually sells for in private-party and eBay completed
transactions — NOT KBB retail, NOT dealer asking prices, NOT MSRP.

Calibration examples (private-party / eBay sold):
  2021 Jeep Wrangler Unlimited Sport, 70k mi  → ~$27,000–$29,000
  2018 Toyota 4Runner SR5, 80k mi             → ~$30,000–$33,000
  2019 Lexus GX460, 60k mi                    → ~$38,000–$42,000
  2020 Jeep Wrangler Unlimited Rubicon, 50k mi → ~$35,000–$38,000

If you set market value too low, ordinary listings look like deals. Most eBay dealers and
private sellers list at or slightly below these comps — that is the market, not a bargain.

## Step 2 — Compute base score from price-to-market ratio

  price < 50% of market   → base 90
  price 50–65% of market  → base 80
  price 65–80% of market  → base 68
  price 80–95% of market  → base 54
  price 95–110% of market → base 44
  price > 110% of market  → base 30

## Step 3 — Apply adjustments (stack multiple if applicable)

  Clean title, documented service history    → +5
  Desirable rare trim or low miles for year  → +5
  Mileage unknown / not disclosed            → −5
  High mileage for type (>150k miles)        → −5
  Rebuilt/salvage title                      → −10
  Needs significant work (motor, trans, etc) → −15
  Flood, fire, frame, or rollover damage     → −25
  Scam signals (no VIN, wire transfer only)  → −20

## Step 4 — Map final score to recommended_action

  80–100 → STRONG BUY
  65–79  → GOOD DEAL
  50–64  → FAIR
  35–49  → PASS
  0–34   → RED FLAG

## Expected score distribution

Across a typical batch of used vehicle listings you should see roughly:
   5% STRONG BUY  — exceptional, clearly well below market
  20% GOOD DEAL  — noticeably below market, worth pursuing
  40% FAIR       — at or near market rate, not a bargain
  25% PASS       — at or above market, condition concerns, or missing info
  10% RED FLAG   — serious problems or pricing that makes no sense

If the majority of your scores are GOOD DEAL, your market value estimates are too low —
recalibrate upward. A dealer listing a Wrangler at $28k when comps are $28–31k is FAIR.

Always call submit_evaluation to return your structured assessment."""


class ClaudeEvaluator:
    """Evaluates Craigslist listings using Claude Haiku for fast, cheap batch evaluation."""

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def evaluate(self, listing: dict, item_name: str, evaluation_notes: str = "", recalls: list | None = None) -> dict:
        """
        Evaluate a listing using Claude.

        Args:
            listing: Enriched raw listing dict (title, price, year, mileage, description, etc.)
            item_name: What we're looking for (e.g. "Toyota 4Runner")
            evaluation_notes: Buyer criteria and red flags for this item type
            recalls: Open NHTSA recall campaigns for this vehicle

        Returns:
            Dict with: value_score, recommended_action, estimated_market_value,
                       pros, cons, red_flags, analysis
        """
        prompt = self._build_prompt(listing, item_name, evaluation_notes, recalls or [])

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=[self._evaluation_tool()],
            tool_choice={"type": "tool", "name": "submit_evaluation"},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_evaluation":
                return block.input

        raise RuntimeError(f"Claude did not call submit_evaluation for '{listing.get('title')}'")

    def _build_prompt(self, listing: dict, item_name: str, evaluation_notes: str, recalls: list) -> str:
        lines = [f"Evaluate this listing for: {item_name}"]

        if evaluation_notes:
            lines.append(f"Buyer criteria: {evaluation_notes}")

        lines.append("")
        lines.append(f"Title: {listing.get('title', 'N/A')}")
        lines.append(f"Price: ${listing.get('price', 0):,}")

        if listing.get("year"):
            lines.append(f"Year: {listing['year']}")
        if listing.get("mileage"):
            lines.append(f"Mileage: {listing['mileage']:,} miles")
        else:
            lines.append("Mileage: UNKNOWN — odometer not disclosed. Apply a -5 uncertainty penalty and note this in cons.")
        if listing.get("location"):
            lines.append(f"Location: {listing['location']}")
        if listing.get("title_status"):
            lines.append(f"Title status: {listing['title_status']}")
        if listing.get("condition"):
            lines.append(f"Condition: {listing['condition']}")

        description = (listing.get("description") or "").strip()
        if description:
            lines.append(f"\nDescription:\n{description[:1500]}")

        if recalls:
            lines.append(f"\nOpen NHTSA Recalls ({len(recalls)}):")
            for r in recalls:
                lines.append(f"  - {r['component']}: {r['summary'][:200]}")

        return "\n".join(lines)

    @staticmethod
    def _evaluation_tool() -> dict:
        return {
            "name": "submit_evaluation",
            "description": "Submit structured evaluation of the listing",
            "input_schema": {
                "type": "object",
                "properties": {
                    "estimated_market_value": {
                        "type": "integer",
                        "description": "What this vehicle (same year, trim, mileage) sells for in private-party and eBay completed transactions. NOT KBB retail or dealer asking price. If set too low, scores will be inflated.",
                    },
                    "value_score": {
                        "type": "number",
                        "description": "0-100 per the system prompt formula. Most listings score 50-64 (FAIR). GOOD DEAL (65-79) means genuinely below market. STRONG BUY (80+) is rare — about 1 in 20 listings.",
                    },
                    "recommended_action": {
                        "type": "string",
                        "enum": ["STRONG BUY", "GOOD DEAL", "FAIR", "PASS", "RED FLAG"],
                        "description": "Must match value_score: 80-100=STRONG BUY, 65-79=GOOD DEAL, 50-64=FAIR, 35-49=PASS, 0-34=RED FLAG",
                    },
                    "pros": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Positive aspects of this listing",
                    },
                    "cons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Negative aspects or concerns",
                    },
                    "red_flags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Serious concerns that could make this a bad purchase",
                    },
                    "analysis": {
                        "type": "string",
                        "description": "2-3 sentence summary of the deal quality",
                    },
                },
                "required": [
                    "value_score",
                    "recommended_action",
                    "estimated_market_value",
                    "pros",
                    "cons",
                    "red_flags",
                    "analysis",
                ],
            },
        }
