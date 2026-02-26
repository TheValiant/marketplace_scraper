# tests/test_binsina_scraper.py

"""Tests for the BinSina scraper using mocked HTTP responses."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.scrapers.binsina_scraper import BinSinaScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestBinSinaScraper(unittest.TestCase):
    """Tests for the BinSina scraper using mocked HTTP responses."""

    def _make_algolia_response(self, fixture_name: str) -> MagicMock:
        """Create a mock response from a fixture JSON file."""
        fixture_path = FIXTURES_DIR / fixture_name
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(fixture_path) as f:
            data = json.load(f)
        mock_resp.json.return_value = data
        return mock_resp

    def _make_homepage_response(self) -> MagicMock:
        """Create a mock response for the BinSina homepage."""
        fixture_path = FIXTURES_DIR / "binsina_homepage.html"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(fixture_path) as f:
            mock_resp.text = f.read()
        return mock_resp

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_search_returns_products(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify that search() parses Algolia hits into Product objects."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        homepage_resp = self._make_homepage_response()
        algolia_resp = self._make_algolia_response("binsina_algolia.json")
        mock_session.get.return_value = homepage_resp
        mock_session.post.return_value = algolia_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(len(products), 4)
        self.assertTrue(all(p.source == "binsina" for p in products))

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_product_fields_parsed_correctly(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify individual product field parsing."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()
        mock_session.post.return_value = self._make_algolia_response(
            "binsina_algolia.json"
        )

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        first = products[0]
        self.assertEqual(
            first.title, "Panadol Extra Optizorb 500mg/65mg Tablets 24s"
        )
        self.assertEqual(first.price, 18.90)
        self.assertEqual(first.currency, "AED")
        self.assertEqual(first.rating, "85")
        self.assertIn("panadol-extra-optizorb", first.url)
        self.assertTrue(first.url.startswith("https://binsina.ae"))

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_empty_url_not_prefixed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify products with empty URL stay empty."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()
        mock_session.post.return_value = self._make_algolia_response(
            "binsina_algolia.json"
        )

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        # Fourth product has empty url in fixture
        self.assertEqual(products[3].url, "")

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_null_rating_becomes_empty_string(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify null rating_summary maps to empty string."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()
        mock_session.post.return_value = self._make_algolia_response(
            "binsina_algolia.json"
        )

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products[3].rating, "None")

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_api_key_extraction(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify API key is extracted from the homepage."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        scraper = BinSinaScraper()
        scraper.session = mock_session
        result = scraper._refresh_api_key()

        self.assertTrue(result)
        self.assertEqual(scraper._api_key, "test_algolia_api_key_abc123")

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_search_handles_empty_hits(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.json.return_value = {"hits": [], "nbPages": 0}
        mock_session.post.return_value = empty_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent")

        self.assertEqual(products, [])

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_search_handles_homepage_failure(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when homepage fetch fails."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        error_resp = MagicMock()
        error_resp.status_code = 503
        mock_session.get.return_value = error_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    @patch("src.scrapers.binsina_scraper.curl_requests.Session")
    def test_search_handles_network_exception(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when the network call raises."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
