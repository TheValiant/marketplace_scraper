# tests/test_app.py

"""Smoke tests for the TUI application using Textual's Pilot."""

import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from textual.widgets import Checkbox, DataTable, Input, Static

from src.models.product import Product
from src.ui.app import EcomSearchApp


class TestEcomSearchApp(unittest.IsolatedAsyncioTestCase):
    """Smoke tests for the Textual TUI."""

    async def test_app_composes_without_crash(self) -> None:
        """Verify the app starts and renders all widgets."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            # Core widgets exist
            app.query_one("#search_input", Input)
            app.query_one("#search_btn")
            app.query_one("#results_table", DataTable)
            app.query_one("#status", Static)
            app.query_one("#source_toggles")
            await pilot.pause()

    async def test_all_source_checkboxes_present(self) -> None:
        """Verify a checkbox exists for every registered source."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            for src in app.settings.AVAILABLE_SOURCES:
                cb = app.query_one(
                    f"#check_{src['id']}", Checkbox
                )
                self.assertTrue(cb.value)
            await pilot.pause()

    async def test_empty_query_shows_warning(self) -> None:
        """Verify submitting an empty query triggers a notification."""
        app = EcomSearchApp()
        async with app.run_test(notifications=True) as pilot:
            await pilot.click("#search_btn")
            await pilot.pause()
            # No products should have been fetched
            self.assertEqual(app.products, [])

    async def test_uncheck_all_sources_shows_error(self) -> None:
        """Verify searching with all sources unchecked notifies user."""
        app = EcomSearchApp()
        async with app.run_test(notifications=True) as pilot:
            # Uncheck all sources
            for src in app.settings.AVAILABLE_SOURCES:
                cb = app.query_one(
                    f"#check_{src['id']}", Checkbox
                )
                cb.value = False

            # Type a query and search
            search_input = app.query_one("#search_input", Input)
            search_input.value = "test"
            await pilot.click("#search_btn")
            await pilot.pause()

    async def test_search_populates_table(self) -> None:
        """Verify successful search fills the results table."""
        fake_products = [
            Product(
                title="Test Product",
                price=99.0,
                currency="AED",
                rating="4.5",
                url="https://example.com/p/1",
                source="noon",
            ),
            Product(
                title="Cheap Product",
                price=49.0,
                currency="AED",
                rating="3.0",
                url="https://example.com/p/2",
                source="noon",
            ),
        ]

        with patch("src.ui.app._load_scraper_class") as mock_load:
            mock_scraper_instance = MagicMock()
            mock_scraper_instance.search.return_value = fake_products
            mock_cls: Any = MagicMock(
                return_value=mock_scraper_instance
            )
            mock_load.return_value = mock_cls

            app = EcomSearchApp()
            app._auto_save_results = MagicMock()  # type: ignore[method-assign]
            async with app.run_test() as pilot:
                # Enable only one source for deterministic count
                sources = app.settings.AVAILABLE_SOURCES
                for src in sources[1:]:
                    cb = app.query_one(
                        f"#check_{src['id']}", Checkbox
                    )
                    cb.value = False

                search_input = app.query_one("#search_input", Input)
                search_input.value = "test"
                await pilot.click("#search_btn")
                await pilot.pause()
                await pilot.pause()

                self.assertEqual(len(app.products), 2)
                table = cast(
                    DataTable[str],
                    app.query_one("#results_table", DataTable),
                )
                self.assertEqual(table.row_count, 2)

    async def test_checkbox_toggle_limits_sources(self) -> None:
        """Verify unchecking a source excludes it from search."""
        call_count = 0

        def make_scraper() -> Any:
            nonlocal call_count
            call_count += 1
            s = MagicMock()
            s.search.return_value = []
            return s

        with patch(
            "src.ui.app._load_scraper_class"
        ) as mock_load:
            mock_load.return_value = make_scraper

            app = EcomSearchApp()
            app._auto_save_results = MagicMock()  # type: ignore[method-assign]
            async with app.run_test() as pilot:
                # Uncheck all except first source
                sources = app.settings.AVAILABLE_SOURCES
                for src in sources[1:]:
                    cb = app.query_one(
                        f"#check_{src['id']}", Checkbox
                    )
                    cb.value = False

                search_input = app.query_one("#search_input", Input)
                search_input.value = "test"
                await pilot.click("#search_btn")
                await pilot.pause()
                await pilot.pause()

                # Only 1 scraper should have been instantiated
                self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
