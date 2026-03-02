# tests/test_price_history_db.py

"""Tests for the SQLite price history store."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.models.product import Product
from src.storage.price_history_db import (
    PriceHistoryDB,
    normalize_url,
)


class TestNormalizeUrl(unittest.TestCase):
    """Tests for URL normalization logic."""

    def test_strips_tracking_params(self) -> None:
        """Amazon tracking params should be removed."""
        raw = (
            "https://www.amazon.ae/Product/dp/B08ZW875PR"
            "/ref=sr_1_243?dib=abc&qid=123&sr=8-5&keywords=x"
        )
        result = normalize_url(raw)
        self.assertIn("/dp/B08ZW875PR", result)
        self.assertNotIn("ref=", result)
        self.assertNotIn("dib=", result)
        self.assertNotIn("qid=", result)
        self.assertNotIn("sr=", result)
        self.assertNotIn("keywords=", result)

    def test_preserves_product_path(self) -> None:
        """The core product path should survive normalization."""
        url = "https://www.amazon.ae/Product-Name/dp/B001234"
        self.assertEqual(normalize_url(url), url)

    def test_strips_fragment(self) -> None:
        """URL fragments should be dropped."""
        url = "https://example.com/product#section"
        self.assertNotIn("#", normalize_url(url))

    def test_empty_url(self) -> None:
        """Empty string should normalize cleanly."""
        self.assertEqual(normalize_url(""), "")

    def test_preserves_non_tracking_params(self) -> None:
        """Unknown params should be preserved."""
        url = "https://example.com/product?color=red&size=L"
        result = normalize_url(url)
        self.assertIn("color=red", result)
        self.assertIn("size=L", result)


class TestPriceHistoryDB(unittest.TestCase):
    """Tests for the PriceHistoryDB class."""

    def setUp(self) -> None:
        """Create a fresh in-memory-like temp DB for each test."""
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test.db"
        self.db = PriceHistoryDB(db_path=self.db_path)

    def tearDown(self) -> None:
        """Close the database."""
        self.db.close()

    def _sample_products(self) -> list[Product]:
        """Return a small set of test products."""
        return [
            Product(
                title="Collagen Peptides 500g",
                price=89.0,
                currency="AED",
                rating="4.5",
                url="https://www.amazon.ae/Collagen/dp/B001",
                source="amazon",
            ),
            Product(
                title="Vitamin D3 1000IU",
                price=25.0,
                currency="AED",
                rating="4.8",
                url="https://www.noon.com/p/12345",
                source="noon",
            ),
        ]

    # ── record_snapshots ─────────────────────────────────

    def test_record_snapshots_inserts(self) -> None:
        """Products should be recorded and queryable."""
        products = self._sample_products()
        count = self.db.record_snapshots(products)
        self.assertEqual(count, 2)

    def test_record_snapshots_skips_invalid(self) -> None:
        """Products with no URL or zero price are skipped."""
        products = [
            Product(title="No URL", price=10.0, url=""),
            Product(title="Zero Price", price=0.0, url="http://x"),
            Product(title="Negative", price=-1.0, url="http://x"),
        ]
        count = self.db.record_snapshots(products)
        self.assertEqual(count, 0)

    def test_record_multiple_snapshots_same_product(self) -> None:
        """Multiple snapshots for the same URL should accumulate."""
        p = Product(
            title="Product",
            price=100.0,
            url="https://example.com/p1",
            source="test",
        )
        self.db.record_snapshots(
            [p], scraped_at=datetime(2026, 1, 1),
        )
        p.price = 90.0
        self.db.record_snapshots(
            [p], scraped_at=datetime(2026, 1, 2),
        )

        history = self.db.get_price_history(
            "https://example.com/p1",
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].price, 100.0)
        self.assertEqual(history[1].price, 90.0)

    def test_record_normalizes_urls(self) -> None:
        """Tracking params should be stripped before storage."""
        p = Product(
            title="Product",
            price=50.0,
            url="https://www.amazon.ae/dp/B001?ref=sr&dib=x",
            source="amazon",
        )
        self.db.record_snapshots([p])

        # Query with clean URL should find the product
        history = self.db.get_price_history(
            "https://www.amazon.ae/dp/B001",
        )
        self.assertEqual(len(history), 1)

    # ── get_price_history ────────────────────────────────

    def test_get_price_history_ordered(self) -> None:
        """Snapshots should be returned oldest-first."""
        url = "https://example.com/p"
        p = Product(title="P", price=100.0, url=url, source="t")
        self.db.record_snapshots(
            [p], scraped_at=datetime(2026, 3, 1),
        )
        p.price = 80.0
        self.db.record_snapshots(
            [p], scraped_at=datetime(2026, 1, 1),
        )

        history = self.db.get_price_history(url)
        self.assertEqual(len(history), 2)
        self.assertTrue(
            history[0].scraped_at < history[1].scraped_at
        )

    def test_get_price_history_empty(self) -> None:
        """Unknown product returns empty list."""
        history = self.db.get_price_history(
            "https://nonexistent.com/x",
        )
        self.assertEqual(history, [])

    # ── get_price_trends (batch) ─────────────────────────

    def test_get_price_trends_batch(self) -> None:
        """Batch query should return data for known URLs."""
        products = self._sample_products()
        self.db.record_snapshots(products)

        urls = [p.url for p in products]
        trends = self.db.get_price_trends(urls)
        self.assertEqual(len(trends), 2)

    def test_get_price_trends_unknown_url(self) -> None:
        """Unknown URLs should be absent from results."""
        trends = self.db.get_price_trends(
            ["https://nonexistent.com/x"],
        )
        self.assertEqual(len(trends), 0)

    # ── get_trend_summary ────────────────────────────────

    def test_trend_summary_returns_stats(self) -> None:
        """Summary should include min, max, avg, count."""
        url = "https://example.com/p"
        p = Product(title="P", price=100.0, url=url, source="t")
        self.db.record_snapshots(
            [p], scraped_at=datetime(2026, 1, 1),
        )
        p.price = 80.0
        self.db.record_snapshots(
            [p], scraped_at=datetime(2026, 2, 1),
        )

        summary = self.db.get_trend_summary(url)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["min"], 80.0)
        self.assertEqual(summary["max"], 100.0)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["latest"], 80.0)

    def test_trend_summary_none_for_unknown(self) -> None:
        """Unknown product returns None."""
        result = self.db.get_trend_summary(
            "https://nonexistent.com/x",
        )
        self.assertIsNone(result)

    # ── toggle_star / is_starred ─────────────────────────

    def test_toggle_star_on_off(self) -> None:
        """Star toggle should flip between True and False."""
        p = Product(
            title="P",
            price=50.0,
            url="https://example.com/p",
            source="test",
        )
        self.db.record_snapshots([p])

        # Initially not starred
        self.assertFalse(
            self.db.is_starred("https://example.com/p"),
        )

        # Toggle on
        new_state = self.db.toggle_star(
            "https://example.com/p",
        )
        self.assertTrue(new_state)
        self.assertTrue(
            self.db.is_starred("https://example.com/p"),
        )

        # Toggle off
        new_state = self.db.toggle_star(
            "https://example.com/p",
        )
        self.assertFalse(new_state)

    def test_toggle_star_unknown_product(self) -> None:
        """Toggling an unknown product returns False."""
        result = self.db.toggle_star(
            "https://nonexistent.com/x",
        )
        self.assertFalse(result)

    # ── get_starred_products ─────────────────────────────

    def test_get_starred_products(self) -> None:
        """Starred products should appear in the watchlist."""
        products = self._sample_products()
        self.db.record_snapshots(products)

        # Star the first one
        self.db.toggle_star(products[0].url)

        starred = self.db.get_starred_products()
        self.assertEqual(len(starred), 1)
        self.assertEqual(
            starred[0]["source"], "amazon",
        )
        self.assertEqual(
            starred[0]["latest_price"], 89.0,
        )

    def test_get_starred_empty(self) -> None:
        """No starred products returns empty list."""
        self.assertEqual(
            self.db.get_starred_products(), [],
        )

    # ── import_single_file ───────────────────────────────

    def test_import_single_file(self) -> None:
        """A well-formed JSON file should be imported."""
        data = [
            {
                "title": "Imported Product",
                "price": 75.0,
                "currency": "AED",
                "rating": "4.0",
                "url": "https://example.com/imported",
                "source": "amazon",
            },
        ]
        filepath = Path(self.tmp_dir) / "amazon_test_20260301_120000.json"
        with open(filepath, "w") as f:
            json.dump(data, f)

        count = self.db.import_single_file(filepath)
        self.assertEqual(count, 1)

        history = self.db.get_price_history(
            "https://example.com/imported",
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0].scraped_at,
            datetime(2026, 3, 1, 12, 0, 0),
        )

    def test_import_skips_bad_filename(self) -> None:
        """Files without a timestamp suffix should be skipped."""
        filepath = Path(self.tmp_dir) / "random_name.json"
        with open(filepath, "w") as f:
            json.dump([], f)

        count = self.db.import_single_file(filepath)
        self.assertEqual(count, 0)

    def test_import_skips_corrupt_json(self) -> None:
        """Files with invalid JSON should be skipped gracefully."""
        filepath = (
            Path(self.tmp_dir) / "amazon_test_20260301_120000.json"
        )
        with open(filepath, "w") as f:
            f.write("NOT JSON {{{")

        count = self.db.import_single_file(filepath)
        self.assertEqual(count, 0)

    # ── import_legacy_results ────────────────────────────

    def test_import_legacy_results_full(self) -> None:
        """Bulk import should process all valid files."""
        tmp = Path(self.tmp_dir) / "results"
        tmp.mkdir()
        for i in range(3):
            data = [
                {
                    "title": f"Product {i}",
                    "price": 10.0 + i,
                    "url": f"https://example.com/{i}",
                    "source": "noon",
                },
            ]
            path = tmp / f"noon_test_20260{i + 1}01_120000.json"
            with open(path, "w") as f:
                json.dump(data, f)

        total = self.db.import_legacy_results(tmp)
        self.assertEqual(total, 3)


if __name__ == "__main__":
    unittest.main()
