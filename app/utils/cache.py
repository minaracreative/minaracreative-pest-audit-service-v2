"""SQLite-based caching for audit results."""
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from app.config import settings
from app.utils.logging_config import logger


class Cache:
    """SQLite cache for audit results. Key: {domain}_{city}_{service}_{business_name_hash}."""

    def __init__(self, db_path: str = "audit_cache.db") -> None:
        self.db_path = db_path
        self._last_cleanup: Optional[datetime] = None
        self._init_db()
        self._cleanup_expired()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_cache (
                cache_key TEXT PRIMARY KEY,
                audit_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Cache database initialized")

    def _cleanup_expired(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute("DELETE FROM audit_cache WHERE expires_at < ?", (now,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        self._last_cleanup = datetime.utcnow()
        if deleted > 0:
            logger.info("Cleaned up %d expired cache entries", deleted)

    def _maybe_cleanup(self) -> None:
        if self._last_cleanup is None:
            return
        if (datetime.utcnow() - self._last_cleanup).total_seconds() >= 86400:  # 24 hours
            self._cleanup_expired()

    def generate_key(self, domain: str, city: str, service: str, business_name: str) -> str:
        """Generate cache key: {domain}_{city}_{service}_{business_name_hash}."""
        name_hash = hashlib.sha256(business_name.encode()).hexdigest()[:16]
        return f"{domain}_{city}_{service}_{name_hash}"

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached audit result."""
        self._maybe_cleanup()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            "SELECT audit_json FROM audit_cache WHERE cache_key = ? AND expires_at > ?",
            (cache_key, now),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            logger.info("Cache hit for key: %s...", cache_key[:50])
            return json.loads(row[0])
        logger.debug("Cache miss for key: %s...", cache_key[:50])
        return None

    def set(self, cache_key: str, audit_data: Dict[str, Any]) -> None:
        """Store audit result in cache."""
        ttl_hours = getattr(settings, "cache_ttl_hours", 24)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=ttl_hours)
        cursor.execute(
            """
            INSERT OR REPLACE INTO audit_cache
            (cache_key, audit_json, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (cache_key, json.dumps(audit_data), now.isoformat(), expires_at.isoformat()),
        )
        conn.commit()
        conn.close()
        logger.info("Cached audit result for key: %s...", cache_key[:50])
