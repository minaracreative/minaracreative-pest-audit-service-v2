"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.constants import ALLOWED_SERVICES


class AuditRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=50)
    website_url: str
    city: str = Field(..., min_length=2, max_length=50)
    primary_service: str
    local_pack_position: str = Field(..., pattern="^(1|2|3|not_visible|unknown)$")

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        """City: 2–50 chars, letters, spaces, hyphens."""
        if not all(c.isalpha() or c.isspace() or c == "-" for c in v):
            raise ValueError("City must contain only letters, spaces, and hyphens")
        return v

    @field_validator("primary_service")
    @classmethod
    def validate_service(cls, v: str) -> str:
        if v not in ALLOWED_SERVICES:
            raise ValueError(f"primary_service must be one of: {', '.join(ALLOWED_SERVICES)}")
        return v


class AuditInputs(BaseModel):
    """Inputs slice returned in audit response (website_url as string)."""

    business_name: str
    website_url: str
    city: str
    primary_service: str
    local_pack_position: str

class ResolvedBusiness(BaseModel):
    """Resolved business from Google Place."""

    place_id: Optional[str] = None
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    google_maps_url: Optional[str] = None
    resolution_status: Literal["found", "not_found", "error"]


class Competitor(BaseModel):
    """Local pack competitor."""

    rank: int
    name: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    address: Optional[str] = None


class LocalVisibility(BaseModel):
    """Local pack visibility."""

    maps_visible_top3: Optional[bool] = None
    top3_competitors: List[Competitor] = Field(default_factory=list)
    local_pack_available: bool
    user_reported_position: Optional[str] = None

class Reviews(BaseModel):
    """Review data."""

    total_reviews: Optional[int] = None
    rating: Optional[float] = None
    last_review_date: Optional[str] = None
    review_data_status: Literal["available", "insufficient_api_data"]


class CallCapture(BaseModel):
    """Call capture assessment."""

    phone_found: bool
    phones_detected: List[str] = Field(default_factory=list)
    phone_consistency: Literal["consistent", "inconsistent", "not_found"]
    form_detected: bool
    call_tracking_detected: Literal["true", "false", "unknown"]
    call_tracking_vendor: Optional[str] = None
    scheduling_widget_detected: bool
    pages_scanned: int = Field(..., ge=0, le=3)
    capture_assessment_status: Literal["completed", "partial_failure", "no_data"]


class AfterHoursRisk(BaseModel):
    """After-hours capture risk."""

    risk_level: Literal["low", "medium", "high", "unknown"]
    reason: str


class SelectedConclusion(BaseModel):
    """Selected conclusion."""

    conclusion: str
    reason: str


class MissedOpportunity(BaseModel):
    """Missed opportunity template output."""

    opportunity_code: str
    opportunity_description: str
    reason: str


class APICall(BaseModel):
    """Debug API call record."""

    service: Literal["google_places", "serpapi", "website_scan"]
    endpoint: str
    status_code: Optional[int] = None
    timestamp: str
    error: Optional[str] = None


class DebugInfo(BaseModel):
    """Debug section."""

    cache_hit: bool
    audit_duration_ms: int
    api_calls: List[APICall] = Field(default_factory=list)


class SalesSafeSummary(BaseModel):
    """Sales-safe summary."""

    headline: str
    key_fact: str


class AuditResponse(BaseModel):
    """Full audit response."""

    audit_id: str
    timestamp: str
    inputs: AuditInputs
    resolved_business: ResolvedBusiness
    local_visibility: LocalVisibility
    reviews: Reviews
    call_capture: CallCapture
    after_hours_risk: AfterHoursRisk
    selected_conclusion: SelectedConclusion
    missed_opportunity: MissedOpportunity
    debug: DebugInfo
    sales_safe_summary: SalesSafeSummary


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str
    timestamp: str


class VersionResponse(BaseModel):
    """GET /version response."""

    version: str
