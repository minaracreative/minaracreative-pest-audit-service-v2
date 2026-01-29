"""Orchestrates audit steps 1–5 in fixed order. Uses time.time() only for timing."""
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.providers.google_places import GooglePlacesProvider
from app.providers.site_scanner import SiteScanner
from app.services.rules import (
    assess_after_hours_risk,
    generate_missed_opportunity,
    generate_sales_safe_summary,
    select_conclusion,
)
from app.utils.constants import SERVICE_READABLE
from app.utils.logging_config import logger


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditRunner:
    """Runs audit in spec order: 1 resolve, 2 local pack, 3 reviews, 4 call capture, 5 after-hours risk."""

    def __init__(self) -> None:
        self.google_places = GooglePlacesProvider()
        self.site_scanner = SiteScanner()
        self.api_calls: List[Dict[str, Any]] = []

    def _log_api(
        self,
        service: str,
        endpoint: str,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        self.api_calls.append({
            "service": service,
            "endpoint": endpoint,
            "status_code": status_code,
            "timestamp": _utc_iso(),
            "error": error,
        })

    async def run_audit(
        self,
        business_name: str,
        website_url: Any,
        city: str,
        primary_service: str,
    ) -> Dict[str, Any]:
        """Run full audit. website_url can be HttpUrl; we pass str(website_url) to stdlib/providers."""
        self.api_calls = []
        start_time = time.time()
        audit_id = str(uuid.uuid4())
        timestamp = _utc_iso()
        website_str = str(website_url)

        logger.info("Starting audit %s for %s in %s", audit_id, business_name, city)

        # Step 1: Resolve Business to Google Place
        place_result = await self.google_places.text_search(
            business_name, city, website_str
        )
        self._log_api(
            "google_places",
            "textsearch",
            place_result.get("status_code"),
            place_result.get("error"),
        )
        if place_result.get("status") != "success" or not place_result.get("result"):
            return self._build_error_response(
                audit_id, timestamp, business_name, website_str, city, primary_service,
                "business_not_found", int((time.time() - start_time) * 1000),
            )

        resolved = place_result["result"]
        place_id = resolved.get("place_id")

        # Step 2: Review Count and Last Activity (Place Details)
        details_result = await self.google_places.get_place_details(place_id)
        self._log_api(
            "google_places",
            "details",
            details_result.get("status_code"),
            details_result.get("error"),
        )

        location = None
        if details_result.get("status") == "success" and details_result.get("result"):
            d = details_result["result"]
            resolved["phone"] = d.get("phone") or resolved.get("phone")
            resolved["website"] = d.get("website") or resolved.get("website")
            resolved["rating"] = d.get("rating") if d.get("rating") is not None else resolved.get("rating")
            resolved["total_reviews"] = d.get("total_reviews") if d.get("total_reviews") is not None else resolved.get("total_reviews")
            resolved["last_review_date"] = d.get("last_review_date")
            location = d.get("location")  # Get location from Place Details, not Text Search

        reviews_data: Dict[str, Any] = {
            "total_reviews": resolved.get("total_reviews"),
            "rating": resolved.get("rating"),
            "last_review_date": resolved.get("last_review_date"),
            "review_data_status": "available" if resolved.get("total_reviews") is not None else "insufficient_api_data",
        }

        # Step 3: Local Pack Visibility via Google Places Nearby Search
        # Get coordinates from Place Details result (not from Text Search)
        location = None
        if details_result.get("status") == "success" and details_result.get("result"):
            d = details_result["result"]
            location = d.get("location")  # This should come from Place Details
            
        if not location:
            location = {"lat": 0, "lng": 0}  # Fallback; Google will still search

        local_pack_result = await self.google_places.nearby_search(
            latitude=location.get("lat", 0),
            longitude=location.get("lng", 0),
            service_type=primary_service,
            radius=5000,  # 5km radius
        )
        self._log_api(
            "google_places",
            "nearby_search",
            local_pack_result.get("status_code"),
            local_pack_result.get("error"),
        )

        # Check if target business is in top 3
        maps_visible_top3 = False
        top3_competitors = local_pack_result.get("top3_competitors", [])

        if top3_competitors and len(top3_competitors) > 0:
            top3_names = [c.get("name", "").lower() for c in top3_competitors]
            target_name = resolved.get("name", "").lower()

            logger.info("Matching target=%s against top3=%s", target_name, top3_names)

            # Fuzzy match target against top 3
            from rapidfuzz import fuzz
            for top_name in top3_names:
                ratio = fuzz.token_set_ratio(target_name, top_name)
                logger.info("Fuzzy match: %s vs %s = %s", target_name, top_name, ratio)
                if ratio >= 80:
                    maps_visible_top3 = True
                    break

        # Update local_pack_result with visibility check
        local_pack_result["maps_visible_top3"] = maps_visible_top3


        # Step 4: Call Capture Assessment (homepage, /contact, /services)
        parsed = urlparse(website_str)
        domain = (parsed.netloc or "").replace("www.", "")
        service_slug = primary_service.replace("_", "-")
        capture_result = await self.site_scanner.scan_website(website_str, service_slug)
        self._log_api("website_scan", domain, None, None)

        # Step 5: After-Hours Capture Risk
        after_hours = assess_after_hours_risk(
            capture_result["pages_scanned"],
            capture_result["phone_found"],
            capture_result["form_detected"],
            capture_result["scheduling_widget_detected"],
        )
 
        # Build audit data for conclusion selection
        audit_data_for_conclusion = {
            'local_visibility': {
                'maps_visible_top3': local_pack_result.get('maps_visible_top3'),
                'top3_competitors': local_pack_result.get('top3_competitors', [])
            },
            'after_hours_risk': after_hours,
            'reviews': reviews_data
        }

        conclusion_data = select_conclusion(audit_data_for_conclusion)


        missed = generate_missed_opportunity(
            conclusion_data["conclusion"],
            primary_service,
            city,
            reviews_data["total_reviews"],
            local_pack_result.get("top3_competitors") or [],
            conclusion_data["reason"],
        )
        sales_summary = generate_sales_safe_summary(
            conclusion_data["conclusion"],
            resolved,
            {"top3_competitors": local_pack_result.get("top3_competitors") or []},
            after_hours,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        response = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "inputs": {
                "business_name": business_name,
                "website_url": website_str,
                "city": city,
                "primary_service": primary_service,
            },
            "resolved_business": {
                "place_id": resolved.get("place_id"),
                "name": resolved.get("name", business_name),
                "address": resolved.get("address", ""),
                "phone": resolved.get("phone"),
                "website": resolved.get("website"),
                "rating": resolved.get("rating"),
                "total_reviews": resolved.get("total_reviews"),
                "google_maps_url": resolved.get("google_maps_url"),
                "resolution_status": "found",
            },
            "local_visibility": {
                "maps_visible_top3": local_pack_result.get("maps_visible_top3"),
                "top3_competitors": local_pack_result.get("top3_competitors", []),
                "local_pack_available": local_pack_result.get("local_pack_available", False),
            },
            "reviews": reviews_data,
            "call_capture": capture_result,
            "after_hours_risk": after_hours,
            "selected_conclusion": conclusion_data,
            "missed_opportunity": missed,
            "debug": {
                "cache_hit": False,
                "audit_duration_ms": elapsed_ms,
                "api_calls": self.api_calls,
            },
            "sales_safe_summary": sales_summary,
        }
        logger.info("Completed audit %s in %s ms", audit_id, elapsed_ms)
        return response

    def _build_error_response(
        self,
        audit_id: str,
        timestamp: str,
        business_name: str,
        website_url: str,
        city: str,
        primary_service: str,
        error_reason: str,
        duration_ms: int,
    ) -> Dict[str, Any]:
        return {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "inputs": {
                "business_name": business_name,
                "website_url": website_url,
                "city": city,
                "primary_service": primary_service,
            },
            "resolved_business": {
                "place_id": None,
                "name": business_name,
                "address": "",
                "phone": None,
                "website": None,
                "rating": None,
                "total_reviews": None,
                "google_maps_url": None,
                "resolution_status": "not_found",
            },
            "local_visibility": {
                "maps_visible_top3": None,
                "top3_competitors": [],
                "local_pack_available": False,
            },
            "reviews": {
                "total_reviews": None,
                "rating": None,
                "last_review_date": None,
                "review_data_status": "insufficient_api_data",
            },
            "call_capture": {
                "phone_found": False,
                "phones_detected": [],
                "phone_consistency": "not_found",
                "form_detected": False,
                "call_tracking_detected": "unknown",
                "call_tracking_vendor": None,
                "scheduling_widget_detected": False,
                "pages_scanned": 0,
                "capture_assessment_status": "no_data",
            },
            "after_hours_risk": {"risk_level": "unknown", "reason": error_reason},
            "selected_conclusion": {
                "conclusion": "Not discoverable to high-intent buyers",
                "reason": error_reason,
            },
            "missed_opportunity": {
                "opportunity_code": "not_discoverable",
                "opportunity_description": "Your local search presence isn't strong enough to appear where buyers are looking. This limits booked jobs.",
                "reason": error_reason,
            },
            "debug": {
                "cache_hit": False,
                "audit_duration_ms": duration_ms,
                "api_calls": self.api_calls,
            },
            "sales_safe_summary": {
                "headline": "Not discoverable to high-intent buyers",
                "key_fact": "Business could not be resolved",
            },
        }
