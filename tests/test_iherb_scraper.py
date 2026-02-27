# tests/test_iherb_scraper.py

"""Tests for the iHerb scraper using mocked HTTP responses."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.scrapers.iherb_scraper import IherbScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestIherbScraper(unittest.TestCase):
    """Tests for the iHerb scraper using mocked fixture HTML."""

    def _make_mock_response(
        self, fixture_name: str,
    ) -> MagicMock:
        """Create a mock response from a fixture HTML file."""
        fixture_path = FIXTURES_DIR / fixture_name
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = fixture_path.read_text()
        return mock_resp

    # ------------------------------------------------------------------
    # Primary path: __NEXT_DATA__ JSON extraction
    # ------------------------------------------------------------------

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_returns_products(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify that search() parses __NEXT_DATA__ into Products."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        self.assertEqual(len(products), 4)
        self.assertTrue(
            all(p.source == "iherb" for p in products)
        )

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_product_fields_parsed_correctly(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify individual product field parsing from JSON."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        first = products[0]
        self.assertIn("CollagenUP", first.title)
        # discountPrice (63.53) is preferred over price (79.41)
        self.assertEqual(first.price, 63.53)
        self.assertEqual(first.currency, "AED")
        self.assertEqual(first.rating, "4.6")
        self.assertIn("/pr/california-gold", first.url)
        self.assertTrue(
            first.url.startswith("https://ae.iherb.com")
        )

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_title_fallback_name(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify fallback from 'title' to 'name' field."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        # Second product uses 'name' (no 'title' key)
        self.assertIn("Sports Research", products[1].title)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_title_fallback_product_name(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify fallback from 'title'/'name' to 'productName'."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        # Third product uses 'productName'
        self.assertIn("Doctor's Best", products[2].title)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_price_fallback_sale_price(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify salePrice is used when price is 0."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        # Third product: price=0, salePrice=52.38
        self.assertEqual(products[2].price, 52.38)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_absolute_url_preserved(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify absolute URLs are not double-prefixed."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        # Second product has absolute URL
        self.assertTrue(
            products[1].url.startswith(
                "https://ae.iherb.com/pr/"
            )
        )
        # Should NOT be double-prefixed
        self.assertFalse(
            products[1].url.startswith(
                "https://ae.iherb.comhttps://"
            )
        )

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_empty_url_stays_empty(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify products with empty URL get empty string."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_search.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        # Fourth product has empty url
        self.assertEqual(products[3].url, "")

    # ------------------------------------------------------------------
    # Fallback path: CSS selector extraction
    # ------------------------------------------------------------------

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_fallback_to_css_selectors(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify CSS selector fallback when __NEXT_DATA__ is absent."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = (
            self._make_mock_response("iherb_no_json.html")
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("collagen")

        self.assertEqual(len(products), 2)
        self.assertEqual(
            products[0].title, "CSS Fallback Product One"
        )
        self.assertEqual(products[0].price, 45.0)
        self.assertEqual(products[0].rating, "4.1")
        self.assertTrue(
            products[0].url.startswith(
                "https://ae.iherb.com/pr/"
            )
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @patch("src.scrapers.base_scraper.cloudscraper")
    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_http_failure(
        self,
        mock_session_cls: MagicMock,
        mock_cloudscraper: MagicMock,
    ) -> None:
        """Verify graceful handling when HTTP request fails."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_session.get.return_value = mock_resp

        # cloudscraper fallback also fails
        mock_cs_scraper = MagicMock()
        mock_cs_resp = MagicMock()
        mock_cs_resp.status_code = 403
        mock_cs_scraper.get.return_value = mock_cs_resp
        mock_cloudscraper.create_scraper.return_value = (
            mock_cs_scraper
        )

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("test")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_empty_products(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Verify graceful handling when no products in JSON."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = (
            '<!DOCTYPE html><html><body>'
            '<script id="__NEXT_DATA__" '
            'type="application/json">'
            '{"props":{"pageProps":{"products":[]}}}'
            '</script></body></html>'
        )
        mock_session.get.return_value = mock_resp

        scraper = IherbScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent")

        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
