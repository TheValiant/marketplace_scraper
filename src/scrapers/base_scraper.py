# src/scrapers/base_scraper.py

"""Abstract base class for all marketplace scrapers."""

import json
import logging
import re
import time
from abc import ABC, abstractmethod

import cloudscraper
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.config.settings import Settings


class BaseScraper(ABC):
    """Abstract base class for all marketplace scrapers."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"ecom_search.{source_name}")
        self.settings = Settings()
        self.selectors = self._load_selectors()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def _load_selectors(self) -> dict:
        """Load CSS selectors for this source from selectors.json."""
        with open(self.settings.SELECTORS_PATH) as f:
            all_selectors = json.load(f)
        return all_selectors.get(self.source_name, {})

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """Fetch a page with curl_cffi, falling back to cloudscraper on failure."""
        headers = {
            **self.settings.DEFAULT_HEADERS,
            "Referer": self._get_homepage(),
        }
        time.sleep(self.settings.REQUEST_DELAY)

        # Primary: curl_cffi (browser-impersonating TLS)
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp = self.session.get(
                    url, headers=headers, timeout=self.settings.REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "lxml")
                self.logger.warning(
                    "[%s] HTTP %d on attempt %d",
                    self.source_name,
                    resp.status_code,
                    attempt + 1,
                )
            except Exception as e:
                self.logger.warning(
                    "[%s] curl_cffi error on attempt %d: %s",
                    self.source_name,
                    attempt + 1,
                    e,
                    exc_info=True,
                )
                time.sleep(self.settings.REQUEST_DELAY * (attempt + 1))

        # Fallback: cloudscraper (JS challenge solver)
        self.logger.info(
            "[%s] curl_cffi exhausted, falling back to cloudscraper",
            self.source_name,
        )
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(
                url, headers=headers, timeout=self.settings.REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            self.logger.error(
                "[%s] cloudscraper fallback also failed: %s",
                self.source_name,
                e,
                exc_info=True,
            )

        return None

    @staticmethod
    def extract_price(text: str) -> float:
        """Extract a numeric price from a string like 'AED 1,299.00'."""
        if not text:
            return 0.0
        numbers = re.findall(r"[\d,]+\.?\d*", text.replace(",", ""))
        return float(numbers[0]) if numbers else 0.0

    @abstractmethod
    def _get_homepage(self) -> str:
        """Return the homepage URL for the Referer header."""
        ...

    @abstractmethod
    def search(self, query: str) -> list:
        """Search for products and return a list of Product objects."""
        ...
