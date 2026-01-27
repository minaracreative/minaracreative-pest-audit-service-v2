

You are a senior backend engineer. Build a production-ready "Pre-Call Audit" service for pest control companies. This code must work flawlessly with Python 3.14.

## Critical Requirements
1. Target Python 3.14 exclusively. All dependencies must have pre-built wheels for Python 3.14.
2. No compilation required. No Rust, no C++, no Cython.
3. All code must be syntactically correct and tested before returning.
4. Use only time.time() for timing. Never use httpx.httpx or custom timing functions.
5. Convert all Pydantic URL objects to strings before passing to stdlib functions.
6. Use html5lib parser, never lxml.
7. Return working, production-ready code.

## Goal
Generate a standardized, sales-safe audit from four inputs. Deterministic logic. No invented data. Consistent outputs.

## Tech Stack (Python 3.14 Compatible)
- Python 3.14
- FastAPI 0.115.0 (tested with 3.14)
- uvicorn[standard] 0.30.0
- httpx 0.27.0
- pydantic 2.9.0 (has 3.14 wheels)
- pydantic-settings 2.4.0
- python-dotenv 1.0.1
- beautifulsoup4 4.13.0
- html5lib 1.1 (pure Python)
- rapidfuzz 3.10.0 (pure Python)
- pytest 8.0.0
- pytest-asyncio 0.24.0

## Inputs (POST /audit)
```json
{
  "business_name": "string (2-50 chars)",
  "website_url": "string (valid URL format)",
  "city": "string (2-50 chars)",
  "primary_service": "pest_control|termite_treatment|rodent_control|mosquito_control|wildlife_removal|general_pest_management|fumigation|bed_bug_treatment|ant_control|cockroach_control"
}
```

## Environment Variables
```
GOOGLE_MAPS_API_KEY=your_key
SERPAPI_API_KEY=your_key
LOG_LEVEL=INFO
CACHE_TTL_HOURS=24
```

## Repository Structure
```
pest-audit-service/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── google_places.py
│   │   ├── serpapi_provider.py
│   │   └── site_scanner.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audit_runner.py
│   │   └── rules.py
│   └── utils/
│       ├── __init__.py
│       ├── cache.py
│       ├── logging_config.py
│       └── constants.py
├── tests/
│   ├── __init__.py
│   ├── test_rules.py
│   ├── test_schemas.py
│   └── test_integration.py
├── requirements.txt
├── .env.example
├── Dockerfile
└── README.md
```

## Audit Logic (Fixed Order)

### Step 1: Resolve Business to Google Place
- Call Google Places Text Search with business_name + city.
- Score by: (1) website domain match, (2) name similarity via rapidfuzz, (3) city match.
- Return: place_id, name, address, phone, website, rating, total_reviews, google_maps_url.
- If no match: return error "business_not_found".
- Log: timestamp, status_code, result count.

### Step 2: Local Pack Visibility vs Top 3
- Call SerpAPI for "{primary_service_readable} {city}".
- Extract top 3 local pack results: name, rating, review_count, address.
- Check if target is in top 3 via fuzzy match (token_set_ratio >= 80) + address.
- Return: maps_visible_top3 (boolean or null), top3_competitors (list).
- If no local pack: set maps_visible_top3: null, local_pack_available: false.
- Log: timestamp, status_code, result count.

### Step 3: Review Count and Last Activity
- Call Google Places Details with place_id.
- Return: total_reviews, rating, last_review_date (ISO format).
- Do NOT compute velocity.
- Log: timestamp, status_code.

### Step 4: Call Capture Assessment
- Fetch up to 3 pages: homepage, /contact, /services.
- For each page:
  - Extract phone numbers from tel: links and regex patterns.
  - Detect forms via <form> element and form vendor signatures (Gravity Forms, Formspree, Typeform, HubSpot).
  - Detect call tracking vendors by static pattern match: callrail, calltrackingmetrics, whatconverts, invoca, ringba.
  - Detect scheduling widgets: Calendly, Acuity, HubSpot scheduling, Booking.com.
- Return: phone_found, phones_detected, phone_consistency, form_detected, call_tracking_detected, scheduling_widget_detected, pages_scanned, capture_assessment_status.
- Log: timestamp, status_code, pages attempted vs succeeded.

### Step 5: After-Hours Capture Risk
Apply in order, stop at first match:
```
if pages_scanned == 0:
  risk = "unknown", reason = "unable_to_scan_website"
elif phone_found == false AND form_detected == false AND scheduling_widget_detected == false:
  risk = "high", reason = "no_capture_mechanisms"
elif phone_found == true AND (form_detected == true OR scheduling_widget_detected == true):
  risk = "low", reason = "multiple_capture_paths"
elif phone_found == true AND form_detected == false AND scheduling_widget_detected == false:
  risk = "medium", reason = "phone_only"
else:
  risk = "low", reason = "has_alternative_capture"
```

## Deterministic Conclusion Selection (Exact Order)

Allowed conclusions (pick one, stop at first match):
1. "Invisible for high-value service"
2. "Losing calls due to capture gaps"
3. "Outpaced by competitors in review activity"
4. "Not discoverable to high-intent buyers"

Selection logic:
```
if maps_visible_top3 == null:
  conclusion = "Not discoverable to high-intent buyers"
  reason = "local_pack_not_available"
elif maps_visible_top3 == false:
  conclusion = "Invisible for high-value service"
  reason = "not_in_top3_local_pack"
elif after_hours_capture_risk == "high":
  conclusion = "Losing calls due to capture gaps"
  reason = "no_after_hours_capture"
elif maps_visible_top3 == true AND top3_competitors[0].review_count >= 2 * total_reviews:
  conclusion = "Outpaced by competitors in review activity"
  reason = "significant_review_gap"
else:
  conclusion = "Not discoverable to high-intent buyers"
  reason = "default"
```

## Missed Opportunity Templates

One template per conclusion:

1. **Invisible for high-value service**: "You're not showing up for {service} in {city}. Competitors in the top 3 local pack are getting calls you're missing."

2. **Losing calls due to capture gaps**: "You only have a phone number for lead capture. Without a contact form or scheduling link, you're losing calls after hours."

3. **Outpaced by competitors in review activity**: "{competitor} has {comp_reviews} reviews vs. your {total_reviews}. Review gap signals lower visibility in local search."

4. **Not discoverable to high-intent buyers**: "Your local search presence isn't strong enough to appear where buyers are looking. This limits booked jobs."

## Response Output (JSON)

```json
{
  "audit_id": "uuid",
  "timestamp": "ISO 8601",
  "inputs": { "business_name", "website_url", "city", "primary_service" },
  "resolved_business": {
    "place_id": "string or null",
    "name": "string",
    "address": "string",
    "phone": "string or null",
    "website": "string or null",
    "rating": "float or null",
    "total_reviews": "int or null",
    "google_maps_url": "string or null",
    "resolution_status": "found | not_found | error"
  },
  "local_visibility": {
    "maps_visible_top3": "boolean or null",
    "top3_competitors": [{"rank": 1, "name": "string", "rating": "float or null", "review_count": "int or null", "address": "string or null"}],
    "local_pack_available": "boolean"
  },
  "reviews": {
    "total_reviews": "int or null",
    "rating": "float or null",
    "last_review_date": "ISO 8601 or null",
    "review_data_status": "available | insufficient_api_data"
  },
  "call_capture": {
    "phone_found": "boolean",
    "phones_detected": ["list of unique phone strings"],
    "phone_consistency": "consistent | inconsistent | not_found",
    "form_detected": "boolean",
    "call_tracking_detected": "true | false | unknown",
    "call_tracking_vendor": "string or null",
    "scheduling_widget_detected": "boolean",
    "pages_scanned": "int (0-3)",
    "capture_assessment_status": "completed | partial_failure | no_data"
  },
  "after_hours_risk": {
    "risk_level": "low | medium | high | unknown",
    "reason": "string"
  },
  "selected_conclusion": {
    "conclusion": "one of four allowed strings",
    "reason": "string"
  },
  "missed_opportunity": {
    "opportunity_code": "string",
    "opportunity_description": "string (templated with actual values)",
    "reason": "string"
  },
  "debug": {
    "cache_hit": "boolean",
    "audit_duration_ms": "int",
    "api_calls": [{"service": "google_places | serpapi | website_scan", "endpoint": "string", "status_code": "int or null", "timestamp": "ISO 8601", "error": "string or null"}]
  },
  "sales_safe_summary": {
    "headline": "string (one-line conclusion)",
    "key_fact": "string (single strongest piece of evidence)"
  }
}
```

## Endpoints

- **POST /audit**: Generate audit from business inputs
- **GET /health**: Return {"status": "ok", "timestamp": "ISO 8601"}
- **GET /version**: Return {"version": "1.0.0"}

## Caching

- Key: `{domain}_{city}_{service}_{business_name_hash}`
- Storage: SQLite with 24-hour TTL
- Delete expired rows on startup and every 24 hours
- Cost savings: eliminates duplicate audits within 24h

## Input Validation

Before any API calls, validate:
```
assert 2 <= len(business_name) <= 50
assert valid_url_format(website_url)
assert 2 <= len(city) <= 50 and city.isalpha() (allow spaces/hyphens)
assert primary_service in ALLOWED_SERVICES
```

Return HTTP 400 with clear error message if validation fails. No API calls made.

## Error Handling

- **Cannot resolve business**: HTTP 400, error: "business_not_found"
- **SerpAPI fails**: HTTP 200, set maps_visible_top3: null, local_pack_available: false
- **Website scan fails**: HTTP 200, set pages_scanned: 0, capture_assessment_status: "no_data"
- **Partial website scan**: HTTP 200, set pages_scanned: <count>, capture_assessment_status: "partial_failure"

All errors logged with timestamp and reason.

## Logging

Log every external request with:
- Timestamp (ISO 8601)
- Service (google_places | serpapi | website_scan)
- Endpoint or URL
- HTTP status code
- Response time (milliseconds)
- Error message (if any)

Never log: API keys, full sensitive URLs, phone numbers extracted from websites, emails, business credentials.

Log level: INFO for audit flow, DEBUG for provider details.

## Testing

**test_rules.py:**
- Same inputs always produce same conclusion (determinism test)
- Test each rule condition independently
- Test boundary cases (null values, 2x review threshold)

**test_schemas.py:**
- Input validation: too short, invalid URL, bad service, missing field
- Verify invalid inputs return HTTP 400 with clear error
- Test valid inputs pass validation

**test_integration.py:**
- Mock Google Places Text Search response
- Mock Google Places Details response
- Mock SerpAPI local pack response
- End-to-end audit generation from inputs to JSON response
- Verify debug logs are present
- Verify status codes are captured

## README

Include:
1. **Setup**: Clone, Python 3.14 install, pip install -r requirements.txt, create .env
2. **Run**: python -m uvicorn app.main:app --reload
3. **Test**: Example curl command for /audit, /health
4. **What it does**: Generates deterministic audits in 2-4 seconds. Checks local visibility, reviews, call capture.
5. **What it doesn't do**: JS site detection, organic ranking, review velocity, competitor website analysis, PDF generation.
6. **Cost**: ~$0.05 per audit (Google Places + SerpAPI).

## requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
pydantic==2.9.0
pydantic-settings==2.4.0
python-dotenv==1.0.1
beautifulsoup4==4.13.0
html5lib==1.1
rapidfuzz==3.10.0
pytest==8.0.0
pytest-asyncio==0.24.0
```

## .env.example

```
GOOGLE_MAPS_API_KEY=your_key_here
SERPAPI_API_KEY=your_key_here
LOG_LEVEL=INFO
CACHE_TTL_HOURS=24
```

## Dockerfile

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

Build this exactly as specified. Do not deviate. All code must be production-ready, tested, and work with Python 3.14 without any compilation or dependency issues. Every file must be complete and syntactically correct. Test the entire code path before returning it.