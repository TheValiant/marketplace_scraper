# src/scrapers/iherb_scraper.py

"""Scraper for ae.iherb.com (UAE) via full-page HTML with AED locale cookie."""

import json
import time
import urllib.parse
from typing import Any, cast

from bs4 import BeautifulSoup, Tag
from curl_cffi import requests as curl_requests

from src.models.product import Product
from src.scrapers import base_scraper as _base_mod
from src.scrapers.base_scraper import BaseScraper


class IherbScraper(BaseScraper):
    """Scraper for ae.iherb.com with AED locale cookie.

    Uses the ``ih-preference`` cookie to get AED prices and
    ``ae.iherb.com`` URLs in the server-rendered HTML.
    Product data is extracted from CSS selectors on
    ``div.product-cell-container`` cards, with ``span.price``
    providing AED-denominated pricing.

    Falls back to cloudscraper if curl_cffi fails.
    """

    SEARCH_URL = (
        "https://ae.iherb.com/search?kw={query}&p={page}"
    )
    BASE_URL = "https://ae.iherb.com"
    _LOCALE_COOKIE = (
        "ih-preference="
        "country%3DAE%26currency%3DAED"
        "%26language%3Den-US%26store%3D0"
    )

    def __init__(self) -> None:
        super().__init__("iherb")
        _cs: Any = _base_mod.cloudscraper
        self._cs_scraper: Any = _cs.create_scraper()

    def _get_homepage(self) -> str:
        """Return the iHerb UAE homepage URL."""
        return "https://ae.iherb.com/"

    def _validate_response(
        self, resp: curl_requests.Response,
    ) -> bool:
        """Allow content-rich iHerb pages that include Cloudflare CDN refs."""
        text = resp.text
        if (
            len(text) > 100_000
            and "product-cell-container" in text
        ):
            return True
        return super()._validate_response(resp)

    # ------------------------------------------------------------------
    # Full-page fetch (primary) — AED prices via locale cookie
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build headers with AED locale cookie."""
        return {
            **self.settings.DEFAULT_HEADERS,
            "Referer": self._get_homepage(),
            "Cookie": self._LOCALE_COOKIE,
        }

    def _fetch_primary(
        self, url: str,
    ) -> BeautifulSoup | None:
        """Fetch full page via curl_cffi with AED cookie."""
        if self._circuit_open:
            return None
        headers = self._build_headers()
        resp = self._fetch_get(url, headers)
        if resp is None:
            return None
        return BeautifulSoup(resp.text, "lxml")

    # ------------------------------------------------------------------
    # Cloudscraper fetch (fallback) — solves JS challenges
    # ------------------------------------------------------------------

    def _fetch_cloudscraper(
        self, url: str,
    ) -> BeautifulSoup | None:
        """Fetch a full page via cloudscraper as fallback."""
        headers: dict[str, str] = {
            **self.settings.DEFAULT_HEADERS,
            "Referer": self._get_homepage(),
            "Cookie": self._LOCALE_COOKIE,
        }
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp: Any = self._cs_scraper.get(
                    url,
                    headers=headers,
                    timeout=self._request_timeout,
                )
                if resp.status_code == 200:
                    text: str = str(resp.text)
                    lower = text.lower()
                    if (
                        "challenges.cloudflare.com" in lower
                        or "just a moment" in lower
                    ):
                        self.logger.warning(
                            "[iherb] Cloudflare challenge "
                            "on cloudscraper attempt %d",
                            attempt + 1,
                        )
                        self._escalate_delay()
                        time.sleep(self._current_delay)
                        continue
                    return BeautifulSoup(text, "lxml")

                self.logger.warning(
                    "[iherb] cloudscraper HTTP %d "
                    "on attempt %d",
                    resp.status_code,
                    attempt + 1,
                )
            except Exception as exc:
                self.logger.warning(
                    "[iherb] cloudscraper error on "
                    "attempt %d: %s",
                    attempt + 1,
                    exc,
                )
                time.sleep(
                    self._current_delay * (attempt + 1)
                )
        return None

    # ------------------------------------------------------------------
    # Combined page fetch (curl_cffi then cloudscraper)
    # ------------------------------------------------------------------

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """Fetch page: curl_cffi first, cloudscraper fallback."""
        if self._circuit_open:
            return None
        self._wait()

        soup = self._fetch_primary(url)
        if soup is not None:
            return soup

        self.logger.info(
            "[iherb] Primary fetch failed, "
            "falling back to cloudscraper",
        )
        return self._fetch_cloudscraper(url)

    # ------------------------------------------------------------------
    # __NEXT_DATA__ JSON extraction (primary)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_next_data(
        soup: BeautifulSoup,
    ) -> list[dict[str, Any]]:
        """Extract product list from __NEXT_DATA__ JSON."""
        script = soup.find(
            "script", id="__NEXT_DATA__"
        )
        if not script or not script.string:
            return []
        try:
            data: dict[str, Any] = json.loads(
                script.string
            )
        except (json.JSONDecodeError, TypeError):
            return []

        page_props: dict[str, Any] = (
            data.get("props", {})
            .get("pageProps", {})
        )
        # Search common iHerb JSON paths
        for key in (
            "products", "searchData",
            "results", "catalogResults",
        ):
            raw: object = page_props.get(key)
            if not isinstance(raw, list) or not raw:
                continue
            items = cast(list[dict[str, Any]], raw)
            return items
        return []

    @staticmethod
    def _parse_json_product(
        item: dict[str, Any],
    ) -> Product:
        """Convert a __NEXT_DATA__ product dict to Product."""
        # Title fallback: title -> name -> productName
        title = str(
            item.get("title")
            or item.get("name")
            or item.get("productName")
            or "Unknown"
        )

        # Price fallback: discountPrice -> price -> salePrice
        discount = float(item.get("discountPrice", 0) or 0)
        base = float(item.get("price", 0) or 0)
        sale = float(item.get("salePrice", 0) or 0)
        price = discount or base or sale

        # URL handling
        url = str(item.get("url", "") or "")
        if url and not url.startswith("http"):
            url = IherbScraper.BASE_URL + url

        rating = str(item.get("rating", "") or "")
        image_url = str(
            item.get("imageUrl")
            or item.get("image")
            or ""
        )

        return Product(
            title=title,
            price=price,
            currency="AED",
            rating=rating,
            url=url,
            source="iherb",
            image_url=image_url,
        )

    def _parse_products(
        self, soup: BeautifulSoup,
    ) -> list[Product]:
        """Extract products: JSON first, then CSS selectors."""
        # Primary: __NEXT_DATA__ JSON extraction
        items = self._extract_next_data(soup)
        if items:
            return [
                self._parse_json_product(i)
                for i in items
            ]

        # Secondary: CSS selector extraction
        card_sel = self.selectors.get(
            "product_card", "div.product-cell-container"
        )
        cards = soup.select(card_sel)
        return [self._parse_card(c) for c in cards]

    # ------------------------------------------------------------------
    # CSS-selector fallback (kept for resilience)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rating(raw: str) -> str:
        """Extract numeric rating from title like '4.7/5 - 307,383 Reviews'."""
        if not raw:
            return ""
        parts = raw.split("/")
        if len(parts) >= 2:
            return parts[0].strip()
        return raw.strip()

    def _parse_card(self, card: Tag) -> Product:
        """Parse a single product card using CSS selectors."""
        title_el = card.select_one(
            self.selectors.get("title", "")
        )
        price_el = card.select_one(
            self.selectors.get("price", "")
        )
        rating_el = card.select_one(
            self.selectors.get("rating", "")
        )
        url_el = card.select_one(
            self.selectors.get("url", "")
        )

        href = ""
        if url_el:
            raw_href = url_el.get("href", "")
            href = str(raw_href) if raw_href else ""
            if href and not href.startswith("http"):
                href = self.BASE_URL + href

        rating_val = ""
        if rating_el:
            raw_title = rating_el.get("title", "")
            rating_val = self._parse_rating(
                str(raw_title) if raw_title else ""
            )

        img_el = card.select_one("img")
        image_url = ""
        if img_el:
            raw_src = img_el.get("src", "")
            image_url = str(raw_src) if raw_src else ""

        return Product(
            title=(
                title_el.get_text(strip=True)
                if title_el
                else "N/A"
            ),
            price=self.extract_price(
                price_el.get_text() if price_el else ""
            ),
            currency="AED",
            rating=rating_val,
            url=href,
            source="iherb",
            image_url=image_url,
        )

    # ------------------------------------------------------------------
    # Public search entry-point
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[Product]:
        """Search iHerb UAE for products matching the query."""
        try:
            products: list[Product] = []
            encoded = urllib.parse.quote_plus(query)

            for page in range(
                1, self.settings.MAX_PAGES + 1
            ):
                url = self.SEARCH_URL.format(
                    query=encoded, page=page
                )
                self.logger.info(
                    "[iherb] Fetching page %d (%d so far)",
                    page,
                    len(products),
                )

                soup = self._get_page(url)
                if not soup:
                    break

                page_products = self._parse_products(soup)

                if not page_products:
                    break

                products.extend(page_products)

                # Stop if no next-page indicator
                next_sel = self.selectors.get(
                    "next_page", ""
                )
                if next_sel and not soup.select_one(
                    next_sel
                ):
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[iherb] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
