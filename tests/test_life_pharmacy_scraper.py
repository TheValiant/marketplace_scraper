# tests/test_life_pharmacy_scraper.py

"""Tests for the Life Pharmacy scraper using mocked HTTP responses."""

import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from src.scrapers.life_pharmacy_scraper import LifePharmacyScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLifePharmacyScraper(unittest.TestCase):
    """Tests for the Life Pharmacy scraper using mocked HTTP responses."""

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

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_returns_products(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify that search() parses API response into Product objects."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "life_pharmacy_search.json"
        )

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(len(products), 3)
        self.assertTrue(
            all(p.source == "life_pharmacy" for p in products)
        )

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_product_fields_parsed_correctly(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify individual product field parsing."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "life_pharmacy_search.json"
        )

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        first = products[0]
        self.assertEqual(
            first.title,
            "Panadol Extra Optizorb 500mg/65mg 24 Tablets",
        )
        self.assertEqual(first.price, 17.50)
        self.assertEqual(first.currency, "AED")
        self.assertEqual(first.rating, "4.5")
        self.assertIn("panadol-extra-optizorb-24-tablets", first.url)
        self.assertTrue(
            first.url.startswith("https://www.lifepharmacy.com/product")
        )
        self.assertIn("panadol_extra.jpg", first.image_url)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_zero_offer_price_returns_zero(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify offer_price of 0 is preserved as 0.0."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "life_pharmacy_search.json"
        )

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        # Third product has offer_price=0
        self.assertEqual(products[2].price, 0.0)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_empty_rating_remains_empty(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify empty rating string is preserved."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_mock_response(
            "life_pharmacy_search.json"
        )

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products[2].rating, "")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_empty_products(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        empty_data: dict[str, Any] = {
            "success": True,
            "data": {"products": []},
        }
        mock_resp.json.return_value = empty_data
        mock_resp.text = json.dumps(mock_resp.json.return_value)
        mock_session.get.return_value = mock_resp

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_http_error(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling on HTTP errors."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_session.get.return_value = mock_resp

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_network_exception(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when the network call raises."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    # --- Retry behaviour tests ---

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_retry_then_succeed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify search recovers after transient failures."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        fail_resp = MagicMock()
        fail_resp.status_code = 503

        ok_resp = self._make_mock_response("life_pharmacy_search.json")
        mock_session.get.side_effect = [fail_resp, fail_resp, ok_resp]

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertGreater(len(products), 0)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_all_retries_exhausted(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify empty list when all retry attempts fail."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        mock_session.get.return_value = fail_resp

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    # --- Malformed data tests ---

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_invalid_json_response(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling of non-JSON response body."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "not valid json"
        mock_session.get.return_value = mock_resp

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_unexpected_json_structure(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify handling when JSON is valid but missing 'data' key."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({"success": True, "items": []})
        mock_session.get.return_value = mock_resp

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_data_not_dict(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify handling when 'data' is a list instead of dict."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({"success": True, "data": []})
        mock_session.get.return_value = mock_resp

        scraper = LifePharmacyScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
