# src/scrapers/base_scraper.py

"""Abstract base class for all marketplace scrapers."""

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import cloudscraper  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.config.settings import Settings
from src.models.product import Product


class BaseScraper(ABC):
    """Abstract base class for all marketplace scrapers."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self.logger = logging.getLogger(
            f"ecom_search.{source_name}"
        )
        self.settings = Settings()
        self.selectors: dict[str, str] = self._load_selectors()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )
        self._current_delay: float = (
            self.settings.REQUEST_DELAY
        )
        self._consecutive_failures: int = 0
        self._circuit_open: bool = False
        self._circuit_opened_at: float = 0.0
        self._request_timeout: int = (
            self.settings.REQUEST_TIMEOUT
        )

    def _load_selectors(self) -> dict[str, str]:
        """Load CSS selectors for this source from selectors.json."""
        with open(self.settings.SELECTORS_PATH) as f:
            all_selectors: dict[str, Any] = json.load(f)
        result: dict[str, str] = all_selectors.get(
            self.source_name, {}
        )
        return result

    def _wait(self) -> None:
        """Sleep using the current (possibly escalated) delay."""
        time.sleep(self._current_delay)

    # Cloudflare challenge page markers (checked before keyword scan)
    _CF_CHALLENGE_MARKERS: list[str] = [
        "challenges.cloudflare.com",
        "cdn-cgi/challenge-platform",
        "just a moment",
        "cf-turnstile",
        "cf_chl_opt",
    ]

    def _validate_response(
        self, resp: curl_requests.Response,
    ) -> bool:
        """Check for Cloudflare challenge pages and CAPTCHA indicators."""
        text = resp.text
        if text.lstrip().startswith(("{", "[")):
            return True
        lower = text.lower()

        # Cloudflare challenge page detection (high-confidence)
        for marker in self._CF_CHALLENGE_MARKERS:
            if marker in lower:
                self.logger.warning(
                    "[%s] Cloudflare challenge detected "
                    "(marker: '%s')",
                    self.source_name,
                    marker,
                )
                return False

        # Generic CAPTCHA keyword scan (skip if page has
        # real product content to avoid false positives)
        has_body_content = (
            "<body" in lower and len(text) > 5000
        )
        if not has_body_content:
            for keyword in self.settings.CAPTCHA_KEYWORDS:
                if keyword in lower:
                    self.logger.warning(
                        "[%s] CAPTCHA keyword '%s' "
                        "detected",
                        self.source_name,
                        keyword,
                    )
                    return False
        return True

    def _check_circuit(self) -> bool:
        """Return True if the circuit breaker blocks this request.

        After CIRCUIT_BREAKER_COOLDOWN seconds the breaker enters
        a half-open state, allowing a single probe request through.
        """
        if not self._circuit_open:
            return False
        elapsed = time.time() - self._circuit_opened_at
        if elapsed >= self.settings.CIRCUIT_BREAKER_COOLDOWN:
            self.logger.info(
                "[%s] Circuit breaker half-open after %.0fs",
                self.source_name,
                elapsed,
            )
            self._circuit_open = False
            return False
        return True

    def _record_success(self) -> None:
        """Reset failure counters after a successful fetch."""
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at = 0.0
        self._current_delay = self.settings.REQUEST_DELAY

    def _record_failure(self) -> None:
        """Track failure and open circuit breaker if needed."""
        self._consecutive_failures += 1
        threshold = (
            self.settings.CIRCUIT_BREAKER_THRESHOLD
        )
        if self._consecutive_failures >= threshold:
            self._circuit_open = True
            self._circuit_opened_at = time.time()
            self.logger.error(
                "[%s] Circuit breaker opened after %d "
                "consecutive failures",
                self.source_name,
                self._consecutive_failures,
            )

    def _escalate_delay(self) -> None:
        """Double the current delay up to the configured max."""
        max_delay = (
            self.settings.REQUEST_DELAY
            * self.settings.MAX_DELAY_MULTIPLIER
        )
        self._current_delay = min(
            self._current_delay * 2, max_delay
        )
        self.logger.warning(
            "[%s] Rate-limited, delay escalated to %.1fs",
            self.source_name,
            self._current_delay,
        )

    def _fetch_get(
        self,
        url: str,
        headers: dict[str, str],
    ) -> curl_requests.Response | None:
        """GET with retries, adaptive delay, and circuit breaker."""
        if self._check_circuit():
            return None
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp = self.session.get(
                    url,
                    headers=headers,
                    timeout=self._request_timeout,
                )
                if resp.status_code == 200:
                    if not self._validate_response(resp):
                        self._escalate_delay()
                        time.sleep(self._current_delay)
                        continue
                    self._record_success()
                    return resp
                self.logger.warning(
                    "[%s] HTTP %d on attempt %d",
                    self.source_name,
                    resp.status_code,
                    attempt + 1,
                )
                if resp.status_code in (429, 403):
                    self._escalate_delay()
                    time.sleep(self._current_delay)
            except Exception as exc:
                self.logger.warning(
                    "[%s] Request error on attempt %d: %s",
                    self.source_name,
                    attempt + 1,
                    exc,
                    exc_info=True,
                )
                time.sleep(
                    self._current_delay * (attempt + 1)
                )
        self._record_failure()
        return None

    def _fetch_post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> curl_requests.Response | None:
        """POST with retries, adaptive delay, and circuit breaker."""
        if self._check_circuit():
            return None
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp = self.session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._request_timeout,
                )
                if resp.status_code == 200:
                    if not self._validate_response(resp):
                        self._escalate_delay()
                        time.sleep(self._current_delay)
                        continue
                    self._record_success()
                    return resp
                self.logger.warning(
                    "[%s] HTTP %d on attempt %d",
                    self.source_name,
                    resp.status_code,
                    attempt + 1,
                )
                if resp.status_code in (429, 403):
                    self._escalate_delay()
                    time.sleep(self._current_delay)
            except Exception as exc:
                self.logger.warning(
                    "[%s] Request error on attempt %d: %s",
                    self.source_name,
                    attempt + 1,
                    exc,
                    exc_info=True,
                )
                time.sleep(
                    self._current_delay * (attempt + 1)
                )
        self._record_failure()
        return None

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """Fetch a page, falling back to cloudscraper on failure."""
        if self._check_circuit():
            return None
        headers: dict[str, str] = {
            **self.settings.DEFAULT_HEADERS,
            "Referer": self._get_homepage(),
        }
        self._wait()

        # Primary: curl_cffi (browser-impersonating TLS)
        resp = self._fetch_get(url, headers)
        if resp:
            return BeautifulSoup(resp.text, "lxml")

        # Fallback: cloudscraper (JS challenge solver)
        self.logger.info(
            "[%s] curl_cffi exhausted, falling back to cloudscraper",
            self.source_name,
        )
        try:
            _cs: Any = cloudscraper
            scraper: Any = _cs.create_scraper()
            fallback_resp: Any = scraper.get(
                url,
                headers=headers,
                timeout=self._request_timeout,
            )
            if fallback_resp.status_code == 200:
                return BeautifulSoup(
                    str(fallback_resp.text), "lxml"
                )
        except Exception as e:
            self.logger.error(
                "[%s] cloudscraper fallback also failed: %s",
                self.source_name,
                e,
                exc_info=True,
            )

        return None

    @staticmethod
    def extract_price(text: str | None) -> float:
        """Extract a numeric price from a string like 'AED 1,299.00'."""
        if not text:
            return 0.0
        cleaned = text.replace(",", "")
        numbers = re.findall(r"[\d,]+\.?\d*", cleaned)
        return float(numbers[0]) if numbers else 0.0

    @abstractmethod
    def _get_homepage(self) -> str:
        """Return the homepage URL for the Referer header."""
        ...

    @abstractmethod
    def search(self, query: str) -> list[Product]:
        """Search for products and return a list of Product objects."""
        ...
