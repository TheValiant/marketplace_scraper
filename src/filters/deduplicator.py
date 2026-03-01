# src/filters/deduplicator.py

"""Product deduplication across multiple marketplace sources."""

import logging
import re

from src.models.product import Product

logger = logging.getLogger("ecom_search.filters")


class ProductDeduplicator:
    """Remove duplicate products using URL normalisation and fuzzy title matching."""

    # Query params that don't affect the product identity
    _STRIP_PARAMS_RE = re.compile(
        r"[?#].*$"
    )

    @staticmethod
    def _normalise_url(url: str) -> str:
        """Normalise a product URL for dedup comparison.

        Strips query parameters, fragments, trailing slashes,
        and lowercases the result.
        """
        if not url:
            return ""
        cleaned = ProductDeduplicator._STRIP_PARAMS_RE.sub(
            "", url
        )
        cleaned = cleaned.rstrip("/").lower()
        return cleaned

    @staticmethod
    def _normalise_title(title: str) -> str:
        """Normalise a title to a comparable key.

        Lowercases, strips non-alphanumeric characters,
        and collapses whitespace.
        """
        lowered = title.lower()
        alpha_only = re.sub(r"[^a-z0-9\s]", "", lowered)
        return " ".join(alpha_only.split())

    @staticmethod
    def deduplicate(
        products: list[Product],
    ) -> tuple[list[Product], int]:
        """Remove duplicate products, keeping the cheapest per group.

        Dedup strategy:
        1. Exact URL match (after normalisation).
        2. Same-source fuzzy title match (normalised titles).

        Returns the deduplicated list and the count of removed dupes.
        """
        if not products:
            return [], 0

        seen_urls: dict[str, int] = {}
        seen_titles: dict[str, int] = {}
        kept: list[Product] = []
        removed = 0

        for product in products:
            norm_url = ProductDeduplicator._normalise_url(
                product.url
            )
            title_key = (
                f"{product.source}:"
                f"{ProductDeduplicator._normalise_title(product.title)}"
            )

            # Check URL-based duplicate
            if norm_url and norm_url in seen_urls:
                existing_idx = seen_urls[norm_url]
                if (
                    product.price > 0
                    and product.price < kept[existing_idx].price
                ):
                    kept[existing_idx] = product
                removed += 1
                continue

            # Check title-based duplicate (same source only)
            if title_key in seen_titles:
                existing_idx = seen_titles[title_key]
                if (
                    product.price > 0
                    and product.price < kept[existing_idx].price
                ):
                    kept[existing_idx] = product
                removed += 1
                continue

            # New unique product
            idx = len(kept)
            if norm_url:
                seen_urls[norm_url] = idx
            seen_titles[title_key] = idx
            kept.append(product)

        if removed:
            logger.info(
                "Deduplication removed %d duplicate products",
                removed,
            )

        return kept, removed
