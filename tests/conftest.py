"""Pytest configuration. Set env vars before any app imports that need config."""
import os

os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-key")
os.environ.setdefault("SERPAPI_API_KEY", "test-key")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("CACHE_TTL_HOURS", "24")
