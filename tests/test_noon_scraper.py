# tests/test_noon_scraper.py

"""Tests for the Noon scraper using mocked HTTP responses."""

import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from src.scrapers.noon_scraper import NoonScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestNoonScraper(unittest.TestCase):
    """Tests for the Noon scraper using mocked HTTP responses."""

    def _make_mock_response(self, fixture_name: str) -> MagicMock:
        """Create a mock response from a fixture JSON file."""
        fixture_path = FIXTURES_DIR / fixture_name
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(fixture_path) as f:
            data = json.load(f)
        mock_resp.json.return_value = data
        mock_resp.text = json.dumps(data)
        return mock_resp

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_search_returns_products(self, mock_session_cls: MagicMock) -> None:
        """Verify that search() parses a fixture JSON into Product objects."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "noon_search.json"
        )

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(len(products), 4)
        self.assertTrue(all(p.source == "noon" for p in products))

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_product_fields_parsed_correctly(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify individual product field parsing."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "noon_search.json"
        )

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        # First product uses 'name' and 'sale_price'
        first = products[0]
        self.assertEqual(
            first.title, "Apple iPhone 15 Pro Max 256GB Natural Titanium"
        )
        self.assertEqual(first.price, 4999.0)
        self.assertEqual(first.currency, "AED")
        self.assertEqual(first.rating, "4.7")
        self.assertIn("N12345678", first.url)

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_fallback_name_fields(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify fallback from 'name' to 'name_en' to 'title'."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "noon_search.json"
        )

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        # Third product uses 'name_en' (no 'name' key)
        self.assertEqual(
            products[2].title, "Google Pixel 8 Pro 128GB Obsidian"
        )
        # Fourth product uses 'title' fallback
        self.assertEqual(
            products[3].title, "OnePlus 12 16GB RAM 512GB Silky Black"
        )

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_missing_sale_price_falls_back_to_price(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify price fallback when sale_price is null."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "noon_search.json"
        )

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        # Third product has null sale_price, should use price
        self.assertEqual(products[2].price, 2699.0)

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_empty_sku_generates_empty_url(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify that products with empty sku get an empty URL."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "noon_search.json"
        )

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        # Fourth product has empty sku
        self.assertEqual(products[3].url, "")

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_search_handles_empty_hits(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        empty_data: dict[str, Any] = {"hits": [], "nbPages": 0}
        mock_resp.json.return_value = empty_data
        mock_resp.text = json.dumps(mock_resp.json.return_value)
        mock_session.get.return_value = mock_resp

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent_product_xyz")

        self.assertEqual(products, [])

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_search_handles_http_error(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling on HTTP errors."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_session.get.return_value = mock_resp

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(products, [])

    @patch("src.scrapers.noon_scraper.curl_requests.Session")
    def test_search_handles_network_exception(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when the network call raises."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
