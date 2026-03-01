# src/filters/product_validator.py

"""Product validation — drop invalid products before filtering."""

import logging

from src.models.product import Product

logger = logging.getLogger("ecom_search.filters")


class ProductValidator:
    """Validate products and drop those with missing essential fields."""

    @staticmethod
    def validate(
        products: list[Product],
    ) -> tuple[list[Product], int]:
        """Drop products with empty/whitespace titles or zero prices.

        Returns the valid products and the count of dropped items.
        """
        valid: list[Product] = []
        dropped = 0

        for product in products:
            if not product.title.strip():
                logger.debug(
                    "Dropped product with empty title "
                    "(source=%s, url=%s)",
                    product.source,
                    product.url,
                )
                dropped += 1
                continue
            if product.price <= 0:
                logger.debug(
                    "Dropped product with zero/negative "
                    "price (title=%s, source=%s)",
                    product.title,
                    product.source,
                )
                dropped += 1
                continue
            valid.append(product)

        if dropped:
            logger.info(
                "Validation dropped %d invalid products",
                dropped,
            )

        return valid, dropped
