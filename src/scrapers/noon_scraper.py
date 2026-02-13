# src/scrapers/noon_scraper.py

"""Scraper for noon.com (UAE) using their internal search API."""

import json
import logging
import time

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

    def __init__(self):
        self.logger = logging.getLogger("ecom_search.noon")
        self.settings = Settings()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def search(self, query: str) -> list[Product]:
        """Search Noon for products matching the query."""
        try:
            products: list[Product] = []
            headers = {
                **self.settings.DEFAULT_HEADERS,
                "Referer": f"https://www.noon.com/uae-en/search/?q={query}",
                "Accept": "application/json",
                "X-Locale": "en-ae",
                "X-Content": "V6",
            }

            for page in range(1, self.settings.MAX_PAGES + 1):
                time.sleep(self.settings.REQUEST_DELAY)
                url = self.SEARCH_API.format(query=query, page=page)

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

                if not resp or resp.status_code != 200:
                    self.logger.warning("[noon] Failed to fetch page %d", page)
                    break

                data = resp.json()
                hits = data.get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    title = (
                        hit.get("name")
                        or hit.get("name_en")
                        or hit.get("title", "N/A")
                    )
                    price = float(
                        hit.get("sale_price")
                        or hit.get("price", 0)
                    )
                    sku = hit.get("sku", "")
                    product_url = (
                        f"https://www.noon.com/uae-en/{sku}/p/"
                        if sku
                        else ""
                    )

                    products.append(
                        Product(
                            title=title,
                            price=price,
                            currency="AED",
                            rating=str(
                                hit.get("rating", "")
                            ),
                            url=product_url,
                            source="noon",
                            image_url=hit.get("image_url", ""),
                        )
                    )

                # Check if there are more pages
                total_pages = data.get("nbPages", 1)
                if page >= total_pages:
                    break

            return products
        except Exception as e:
            self.logger.error("[noon] Search failed: %s", e, exc_info=True)
            return []
