"""Google Maps Local Pack via SerpAPI."""
import time
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings
from app.utils.logging_config import logger


class GoogleMapsSearchProvider:
    """Use SerpAPI to get actual Google Maps Local Pack results."""

    def __init__(self) -> None:
        self.api_key = settings.serpapi_api_key

    async def local_pack_search(
        self, service: str, city: str
    ) -> Dict[str, Any]:
        """
        Query Google Maps Local Pack via SerpAPI.
        Returns top 3 businesses in actual Maps ranking order.
        """
        query = f"{service} {city}"
        url = "https://api.serpapi.com/search"
        params = {
            "q": query,
            "engine": "google_maps",
            "api_key": self.api_key,
            "num": 3,
        }
 
        logger.info("Using SerpAPI key: %s...", self.api_key[:10] if self.api_key else "MISSING")
        logger.info("SerpAPI request: url=%s query=%s", url, query)
        
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
            status_code = response.status_code
            elapsed_ms = int((time.time() - t0) * 1000)

            logger.info(
                "SerpAPI Google Maps - timestamp=%s status_code=%s elapsed_ms=%s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
                status_code,
                elapsed_ms,
            )

            if status_code != 200:
                return {
                    "status": "error",
                    "status_code": status_code,
                    "error": f"HTTP {status_code}",
                    "results": [],
                    "local_pack_available": False,
                }

            data = response.json()
            results = data.get("local_results", [])

            # Extract top 3 from actual Maps results
            top3 = []
            for i, result in enumerate(results[:3]):
                top3.append({
                    "rank": i + 1,
                    "name": result.get("title"),
                    "rating": result.get("rating"),
                    "review_count": result.get("review_count", 0),
                    "address": result.get("address"),
                    "type": result.get("type"),
                })
                logger.info(
                    "Local Pack result[%s] rank=%s name=%s rating=%s reviews=%s",
                    i,
                    i + 1,
                    result.get("title"),
                    result.get("rating"),
                    result.get("review_count", 0),
                )

            return {
                "status": "success",
                "status_code": 200,
                "error": None,
                "results": top3,
                "local_pack_available": len(results) > 0,
            }

        except Exception as e:
            logger.exception("SerpAPI Google Maps error: %s", str(e))
            return {
                "status": "error",
                "status_code": None,
                "error": str(e),
                "results": [],
                "local_pack_available": False,
            }
