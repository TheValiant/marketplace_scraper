# src/scrapers/binsina_scraper.py

"""Scraper for binsina.ae (UAE) via their Algolia-powered search API."""

import json
import re
import time
from typing import Any, cast

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class BinSinaScraper(BaseScraper):
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

    def __init__(self) -> None:
        super().__init__("binsina")
        self.api_key: str = ""
        self._api_key_expires_at: float = 0.0

    def _get_homepage(self) -> str:
        """Return the BinSina homepage URL."""
        return self.HOMEPAGE_URL

    def refresh_api_key(self) -> bool:
        """Fetch a fresh Algolia API key from the BinSina homepage."""
        try:
            headers: dict[str, str] = {
                **self.settings.DEFAULT_HEADERS,
                "Referer": "https://binsina.ae/",
            }
            resp = self.session.get(
                self.HOMEPAGE_URL,
                headers=headers,
                timeout=self.settings.REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                self.logger.warning(
                    "[binsina] Homepage returned HTTP %d",
                    resp.status_code,
                )
                return False

            match = re.search(
                r"window\.algoliaConfig\s*=\s*(\{.*?\});",
                resp.text,
                re.DOTALL,
            )
            if not match:
                self.logger.error(
                    "[binsina] Could not find algoliaConfig"
                )
                return False

            config: dict[str, Any] = json.loads(match.group(1))
            self.api_key = str(config.get("apiKey", ""))
            if not self.api_key:
                self.logger.error(
                    "[binsina] Empty API key in algoliaConfig"
                )
                return False

            self.logger.info("[binsina] Refreshed Algolia API key")
            self._api_key_expires_at = (
                time.time()
                + self.settings.API_KEY_CACHE_TTL
            )
            return True
        except Exception as exc:
            self.logger.error(
                "[binsina] Failed to refresh API key: %s",
                exc,
                exc_info=True,
            )
            return False

    @staticmethod
    def _parse_hit(hit: dict[str, Any]) -> Product:
        """Parse a single Algolia hit into a Product."""
        title = str(hit.get("name", "N/A"))
        price = BinSinaScraper._extract_price(hit)
        product_url = str(hit.get("url", ""))
        if product_url and not product_url.startswith("http"):
            product_url = (
                BinSinaScraper.BASE_PRODUCT_URL + product_url
            )
        return Product(
            title=title,
            price=price,
            currency="AED",
            rating=str(hit.get("rating_summary", "")),
            url=product_url,
            source="binsina",
            image_url=str(hit.get("image_url", "")),
        )

    def search(self, query: str) -> list[Product]:
        """Search BinSina for products matching the query."""
        try:
            is_expired = (
                time.time() >= self._api_key_expires_at
            )
            if (not self.api_key or is_expired) and (
                not self.refresh_api_key()
            ):
                self.logger.error("[binsina] No API key available")
                return []

            products: list[Product] = []
            url = self.ALGOLIA_URL.format(
                app_id=self.ALGOLIA_APP_ID,
                index=self.ALGOLIA_INDEX,
            )
            headers: dict[str, str] = {
                "X-Algolia-Application-Id": self.ALGOLIA_APP_ID,
                "X-Algolia-API-Key": self.api_key,
                "Content-Type": "application/json",
                "Referer": self.HOMEPAGE_URL,
            }

            for page in range(self.settings.MAX_PAGES):
                self._wait()
                payload: dict[str, Any] = {
                    "query": query,
                    "page": page,
                    "hitsPerPage": 40,
                }

                resp = self._fetch_post(url, headers, payload)
                if not resp:
                    self.logger.warning(
                        "[binsina] Failed page %d", page
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
                if page + 1 >= total_pages:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[binsina] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []

    @staticmethod
    def _extract_price(hit: dict[str, Any]) -> float:
        """Extract the AED price from an Algolia hit."""
        try:
            price_data: Any = hit.get("price", {})
            if isinstance(price_data, dict):
                price_map = cast(
                    dict[str, Any], price_data
                )
                aed: Any = price_map.get("AED", {})
                if isinstance(aed, dict):
                    aed_map = cast(
                        dict[str, Any], aed
                    )
                    return float(
                        aed_map.get("default", 0)
                    )
                return 0.0
            return float(price_data) if price_data else 0.0
        except (TypeError, ValueError):
            return 0.0
