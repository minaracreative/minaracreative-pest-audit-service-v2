"""FastAPI app: POST /audit, GET /health, GET /version."""
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import (
    AuditRequest,
    AuditResponse,
    HealthResponse,
    VersionResponse,
)
from app.services.audit_runner import AuditRunner
from app.utils.cache import Cache
from app.utils.logging_config import logger, setup_logging

setup_logging()

app = FastAPI(
    title="Pre-Call Audit Service",
    description="MVP service for standardized pre-call audits for pest control companies",
    version="1.0.0",
)

cache = Cache()
audit_runner = AuditRunner()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return status and timestamp."""
    return HealthResponse(status="ok", timestamp=_utc_iso())


@app.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Return version."""
    return VersionResponse(version="1.0.0")


@app.post("/audit", response_model=AuditResponse)
async def create_audit(request: AuditRequest) -> AuditResponse:
    """
    Generate audit from business inputs. Validates before any API calls.
    On business_not_found returns HTTP 400. On SerpAPI/website failures
    returns HTTP 200 with null/partial data per spec.
    """
    website_str = str(request.website_url)
    parsed = urlparse(website_str)
    domain = (parsed.netloc or "").replace("www.", "")
    cache_key = cache.generate_key(
        domain, request.city, request.primary_service, request.business_name
    )
    cached = cache.get(cache_key)
    if cached:
        cached["debug"]["cache_hit"] = True
        return AuditResponse.model_validate(cached)

    audit_result = await audit_runner.run_audit(
        request.business_name,
        request.website_url,
        request.city,
        request.primary_service,
    )

    if audit_result["resolved_business"]["resolution_status"] == "not_found":
        logger.warning("Business not found: %s in %s", request.business_name, request.city)
        raise HTTPException(status_code=400, detail="business_not_found")

    audit_result["debug"]["cache_hit"] = False
    cache.set(cache_key, audit_result)
    return AuditResponse.model_validate(audit_result)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: object, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
