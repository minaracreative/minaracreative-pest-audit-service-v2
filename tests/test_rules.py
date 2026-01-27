"""Tests for rule-based logic: determinism, each rule, boundary cases."""
import pytest

from app.services.rules import (
    assess_after_hours_risk,
    select_conclusion,
    generate_missed_opportunity,
    generate_sales_safe_summary,
)


class TestAfterHoursRisk:
    """Test after-hours capture risk (each rule independently)."""

    def test_pages_scanned_zero(self):
        result = assess_after_hours_risk(0, False, False, False)
        assert result["risk_level"] == "unknown"
        assert result["reason"] == "unable_to_scan_website"

    def test_no_capture_mechanisms(self):
        result = assess_after_hours_risk(3, False, False, False)
        assert result["risk_level"] == "high"
        assert result["reason"] == "no_capture_mechanisms"

    def test_multiple_capture_paths(self):
        result = assess_after_hours_risk(3, True, True, False)
        assert result["risk_level"] == "low"
        assert result["reason"] == "multiple_capture_paths"
        result = assess_after_hours_risk(3, True, False, True)
        assert result["risk_level"] == "low"
        assert result["reason"] == "multiple_capture_paths"

    def test_phone_only(self):
        result = assess_after_hours_risk(3, True, False, False)
        assert result["risk_level"] == "medium"
        assert result["reason"] == "phone_only"

    def test_has_alternative_capture(self):
        result = assess_after_hours_risk(3, False, True, False)
        assert result["risk_level"] == "low"
        assert result["reason"] == "has_alternative_capture"


class TestConclusionSelection:
    """Determinism and each rule; boundary (null, 2x review threshold)."""

    def test_same_inputs_same_conclusion(self):
        r1 = select_conclusion(None, "low", 50, [])
        r2 = select_conclusion(None, "low", 50, [])
        assert r1["conclusion"] == r2["conclusion"] and r1["reason"] == r2["reason"]

    def test_maps_visible_null(self):
        result = select_conclusion(None, "low", 100, [])
        assert result["conclusion"] == "Not discoverable to high-intent buyers"
        assert result["reason"] == "local_pack_not_available"

    def test_maps_visible_false(self):
        result = select_conclusion(False, "low", 100, [])
        assert result["conclusion"] == "Invisible for high-value service"
        assert result["reason"] == "not_in_top3_local_pack"

    def test_after_hours_high(self):
        result = select_conclusion(True, "high", 100, [])
        assert result["conclusion"] == "Losing calls due to capture gaps"
        assert result["reason"] == "no_after_hours_capture"

    def test_review_gap_2x_boundary(self):
        competitors = [{"name": "X", "review_count": 200}]
        result = select_conclusion(True, "low", 100, competitors)
        assert result["conclusion"] == "Outpaced by competitors in review activity"
        assert result["reason"] == "significant_review_gap"

    def test_review_gap_below_2x(self):
        competitors = [{"name": "X", "review_count": 150}]
        result = select_conclusion(True, "low", 100, competitors)
        assert result["conclusion"] == "Not discoverable to high-intent buyers"
        assert result["reason"] == "default"

    def test_default_conclusion(self):
        result = select_conclusion(True, "low", 100, [])
        assert result["conclusion"] == "Not discoverable to high-intent buyers"
        assert result["reason"] == "default"

    def test_boundary_null_total_reviews(self):
        result = select_conclusion(True, "low", None, [{"review_count": 10}])
        assert result["reason"] == "default"


class TestMissedOpportunity:
    """Templates and boundary cases."""

    def test_invisible_high_value(self):
        result = generate_missed_opportunity(
            "Invisible for high-value service",
            "pest_control",
            "Austin",
            100,
            [],
            "not_in_top3_local_pack",
        )
        assert result["opportunity_code"] == "invisible_high_value"
        assert "pest control" in result["opportunity_description"]
        assert "Austin" in result["opportunity_description"]

    def test_outpaced_competitors(self):
        competitors = [{"name": "ABC Pest", "review_count": 200}]
        result = generate_missed_opportunity(
            "Outpaced by competitors in review activity",
            "pest_control",
            "Austin",
            100,
            competitors,
            "significant_review_gap",
        )
        assert result["opportunity_code"] == "review_gap"
        assert "ABC Pest" in result["opportunity_description"]
        assert "200" in result["opportunity_description"]
        assert "100" in result["opportunity_description"]


class TestSalesSafeSummary:
    """Headline and key_fact."""

    def test_invisible_summary(self):
        result = generate_sales_safe_summary(
            "Invisible for high-value service",
            {},
            {"top3_competitors": []},
            {"risk_level": "low"},
        )
        assert result["headline"] == "Invisible for high-value service"
        assert "top 3" in result["key_fact"].lower()

    def test_capture_gaps_summary(self):
        result = generate_sales_safe_summary(
            "Losing calls due to capture gaps",
            {},
            {},
            {"risk_level": "high"},
        )
        assert result["headline"] == "Losing calls due to capture gaps"
        assert "high" in result["key_fact"].lower()
