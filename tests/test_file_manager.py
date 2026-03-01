# tests/test_file_manager.py

"""Tests for the FileManager storage module."""

import csv
import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from src.models.product import Product
from src.storage.file_manager import FileManager


class TestFileManager(unittest.TestCase):
    """Tests for JSON/CSV save and export."""

    def setUp(self) -> None:
        """Set up a temp directory for results."""
        import tempfile

        self.tmp_dir = tempfile.mkdtemp()

        def _fake_init(inst: Any) -> None:
            inst.results_dir = Path(self.tmp_dir)

        self._patcher = patch.object(
            FileManager, "__init__", _fake_init
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.fm = FileManager()

    def _sample_products(self) -> list[Product]:
        """Return a small list of test products."""
        return [
            Product(
                title="Product A",
                price=100.0,
                currency="AED",
                rating="4.5",
                url="https://example.com/a",
                source="noon",
            ),
            Product(
                title="Product B",
                price=50.0,
                currency="AED",
                rating="3.0",
                url="https://example.com/b",
                source="amazon",
            ),
        ]

    def test_save_results_creates_json(self) -> None:
        """Verify save_results writes a valid JSON file."""
        products = self._sample_products()
        path = self.fm.save_results("test query", products, "combined")

        self.assertTrue(path.exists())
        self.assertTrue(path.name.endswith(".json"))
        with open(path) as f:
            data: list[dict[str, Any]] = json.load(f)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["title"], "Product A")

    def test_save_results_empty_list(self) -> None:
        """Verify save_results handles an empty product list."""
        path = self.fm.save_results("empty", [], "combined")

        self.assertTrue(path.exists())
        with open(path) as f:
            data: list[dict[str, Any]] = json.load(f)
        self.assertEqual(data, [])

    def test_export_csv_creates_file(self) -> None:
        """Verify export_csv writes a valid CSV file."""
        products = self._sample_products()
        path = self.fm.export_csv("test query", products, "combined")

        self.assertTrue(path.exists())
        self.assertTrue(path.name.endswith(".csv"))
        with open(path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 2 data rows
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0],
            ["Title", "Price", "Currency", "Rating", "Source", "URL"],
        )

    def test_export_csv_sorted_by_price(self) -> None:
        """Verify CSV rows are sorted by price ascending."""
        products = self._sample_products()
        path = self.fm.export_csv("test", products, "combined")

        with open(path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # First data row should be the cheapest (Product B, 50.0)
        self.assertEqual(rows[1][0], "Product B")
        self.assertEqual(rows[2][0], "Product A")

    def test_export_csv_empty_list(self) -> None:
        """Verify export_csv handles an empty product list."""
        path = self.fm.export_csv("empty", [], "combined")

        self.assertTrue(path.exists())
        with open(path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header only, no data rows
        self.assertEqual(len(rows), 1)

    def test_save_results_filename_format(self) -> None:
        """Verify filename contains source, query, and timestamp."""
        path = self.fm.save_results("multi word", [], "noon")

        self.assertIn("noon", path.name)
        self.assertIn("multi_word", path.name)
        self.assertTrue(path.name.endswith(".json"))

    def test_export_csv_filename_format(self) -> None:
        """Verify CSV filename contains 'export_' prefix."""
        path = self.fm.export_csv("test", [], "combined")

        self.assertTrue(path.name.startswith("export_"))
        self.assertIn("combined", path.name)
        self.assertTrue(path.name.endswith(".csv"))

    # --- format_tsv tests ---

    def test_format_tsv_header_and_rows(self) -> None:
        """Verify TSV output contains a header and tab-separated rows."""
        products = self._sample_products()
        result = self.fm.format_tsv(products)
        lines = result.split("\n")

        self.assertEqual(len(lines), 3)  # header + 2 rows
        self.assertEqual(
            lines[0],
            "Title\tPrice\tCurrency\tRating\tSource\tURL",
        )
        # Each data line has 6 tab-separated fields
        for line in lines[1:]:
            self.assertEqual(len(line.split("\t")), 6)

    def test_format_tsv_sorted_by_price(self) -> None:
        """Verify TSV rows are sorted by price ascending."""
        products = self._sample_products()
        result = self.fm.format_tsv(products)
        lines = result.split("\n")

        # First data row = cheapest (Product B, 50.0)
        self.assertTrue(lines[1].startswith("Product B"))
        self.assertTrue(lines[2].startswith("Product A"))

    def test_format_tsv_empty_list(self) -> None:
        """Verify TSV with no products returns header only."""
        result = self.fm.format_tsv([])
        lines = result.split("\n")

        self.assertEqual(len(lines), 1)
        self.assertEqual(
            lines[0],
            "Title\tPrice\tCurrency\tRating\tSource\tURL",
        )

    # ── Extra edge-case tests ────────────────────────────

    def test_save_results_special_chars_in_query(self) -> None:
        """Spaces in query are replaced for the filename."""
        products = self._sample_products()
        path = self.fm.save_results(
            "multi collagen", products, "combined"
        )
        self.assertIn("multi_collagen", path.name)
        self.assertTrue(path.exists())

    def test_format_tsv_with_tab_in_title(self) -> None:
        """Tab characters in product titles appear literally in TSV."""
        products = [
            Product(
                title="Tab\there",
                price=5.0,
                currency="AED",
                rating="",
                url="",
                source="test",
            ),
        ]
        result = self.fm.format_tsv(products)
        data_line = result.split("\n")[1]
        # Title field itself contains a tab, so column count increases
        self.assertIn("Tab", data_line)
        self.assertIn("here", data_line)

    def test_export_csv_special_chars_in_query(self) -> None:
        """Spaces in query are replaced for CSV filename."""
        products = self._sample_products()
        path = self.fm.export_csv(
            "krill oil", products, "combined"
        )
        self.assertIn("krill_oil", path.name)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
