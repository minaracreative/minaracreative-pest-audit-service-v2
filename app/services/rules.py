"""Deterministic rule-based logic: after-hours risk, conclusion selection, missed opportunity."""
from typing import Any, Dict, List, Optional

from app.utils.constants import CONCLUSION_TEMPLATES, SERVICE_READABLE


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
    Deterministic conclusion selection based on audit signals.
    Rules applied in order - stops at first match.
    """
    maps_visible_top3 = audit_data.get('local_visibility', {}).get('maps_visible_top3')
    after_hours_risk = audit_data.get('after_hours_risk', {}).get('risk_level')
    total_reviews = audit_data.get('reviews', {}).get('total_reviews')
    top3_competitors = audit_data.get('local_visibility', {}).get('top3_competitors', [])

    # Rule 1: If maps visible in top 3, check other conditions first
    if maps_visible_top3 == True:
        # Rule 1a: Check if outpaced by competitors
        if top3_competitors and len(top3_competitors) > 0:
            competitor_reviews = top3_competitors[0].get('review_count', 0)
            if competitor_reviews and total_reviews and competitor_reviews >= (2 * total_reviews):
                return {
                    "conclusion": "Outpaced by competitors in review activity",
                    "reason": "significant_review_gap"
                }

        # Rule 1b: Check if losing calls
        if after_hours_risk == "high":
            return {
                "conclusion": "Losing calls due to capture gaps",
                "reason": "no_after_hours_capture"
            }

        # Rule 1c: If visible in top 3 but no other issues
        return {
            "conclusion": "Not discoverable to high-intent buyers",
            "reason": "default"
        }

    # Rule 2: If NOT visible in top 3
    elif maps_visible_top3 == False:
        return {
            "conclusion": "Invisible for high-value service",
            "reason": "not_in_top3_local_pack"
        }

    # Rule 3: If local pack data unavailable
    elif maps_visible_top3 == None:
        # Still check call capture risk
        if after_hours_risk == "high":
            return {
                "conclusion": "Losing calls due to capture gaps",
                "reason": "no_after_hours_capture"
            }

        return {
            "conclusion": "Not discoverable to high-intent buyers",
            "reason": "local_pack_not_available"
        }

    # Default fallback
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
    """
    One template per conclusion. Placeholders per spec:
    - Invisible: {service}, {city}
    - Outpaced: {competitor}, {comp_reviews}, {total_reviews}
    - Others: literal.
    """
    service_readable = SERVICE_READABLE.get(primary_service, primary_service.replace("_", " "))
    codes = {
        "Invisible for high-value service": "invisible_high_value",
        "Losing calls due to capture gaps": "capture_gaps",
        "Outpaced by competitors in review activity": "review_gap",
        "Not discoverable to high-intent buyers": "not_discoverable",
    }
    opportunity_code = codes.get(conclusion, "not_discoverable")
    template = CONCLUSION_TEMPLATES.get(
        conclusion,
        CONCLUSION_TEMPLATES["Not discoverable to high-intent buyers"],
    )
    if conclusion == "Invisible for high-value service":
        opportunity_description = template.format(service=service_readable, city=city)
    elif conclusion == "Outpaced by competitors in review activity":
        if top3_competitors:
            comp_name = top3_competitors[0].get("name") or "Competitor"
            comp_reviews = top3_competitors[0].get("review_count") or 0
        else:
            comp_name = "Competitor"
            comp_reviews = 0
        opportunity_description = template.format(
            competitor=comp_name,
            comp_reviews=comp_reviews,
            total_reviews=total_reviews or 0,
        )
    else:
        opportunity_description = template
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
