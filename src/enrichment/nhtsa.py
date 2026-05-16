"""
NHTSA Recalls API client — checks for open safety recalls by make/model/year.
Free, no auth required. Ported from VehicleWellnessCenter/externalApis.ts.
"""
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"

# Maps wish_list_name → (NHTSA make, NHTSA model) as NHTSA expects them
NHTSA_LOOKUP: dict[str, tuple[str, str]] = {
    "Jeep Wrangler":             ("Jeep",   "Wrangler"),
    "Jeep Renegade Trailhawk":   ("Jeep",   "Renegade"),
    "Toyota 4Runner":            ("Toyota", "4Runner"),
    "Lexus GX460":               ("Lexus",  "GX460"),
}


def get_open_recalls(wish_list_name: str, year: Optional[int]) -> list[dict]:
    """
    Returns a list of NHTSA recall campaigns for this vehicle type and year.
    Each entry: {campaign, component, summary, consequence, remedy}
    Returns [] silently on any failure or if year is unknown.
    """
    if not year:
        return []
    nhtsa = NHTSA_LOOKUP.get(wish_list_name)
    if not nhtsa:
        return []

    make, model = nhtsa
    try:
        resp = requests.get(
            RECALLS_URL,
            params={"make": make, "model": model, "modelYear": year},
            timeout=10,
        )
        resp.raise_for_status()
        recalls = [
            {
                "campaign":    r.get("NHTSACampaignNumber", ""),
                "component":   r.get("Component", ""),
                "summary":     r.get("Summary", ""),
                "consequence": r.get("Consequence", ""),
                "remedy":      r.get("Remedy", ""),
            }
            for r in resp.json().get("results", [])
        ]
        if recalls:
            logger.info(f"[nhtsa] {year} {make} {model}: {len(recalls)} recall(s)")
        return recalls
    except Exception as e:
        logger.debug(f"[nhtsa] Recall check failed for {year} {make} {model}: {e}")
        return []
