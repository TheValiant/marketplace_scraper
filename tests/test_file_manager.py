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


if __name__ == "__main__":
    unittest.main()
