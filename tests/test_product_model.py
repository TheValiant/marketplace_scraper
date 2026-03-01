# tests/test_product_model.py

"""Tests for the Product dataclass."""

import unittest

from src.models.product import Product


class TestProductModel(unittest.TestCase):
    """Product dataclass unit tests."""

    def test_init_with_all_fields(self) -> None:
        """All fields are stored correctly."""
        product = Product(
            title="Collagen",
            price=89.0,
            currency="USD",
            rating="4.5",
            url="https://example.com/p",
            source="amazon",
            image_url="https://example.com/img.jpg",
        )
        self.assertEqual(product.title, "Collagen")
        self.assertEqual(product.price, 89.0)
        self.assertEqual(product.currency, "USD")
        self.assertEqual(product.rating, "4.5")
        self.assertEqual(product.url, "https://example.com/p")
        self.assertEqual(product.source, "amazon")
        self.assertEqual(
            product.image_url, "https://example.com/img.jpg"
        )

    def test_defaults(self) -> None:
        """Optional fields default to expected values."""
        product = Product(title="X", price=1.0)
        self.assertEqual(product.currency, "AED")
        self.assertEqual(product.rating, "")
        self.assertEqual(product.url, "")
        self.assertEqual(product.source, "")
        self.assertEqual(product.image_url, "")

    def test_equality(self) -> None:
        """Two products with identical fields are equal."""
        a = Product(title="A", price=10.0, source="noon")
        b = Product(title="A", price=10.0, source="noon")
        self.assertEqual(a, b)

    def test_inequality_different_price(self) -> None:
        """Products with different prices are not equal."""
        a = Product(title="A", price=10.0, source="noon")
        b = Product(title="A", price=20.0, source="noon")
        self.assertNotEqual(a, b)

    def test_inequality_different_title(self) -> None:
        """Products with different titles are not equal."""
        a = Product(title="A", price=10.0)
        b = Product(title="B", price=10.0)
        self.assertNotEqual(a, b)

    def test_edge_empty_strings(self) -> None:
        """Product can be created with empty strings."""
        product = Product(title="", price=0.0, currency="")
        self.assertEqual(product.title, "")
        self.assertEqual(product.price, 0.0)
        self.assertEqual(product.currency, "")

    def test_edge_very_long_title(self) -> None:
        """Product handles very long titles without error."""
        long_title = "A" * 10_000
        product = Product(title=long_title, price=1.0)
        self.assertEqual(len(product.title), 10_000)

    def test_edge_negative_price(self) -> None:
        """Product stores negative prices (validation is external)."""
        product = Product(title="X", price=-5.0)
        self.assertEqual(product.price, -5.0)

    def test_edge_large_price(self) -> None:
        """Product stores very large prices without overflow."""
        product = Product(title="X", price=999_999_999.99)
        self.assertEqual(product.price, 999_999_999.99)


if __name__ == "__main__":
    unittest.main()
