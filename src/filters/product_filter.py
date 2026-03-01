# src/filters/product_filter.py

"""Post-scrape product filtering by negative keywords."""

import logging

from src.models.product import Product

logger = logging.getLogger("ecom_search.filters")


class ProductFilter:
    """Filter scraped products based on user-defined exclusion keywords."""

    @staticmethod
    def filter_by_keywords(
        products: list[Product],
        negative_keywords: list[str],
    ) -> tuple[list[Product], int]:
        """Remove products whose title contains any negative keyword.

        Returns the filtered list and the count of excluded products.
        """
        if not negative_keywords:
            return products, 0

        lowered_keywords = [kw.lower() for kw in negative_keywords]

        kept: list[Product] = []
        excluded = 0
        for product in products:
            title_lower = product.title.lower()
            if any(kw in title_lower for kw in lowered_keywords):
                excluded += 1
            else:
                kept.append(product)

        if excluded:
            logger.info(
                "Filtered out %d products matching negative keywords",
                excluded,
            )

        return kept, excluded
