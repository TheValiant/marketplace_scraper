# src/scrapers/noon_scraper.py

"""Scraper for noon.com (UAE) using their internal search API."""

import json
from typing import Any

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class NoonScraper(BaseScraper):
    """Scraper for noon.com (UAE) via internal JSON API.

    Noon is a Next.js SPA that returns 403 for HTML scraping.
    This scraper uses their internal catalog search API instead.
    """

    SEARCH_API = (
        "https://www.noon.com/_svc/catalog/api/v3/u/"
        "search?q={query}&page={page}&limit=40&locale=en-ae"
    )

    def __init__(self) -> None:
        super().__init__("noon")

    def _get_homepage(self) -> str:
        """Return the Noon homepage URL."""
        return "https://www.noon.com/uae-en/"

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
                self._wait()
                url = self.SEARCH_API.format(
                    query=query, page=page
                )

                resp = self._fetch_get(url, headers)
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
