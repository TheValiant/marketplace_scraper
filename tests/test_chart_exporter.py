# tests/test_chart_exporter.py

"""Tests for the Plotly chart exporter."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.models.product import Product
from src.storage.chart_exporter import (
    export_comparison_chart,
    export_price_chart,
    export_watchlist_dashboard,
)
from src.storage.price_history_db import PriceHistoryDB


class _DBMixin:
    """Provide an in-memory PriceHistoryDB with sample data."""

    db: PriceHistoryDB

    def _setup_db(self) -> None:
        """Set up a temporary in-memory database with products."""
        self.db = PriceHistoryDB(db_path=Path(":memory:"))
        now = datetime.now()
        products = [
            Product(
                title="Test Collagen Powder",
                price=50.0 + i * 2,
                currency="AED",
                rating="4.5",
                url=f"https://www.amazon.ae/dp/B000{i}",
                source="amazon",
            )
            for i in range(5)
        ]
        # Record multiple snapshots across time
        for day in range(5):
            at = now - timedelta(days=5 - day)
            adjusted = [
                Product(
                    title=p.title,
                    price=p.price + day,
                    currency=p.currency,
                    rating=p.rating,
                    url=p.url,
                    source=p.source,
                )
                for p in products
            ]
            self.db.record_snapshots(
                adjusted, scraped_at=at,
            )


class TestExportPriceChart(
    _DBMixin, unittest.TestCase,
):
    """Tests for single-product chart export."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self._setup_db()

    def tearDown(self) -> None:
        """Clean up."""
        self.db.close()

    @patch("src.storage.chart_exporter.webbrowser")
    def test_generates_html_file(
        self, _mock_wb: object,
    ) -> None:
        """Export should create an HTML file."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.storage.chart_exporter._CHARTS_DIR",
                Path(tmp),
            ):
                result = export_price_chart(
                    "https://www.amazon.ae/dp/B0000",
                    self.db,
                    open_browser=False,
                )
                self.assertIsNotNone(result)
                assert result is not None
                self.assertTrue(result.exists())
                content = result.read_text()
                self.assertIn("plotly", content.lower())

    def test_returns_none_for_insufficient_data(
        self,
    ) -> None:
        """Export should return None when < 2 snapshots."""
        # Create product with only 1 snapshot
        db2 = PriceHistoryDB(db_path=Path(":memory:"))
        db2.record_snapshots([
            Product(
                title="Single",
                price=10.0,
                currency="AED",
                rating="",
                url="https://example.com/single",
                source="noon",
            ),
        ])
        result = export_price_chart(
            "https://example.com/single",
            db2,
            open_browser=False,
        )
        self.assertIsNone(result)
        db2.close()


class TestExportComparisonChart(
    _DBMixin, unittest.TestCase,
):
    """Tests for multi-product comparison chart."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self._setup_db()

    def tearDown(self) -> None:
        """Clean up."""
        self.db.close()

    @patch("src.storage.chart_exporter.webbrowser")
    def test_generates_comparison_html(
        self, _mock_wb: object,
    ) -> None:
        """Comparison chart should include multiple traces."""
        urls = [
            f"https://www.amazon.ae/dp/B000{i}"
            for i in range(3)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.storage.chart_exporter._CHARTS_DIR",
                Path(tmp),
            ):
                result = export_comparison_chart(
                    urls, self.db,
                    open_browser=False,
                )
                self.assertIsNotNone(result)
                assert result is not None
                self.assertTrue(result.exists())

    def test_returns_none_for_empty_urls(self) -> None:
        """Comparison with no matching URLs returns None."""
        result = export_comparison_chart(
            ["https://nonexistent.example.com"],
            self.db,
            open_browser=False,
        )
        self.assertIsNone(result)


class TestExportWatchlistDashboard(
    _DBMixin, unittest.TestCase,
):
    """Tests for the watchlist dashboard chart."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self._setup_db()

    def tearDown(self) -> None:
        """Clean up."""
        self.db.close()

    def test_returns_none_when_no_stars(self) -> None:
        """Dashboard returns None with no starred products."""
        result = export_watchlist_dashboard(
            self.db, open_browser=False,
        )
        self.assertIsNone(result)

    @patch("src.storage.chart_exporter.webbrowser")
    def test_generates_dashboard_with_stars(
        self, _mock_wb: object,
    ) -> None:
        """Dashboard should generate chart for starred products."""
        self.db.toggle_star(
            "https://www.amazon.ae/dp/B0000",
        )
        self.db.toggle_star(
            "https://www.amazon.ae/dp/B0001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.storage.chart_exporter._CHARTS_DIR",
                Path(tmp),
            ):
                result = export_watchlist_dashboard(
                    self.db, open_browser=False,
                )
                self.assertIsNotNone(result)
                assert result is not None
                self.assertTrue(result.exists())


if __name__ == "__main__":
    unittest.main()
