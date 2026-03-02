# src/filters/deduplicator.py

"""Product deduplication across multiple marketplace sources."""

import logging
import re
from collections import defaultdict

from rapidfuzz import fuzz

from src.config.settings import Settings
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

        # ── Pass 3: cross-source fuzzy title matching ────
        kept, fuzzy_removed = (
            ProductDeduplicator._fuzzy_cross_source(kept)
        )
        removed += fuzzy_removed

        if removed:
            logger.info(
                "Deduplication removed %d duplicate products",
                removed,
            )

        return kept, removed

    # ── Fuzzy cross-source helpers ───────────────────────

    @staticmethod
    def _bucket_key(title: str) -> str:
        """Return first 3 normalised words as a bucket key."""
        words = ProductDeduplicator._normalise_title(
            title
        ).split()
        return " ".join(words[:3])

    @staticmethod
    def _prices_close(a: float, b: float) -> bool:
        """Return True if two prices are within the tolerance."""
        if a <= 0 or b <= 0:
            return False
        tolerance = Settings.FUZZY_PRICE_TOLERANCE
        return abs(a - b) / max(a, b) <= tolerance

    @staticmethod
    def _is_fuzzy_match(
        pa: Product,
        norm_a: str,
        pb: Product,
    ) -> bool:
        """Return True if two cross-source products are fuzzy-equal."""
        if pa.source == pb.source:
            return False
        norm_b = ProductDeduplicator._normalise_title(
            pb.title
        )
        score = fuzz.token_set_ratio(norm_a, norm_b)
        if score < Settings.FUZZY_MATCH_THRESHOLD:
            return False
        return ProductDeduplicator._prices_close(
            pa.price, pb.price,
        )

    @staticmethod
    def _merge_bucket(
        indices: list[int],
        products: list[Product],
        merged_into: dict[int, int],
    ) -> None:
        """Compare all pairs in a bucket and record merges."""
        for i, idx_a in enumerate(indices):
            if idx_a in merged_into:
                continue
            pa = products[idx_a]
            norm_a = ProductDeduplicator._normalise_title(
                pa.title
            )
            for idx_b in indices[i + 1:]:
                if idx_b in merged_into:
                    continue
                pb = products[idx_b]
                if not ProductDeduplicator._is_fuzzy_match(
                    pa, norm_a, pb,
                ):
                    continue
                if pb.price > 0 and pb.price < pa.price:
                    merged_into[idx_a] = idx_b
                    break
                merged_into[idx_b] = idx_a

    @staticmethod
    def _fuzzy_cross_source(
        products: list[Product],
    ) -> tuple[list[Product], int]:
        """Merge cross-source duplicates using fuzzy title matching.

        Groups products by a coarse bucket key (first 3 words),
        then compares pairs from different sources using
        rapidfuzz token_set_ratio.  Merges when the score
        exceeds the threshold and prices are close enough.
        """
        buckets: dict[str, list[int]] = defaultdict(list)
        for idx, p in enumerate(products):
            key = ProductDeduplicator._bucket_key(p.title)
            buckets[key].append(idx)

        merged_into: dict[int, int] = {}

        for indices in buckets.values():
            if len(indices) >= 2:
                ProductDeduplicator._merge_bucket(
                    indices, products, merged_into,
                )

        if not merged_into:
            return products, 0

        kept = [
            p for idx, p in enumerate(products)
            if idx not in merged_into
        ]
        return kept, len(merged_into)
