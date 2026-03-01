# tests/test_product_validator.py

"""Tests for ProductValidator."""

import unittest

from src.filters.product_validator import ProductValidator
from src.models.product import Product


def _p(
    title: str = "Collagen", price: float = 10.0,
) -> Product:
    """Create a minimal Product."""
    return Product(
        title=title, price=price, source="test"
    )


class TestProductValidator(unittest.TestCase):
    """ProductValidator.validate unit tests."""

    def test_empty_list_returns_empty(self) -> None:
        """An empty input returns an empty list and zero dropped."""
        valid, dropped = ProductValidator.validate([])
        self.assertEqual(valid, [])
        self.assertEqual(dropped, 0)

    def test_valid_products_pass_through(self) -> None:
        """Products with title and positive price pass validation."""
        products = [_p("Collagen Powder", 89.0), _p("Vitamin D", 45.0)]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 2)
        self.assertEqual(dropped, 0)

    def test_empty_title_dropped(self) -> None:
        """A product with an empty title is dropped."""
        products = [_p("", 10.0), _p("Collagen", 10.0)]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 1)
        self.assertEqual(dropped, 1)
        self.assertEqual(valid[0].title, "Collagen")

    def test_whitespace_title_dropped(self) -> None:
        """A product with a whitespace-only title is dropped."""
        products = [_p("   ", 10.0)]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 0)
        self.assertEqual(dropped, 1)

    def test_zero_price_dropped(self) -> None:
        """A product with price 0.0 is dropped."""
        products = [_p("Collagen", 0.0)]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 0)
        self.assertEqual(dropped, 1)

    def test_negative_price_dropped(self) -> None:
        """A product with a negative price is dropped."""
        products = [_p("Collagen", -5.0)]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 0)
        self.assertEqual(dropped, 1)

    def test_mixed_valid_and_invalid(self) -> None:
        """A mix of valid and invalid products is filtered correctly."""
        products = [
            _p("Good Product", 25.0),
            _p("", 10.0),
            _p("Zero Price", 0.0),
            _p("Another Good", 50.0),
            _p("   ", 15.0),
        ]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 2)
        self.assertEqual(dropped, 3)
        titles = [p.title for p in valid]
        self.assertIn("Good Product", titles)
        self.assertIn("Another Good", titles)

    def test_all_invalid_returns_empty(self) -> None:
        """When all products are invalid, returns empty list."""
        products = [_p("", 0.0), _p("  ", 0.0), _p("", 10.0)]
        valid, dropped = ProductValidator.validate(products)
        self.assertEqual(len(valid), 0)
        self.assertEqual(dropped, 3)
