"""Website scanner for call capture. Uses html5lib only. time.time() for timing."""
import re
import time
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup

from app.utils.constants import (
    CALL_TRACKING_VENDORS,
    FORM_VENDORS,
    SCHEDULING_WIDGETS,
)
from app.utils.logging_config import logger


class SiteScanner:
    """Scan homepage, /contact, /services. Extract phones, forms, call tracking, scheduling."""

    def __init__(self) -> None:
        self.phone_re = re.compile(
            r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        )

    async def scan_website(self, website_url: str, service_slug: str = "services") -> Dict[str, Any]:
        """
        Fetch up to 3 pages: homepage, /contact, /services.
        Use stdlib/str URL only (caller passes str(website_url)).
        Parser: html5lib only.
        """
        url_str = str(website_url)
        if "://" not in url_str:
            url_str = "https://" + url_str
        from urllib.parse import urlparse
        parsed = urlparse(url_str)
        base = f"{parsed.scheme or 'https'}://{parsed.netloc or parsed.path}"
        base = base.rstrip("/")
        pages = [
            base + "/",
            base + "/contact",
            base + "/services",
        ]
        all_phones: set[str] = set()
        form_detected = False
        call_tracking_detected = False
        call_tracking_vendor: str | None = None
        scheduling_widget_detected = False
        pages_scanned = 0
        pages_attempted = 0
        status_code_last: int | None = None

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for page_url in pages:
                pages_attempted += 1
                t0 = time.time()
                try:
                    response = await client.get(page_url)
                    status_code_last = response.status_code
                    elapsed_ms = int((time.time() - t0) * 1000)
                    logger.info(
                        "Website Scan - timestamp=%s status_code=%s elapsed_ms=%s",
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
                        response.status_code,
                        elapsed_ms,
                    )
                    if response.status_code == 200:
                        pages_scanned += 1
                        # html5lib only
                        soup = BeautifulSoup(response.text, "html5lib")
                        phones = self._extract_phones(soup, response.text)
                        all_phones.update(phones)
                        if not form_detected:
                            form_detected = self._detect_form(soup, response.text)
                        if not call_tracking_detected:
                            det, vend = self._detect_call_tracking(soup, response.text)
                            call_tracking_detected = det
                            call_tracking_vendor = vend
                        if not scheduling_widget_detected:
                            scheduling_widget_detected = self._detect_scheduling(
                                soup, response.text
                            )
                except Exception as e:
                    elapsed_ms = int((time.time() - t0) * 1000)
                    logger.warning(
                        "Website Scan error url=%s elapsed_ms=%s err=%s",
                        page_url[:80],
                        elapsed_ms,
                        str(e),
                    )

        logger.info(
            "Website Scan - pages_attempted=%s pages_succeeded=%s",
            pages_attempted,
            pages_scanned,
        )
        phone_list = sorted(set(all_phones))
        phone_found = len(phone_list) > 0
        if not phone_list:
            phone_consistency = "not_found"
        elif len(phone_list) == 1:
            phone_consistency = "consistent"
        else:
            phone_consistency = "inconsistent"
        ct_status = "unknown" if call_tracking_detected is None else ("true" if call_tracking_detected else "false")
        if pages_scanned == 0:
            capture_status = "no_data"
        elif pages_scanned < pages_attempted:
            capture_status = "partial_failure"
        else:
            capture_status = "completed"

        return {
            "phone_found": phone_found,
            "phones_detected": phone_list,
            "phone_consistency": phone_consistency,
            "form_detected": form_detected,
            "call_tracking_detected": ct_status,
            "call_tracking_vendor": call_tracking_vendor,
            "scheduling_widget_detected": scheduling_widget_detected,
            "pages_scanned": pages_scanned,
            "capture_assessment_status": capture_status,
        }

    def _extract_phones(self, soup: BeautifulSoup, html_text: str) -> List[str]:
        """From tel: links and regex."""
        out: set[str] = set()
        for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
            href = a.get("href") or ""
            p = href.replace("tel:", "").strip()
            if p:
                out.add(p)
        for m in self.phone_re.findall(html_text):
            n = re.sub(r"[^\d]", "", m)
            if len(n) == 10:
                out.add(f"({n[:3]}) {n[3:6]}-{n[6:]}")
            elif len(n) == 11 and n[0] == "1":
                n = n[1:]
                out.add(f"({n[:3]}) {n[3:6]}-{n[6:]}")
        return list(out)

    def _detect_form(self, soup: BeautifulSoup, html_text: str) -> bool:
        """<form> or Gravity Forms, Formspree, Typeform, HubSpot."""
        if soup.find("form"):
            return True
        low = html_text.lower()
        for v in FORM_VENDORS:
            if v in low:
                return True
        return False

    def _detect_call_tracking(self, soup: BeautifulSoup, html_text: str) -> tuple[bool, str | None]:
        """callrail, calltrackingmetrics, whatconverts, invoca, ringba."""
        low = html_text.lower()
        for script in soup.find_all("script", src=True):
            src = (script.get("src") or "").lower()
            for v in CALL_TRACKING_VENDORS:
                if v in src:
                    return True, v
        for v in CALL_TRACKING_VENDORS:
            if v in low:
                return True, v
        return False, None

    def _detect_scheduling(self, soup: BeautifulSoup, html_text: str) -> bool:
        """Calendly, Acuity, HubSpot scheduling, Booking.com."""
        low = html_text.lower()
        for w in SCHEDULING_WIDGETS:
            if w in low:
                return True
        return False
