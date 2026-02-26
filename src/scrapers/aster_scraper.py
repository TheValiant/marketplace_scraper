# src/scrapers/aster_scraper.py

"""Scraper for myaster.com (UAE) using their Elasticsearch-based search API."""

import logging
import time
import urllib.parse

from curl_cffi import requests as curl_requests

from src.config.settings import Settings
from src.models.product import Product


class AsterScraper:
    """Scraper for myaster.com via their public search API.

    myAster is a Next.js app backed by an Elasticsearch search service
    at api.myaster.com.  The endpoint requires no authentication.
    """

    SEARCH_API = (
        "https://api.myaster.com/uae/ae/search/api/search"
        "?text={query}&productPageSize={page_size}"
        "&productPageFrom={page}"
    )
    PAGE_SIZE = 50
    BASE_PRODUCT_URL = "https://www.myaster.com/en/online-pharmacy"

    def __init__(self):
        self.logger = logging.getLogger("ecom_search.aster")
        self.settings = Settings()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def search(self, query: str) -> list[Product]:
        """Search myAster for products matching the query."""
        try:
            products: list[Product] = []
            encoded_query = urllib.parse.quote(query, safe="")
            headers = {
                **self.settings.DEFAULT_HEADERS,
                "Accept": "application/json",
                "Origin": "https://www.myaster.com",
                "Referer": "https://www.myaster.com/en/online-pharmacy",
            }

            for page in range(self.settings.MAX_PAGES):
                time.sleep(self.settings.REQUEST_DELAY)
                url = self.SEARCH_API.format(
                    query=encoded_query,
                    page_size=self.PAGE_SIZE,
                    page=page,
                )

                resp = None
                for attempt in range(self.settings.MAX_RETRIES):
                    try:
                        resp = self.session.get(
                            url,
                            headers=headers,
                            timeout=self.settings.REQUEST_TIMEOUT,
                        )
                        if resp.status_code == 200:
                            break
                        self.logger.warning(
                            "[aster] HTTP %d on attempt %d",
                            resp.status_code,
                            attempt + 1,
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "[aster] Request error on attempt %d: %s",
                            attempt + 1,
                            exc,
                            exc_info=True,
                        )
                        time.sleep(
                            self.settings.REQUEST_DELAY * (attempt + 1)
                        )

                if not resp or resp.status_code != 200:
                    self.logger.warning(
                        "[aster] Failed to fetch page %d", page
                    )
                    break

                data = resp.json()
                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    title = item.get("name", "N/A")
                    price = self._extract_price(item)
                    product_path = item.get("productUrl", "")
                    product_url = (
                        f"{self.BASE_PRODUCT_URL}{product_path}"
                        if product_path
                        else ""
                    )

                    products.append(
                        Product(
                            title=title,
                            price=price,
                            currency=item.get("currency", "AED") or "AED",
                            rating=str(item.get("avgRating", "")),
                            url=product_url,
                            source="aster",
                            image_url=item.get("small_image", ""),
                        )
                    )

                total_pages = data.get("totalPages", 1)
                if page + 1 >= total_pages:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[aster] Search failed: %s", exc, exc_info=True
            )
            return []

    @staticmethod
    def _extract_price(item: dict) -> float:
        """Extract the final price, preferring special_price over price."""
        try:
            special = item.get("special_price")
            if special is not None and special > 0:
                return float(special)
            return float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
