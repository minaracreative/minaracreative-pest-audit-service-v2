"""Deterministic rule-based logic: after-hours risk, conclusion selection, missed opportunity."""
from typing import Any, Dict, List, Optional
from app.utils.logging_config import logger
from app.utils.constants import SERVICE_READABLE


def assess_after_hours_risk(
    pages_scanned: int,
    phone_found: bool,
    form_detected: bool,
    scheduling_widget_detected: bool,
) -> Dict[str, str]:
    """
    After-Hours Capture Risk. Apply in order, stop at first match.
    Returns risk_level and reason.
    """
    if pages_scanned == 0:
        return {"risk_level": "unknown", "reason": "unable_to_scan_website"}
    if not phone_found and not form_detected and not scheduling_widget_detected:
        return {"risk_level": "high", "reason": "no_capture_mechanisms"}
    if phone_found and (form_detected or scheduling_widget_detected):
        return {"risk_level": "low", "reason": "multiple_capture_paths"}
    if phone_found and not form_detected and not scheduling_widget_detected:
        return {"risk_level": "medium", "reason": "phone_only"}
    return {"risk_level": "low", "reason": "has_alternative_capture"}

def select_conclusion(audit_data):
    """
    Deterministic conclusion based on user's reported Maps position + review comparison.
    """
    maps_visible_top3 = audit_data.get('local_visibility', {}).get('maps_visible_top3')
    after_hours_risk = audit_data.get('after_hours_risk', {}).get('risk_level')
    total_reviews = audit_data.get('reviews', {}).get('total_reviews')
    top3_competitors = audit_data.get('local_visibility', {}).get('top3_competitors', [])

    logger.info("Conclusion logic: visible=%s after_hours=%s reviews=%s competitors=%s", 
                maps_visible_top3, after_hours_risk, total_reviews, len(top3_competitors))

    # If in top 3, check for issues
    if maps_visible_top3 == True:
        # Check if outpaced by competitors
        if top3_competitors and len(top3_competitors) > 0:
            top_competitor = top3_competitors[0]
            competitor_reviews = top_competitor.get('review_count', 0)

            if competitor_reviews and total_reviews and competitor_reviews >= (2 * total_reviews):
                return {
                    "conclusion": "Outpaced by competitors in review activity",
                    "reason": "significant_review_gap"
                }

        # Check if losing calls
        if after_hours_risk == "high":
            return {
                "conclusion": "Losing calls due to capture gaps",
                "reason": "no_after_hours_capture"
            }

        # Visible in top 3, no major issues
        return {
            "conclusion": "You're visible and well-positioned locally",
            "reason": "top_3_position_with_strong_capture"
        }

    # NOT in top 3
    if maps_visible_top3 == False:
        # Still check for call capture issues
        if after_hours_risk == "high":
            return {
                "conclusion": "Losing calls due to capture gaps",
                "reason": "no_after_hours_capture"
            }

        return {
            "conclusion": "Invisible for high-value service",
            "reason": "not_in_top3_local_pack"
        }

    # Default (unknown position)
    return {
        "conclusion": "Not discoverable to high-intent buyers",
        "reason": "default"
    }

def generate_missed_opportunity(
    conclusion: str,
    primary_service: str,
    city: str,
    total_reviews: Optional[int],
    top3_competitors: List[Dict[str, Any]],
    selected_reason: str,
) -> Dict[str, str]:
    """One template per conclusion."""
    service_readable = SERVICE_READABLE.get(primary_service, primary_service.replace("_", " "))

    templates = {
        "Invisible for high-value service": f"You're not showing up for {service_readable} in {city}. Competitors in the local pack are getting calls you're missing.",
        "Losing calls due to capture gaps": "You only have a phone number for lead capture. Without a contact form or scheduling link, you're losing calls after hours.",
        "Outpaced by competitors in review activity": f"Top competitor has {top3_competitors[0].get('review_count', 0) if top3_competitors else 0} reviews vs. your {total_reviews or 0}. Review gap signals lower visibility in local search.",
        "Not discoverable to high-intent buyers": "Your local search presence isn't strong enough to appear where buyers are looking. This limits booked jobs.",
        "You're visible and well-positioned locally": f"You're visible and ranked well for {service_readable} in {city}. Focus on maintaining review momentum and consistent customer engagement.",
    }

    codes = {
        "Invisible for high-value service": "invisible_high_value",
        "Losing calls due to capture gaps": "capture_gaps",
        "Outpaced by competitors in review activity": "review_gap",
        "Not discoverable to high-intent buyers": "not_discoverable",
        "You're visible and well-positioned locally": "well_positioned",
    }

    opportunity_code = codes.get(conclusion, "not_discoverable")
    opportunity_description = templates.get(conclusion, templates["Not discoverable to high-intent buyers"])

    return {
        "opportunity_code": opportunity_code,
        "opportunity_description": opportunity_description,
        "reason": selected_reason,
    }

def generate_sales_safe_summary(
    conclusion: str,
    resolved_business: Dict[str, Any],
    local_visibility: Dict[str, Any],
    after_hours_risk: Dict[str, str],
) -> Dict[str, str]:
    """headline = conclusion; key_fact = single strongest piece of evidence."""
    headline = conclusion
    if conclusion == "Invisible for high-value service":
        key_fact = "Not appearing in top 3 local pack results"
    elif conclusion == "Losing calls due to capture gaps":
        key_fact = f"After-hours risk: {after_hours_risk.get('risk_level', 'unknown')}"
    elif conclusion == "Outpaced by competitors in review activity":
        comps = local_visibility.get("top3_competitors") or []
        if comps:
            key_fact = f"Top competitor has {comps[0].get('review_count', 0)} reviews"
        else:
            key_fact = "Significant review gap with competitors"
    else:
        key_fact = "Limited local search visibility"
    return {"headline": headline, "key_fact": key_fact}
