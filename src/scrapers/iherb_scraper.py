# src/scrapers/iherb_scraper.py

"""Scraper for ae.iherb.com (UAE) via embedded Next.js JSON data."""

import json
import urllib.parse
from typing import Any, cast

from bs4 import BeautifulSoup, Tag

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class IherbScraper(BaseScraper):
    """Scraper for ae.iherb.com via embedded __NEXT_DATA__ JSON.

    iHerb is a Next.js React application protected by Cloudflare.
    Product data is pre-loaded into a ``<script id="__NEXT_DATA__">``
    tag.  When that tag is absent, CSS selectors from selectors.json
    are used as a fallback.
    """

    SEARCH_URL = (
        "https://ae.iherb.com/search?kw={query}&p={page}"
    )
    BASE_URL = "https://ae.iherb.com"

    def __init__(self) -> None:
        super().__init__("iherb")

    def _get_homepage(self) -> str:
        """Return the iHerb UAE homepage URL."""
        return "https://ae.iherb.com/"

    # ------------------------------------------------------------------
    # Primary: extract from __NEXT_DATA__ JSON
    # ------------------------------------------------------------------

    @staticmethod
    def _find_products_in_json(
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Walk common Next.js paths to locate the product list."""
        props: dict[str, Any] = data.get("props", {})
        page_props: dict[str, Any] = props.get(
            "pageProps", {}
        )

        # Try several known paths
        for key in (
            "products",
            "searchData",
            "results",
            "catalogResults",
        ):
            candidate: Any = page_props.get(key)
            if isinstance(candidate, list) and candidate:
                typed_list = cast(
                    list[dict[str, Any]], candidate
                )
                return typed_list
            if isinstance(candidate, dict):
                typed_dict = cast(
                    dict[str, Any], candidate
                )
                inner: Any = typed_dict.get("products")
                if isinstance(inner, list):
                    return cast(
                        list[dict[str, Any]], inner
                    )

        return []

    @staticmethod
    def _parse_json_product(
        item: dict[str, Any],
    ) -> Product:
        """Parse a single product dict from the JSON payload."""
        title = str(
            item.get("title")
            or item.get("name")
            or item.get("productName", "N/A")
        )
        price = IherbScraper._extract_item_price(item)
        product_url = str(item.get("url", "") or "")
        if product_url and not product_url.startswith("http"):
            product_url = (
                IherbScraper.BASE_URL + product_url
            )
        return Product(
            title=title,
            price=price,
            currency="AED",
            rating=str(item.get("rating", "")),
            url=product_url,
            source="iherb",
            image_url=str(
                item.get("imageUrl")
                or item.get("image", "")
            ),
        )

    @staticmethod
    def _extract_item_price(
        item: dict[str, Any],
    ) -> float:
        """Extract a numeric price from various JSON shapes."""
        for key in ("discountPrice", "salePrice", "price"):
            raw: Any = item.get(key)
            if raw is None:
                continue
            if isinstance(raw, (int, float)):
                val = float(raw)
                if val > 0:
                    return val
            if isinstance(raw, str):
                val = BaseScraper.extract_price(raw)
                if val > 0:
                    return val
        return 0.0

    # ------------------------------------------------------------------
    # Fallback: CSS-selector scraping
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

    def _parse_from_selectors(
        self, soup: BeautifulSoup,
    ) -> list[Product]:
        """Extract products using CSS selectors (fallback)."""
        card_sel = self.selectors.get("product_card", "")
        if not card_sel:
            return []
        cards = soup.select(card_sel)
        return [self._parse_card(card) for card in cards]

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

                # Primary: __NEXT_DATA__ embedded JSON
                page_products = self._extract_from_json(
                    soup
                )
                if page_products:
                    products.extend(page_products)
                else:
                    # Fallback: CSS selectors
                    css_products = (
                        self._parse_from_selectors(soup)
                    )
                    if css_products:
                        products.extend(css_products)
                    else:
                        # No products found on this page
                        break

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

    def _extract_from_json(
        self, soup: BeautifulSoup,
    ) -> list[Product]:
        """Try to extract products from __NEXT_DATA__ script tag."""
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []

        try:
            data: dict[str, Any] = json.loads(
                script.string
            )
        except (json.JSONDecodeError, TypeError):
            self.logger.warning(
                "[iherb] Failed to parse __NEXT_DATA__ JSON"
            )
            return []

        items = self._find_products_in_json(data)
        return [
            self._parse_json_product(item)
            for item in items
        ]
