# src/scrapers/aster_scraper.py

"""Scraper for myaster.com (UAE) via Elasticsearch search API."""

import json
import urllib.parse
from typing import Any

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class AsterScraper(BaseScraper):
    """Scraper for myaster.com via their public search API.

    myAster is a Next.js app backed by an Elasticsearch search
    service at api.myaster.com. No authentication required.
    """

    SEARCH_API = (
        "https://api.myaster.com/uae/ae/search/api/search"
        "?text={query}&productPageSize={page_size}"
        "&productPageFrom={page}"
    )
    PAGE_SIZE = 50
    BASE_URL = "https://www.myaster.com/en/online-pharmacy"

    def __init__(self) -> None:
        super().__init__("aster")

    def _get_homepage(self) -> str:
        """Return the Aster homepage URL."""
        return self.BASE_URL

    def _parse_item(self, item: dict[str, Any]) -> Product:
        """Parse a single API item into a Product."""
        title = str(item.get("name", "N/A"))
        price = self._extract_price(item)
        product_path = str(item.get("productUrl", "") or "")
        product_url = (
            f"{self.BASE_URL}{product_path}"
            if product_path
            else ""
        )
        currency = str(
            item.get("currency", "AED") or "AED"
        )
        return Product(
            title=title,
            price=price,
            currency=currency,
            rating=str(item.get("avgRating", "")),
            url=product_url,
            source="aster",
            image_url=str(item.get("small_image", "")),
        )

    def search(self, query: str) -> list[Product]:
        """Search myAster for products matching the query."""
        try:
            products: list[Product] = []
            encoded = urllib.parse.quote(query, safe="")
            headers: dict[str, str] = {
                **self.settings.DEFAULT_HEADERS,
                "Accept": "application/json",
                "Origin": "https://www.myaster.com",
                "Referer": self.BASE_URL,
            }

            for page in range(self.settings.MAX_PAGES):
                self._wait()
                url = self.SEARCH_API.format(
                    query=encoded,
                    page_size=self.PAGE_SIZE,
                    page=page,
                )

                resp = self._fetch_get(url, headers)
                if not resp:
                    self.logger.warning(
                        "[aster] Failed page %d", page
                    )
                    break

                data: dict[str, Any] = json.loads(resp.text)
                items: list[dict[str, Any]] = data.get(
                    "data", []
                )
                if not items:
                    break

                for item in items:
                    products.append(self._parse_item(item))

                total: int = int(
                    data.get("totalPages", 1)
                )
                if page + 1 >= total:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[aster] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []

    @staticmethod
    def _extract_price(item: dict[str, Any]) -> float:
        """Extract price, preferring special_price over price."""
        try:
            special: Any = item.get("special_price")
            if special is not None and float(special) > 0:
                return float(special)
            return float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
