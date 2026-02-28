# src/scrapers/iherb_scraper.py

"""Scraper for ae.iherb.com (UAE) via AJAX partial-HTML endpoint."""

import time
import urllib.parse
from typing import Any

import cloudscraper  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class IherbScraper(BaseScraper):
    """Scraper for ae.iherb.com using the AJAX search endpoint.

    iHerb returns a lightweight HTML fragment (no Cloudflare
    challenge) when the ``X-Requested-With: XMLHttpRequest``
    header is present.  Product data is extracted from
    ``data-ga-*`` attributes on ``a.absolute-link`` elements
    inside ``div.product-cell-container`` cards.

    Falls back to cloudscraper full-page rendering if the
    AJAX approach fails.
    """

    SEARCH_URL = (
        "https://ae.iherb.com/search?kw={query}&p={page}"
    )
    BASE_URL = "https://ae.iherb.com"

    def __init__(self) -> None:
        super().__init__("iherb")
        _cs: Any = cloudscraper
        self._cs_scraper: Any = _cs.create_scraper()

    def _get_homepage(self) -> str:
        """Return the iHerb UAE homepage URL."""
        return "https://ae.iherb.com/"

    # ------------------------------------------------------------------
    # AJAX fetch (primary) — bypasses Cloudflare
    # ------------------------------------------------------------------

    def _ajax_headers(self) -> dict[str, str]:
        """Build headers for the AJAX partial-HTML endpoint."""
        return {
            **self.settings.DEFAULT_HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self._get_homepage(),
        }

    def _fetch_ajax(
        self, url: str,
    ) -> BeautifulSoup | None:
        """Fetch a page via the AJAX endpoint using curl_cffi."""
        if self._circuit_open:
            return None
        headers = self._ajax_headers()
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
        }
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp: Any = self._cs_scraper.get(
                    url,
                    headers=headers,
                    timeout=self.settings.REQUEST_TIMEOUT,
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
    # Combined page fetch (AJAX then cloudscraper)
    # ------------------------------------------------------------------

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """Fetch page: AJAX first, cloudscraper fallback."""
        if self._circuit_open:
            return None
        self._wait()

        soup = self._fetch_ajax(url)
        if soup is not None:
            # AJAX succeeded — return even if no products
            # (legitimate empty result for unknown queries)
            return soup

        self.logger.info(
            "[iherb] AJAX fetch failed, "
            "falling back to cloudscraper",
        )
        return self._fetch_cloudscraper(url)

    # ------------------------------------------------------------------
    # Product extraction from data-ga-* attributes (primary)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ga_card(card: Tag) -> Product | None:
        """Extract product data from data-ga-* attributes."""
        link = card.select_one("a.absolute-link")
        if not link:
            return None

        title = str(link.get("title", "") or "")
        if not title:
            title_el = card.select_one("div.product-title")
            title = (
                title_el.get_text(strip=True)
                if title_el
                else "N/A"
            )

        price_raw = str(
            link.get("data-ga-discount-price", "0")
        )
        price = BaseScraper.extract_price(price_raw)

        href = str(link.get("href", "") or "")
        if href and not href.startswith("http"):
            href = IherbScraper.BASE_URL + href

        brand = str(
            link.get("data-ga-brand-name", "") or ""
        )
        rating_el = card.select_one("a.rating-count")
        rating_text = (
            rating_el.get_text(strip=True)
            if rating_el
            else ""
        )

        img_el = card.select_one("img[itemprop='image']")
        image_url = ""
        if img_el:
            image_url = str(img_el.get("src", "") or "")

        full_title = (
            f"{brand}, {title}" if brand and brand
            not in title else title
        )

        return Product(
            title=full_title,
            price=price,
            currency="AED",
            rating=rating_text,
            url=href,
            source="iherb",
            image_url=image_url,
        )

    def _parse_products(
        self, soup: BeautifulSoup,
    ) -> list[Product]:
        """Extract products from HTML using data-ga-* attrs."""
        card_sel = self.selectors.get(
            "product_card", "div.product-cell-container"
        )
        cards = soup.select(card_sel)
        products: list[Product] = []
        for card in cards:
            product = self._parse_ga_card(card)
            if product:
                products.append(product)
        return products

    # ------------------------------------------------------------------
    # CSS-selector fallback (kept for resilience)
    # ------------------------------------------------------------------

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
            rating_val = str(raw_title) if raw_title else ""

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

                # Primary: data-ga-* attribute extraction
                page_products = self._parse_products(soup)
                if not page_products:
                    # Fallback: plain CSS selectors
                    card_sel = self.selectors.get(
                        "product_card", ""
                    )
                    if card_sel:
                        cards = soup.select(card_sel)
                        page_products = [
                            self._parse_card(c)
                            for c in cards
                        ]

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
