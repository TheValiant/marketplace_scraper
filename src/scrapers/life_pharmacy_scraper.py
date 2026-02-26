# src/scrapers/life_pharmacy_scraper.py

"""Scraper for lifepharmacy.com (UAE) using their REST product search API."""

import logging
import time
import urllib.parse

from curl_cffi import requests as curl_requests

from src.config.settings import Settings
from src.models.product import Product


class LifePharmacyScraper:
    """Scraper for lifepharmacy.com via their public REST search API.

    Life Pharmacy is a Nuxt.js SPA with a backend API at
    prodapp.lifepharmacy.com.  The search endpoint returns all
    matching products in a single response.
    """

    SEARCH_API = (
        "https://prodapp.lifepharmacy.com/api/v1/products/search/"
        "{query}?lang=ae-en"
    )
    BASE_PRODUCT_URL = "https://www.lifepharmacy.com/product"

    def __init__(self):
        self.logger = logging.getLogger("ecom_search.life_pharmacy")
        self.settings = Settings()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def search(self, query: str) -> list[Product]:
        """Search Life Pharmacy for products matching the query."""
        try:
            products: list[Product] = []
            encoded_query = urllib.parse.quote(query, safe="")
            url = self.SEARCH_API.format(query=encoded_query)
            headers = {
                **self.settings.DEFAULT_HEADERS,
                "Accept": "application/json",
                "Referer": "https://www.lifepharmacy.com/",
            }

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
                        "[life_pharmacy] HTTP %d on attempt %d",
                        resp.status_code,
                        attempt + 1,
                    )
                except Exception as exc:
                    self.logger.warning(
                        "[life_pharmacy] Request error on attempt %d: %s",
                        attempt + 1,
                        exc,
                        exc_info=True,
                    )
                    time.sleep(
                        self.settings.REQUEST_DELAY * (attempt + 1)
                    )

            if not resp or resp.status_code != 200:
                self.logger.warning("[life_pharmacy] Failed to fetch results")
                return []

            data = resp.json()
            items = (
                data.get("data", {}).get("products", [])
                if isinstance(data.get("data"), dict)
                else []
            )

            for item in items:
                title = item.get("title", "N/A")
                sale = item.get("sale", {}) or {}
                price = float(sale.get("offer_price", 0) or 0)
                currency = sale.get("currency", "AED") or "AED"
                slug = item.get("slug", "")
                product_url = (
                    f"{self.BASE_PRODUCT_URL}/{slug}" if slug else ""
                )
                images = item.get("images", {}) or {}
                image_url = images.get("featured_image", "")

                products.append(
                    Product(
                        title=title,
                        price=price,
                        currency=currency,
                        rating=str(item.get("rating", "")),
                        url=product_url,
                        source="life_pharmacy",
                        image_url=image_url,
                    )
                )

            return products
        except Exception as exc:
            self.logger.error(
                "[life_pharmacy] Search failed: %s", exc, exc_info=True
            )
            return []
