# tests/test_deduplicator.py

"""Tests for ProductDeduplicator cross-source deduplication."""

import unittest

from src.filters.deduplicator import ProductDeduplicator
from src.models.product import Product


def _make(
    title: str,
    price: float = 10.0,
    source: str = "test",
    url: str = "",
) -> Product:
    """Create a minimal Product."""
    return Product(
        title=title,
        price=price,
        source=source,
        url=url,
    )


class TestDeduplicate(unittest.TestCase):
    """ProductDeduplicator.deduplicate behaviour."""

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        kept, removed = ProductDeduplicator.deduplicate([])
        self.assertEqual(len(kept), 0)
        self.assertEqual(removed, 0)

    def test_no_duplicates(self) -> None:
        """Unique products are all kept."""
        products = [
            _make("Alpha", url="https://a.com/1"),
            _make("Beta", url="https://b.com/2"),
        ]
        kept, removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 2)
        self.assertEqual(removed, 0)

    def test_exact_url_dedup(self) -> None:
        """Products with identical URLs are deduplicated."""
        products = [
            _make("Widget A", price=20.0, url="https://shop.com/item/1"),
            _make("Widget A", price=15.0, url="https://shop.com/item/1"),
        ]
        kept, removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(kept[0].price, 15.0)

    def test_url_normalisation(self) -> None:
        """Query params and trailing slashes are stripped."""
        products = [
            _make("Item", price=10.0, url="https://shop.com/item/1?ref=abc"),
            _make("Item", price=8.0, url="https://shop.com/item/1/"),
        ]
        kept, removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(kept[0].price, 8.0)

    def test_same_source_title_dedup(self) -> None:
        """Same-source products with identical normalised titles are deduped."""
        products = [
            _make("Collagen Peptides!", price=25.0, source="amazon"),
            _make("collagen peptides", price=20.0, source="amazon"),
        ]
        kept, removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(kept[0].price, 20.0)

    def test_cross_source_not_deduped_by_title(self) -> None:
        """Products from different sources with same title are kept."""
        products = [
            _make("Vitamin D3", source="amazon"),
            _make("Vitamin D3", source="noon"),
        ]
        kept, removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 2)
        self.assertEqual(removed, 0)

    def test_keeps_cheapest_on_url_clash(self) -> None:
        """When URL duplicates exist, the cheapest price wins."""
        products = [
            _make("X", price=30.0, url="https://a.com/1"),
            _make("X", price=10.0, url="https://a.com/1"),
            _make("X", price=20.0, url="https://a.com/1"),
        ]
        kept, removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].price, 10.0)
        self.assertEqual(removed, 2)

    def test_zero_price_not_preferred(self) -> None:
        """A zero-price duplicate does not replace a priced one."""
        products = [
            _make("Y", price=15.0, url="https://a.com/2"),
            _make("Y", price=0.0, url="https://a.com/2"),
        ]
        kept, _removed = ProductDeduplicator.deduplicate(products)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].price, 15.0)
