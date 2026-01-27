"""SerpAPI provider for local pack. Uses time.time() for timing only."""
import time
from typing import Any, Dict, List, Optional

import httpx
from rapidfuzz import fuzz

from app.config import settings
from app.utils.logging_config import logger


class SerpAPIProvider:
    """Provider for SerpAPI local pack queries."""

    BASE_URL = "https://serpapi.com/search"

    def __init__(self) -> None:
        self.api_key = settings.serpapi_api_key

    async def get_local_pack(
        self,
        query: str,
        target_business_name: str,
        target_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call SerpAPI for "{primary_service_readable} {city}".
        Extract top 3 local pack: name, rating, review_count, address.
        Check if target is in top 3 via token_set_ratio >= 80 and address.
        Return maps_visible_top3 (bool or null), top3_competitors.
        If no local pack: maps_visible_top3=None, local_pack_available=False.
        """
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "location": "United States",
        }
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.BASE_URL, params=params)
            status_code = response.status_code
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                "SerpAPI Local Pack - timestamp=%s status_code=%s elapsed_ms=%s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
                status_code,
                elapsed_ms,
            )
            if status_code != 200:
                return {
                    "status": "error",
                    "status_code": status_code,
                    "error": f"HTTP {status_code}",
                    "local_pack_available": False,
                    "maps_visible_top3": None,
                    "top3_competitors": [],
                }
            data = response.json()
            local_pack = data.get("local_results", [])
            if not isinstance(local_pack, list):
                local_pack = []
            if not local_pack:
                logger.info("SerpAPI - No local pack results")
                return {
                    "status": "success",
                    "status_code": status_code,
                    "local_pack_available": False,
                    "maps_visible_top3": None,
                    "top3_competitors": [],
                }
            top3: List[Dict[str, Any]] = []
            for idx, item in enumerate(local_pack[:3], start=1):
                if not isinstance(item, dict):
                    continue
                top3.append({
                    "rank": idx,
                    "name": item.get("title") or "",
                    "rating": float(item["rating"]) if item.get("rating") is not None else None,
                    "review_count": int(item["reviews"]) if item.get("reviews") is not None else None,
                    "address": item.get("address"),
                })
            maps_visible = self._check_target_in_top3(top3, target_business_name, target_address)
            logger.info(
                "SerpAPI - result_count=%s maps_visible_top3=%s",
                len(top3),
                maps_visible,
            )
            return {
                "status": "success",
                "status_code": status_code,
                "local_pack_available": True,
                "maps_visible_top3": maps_visible,
                "top3_competitors": top3,
            }
        except Exception as e:
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.exception("SerpAPI error elapsed_ms=%s", elapsed_ms)
            return {
                "status": "error",
                "status_code": None,
                "error": str(e),
                "local_pack_available": False,
                "maps_visible_top3": None,
                "top3_competitors": [],
            }

    def _check_target_in_top3(
        self,
        top3: List[Dict],
        target_name: str,
        target_address: Optional[str],
    ) -> Optional[bool]:
        """True if target in top 3 (token_set_ratio >= 80 and address match when available)."""
        target_lower = target_name.lower()
        for c in top3:
            name = (c.get("name") or "").lower()
            if fuzz.token_set_ratio(target_lower, name) >= 80:
                if target_address:
                    addr = (c.get("address") or "").lower()
                    taddr = target_address.lower()
                    if taddr in addr or addr in taddr:
                        return True
                else:
                    if fuzz.token_set_ratio(target_lower, name) >= 90:
                        return True
        return False
