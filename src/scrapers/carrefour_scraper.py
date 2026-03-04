# src/scrapers/carrefour_scraper.py

"""Scraper for carrefouruae.com (UAE) via Constructor.io search API."""

import json
import urllib.parse
from typing import Any

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class CarrefourScraper(BaseScraper):
    """Scraper for Carrefour UAE (Grocery).

    Queries the Constructor.io search API that powers the
    Carrefour UAE storefront.  Returns structured JSON with
    product title, price, URL and image — no HTML parsing
    required.
    """

    BASE_URL = "https://www.carrefouruae.com"
    _CNSTRC_SEARCH_URL = (
        "https://ac.cnstrc.com/search/{query}"
    )
    _CNSTRC_KEY = "key_XDncjMu1MeYJOCiU"
    _PAGE_SIZE = 40

    def __init__(self) -> None:
        super().__init__("carrefour")

    def _get_homepage(self) -> str:
        """Return the Carrefour UAE homepage URL."""
        return f"{self.BASE_URL}/mafuae/en/"

    # ----------------------------------------------------------
    # JSON result parsing
    # ----------------------------------------------------------

    @staticmethod
    def _parse_result(
        item: dict[str, Any],
    ) -> Product | None:
        """Map a single Constructor.io result to a Product."""
        title = str(item.get("value", "")).strip()
        if not title:
            return None
        data: dict[str, Any] = item.get("data", {})
        price = float(data.get("price", 0) or 0)
        url = str(data.get("url", ""))
        image_url = str(data.get("image_url", ""))
        return Product(
            title=title,
            price=price,
            currency="AED",
            url=url,
            source="carrefour",
            image_url=image_url,
        )

    # ----------------------------------------------------------
    # Public search entry-point
    # ----------------------------------------------------------

    def search(self, query: str) -> list[Product]:
        """Search Carrefour UAE for grocery products."""
        try:
            products: list[Product] = []
            encoded = urllib.parse.quote_plus(query)
            api_url = self._CNSTRC_SEARCH_URL.format(
                query=encoded,
            )
            headers: dict[str, str] = {
                **self._session_headers,
                "Accept": "*/*",
                "Referer": self._get_homepage(),
                "Origin": self.BASE_URL,
            }

            for page in range(
                1, self.settings.MAX_PAGES + 1
            ):
                params = (
                    f"?key={self._CNSTRC_KEY}"
                    f"&page={page}"
                    f"&num_results_per_page="
                    f"{self._PAGE_SIZE}"
                )
                url = f"{api_url}{params}"
                self.logger.info(
                    "[carrefour] Fetching page %d "
                    "(%d so far)",
                    page,
                    len(products),
                )

                self._wait()
                resp = self._fetch_get(url, headers)
                if resp is None:
                    break

                payload: dict[str, Any] = json.loads(
                    resp.text,
                )
                response: dict[str, Any] = (
                    payload.get("response", {})
                )
                results: list[dict[str, Any]] = (
                    response.get("results", [])
                )

                if not results:
                    break

                for item in results:
                    product = self._parse_result(item)
                    if product is not None:
                        products.append(product)

                if len(results) < self._PAGE_SIZE:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[carrefour] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
