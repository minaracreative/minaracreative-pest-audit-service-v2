"""Integration tests: mock Google/SerpAPI, end-to-end audit, debug and status codes."""
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure env before app.main loads config
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-key")
os.environ.setdefault("SERPAPI_API_KEY", "test-key")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("CACHE_TTL_HOURS", "24")

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def full_audit_response():
    """Full audit response matching AuditResponse schema."""
    return {
        "audit_id": "test-uuid-1234",
        "timestamp": "2024-01-15T10:00:00Z",
        "inputs": {
            "business_name": "ABC Pest Control",
            "website_url": "https://abcpestcontrol.com",
            "city": "Austin",
            "primary_service": "pest_control",
        },
        "resolved_business": {
            "place_id": "ChIJTest123",
            "name": "ABC Pest Control",
            "address": "123 Main St, Austin, TX 78701",
            "phone": "(512) 555-1234",
            "website": "https://abcpestcontrol.com",
            "rating": 4.5,
            "total_reviews": 150,
            "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJTest123",
            "resolution_status": "found",
        },
        "local_visibility": {
            "maps_visible_top3": False,
            "top3_competitors": [
                {"rank": 1, "name": "XYZ Pest", "rating": 4.8, "review_count": 300, "address": "456 Oak Ave"},
                {"rank": 2, "name": "DEF Pest", "rating": 4.6, "review_count": 250, "address": "789 Pine St"},
                {"rank": 3, "name": "GHI Pest", "rating": 4.4, "review_count": 200, "address": "321 Elm"},
            ],
            "local_pack_available": True,
        },
        "reviews": {
            "total_reviews": 150,
            "rating": 4.5,
            "last_review_date": "2024-01-15T10:30:00Z",
            "review_data_status": "available",
        },
        "call_capture": {
            "phone_found": True,
            "phones_detected": ["(512) 555-1234"],
            "phone_consistency": "consistent",
            "form_detected": False,
            "call_tracking_detected": "false",
            "call_tracking_vendor": None,
            "scheduling_widget_detected": False,
            "pages_scanned": 3,
            "capture_assessment_status": "completed",
        },
        "after_hours_risk": {"risk_level": "medium", "reason": "phone_only"},
        "selected_conclusion": {
            "conclusion": "Invisible for high-value service",
            "reason": "not_in_top3_local_pack",
        },
        "missed_opportunity": {
            "opportunity_code": "invisible_high_value",
            "opportunity_description": "You're not showing up for pest control in Austin. Competitors in the top 3 local pack are getting calls you're missing.",
            "reason": "not_in_top3_local_pack",
        },
        "debug": {
            "cache_hit": False,
            "audit_duration_ms": 2000,
            "api_calls": [
                {"service": "google_places", "endpoint": "textsearch", "status_code": 200, "timestamp": "2024-01-15T10:00:00Z", "error": None},
                {"service": "serpapi", "endpoint": "local_pack", "status_code": 200, "timestamp": "2024-01-15T10:00:01Z", "error": None},
                {"service": "google_places", "endpoint": "details", "status_code": 200, "timestamp": "2024-01-15T10:00:02Z", "error": None},
                {"service": "website_scan", "endpoint": "abcpestcontrol.com", "status_code": None, "timestamp": "2024-01-15T10:00:03Z", "error": None},
            ],
        },
        "sales_safe_summary": {
            "headline": "Invisible for high-value service",
            "key_fact": "Not appearing in top 3 local pack results",
        },
    }


@patch("app.main.cache")
@patch("app.main.audit_runner")
def test_audit_endpoint_success(mock_runner, mock_cache, client, full_audit_response):
    """End-to-end: POST /audit returns 200 and full JSON; debug.api_calls and status codes present."""
    mock_cache.get.return_value = None
    mock_cache.generate_key.return_value = "test_key"
    mock_runner.run_audit = AsyncMock(return_value=full_audit_response)

    response = client.post(
        "/audit",
        json={
            "business_name": "ABC Pest Control",
            "website_url": "https://abcpestcontrol.com",
            "city": "Austin",
            "primary_service": "pest_control",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["audit_id"] == "test-uuid-1234"
    assert data["resolved_business"]["name"] == "ABC Pest Control"
    assert data["selected_conclusion"]["conclusion"] == "Invisible for high-value service"
    assert "debug" in data
    assert "api_calls" in data["debug"]
    assert data["debug"]["audit_duration_ms"] == 2000
    assert mock_cache.set.called


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_version_endpoint(client):
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"


def test_audit_validation_too_short(client):
    """Invalid input returns 422 (validation error)."""
    response = client.post(
        "/audit",
        json={
            "business_name": "A",
            "website_url": "https://example.com",
            "city": "Austin",
            "primary_service": "pest_control",
        },
    )
    assert response.status_code == 422


def test_audit_validation_invalid_service(client):
    response = client.post(
        "/audit",
        json={
            "business_name": "AB",
            "website_url": "https://example.com",
            "city": "Austin",
            "primary_service": "invalid_service",
        },
    )
    assert response.status_code == 422


@patch("app.main.cache")
@patch("app.main.audit_runner")
def test_audit_business_not_found_returns_400(mock_runner, mock_cache, client, full_audit_response):
    """When resolution_status is not_found, endpoint returns HTTP 400 business_not_found."""
    full_audit_response["resolved_business"]["resolution_status"] = "not_found"
    mock_cache.get.return_value = None
    mock_cache.generate_key.return_value = "k"
    mock_runner.run_audit = AsyncMock(return_value=full_audit_response)

    response = client.post(
        "/audit",
        json={
            "business_name": "Nonexistent Co",
            "website_url": "https://nonexistent.com",
            "city": "Austin",
            "primary_service": "pest_control",
        },
    )
    assert response.status_code == 400
    assert response.json().get("error") == "business_not_found"
