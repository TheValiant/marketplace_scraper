# src/scrapers/binsina_scraper.py

"""Scraper for binsina.ae (UAE) using their Algolia-powered search API."""

import json
import logging
import re
import time

from curl_cffi import requests as curl_requests

from src.config.settings import Settings
from src.models.product import Product


class BinSinaScraper:
    """Scraper for binsina.ae via Algolia product search.

    BinSina uses Magento 2 with Algolia for search.  The API key is
    time-limited and must be scraped from the homepage each session.
    """

    ALGOLIA_APP_ID = "FTRV4XOC74"
    ALGOLIA_INDEX = "magento2_en_products"
    ALGOLIA_URL = (
        "https://{app_id}-dsn.algolia.net/1/indexes/{index}/query"
    )
    HOMEPAGE_URL = "https://binsina.ae/en/"
    BASE_PRODUCT_URL = "https://binsina.ae"

    def __init__(self):
        self.logger = logging.getLogger("ecom_search.binsina")
        self.settings = Settings()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )
        self._api_key: str = ""

    def _refresh_api_key(self) -> bool:
        """Fetch a fresh Algolia API key from the BinSina homepage."""
        try:
            resp = self.session.get(
                self.HOMEPAGE_URL,
                headers={
                    **self.settings.DEFAULT_HEADERS,
                    "Referer": "https://binsina.ae/",
                },
                timeout=self.settings.REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                self.logger.warning(
                    "[binsina] Homepage returned HTTP %d", resp.status_code
                )
                return False

            match = re.search(
                r"window\.algoliaConfig\s*=\s*(\{.*?\});",
                resp.text,
                re.DOTALL,
            )
            if not match:
                self.logger.error(
                    "[binsina] Could not find algoliaConfig in homepage"
                )
                return False

            config = json.loads(match.group(1))
            self._api_key = config.get("apiKey", "")
            if not self._api_key:
                self.logger.error("[binsina] Empty API key in algoliaConfig")
                return False

            self.logger.info("[binsina] Refreshed Algolia API key")
            return True
        except Exception as exc:
            self.logger.error(
                "[binsina] Failed to refresh API key: %s",
                exc,
                exc_info=True,
            )
            return False

    def search(self, query: str) -> list[Product]:
        """Search BinSina for products matching the query."""
        try:
            if not self._api_key and not self._refresh_api_key():
                self.logger.error("[binsina] No API key available")
                return []

            products: list[Product] = []
            url = self.ALGOLIA_URL.format(
                app_id=self.ALGOLIA_APP_ID, index=self.ALGOLIA_INDEX
            )
            headers = {
                "X-Algolia-Application-Id": self.ALGOLIA_APP_ID,
                "X-Algolia-API-Key": self._api_key,
                "Content-Type": "application/json",
                "Referer": self.HOMEPAGE_URL,
            }

            for page in range(self.settings.MAX_PAGES):
                time.sleep(self.settings.REQUEST_DELAY)
                payload = {
                    "query": query,
                    "page": page,
                    "hitsPerPage": 40,
                }

                resp = None
                for attempt in range(self.settings.MAX_RETRIES):
                    try:
                        resp = self.session.post(
                            url,
                            headers=headers,
                            json=payload,
                            timeout=self.settings.REQUEST_TIMEOUT,
                        )
                        if resp.status_code == 200:
                            break
                        self.logger.warning(
                            "[binsina] HTTP %d on attempt %d",
                            resp.status_code,
                            attempt + 1,
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "[binsina] Request error on attempt %d: %s",
                            attempt + 1,
                            exc,
                            exc_info=True,
                        )
                        time.sleep(
                            self.settings.REQUEST_DELAY * (attempt + 1)
                        )

                if not resp or resp.status_code != 200:
                    self.logger.warning(
                        "[binsina] Failed to fetch page %d", page
                    )
                    break

                data = resp.json()
                hits = data.get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    title = hit.get("name", "N/A")
                    price = self._extract_price(hit)
                    product_url = hit.get("url", "")
                    if product_url and not product_url.startswith("http"):
                        product_url = self.BASE_PRODUCT_URL + product_url

                    products.append(
                        Product(
                            title=title,
                            price=price,
                            currency="AED",
                            rating=str(hit.get("rating_summary", "")),
                            url=product_url,
                            source="binsina",
                            image_url=hit.get("image_url", ""),
                        )
                    )

                total_pages = data.get("nbPages", 1)
                if page + 1 >= total_pages:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[binsina] Search failed: %s", exc, exc_info=True
            )
            return []

    @staticmethod
    def _extract_price(hit: dict) -> float:
        """Extract the AED price from an Algolia hit."""
        try:
            price_data = hit.get("price", {})
            if isinstance(price_data, dict):
                aed = price_data.get("AED", {})
                if isinstance(aed, dict):
                    return float(aed.get("default", 0))
            return float(price_data) if price_data else 0.0
        except (TypeError, ValueError):
            return 0.0
