# src/scrapers/sephora_scraper.py

"""Scraper for sephora.me (UAE) using Demandware HTML product grids."""

import urllib.parse

from bs4 import Tag

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class SephoraScraper(BaseScraper):
    """Scraper for Sephora UAE (Beauty).

    Parses Salesforce Commerce Cloud (Demandware) HTML
    product grids.  Extracts brand and product name
    separately to build accurate titles.

    Note: ``sephora.ae`` redirects to ``sephora.me``.
    """

    BASE_URL = "https://www.sephora.me"
    SEARCH_URL = (
        "https://www.sephora.me/ae-en/"
        "search?q={query}&start={start}&sz=36"
    )
    _PAGE_SIZE = 36

    def __init__(self) -> None:
        super().__init__("sephora")

    def _get_homepage(self) -> str:
        """Return the Sephora UAE homepage URL."""
        return f"{self.BASE_URL}/ae-en/"

    # ----------------------------------------------------------
    # Card parsing
    # ----------------------------------------------------------

    def _parse_card(self, card: Tag) -> Product:
        """Parse a Demandware product tile into a Product."""
        # Sephora splits Brand and Product Name
        brand_el = card.select_one(
            self.selectors.get(
                "brand", "a.link.product-brand"
            )
        )
        name_el = card.select_one(
            self.selectors.get("title", "")
        )

        brand = (
            brand_el.get_text(strip=True)
            if brand_el
            else ""
        )
        name = (
            name_el.get_text(strip=True)
            if name_el
            else ""
        )
        full_title = (
            f"{brand} - {name}".strip(" -") or "N/A"
        )

        # Price
        price_el = card.select_one(
            self.selectors.get("price", "")
        )
        price_val = self.extract_price(
            price_el.get_text() if price_el else ""
        )

        # URL
        url_el = card.select_one(
            self.selectors.get("url", "")
        )
        href = ""
        if url_el:
            raw_href = url_el.get("href", "")
            href = str(raw_href) if raw_href else ""
            if href and not href.startswith("http"):
                href = f"{self.BASE_URL}{href}"

        # Image
        img_el = card.select_one("img")
        image_url = ""
        if img_el:
            raw_src = img_el.get("src", "")
            image_url = (
                str(raw_src) if raw_src else ""
            )

        return Product(
            title=full_title,
            price=price_val,
            currency="AED",
            url=href,
            source="sephora",
            image_url=image_url,
        )

    # ----------------------------------------------------------
    # Public search entry-point
    # ----------------------------------------------------------

    def search(self, query: str) -> list[Product]:
        """Search Sephora UAE for beauty products."""
        try:
            products: list[Product] = []
            encoded = urllib.parse.quote_plus(query)

            for page in range(self.settings.MAX_PAGES):
                start_offset = page * self._PAGE_SIZE
                url = self.SEARCH_URL.format(
                    query=encoded,
                    start=start_offset,
                )
                self.logger.info(
                    "[sephora] Fetching page %d "
                    "(offset %d)",
                    page + 1,
                    start_offset,
                )

                soup = self._get_page(url)
                if not soup:
                    break

                card_sel = self.selectors.get(
                    "product_card", "div.grid-tile"
                )
                cards = soup.select(card_sel)
                if not cards:
                    break

                for card in cards:
                    parsed = self._parse_card(card)
                    if parsed.title != "N/A":
                        products.append(parsed)

                # Stop if fewer results than page size
                if len(cards) < self._PAGE_SIZE:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[sephora] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
