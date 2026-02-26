# tests/test_aster_scraper.py

"""Tests for the Aster scraper using mocked HTTP responses."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.scrapers.aster_scraper import AsterScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestAsterScraper(unittest.TestCase):
    """Tests for the Aster scraper using mocked HTTP responses."""

    def _make_mock_response(self, fixture_name: str) -> MagicMock:
        """Create a mock response from a fixture JSON file."""
        fixture_path = FIXTURES_DIR / fixture_name
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(fixture_path) as f:
            data = json.load(f)
        mock_resp.json.return_value = data
        return mock_resp

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_search_returns_products(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify that search() parses API response into Product objects."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "aster_search.json"
        )

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(len(products), 3)
        self.assertTrue(all(p.source == "aster" for p in products))

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_product_fields_parsed_correctly(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify individual product field parsing."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "aster_search.json"
        )

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        first = products[0]
        self.assertEqual(
            first.title,
            "Panadol Cold & Flu - NIGHT Tablets 24s",
        )
        # special_price=19.5 should be preferred over price=25.0
        self.assertEqual(first.price, 19.5)
        self.assertEqual(first.currency, "AED")
        self.assertEqual(first.rating, "4.2")
        self.assertIn("/p/panadol-cold-flu-night-24s/1068001", first.url)
        self.assertTrue(
            first.url.startswith(
                "https://www.myaster.com/en/online-pharmacy"
            )
        )

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_null_special_price_falls_back_to_price(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify price fallback when special_price is null."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "aster_search.json"
        )

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        # Second product has special_price=null, should use price=18.0
        self.assertEqual(products[1].price, 18.0)

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_zero_special_price_falls_back_to_price(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify price fallback when special_price is 0."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "aster_search.json"
        )

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        # Third product has special_price=0, should use price=22.0
        self.assertEqual(products[2].price, 22.0)

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_empty_product_url_stays_empty(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify products with empty productUrl get an empty URL."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "aster_search.json"
        )

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        # Third product has empty productUrl
        self.assertEqual(products[2].url, "")

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_search_handles_empty_data(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [],
            "totalPages": 0,
            "totalItems": 0,
        }
        mock_session.get.return_value = mock_resp

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent")

        self.assertEqual(products, [])

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_search_handles_http_error(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling on HTTP errors."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_session.get.return_value = mock_resp

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    @patch("src.scrapers.aster_scraper.curl_requests.Session")
    def test_search_handles_network_exception(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when the network call raises."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        scraper = AsterScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
