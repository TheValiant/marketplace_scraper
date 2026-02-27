# tests/test_binsina_scraper.py

"""Tests for the BinSina scraper using mocked HTTP responses."""

import json
import unittest
from pathlib import Path
from typing import Any
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
        mock_resp.text = json.dumps(data)
        return mock_resp

    def _make_homepage_response(self) -> MagicMock:
        """Create a mock response for the BinSina homepage."""
        fixture_path = FIXTURES_DIR / "binsina_homepage.html"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(fixture_path) as f:
            mock_resp.text = f.read()
        return mock_resp

    @patch("src.scrapers.base_scraper.curl_requests.Session")
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

    @patch("src.scrapers.base_scraper.curl_requests.Session")
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

    @patch("src.scrapers.base_scraper.curl_requests.Session")
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

    @patch("src.scrapers.base_scraper.curl_requests.Session")
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

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_api_key_extraction(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify API key is extracted from the homepage."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        scraper = BinSinaScraper()
        scraper.session = mock_session
        result = scraper.refresh_api_key()

        self.assertTrue(result)
        self.assertEqual(scraper.api_key, "test_algolia_api_key_abc123")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_empty_hits(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_data: dict[str, Any] = {"hits": [], "nbPages": 0}
        empty_resp.json.return_value = empty_data
        empty_resp.text = json.dumps(empty_resp.json.return_value)
        mock_session.post.return_value = empty_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
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

    @patch("src.scrapers.base_scraper.curl_requests.Session")
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

    # --- API key edge-case tests ---

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_api_key_missing_from_homepage(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when algoliaConfig is absent."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>No algolia here</body></html>"
        mock_session.get.return_value = resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        result = scraper.refresh_api_key()

        self.assertFalse(result)
        self.assertEqual(scraper.api_key, "")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_api_key_empty_in_config(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify handling when algoliaConfig exists but apiKey is empty."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        html = (
            '<html><script>'
            'window.algoliaConfig = {"apiKey": "", "appId": "X"};'
            '</script></html>'
        )
        resp = MagicMock()
        resp.status_code = 200
        resp.text = html
        mock_session.get.return_value = resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        result = scraper.refresh_api_key()

        self.assertFalse(result)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_api_key_homepage_network_failure(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify handling when homepage request raises exception."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("timeout")

        scraper = BinSinaScraper()
        scraper.session = mock_session
        result = scraper.refresh_api_key()

        self.assertFalse(result)
        self.assertEqual(scraper.api_key, "")

    # --- Retry behaviour tests ---

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_retry_then_succeed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify search recovers after transient POST failures."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        fail_resp = MagicMock()
        fail_resp.status_code = 503

        ok_resp = self._make_algolia_response("binsina_algolia.json")
        mock_session.post.side_effect = [fail_resp, fail_resp, ok_resp]

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertGreater(len(products), 0)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_all_retries_exhausted(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify empty list when all POST retries fail."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        mock_session.post.return_value = fail_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    # --- Malformed data tests ---

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_invalid_json_response(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling of non-JSON response from Algolia."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.text = "not valid json"
        mock_session.post.return_value = bad_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_unexpected_json_structure(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify handling when JSON is valid but missing 'hits' key."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = self._make_homepage_response()

        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.text = json.dumps({"results": [], "total": 0})
        mock_session.post.return_value = bad_resp

        scraper = BinSinaScraper()
        scraper.session = mock_session
        products = scraper.search("panadol")

        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
