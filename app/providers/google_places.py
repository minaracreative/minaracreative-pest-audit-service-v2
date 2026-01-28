"""Google Places API provider. Uses time.time() for timing only."""
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from rapidfuzz import fuzz

from app.config import settings
from app.utils.logging_config import logger


class GooglePlacesProvider:
    """Provider for Google Places Text Search and Place Details."""

    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self) -> None:
        self.api_key = settings.google_maps_api_key

    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        service_type: str,
        radius: int = 5000,
    ) -> Dict[str, Any]:
        """
        Search for nearby businesses using Google Places Nearby Search API.
        Returns top 3 competitors by relevance.
        """
        start_time = time.time()

        # Map service types to Google Places types
        service_type_map = {
            "pest_control": "pest_control",
            "termite_treatment": "pest_control",
            "rodent_control": "pest_control",
            "mosquito_control": "pest_control",
            "wildlife_removal": "pest_control",
            "general_pest_management": "pest_control",
            "fumigation": "pest_control",
            "bed_bug_treatment": "pest_control",
            "ant_control": "pest_control",
            "cockroach_control": "pest_control",
        }

        place_type = service_type_map.get(service_type, "pest_control")

        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{latitude},{longitude}",
            "radius": radius,
            "type": place_type,
            "key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                elapsed_ms = int((time.time() - start_time) * 1000)

                if response.status_code != 200:
                    return {
                        "status": "error",
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}",
                        "maps_visible_top3": None,
                        "top3_competitors": [],
                        "local_pack_available": False,
                    }

                data = response.json()
                results = data.get("results", [])

                # Extract top 3
                top3 = []
                for i, result in enumerate(results[:3]):
                    top3.append({
                        "rank": i + 1,
                        "name": result.get("name"),
                        "rating": result.get("rating"),
                        "review_count": result.get("user_ratings_total", 0),
                        "address": result.get("vicinity"),
                    })

                return {
                    "status": "success",
                    "status_code": 200,
                    "error": None,
                    "maps_visible_top3": len(results) > 0,
                    "top3_competitors": top3,
                    "local_pack_available": len(results) > 0,
                }

    except Exception as e:
        return {
            "status": "error",
            "status_code": None,
            "error": str(e),
            "maps_visible_top3": None,
            "top3_competitors": [],
            "local_pack_available": False,
        }


    async def text_search(
        self, business_name: str, city: str, website_url: str
    ) -> Dict[str, Any]:
        """
        Call Google Places Text Search with business_name + city.
        Score by (1) website domain match, (2) name similarity rapidfuzz, (3) city match.
        Return place_id, name, address, phone, website, rating, total_reviews, google_maps_url.
        """
        query = f"{business_name} {city}"
        url = f"{self.BASE_URL}/textsearch/json"
        params = {"query": query, "key": self.api_key}
        # Convert URL to string before any stdlib use
        website_str = str(website_url) if hasattr(website_url, "__str__") else website_url

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
            status_code = response.status_code
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                "Google Places Text Search - timestamp=%s status_code=%s result_count=%s elapsed_ms=%s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
                status_code,
                len(response.json().get("results", [])) if status_code == 200 else 0,
                elapsed_ms,
            )
            if status_code != 200:
                return {
                    "status": "error",
                    "status_code": status_code,
                    "error": f"HTTP {status_code}",
                    "result": None,
                }
            data = response.json()
            results = data.get("results", [])
            best_match = self._select_best_match(results, business_name, city, website_str)
            return {
                "status": "success",
                "status_code": status_code,
                "result": best_match,
                "result_count": len(results),
            }
        except Exception as e:
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.exception("Google Places Text Search error elapsed_ms=%s", elapsed_ms)
            return {
                "status": "error",
                "status_code": None,
                "error": str(e),
                "result": None,
            }

    def _select_best_match(
        self,
        results: List[Dict],
        business_name: str,
        city: str,
        website_url_str: str,
    ) -> Optional[Dict[str, Any]]:
        """Score by website domain match, name similarity, city match."""
        if not results:
            return None
        try:
            parsed = urlparse(website_url_str)
            target_domain = (parsed.netloc or "").lower().replace("www.", "")
        except Exception:
            target_domain = ""
        scored: List[tuple[float, Dict]] = []
        for r in results:
            score = 0.0
            if target_domain:
                res_web = r.get("website")
                if res_web:
                    try:
                        d = urlparse(str(res_web)).netloc.lower().replace("www.", "")
                        if d == target_domain:
                            score += 1000.0
                    except Exception:
                        pass
            name_sim = fuzz.token_set_ratio(business_name.lower(), (r.get("name") or "").lower())
            score += float(name_sim)
            addr = (r.get("formatted_address") or "").lower()
            if city.lower() in addr:
                score += 50.0
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] > 0:
            return self._format_place_result(scored[0][1])
        return None

    def _format_place_result(self, result: Dict) -> Dict[str, Any]:
        place_id = result.get("place_id")
        name = result.get("name") or ""
        address = result.get("formatted_address") or ""
        rating = result.get("rating")
        total = result.get("user_ratings_total")
        google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None
        return {
            "place_id": place_id,
            "name": name,
            "address": address,
            "phone": None,
            "website": result.get("website"),
            "rating": float(rating) if rating is not None else None,
            "total_reviews": int(total) if total is not None else None,
            "google_maps_url": google_maps_url,
        }

    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """
        Call Google Places Details. Return total_reviews, rating, last_review_date (ISO).
        Do not compute velocity.
        """
        url = f"{self.BASE_URL}/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,reviews",
            "key": self.api_key,
        }
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
            status_code = response.status_code
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                "Google Places Details - timestamp=%s status_code=%s elapsed_ms=%s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
                status_code,
                elapsed_ms,
            )
            if status_code != 200:
                return {
                    "status": "error",
                    "status_code": status_code,
                    "error": f"HTTP {status_code}",
                    "result": None,
                }
            data = response.json()
            result = data.get("result")
            if not result:
                return {
                    "status": "error",
                    "status_code": status_code,
                    "error": "No result in response",
                    "result": None,
                }
            last_review_date = None
            reviews = result.get("reviews") or []
            if reviews:
                sorted_reviews = sorted(reviews, key=lambda x: x.get("time", 0), reverse=True)
                if sorted_reviews and sorted_reviews[0].get("time"):
                    ts = sorted_reviews[0]["time"]
                    last_review_date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
            return {
                "status": "success",
                "status_code": status_code,
                "result": {
                    "phone": result.get("formatted_phone_number"),
                    "website": result.get("website"),
                    "rating": float(result["rating"]) if result.get("rating") is not None else None,
                    "total_reviews": int(result["user_ratings_total"]) if result.get("user_ratings_total") is not None else None,
                    "last_review_date": last_review_date,
                },
            }
        except Exception as e:
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.exception("Google Places Details error elapsed_ms=%s", elapsed_ms)
            return {
                "status": "error",
                "status_code": None,
                "error": str(e),
                "result": None,
            }
