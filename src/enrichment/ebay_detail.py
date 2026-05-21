"""
eBay item detail fetcher — retrieves full listing data (mileage, title status,
description) for eBay listings where the Browse API summary was incomplete.
Reuses the same OAuth credentials as the scraper.
"""
import base64
import logging
import os
import re
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
ITEM_URL  = "https://api.ebay.com/buy/browse/v1/item/{item_id}"


class EbayDetailFetcher:
    """Fetches full eBay item details to fill in gaps left by the Browse API summary."""

    def __init__(self):
        self.app_id  = os.getenv("EBAY_APP_ID", "")
        self.cert_id = os.getenv("EBAY_CERT_ID", "")
        self._token: Optional[str] = None
        self._token_expires: float = 0.0
        self.session = requests.Session()

    def _get_token(self) -> Optional[str]:
        if not self.app_id or not self.cert_id:
            return None
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        credentials = base64.b64encode(f"{self.app_id}:{self.cert_id}".encode()).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        return self._token

    def exists(self, ebay_item_id: str) -> bool:
        """Return True only if the eBay listing is still active and purchasable."""
        if not ebay_item_id:
            return True  # Can't verify — assume alive
        try:
            token = self._get_token()
            if not token:
                return True  # Can't verify without credentials — assume alive
            resp = self.session.get(
                ITEM_URL.format(item_id=ebay_item_id),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code in (404, 410):
                return False
            if not resp.ok:
                return True  # Other error — assume alive, retry next run
            data = resp.json()
            # Sold/ended Fixed Price listings return 200 but show no buying options
            # or report SOLD_OUT / UNAVAILABLE availability
            buying_options = data.get("buyingOptions", [])
            if buying_options and not any(o in buying_options for o in ("FIXED_PRICE", "BEST_OFFER", "AUCTION")):
                return False
            for avail in data.get("estimatedAvailabilities", []):
                status = avail.get("estimatedAvailabilityStatus", "")
                if status in ("SOLD_OUT", "UNAVAILABLE"):
                    return False
            return True
        except Exception:
            return True  # Network error — assume alive, retry next run

    def fetch(self, ebay_item_id: str) -> dict:
        """
        Fetch full item detail for a single eBay listing.
        Returns a dict with any of: mileage, title_status, description, condition.
        Returns empty dict silently on any failure — enrichment is best-effort.
        """
        if not ebay_item_id:
            return {}
        try:
            token = self._get_token()
            if not token:
                return {}
            resp = self.session.get(
                ITEM_URL.format(item_id=ebay_item_id),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code in (404, 410):
                return {}
            resp.raise_for_status()
            return self._parse(resp.json())
        except Exception as e:
            logger.debug(f"[ebay_detail] Failed for {ebay_item_id}: {e}")
            return {}

    def _parse(self, item: dict) -> dict:
        result: dict = {}

        # localizedAspects has all the structured fields: Mileage, Vehicle Title, etc.
        mileage: Optional[int] = None
        for aspect in item.get("localizedAspects", []):
            name  = aspect.get("name", "").lower()
            value = aspect.get("value", "")
            if name in ("mileage", "odometer"):
                digits = re.sub(r"[^\d]", "", value)
                if digits:
                    mileage = int(digits)
            elif name == "vehicle title":
                result["title_status"] = value.lower()

        if mileage is not None:
            result["mileage"] = mileage

        # Full HTML description — strip tags
        desc_html = item.get("description", "")
        if desc_html:
            clean = re.sub(r"<[^>]+>", " ", desc_html)
            clean = re.sub(r"\s+", " ", clean).strip()
            result["description"] = clean[:2000]

        # Condition string (e.g. "Used", "Certified Pre-Owned")
        condition = item.get("condition", "")
        if condition:
            result["condition"] = condition

        return result
