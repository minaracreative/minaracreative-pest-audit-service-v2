"""Input validation: too short, invalid URL, bad service, missing field; valid pass; invalid -> 400."""
import pytest
from pydantic import ValidationError

from app.schemas import AuditRequest
from app.utils.constants import ALLOWED_SERVICES


class TestAuditRequestValidation:
    """Input validation and HTTP 400 behavior via ValidationError."""

    def test_valid_request(self):
        req = AuditRequest(
            business_name="AB",
            website_url="https://example.com",
            city="Austin",
            primary_service="pest_control",
        )
        assert req.business_name == "AB"
        assert "example.com" in str(req.website_url)
        assert req.city == "Austin"
        assert req.primary_service == "pest_control"

    def test_business_name_too_short(self):
        with pytest.raises(ValidationError) as exc_info:
            AuditRequest(
                business_name="A",
                website_url="https://example.com",
                city="Austin",
                primary_service="pest_control",
            )
        assert "2" in str(exc_info.value) or "min" in str(exc_info.value).lower()

    def test_business_name_too_long(self):
        with pytest.raises(ValidationError):
            AuditRequest(
                business_name="A" * 51,
                website_url="https://example.com",
                city="Austin",
                primary_service="pest_control",
            )

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            AuditRequest(
                business_name="AB",
                website_url="not-a-valid-url",
                city="Austin",
                primary_service="pest_control",
            )

    def test_city_too_short(self):
        with pytest.raises(ValidationError):
            AuditRequest(
                business_name="AB",
                website_url="https://example.com",
                city="A",
                primary_service="pest_control",
            )

    def test_city_invalid_characters(self):
        with pytest.raises(ValidationError) as exc_info:
            AuditRequest(
                business_name="AB",
                website_url="https://example.com",
                city="Austin123",
                primary_service="pest_control",
            )
        msg = str(exc_info.value).lower()
        assert "letters" in msg or "city" in msg or "value" in msg

    def test_city_with_hyphen_and_spaces(self):
        req = AuditRequest(
            business_name="AB",
            website_url="https://example.com",
            city="New York",
            primary_service="pest_control",
        )
        assert req.city == "New York"
        req2 = AuditRequest(
            business_name="AB",
            website_url="https://example.com",
            city="St-Louis",
            primary_service="pest_control",
        )
        assert req2.city == "St-Louis"

    def test_invalid_primary_service(self):
        with pytest.raises(ValidationError) as exc_info:
            AuditRequest(
                business_name="AB",
                website_url="https://example.com",
                city="Austin",
                primary_service="invalid_service",
            )
        assert "one of" in str(exc_info.value).lower() or "primary_service" in str(exc_info.value).lower()

    def test_all_allowed_services_pass(self):
        for svc in ALLOWED_SERVICES:
            req = AuditRequest(
                business_name="AB",
                website_url="https://example.com",
                city="Austin",
                primary_service=svc,
            )
            assert req.primary_service == svc

    def test_missing_field_rejected(self):
        with pytest.raises(ValidationError):
            AuditRequest.model_validate({
                "business_name": "AB",
                "website_url": "https://example.com",
                "city": "Austin",
            })
