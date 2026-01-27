# Pre-Call Audit Service

Production-ready Pre-Call Audit service for pest control companies. Generates standardized, sales-safe audits from business name, website URL, city, and primary service.

## Setup

1. Clone the repository.
2. Install Python 3.14.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set `GOOGLE_MAPS_API_KEY` and `SERPAPI_API_KEY`.

## Run

```bash
python -m uvicorn app.main:app --reload
```

Server runs at `http://127.0.0.1:8000` by default.

## Test (curl)

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Example audit:

```bash
curl -X POST http://127.0.0.1:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"business_name":"Acme Pest","website_url":"https://acmepest.example.com","city":"Phoenix","primary_service":"pest_control"}'
```

## What it does

- Generates **deterministic** audits in about 2–4 seconds.
- Checks **local visibility** (top 3 local pack via SerpAPI).
- Pulls **review count, rating, last review date** from Google Places.
- Assesses **call capture** (phones, forms, call tracking, scheduling) from homepage, `/contact`, and `/services`.

## What it doesn’t do

- JS-rendered site detection  
- Organic ranking analysis  
- Review velocity  
- Competitor website analysis  
- PDF generation  

## Cost

Roughly **~$0.05 per audit** (Google Places + SerpAPI). Caching by `{domain}_{city}_{service}_{business_name_hash}` with a 24-hour TTL reduces duplicate calls.
"# pest-audit-service" 
