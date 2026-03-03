# src/scrapers/carrefour_scraper.py

"""Scraper for carrefouruae.com (UAE) via Next.js data / HTML."""

import json
import time
import urllib.parse
from typing import Any, cast

from bs4 import BeautifulSoup, Tag
from curl_cffi import requests as curl_requests

from src.models.product import Product
from src.scrapers import base_scraper as _base_mod
from src.scrapers.base_scraper import BaseScraper


class CarrefourScraper(BaseScraper):
    """Scraper for Carrefour UAE (Grocery).

    Uses a dual-fetch approach (curl_cffi then cloudscraper)
    to bypass aggressive Cloudflare protections.  Extracts
    products from ``__NEXT_DATA__`` JSON first, falling back
    to CSS selectors from ``selectors.json``.
    """

    BASE_URL = "https://www.carrefouruae.com"
    SEARCH_URL = (
        "https://www.carrefouruae.com/mafuae/en/"
        "search?q={query}&currentPage={page}"
    )

    def __init__(self) -> None:
        super().__init__("carrefour")
        _cs: Any = _base_mod.cloudscraper
        self._cs_scraper: Any = _cs.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            },
        )

    def _get_homepage(self) -> str:
        """Return the Carrefour UAE homepage URL."""
        return f"{self.BASE_URL}/mafuae/en/"

    # ----------------------------------------------------------
    # Response validation
    # ----------------------------------------------------------

    def _validate_response(
        self, resp: curl_requests.Response,
    ) -> bool:
        """Accept large Carrefour pages that contain product markers."""
        text = resp.text
        if (
            len(text) > 50_000
            and "__NEXT_DATA__" in text
        ):
            return True
        return super()._validate_response(resp)

    @staticmethod
    def _validate_fallback_text(text: str) -> bool:
        """Return False when cloudscraper receives a bot challenge."""
        lower = text.lower()
        if (
            "challenges.cloudflare.com" in lower
            or "enable javascript" in lower
        ):
            return False
        return True

    # ----------------------------------------------------------
    # Hybrid page fetch (curl_cffi → cloudscraper)
    # ----------------------------------------------------------

    def _get_page_hybrid(
        self, url: str,
    ) -> BeautifulSoup | None:
        """Fetch page via curl_cffi, falling back to cloudscraper."""
        if self._circuit_open:
            return None
        self._wait()

        headers: dict[str, str] = {
            **self._session_headers,
            "Referer": self._get_homepage(),
        }

        # Primary: curl_cffi
        resp = self._fetch_get(url, headers)
        if resp is not None:
            return BeautifulSoup(resp.text, "lxml")

        self.logger.info(
            "[carrefour] curl_cffi exhausted, "
            "attempting cloudscraper fallback",
        )
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                cs_resp: Any = self._cs_scraper.get(
                    url,
                    headers=headers,
                    timeout=self._request_timeout,
                )
                if cs_resp.status_code == 200:
                    text: str = str(cs_resp.text)
                    if not self._validate_fallback_text(
                        text,
                    ):
                        self._escalate_delay()
                        time.sleep(self._current_delay)
                        continue
                    return BeautifulSoup(text, "lxml")

                self.logger.warning(
                    "[carrefour] cloudscraper HTTP %d "
                    "on attempt %d",
                    cs_resp.status_code,
                    attempt + 1,
                )
            except Exception as exc:
                self.logger.warning(
                    "[carrefour] cloudscraper error "
                    "on attempt %d: %s",
                    attempt + 1,
                    exc,
                )
                time.sleep(
                    self._current_delay * (attempt + 1)
                )
        return None

    # ----------------------------------------------------------
    # __NEXT_DATA__ JSON extraction (primary)
    # ----------------------------------------------------------

    def _parse_next_data(
        self, soup: BeautifulSoup,
    ) -> list[Product]:
        """Extract products from Next.js hydration data."""
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

        products: list[Product] = []

        # Carrefour stores products in Apollo state
        initial_state: dict[str, Any] = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialState", {})
        )
        for raw_val in initial_state.values():
            if not isinstance(raw_val, dict):
                continue
            val = cast(dict[str, Any], raw_val)
            if val.get("__typename") != "Product":
                continue

            title = str(val.get("name", "N/A"))
            price_obj: object = val.get("price", {})
            price = 0.0
            if isinstance(price_obj, dict):
                p_dict = cast(
                    dict[str, Any], price_obj
                )
                price = float(
                    p_dict.get("value", 0) or 0
                )
            elif isinstance(
                price_obj, (int, float)
            ):
                price = float(price_obj)

            url_path = str(val.get("url", ""))
            full_url = (
                f"{self.BASE_URL}{url_path}"
                if url_path
                else ""
            )
            image_url = str(
                val.get("imageUrl", "")
            )

            products.append(
                Product(
                    title=title,
                    price=price,
                    currency="AED",
                    url=full_url,
                    source="carrefour",
                    image_url=image_url,
                )
            )

        return products

    # ----------------------------------------------------------
    # CSS fallback
    # ----------------------------------------------------------

    def _parse_css_card(self, card: Tag) -> Product:
        """Fallback parser using CSS selectors from JSON."""
        title_el = card.select_one(
            self.selectors.get("title", "")
        )
        price_el = card.select_one(
            self.selectors.get("price", "")
        )
        url_el = card.select_one(
            self.selectors.get("url", "")
        )

        href = ""
        if url_el:
            raw_href = url_el.get("href", "")
            href = str(raw_href) if raw_href else ""
            if href and not href.startswith("http"):
                href = f"{self.BASE_URL}{href}"

        img_el = card.select_one("img")
        image_url = ""
        if img_el:
            raw_src = img_el.get("src", "")
            image_url = (
                str(raw_src) if raw_src else ""
            )

        return Product(
            title=(
                title_el.get_text(strip=True)
                if title_el
                else "N/A"
            ),
            price=self.extract_price(
                price_el.get_text()
                if price_el
                else ""
            ),
            currency="AED",
            url=href,
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

            # Carrefour pagination is 0-indexed
            for page in range(self.settings.MAX_PAGES):
                url = self.SEARCH_URL.format(
                    query=encoded, page=page
                )
                self.logger.info(
                    "[carrefour] Fetching page %d "
                    "(%d so far)",
                    page,
                    len(products),
                )

                soup = self._get_page_hybrid(url)
                if not soup:
                    break

                # Primary: __NEXT_DATA__ JSON
                page_products = self._parse_next_data(
                    soup
                )

                # Fallback: CSS selectors
                if not page_products:
                    card_sel = self.selectors.get(
                        "product_card", ""
                    )
                    if card_sel:
                        cards = soup.select(card_sel)
                        page_products = [
                            self._parse_css_card(c)
                            for c in cards
                        ]

                if not page_products:
                    break

                products.extend(page_products)

            return products
        except Exception as exc:
            self.logger.error(
                "[carrefour] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
