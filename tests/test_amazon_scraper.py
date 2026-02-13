# tests/test_amazon_scraper.py

"""Tests for the Amazon scraper using mocked HTTP responses."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from src.scrapers.amazon_scraper import AmazonScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestAmazonScraper(unittest.TestCase):
    """Tests for the Amazon scraper using mocked HTTP responses."""

    def _load_fixture_soup(self, fixture_name: str) -> BeautifulSoup:
        """Load an HTML fixture file as a BeautifulSoup object."""
        fixture_path = FIXTURES_DIR / fixture_name
        with open(fixture_path, encoding="utf-8") as f:
            return BeautifulSoup(f.read(), "lxml")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_returns_products(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify that search() parses a fixture page into Product objects."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(FIXTURES_DIR / "amazon_search.html", encoding="utf-8") as f:
            mock_resp.text = f.read()
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(len(products), 4)
        self.assertTrue(all(p.source == "amazon" for p in products))

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_product_title_parsed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify product titles are extracted correctly."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(FIXTURES_DIR / "amazon_search.html", encoding="utf-8") as f:
            mock_resp.text = f.read()
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(
            products[0].title,
            "Apple iPhone 15 Pro Max 256GB - Natural Titanium",
        )
        self.assertEqual(
            products[1].title,
            "Samsung Galaxy S24 Ultra 512GB Titanium Gray",
        )

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_product_price_parsed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify prices are extracted and parsed to float."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(FIXTURES_DIR / "amazon_search.html", encoding="utf-8") as f:
            mock_resp.text = f.read()
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(products[0].price, 4899.0)
        self.assertEqual(products[1].price, 4199.0)
        # Product 3 has no price element
        self.assertEqual(products[2].price, 0.0)
        self.assertEqual(products[3].price, 3099.0)

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_product_rating_parsed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify ratings are parsed correctly."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(FIXTURES_DIR / "amazon_search.html", encoding="utf-8") as f:
            mock_resp.text = f.read()
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertEqual(products[0].rating, "4.6 out of 5 stars")
        # Product 3 has no rating
        self.assertEqual(products[2].rating, "")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_product_url_constructed(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify URLs are constructed with the amazon.ae prefix."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with open(FIXTURES_DIR / "amazon_search.html", encoding="utf-8") as f:
            mock_resp.text = f.read()
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertTrue(
            products[0].url.startswith("https://www.amazon.ae/")
        )
        self.assertIn("B0CTEST001", products[0].url)
        # Product 4 has no link
        self.assertEqual(products[3].url, "")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_empty_page(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body></body></html>"
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent_product_xyz")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_http_error(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling on HTTP errors (all retries fail)."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_session.get.return_value = mock_resp

        scraper = AmazonScraper()
        scraper.session = mock_session

        # Also mock cloudscraper fallback
        with patch("src.scrapers.base_scraper.cloudscraper") as mock_cs:
            mock_cs_scraper = MagicMock()
            mock_cs.create_scraper.return_value = mock_cs_scraper
            mock_cs_resp = MagicMock()
            mock_cs_resp.status_code = 503
            mock_cs_scraper.get.return_value = mock_cs_resp

            products = scraper.search("iphone")

        self.assertEqual(products, [])

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_network_exception(
        self, mock_session_cls: MagicMock
    ) -> None:
        """Verify graceful handling when network is unreachable."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        scraper = AmazonScraper()
        scraper.session = mock_session

        with patch("src.scrapers.base_scraper.cloudscraper") as mock_cs:
            mock_cs.create_scraper.return_value.get.side_effect = (
                ConnectionError("Network unreachable")
            )
            products = scraper.search("iphone")

        self.assertEqual(products, [])

    def test_extract_price_various_formats(self) -> None:
        """Verify BaseScraper.extract_price handles different price formats."""
        scraper = AmazonScraper()

        self.assertEqual(scraper.extract_price("AED 1,299.00"), 1299.0)
        self.assertEqual(scraper.extract_price("4,899.00"), 4899.0)
        self.assertEqual(scraper.extract_price("199"), 199.0)
        self.assertEqual(scraper.extract_price(""), 0.0)
        self.assertEqual(scraper.extract_price(None), 0.0)


if __name__ == "__main__":
    unittest.main()
