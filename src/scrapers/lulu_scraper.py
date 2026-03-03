# src/scrapers/lulu_scraper.py

"""Scraper for LuLu Hypermarket UAE via RSC payload extraction."""

import json
import time
import urllib.parse
from typing import Any, cast

from curl_cffi import requests as curl_requests

from src.models.product import Product
from src.scrapers import base_scraper as _base_mod
from src.scrapers.base_scraper import BaseScraper


class LuluScraper(BaseScraper):
    """Scraper for LuLu Hypermarket (gcc.luluhypermarket.com).

    LuLu runs on Akinon Commerce Cloud with Next.js RSC
    streaming.  Product data is embedded as escaped JSON
    inside ``self.__next_f.push`` script blocks.  This
    scraper extracts the JSON payload directly from the
    HTML rather than using CSS selectors.

    Uses a dual-fetch chain (curl_cffi then cloudscraper)
    to bypass Cloudflare protections.
    """

    BASE_URL = "https://gcc.luluhypermarket.com"
    SEARCH_URL = (
        "https://gcc.luluhypermarket.com/en-ae/list/"
        "?search_text={query}&page={page}"
    )
    _PAGE_SIZE = 20

    def __init__(self) -> None:
        super().__init__("lulu")
        _cs: Any = _base_mod.cloudscraper
        self._cs_scraper: Any = _cs.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            },
        )

    def _get_homepage(self) -> str:
        """Return the LuLu UAE homepage URL."""
        return f"{self.BASE_URL}/en-ae/"

    # ----------------------------------------------------------
    # Response validation
    # ----------------------------------------------------------

    def _validate_response(
        self, resp: curl_requests.Response,
    ) -> bool:
        """Accept large LuLu pages that contain product markers."""
        text = resp.text
        if len(text) > 100_000 and "products" in text:
            return True
        return super()._validate_response(resp)

    # ----------------------------------------------------------
    # Cloudscraper fallback
    # ----------------------------------------------------------

    def _fetch_cloudscraper(
        self, url: str, headers: dict[str, str],
    ) -> str | None:
        """Fetch raw HTML via cloudscraper as fallback."""
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
                        self._escalate_delay()
                        time.sleep(self._current_delay)
                        continue
                    return text
                self.logger.warning(
                    "[lulu] cloudscraper HTTP %d "
                    "on attempt %d",
                    resp.status_code,
                    attempt + 1,
                )
            except Exception as exc:
                self.logger.warning(
                    "[lulu] cloudscraper error "
                    "on attempt %d: %s",
                    attempt + 1,
                    exc,
                )
                time.sleep(
                    self._current_delay * (attempt + 1)
                )
        return None

    def _fetch_page_html(
        self, url: str, headers: dict[str, str],
    ) -> str | None:
        """Fetch page HTML: curl_cffi first, cloudscraper fallback."""
        resp = self._fetch_get(url, headers)
        if resp is not None:
            return resp.text

        self.logger.info(
            "[lulu] curl_cffi exhausted, "
            "attempting cloudscraper fallback",
        )
        return self._fetch_cloudscraper(url, headers)

    # ----------------------------------------------------------
    # RSC payload extraction
    # ----------------------------------------------------------

    @staticmethod
    def _find_brace_block(
        html: str, start: int, open_ch: str, close_ch: str,
    ) -> str:
        """Extract a balanced brace/bracket block from *start*."""
        depth = 0
        end = start
        for i in range(start, len(html)):
            if html[i] == open_ch:
                depth += 1
            elif html[i] == close_ch:
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        return html[start:end]

    @staticmethod
    def _parse_pagination(
        html: str, products_idx: int,
    ) -> dict[str, Any]:
        """Extract pagination dict preceding the products marker."""
        pag_marker = r'\"pagination\":{'
        pag_idx = html.rfind(pag_marker, 0, products_idx)
        if pag_idx == -1:
            return {}
        pag_start = pag_idx + len(pag_marker) - 1
        raw = LuluScraper._find_brace_block(
            html, pag_start, '{', '}',
        )
        raw = raw.replace('\\"', '"')
        try:
            result: dict[str, Any] = json.loads(raw)
            return result
        except (json.JSONDecodeError, ValueError):
            return {}

    @staticmethod
    def _parse_products_array(
        html: str, marker_idx: int, marker_len: int,
    ) -> list[dict[str, Any]]:
        """Extract and parse the products JSON array."""
        arr_start = marker_idx + marker_len - 1
        raw = LuluScraper._find_brace_block(
            html, arr_start, '[', ']',
        )
        raw = raw.replace('\\"', '"')
        try:
            parsed: list[dict[str, Any]] = json.loads(raw)
            return parsed
        except (json.JSONDecodeError, ValueError):
            return []

    @staticmethod
    def _extract_products_json(
        html: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Pull products list and pagination from the RSC payload."""
        marker = r'\"products\":['
        idx = html.find(marker)
        if idx == -1:
            return [], {}

        pagination = LuluScraper._parse_pagination(
            html, idx,
        )
        products = LuluScraper._parse_products_array(
            html, idx, len(marker),
        )
        return products, pagination

    # ----------------------------------------------------------
    # Product mapping
    # ----------------------------------------------------------

    def _hit_to_product(
        self, hit: dict[str, Any],
    ) -> Product:
        """Convert a single Akinon product dict to a Product."""
        title = str(hit.get("name", "N/A"))

        price = 0.0
        raw_price: object = hit.get("price")
        if isinstance(raw_price, str):
            price = self.extract_price(raw_price)
        elif isinstance(raw_price, (int, float)):
            price = float(raw_price)

        abs_url: str = str(
            hit.get("absolute_url", "")
        )
        full_url = (
            f"{self.BASE_URL}/en-ae{abs_url}"
            if abs_url
            else ""
        )

        image_url = ""
        images: object = hit.get(
            "productimage_set"
        )
        if isinstance(images, list) and images:
            first_img = cast(
                dict[str, Any], images[0],
            )
            image_url = str(
                first_img.get("image", "")
            )

        return Product(
            title=title,
            price=price,
            currency="AED",
            url=full_url,
            source="lulu",
            image_url=image_url,
        )

    # ----------------------------------------------------------
    # Public search entry-point
    # ----------------------------------------------------------

    def search(self, query: str) -> list[Product]:
        """Search LuLu Hypermarket for products."""
        try:
            products: list[Product] = []
            encoded = urllib.parse.quote_plus(query)

            for page in range(
                1, self.settings.MAX_PAGES + 1
            ):
                self._wait()
                url = self.SEARCH_URL.format(
                    query=encoded, page=page
                )
                self.logger.info(
                    "[lulu] Fetching page %d (%d so far)",
                    page,
                    len(products),
                )

                headers: dict[str, str] = {
                    **self._session_headers,
                    "Referer": (
                        f"{self.BASE_URL}/en-ae/"
                        f"list/?search_text={encoded}"
                    ),
                }

                html = self._fetch_page_html(
                    url, headers,
                )
                if not html:
                    self.logger.warning(
                        "[lulu] Failed page %d", page,
                    )
                    break

                hits, pagination = (
                    self._extract_products_json(html)
                )

                if not hits:
                    self.logger.info(
                        "[lulu] No products on page %d",
                        page,
                    )
                    break

                for hit in hits:
                    if not hit.get("in_stock", True):
                        continue
                    products.append(
                        self._hit_to_product(hit)
                    )

                # Pagination guard
                num_pages = int(
                    pagination.get("num_pages", 1)
                )
                if page >= num_pages:
                    break

            return products
        except Exception as exc:
            self.logger.error(
                "[lulu] Search failed: %s",
                exc,
                exc_info=True,
            )
            return []
