# src/scrapers/sephora_scraper.py

"""Scraper for sephora.me (UAE) via RSC flight-data extraction."""

import json
import re
import urllib.parse
from typing import Any, cast

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper

# Extracts the string payload from each RSC push call
_RSC_PUSH_RE = re.compile(
    r'self\.__next_f\.push\(\[1,"(.*?)"\]\)',
    re.DOTALL,
)

# Locates the products JSON array inside RSC data
_PRODUCTS_KEY = '"products":[{"productId"'


class SephoraScraper(BaseScraper):
    """Scraper for Sephora UAE (Beauty).

    Extracts product data from React Server Component
    (RSC) flight payload embedded in the HTML response.

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
    # RSC flight-data helpers
    # ----------------------------------------------------------

    @staticmethod
    def _unescape_rsc(html: str) -> str:
        """Extract and unescape RSC push payloads."""
        chunks: list[str] = []
        for match in _RSC_PUSH_RE.finditer(html):
            raw = match.group(1)
            unescaped = (
                raw.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\\\", "\\")
            )
            chunks.append(unescaped)
        return "".join(chunks)

    @staticmethod
    def _find_products(
        rsc_text: str,
    ) -> list[dict[str, Any]]:
        """Find and parse the products JSON array."""
        idx = rsc_text.find(_PRODUCTS_KEY)
        if idx == -1:
            return []
        arr_start = rsc_text.index("[", idx)
        decoder = json.JSONDecoder()
        try:
            parsed: object
            parsed, _ = decoder.raw_decode(
                rsc_text, arr_start,
            )
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(parsed, list):
            return []
        return cast(
            list[dict[str, Any]], parsed,
        )

    def _map_product(
        self, obj: dict[str, Any],
    ) -> Product | None:
        """Map a single product dict to a Product."""
        product_id = str(
            obj.get("productId", ""),
        )
        name = str(
            obj.get("productName", ""),
        ).strip()
        if not name:
            return None

        price = float(obj.get("c_price", 0) or 0)

        # Brand (inline object with id/name)
        brand = ""
        brand_obj: object = obj.get("c_brand", "")
        if isinstance(brand_obj, dict):
            bd = cast(dict[str, Any], brand_obj)
            brand = str(
                bd.get(
                    "name", bd.get("id", ""),
                )
            )
        elif isinstance(brand_obj, str):
            brand = brand_obj

        title = (
            f"{brand} - {name}".strip(" -")
            if brand
            else name
        )

        # Image (inline object with disBaseLink)
        image_url = ""
        image_obj: object = obj.get("image", "")
        if isinstance(image_obj, dict):
            im = cast(dict[str, Any], image_obj)
            image_url = str(
                im.get(
                    "disBaseLink",
                    im.get("link", ""),
                )
            )

        # Rating
        rating_val = obj.get(
            "c_bvAverageRating", "",
        )
        rating = (
            str(rating_val) if rating_val else ""
        )

        # URL
        slug = re.sub(
            r'[^a-z0-9]+', '-', name.lower(),
        ).strip('-')
        url = (
            f"{self.BASE_URL}/ae-en/p/"
            f"{slug}/{product_id}"
        )

        return Product(
            title=title,
            price=price,
            currency="AED",
            rating=rating,
            url=url,
            source="sephora",
            image_url=image_url,
        )

    def _extract_products(
        self, html: str,
    ) -> list[Product]:
        """Extract all products from RSC flight data."""
        rsc_text = self._unescape_rsc(html)
        raw_items = self._find_products(rsc_text)
        products: list[Product] = []
        seen_ids: set[str] = set()

        for item in raw_items:
            pid = str(item.get("productId", ""))
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            product = self._map_product(item)
            if product is not None:
                products.append(product)

        return products

    # ----------------------------------------------------------
    # Public search entry-point
    # ----------------------------------------------------------

    def search(self, query: str) -> list[Product]:
        """Search Sephora UAE for beauty products."""
        try:
            products: list[Product] = []
            encoded = urllib.parse.quote_plus(query)
            headers: dict[str, str] = {
                **self._session_headers,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Referer": self._get_homepage(),
            }

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

                self._wait()
                resp = self._fetch_get(url, headers)
                if resp is None:
                    break

                page_products = self._extract_products(
                    resp.text,
                )
                if not page_products:
                    break

                products.extend(page_products)

                if (
                    len(page_products) < self._PAGE_SIZE
                ):
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[sephora] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
