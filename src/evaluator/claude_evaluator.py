"""
Claude-based deal evaluator — replaces the rule-based ValueEvaluator.
Uses claude-haiku via the Anthropic SDK with tool_use for structured output
and prompt caching on the system prompt to reduce API costs across batch runs.
"""
import os
import logging

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert deal evaluator helping find exceptional bargains on Craigslist.
Your job is to evaluate listings and identify when items are priced significantly below fair market value.

## Scoring formula

Step 1 — Establish estimated_market_value for this item in this condition and region.
Step 2 — Compute a base score from the price-to-market ratio:

  price < 50% of market  → base 90
  price 50–65% of market → base 80
  price 65–80% of market → base 68
  price 80–95% of market → base 54
  price 95–110% of market → base 44
  price > 110% of market → base 30

Step 3 — Apply adjustments (stack multiple if applicable):
  Clean title, documented service history    → +5
  Desirable rare trim or low miles for year  → +5
  High mileage for type (>150k miles)        → −5
  Rebuilt/salvage title                      → −10
  Needs significant work (motor, trans, etc) → −15
  Flood, fire, frame, or rollover damage     → −25
  Scam signals (no VIN, wire transfer only)  → −20

Step 4 — Set recommended_action to match the final score:
  80–100 → STRONG BUY
  65–79  → GOOD DEAL
  50–64  → FAIR
  35–49  → PASS
  0–34   → RED FLAG

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
                        "description": "Estimated fair market value in USD for this item in this condition and region. Establish this first before scoring.",
                    },
                    "value_score": {
                        "type": "number",
                        "description": "0-100 score computed from the price-to-market-value ratio plus condition adjustments per the system prompt formula. Use the full range — do not anchor at 72.",
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
