"""Constants used throughout the application."""
from typing import Dict

ALLOWED_SERVICES = [
    "pest_control",
    "termite_treatment",
    "rodent_control",
    "mosquito_control",
    "wildlife_removal",
    "general_pest_management",
    "fumigation",
    "bed_bug_treatment",
    "ant_control",
    "cockroach_control",
]

SERVICE_READABLE: Dict[str, str] = {
    "pest_control": "pest control",
    "termite_treatment": "termite treatment",
    "rodent_control": "rodent control",
    "mosquito_control": "mosquito control",
    "wildlife_removal": "wildlife removal",
    "general_pest_management": "general pest management",
    "fumigation": "fumigation",
    "bed_bug_treatment": "bed bug treatment",
    "ant_control": "ant control",
    "cockroach_control": "cockroach control",
}

CALL_TRACKING_VENDORS = [
    "callrail",
    "calltrackingmetrics",
    "whatconverts",
    "invoca",
    "ringba",
]

FORM_VENDORS = [
    "gravity-forms",
    "gravityforms",
    "formspree",
    "typeform",
    "hubspot",
]

SCHEDULING_WIDGETS = [
    "calendly",
    "acuity",
    "hubspot scheduling",
    "booking.com",
]

# Missed opportunity templates per spec (exact placeholders)
CONCLUSION_TEMPLATES = {
    "Invisible for high-value service": "You're not showing up for {service} in {city}. Competitors in the top 3 local pack are getting calls you're missing.",
    "Losing calls due to capture gaps": "You only have a phone number for lead capture. Without a contact form or scheduling link, you're losing calls after hours.",
    "Outpaced by competitors in review activity": "{competitor} has {comp_reviews} reviews vs. your {total_reviews}. Review gap signals lower visibility in local search.",
    "Not discoverable to high-intent buyers": "Your local search presence isn't strong enough to appear where buyers are looking. This limits booked jobs.",
}
