# src/scrapers/life_pharmacy_scraper.py

"""Scraper for lifepharmacy.com (UAE) via their REST search API."""

import json
import logging
import time
import urllib.parse
from typing import Any, cast

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

    def __init__(self) -> None:
        self.logger = logging.getLogger(
            "ecom_search.life_pharmacy"
        )
        self.settings = Settings()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def _fetch(
        self,
        url: str,
        headers: dict[str, str],
    ) -> curl_requests.Response | None:
        """GET request with retries."""
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
                    "[life_pharmacy] HTTP %d on attempt %d",
                    resp.status_code,
                    attempt + 1,
                )
            except Exception as exc:
                self.logger.warning(
                    "[life_pharmacy] Request error attempt %d: %s",
                    attempt + 1,
                    exc,
                    exc_info=True,
                )
                time.sleep(
                    self.settings.REQUEST_DELAY * (attempt + 1)
                )
        return None

    @staticmethod
    def _parse_item(item: dict[str, Any]) -> Product:
        """Parse a single API item into a Product."""
        title = str(item.get("title", "N/A"))
        sale: dict[str, Any] = item.get("sale", {}) or {}
        price = float(sale.get("offer_price", 0) or 0)
        currency = str(sale.get("currency", "AED") or "AED")
        slug = str(item.get("slug", ""))
        product_url = (
            f"{LifePharmacyScraper.BASE_PRODUCT_URL}/{slug}"
            if slug
            else ""
        )
        images: dict[str, Any] = (
            item.get("images", {}) or {}
        )
        image_url = str(images.get("featured_image", ""))
        return Product(
            title=title,
            price=price,
            currency=currency,
            rating=str(item.get("rating", "")),
            url=product_url,
            source="life_pharmacy",
            image_url=image_url,
        )

    def search(self, query: str) -> list[Product]:
        """Search Life Pharmacy for products matching the query."""
        try:
            encoded = urllib.parse.quote(query, safe="")
            url = self.SEARCH_API.format(query=encoded)
            headers: dict[str, str] = {
                **self.settings.DEFAULT_HEADERS,
                "Accept": "application/json",
                "Referer": "https://www.lifepharmacy.com/",
            }

            resp = self._fetch(url, headers)
            if not resp:
                self.logger.warning(
                    "[life_pharmacy] Failed to fetch results"
                )
                return []

            data: dict[str, Any] = json.loads(resp.text)
            raw_data: Any = data.get("data")
            items: list[dict[str, Any]] = (
                cast(
                    dict[str, Any], raw_data
                ).get("products", [])
                if isinstance(raw_data, dict)
                else []
            )

            return [self._parse_item(item) for item in items]
        except Exception as exc:
            self.logger.error(
                "[life_pharmacy] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
