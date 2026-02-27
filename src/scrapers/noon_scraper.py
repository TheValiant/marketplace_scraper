# src/scrapers/noon_scraper.py

"""Scraper for noon.com (UAE) using their internal search API."""

import json
import logging
import time
from typing import Any

from curl_cffi import requests as curl_requests

from src.config.settings import Settings
from src.models.product import Product


class NoonScraper:
    """Scraper for noon.com (UAE) via internal JSON API.

    Noon is a Next.js SPA that returns 403 for HTML scraping.
    This scraper uses their internal catalog search API instead.
    """

    SEARCH_API = (
        "https://www.noon.com/_svc/catalog/api/v3/u/"
        "search?q={query}&page={page}&limit=40&locale=en-ae"
    )

    def __init__(self) -> None:
        self.logger = logging.getLogger("ecom_search.noon")
        self.settings = Settings()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def _fetch_page(
        self,
        url: str,
        headers: dict[str, str],
    ) -> curl_requests.Response | None:
        """Fetch a single page with retries."""
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.settings.REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    return resp
                self.logger.warning(
                    "[noon] HTTP %d on attempt %d",
                    resp.status_code,
                    attempt + 1,
                )
            except Exception as e:
                self.logger.warning(
                    "[noon] Request error on attempt %d: %s",
                    attempt + 1,
                    e,
                    exc_info=True,
                )
                time.sleep(
                    self.settings.REQUEST_DELAY * (attempt + 1)
                )
        return None

    @staticmethod
    def _parse_hit(hit: dict[str, Any]) -> Product:
        """Parse a single Noon API hit into a Product."""
        title: str = str(
            hit.get("name")
            or hit.get("name_en")
            or hit.get("title", "N/A")
        )
        price = float(
            hit.get("sale_price") or hit.get("price", 0)
        )
        sku: str = str(hit.get("sku", "") or "")
        product_url = (
            f"https://www.noon.com/uae-en/{sku}/p/"
            if sku
            else ""
        )
        return Product(
            title=title,
            price=price,
            currency="AED",
            rating=str(hit.get("rating", "")),
            url=product_url,
            source="noon",
            image_url=str(hit.get("image_url", "")),
        )

    def search(self, query: str) -> list[Product]:
        """Search Noon for products matching the query."""
        try:
            products: list[Product] = []
            headers: dict[str, str] = {
                **self.settings.DEFAULT_HEADERS,
                "Referer": (
                    "https://www.noon.com/uae-en/"
                    f"search/?q={query}"
                ),
                "Accept": "application/json",
                "X-Locale": "en-ae",
                "X-Content": "V6",
            }

            for page in range(1, self.settings.MAX_PAGES + 1):
                time.sleep(self.settings.REQUEST_DELAY)
                url = self.SEARCH_API.format(
                    query=query, page=page
                )

                resp = self._fetch_page(url, headers)
                if not resp:
                    self.logger.warning(
                        "[noon] Failed to fetch page %d", page
                    )
                    break

                data: dict[str, Any] = json.loads(resp.text)
                hits: list[dict[str, Any]] = data.get(
                    "hits", []
                )
                if not hits:
                    break

                for hit in hits:
                    products.append(self._parse_hit(hit))

                total_pages: int = int(
                    data.get("nbPages", 1)
                )
                if page >= total_pages:
                    break

            return products
        except Exception as e:
            self.logger.error(
                "[noon] Search failed: %s", e, exc_info=True
            )
            return []
