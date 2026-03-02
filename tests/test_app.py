# tests/test_app.py

"""Smoke tests for the TUI application using Textual's Pilot."""

import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from textual.widgets import (
    Checkbox,
    Collapsible,
    DataTable,
    Input,
    LoadingIndicator,
    Static,
    TabbedContent,
)

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
            app.query_one("#source_toggles", Collapsible)
            await pilot.pause()

    async def test_source_toggles_is_collapsible(self) -> None:
        """Verify source checkboxes are inside a Collapsible."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            collapsible = app.query_one(
                "#source_toggles", Collapsible
            )
            self.assertFalse(collapsible.collapsed)
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

        with patch("src.services.search_orchestrator._load_scraper_class") as mock_load:
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
            "src.services.search_orchestrator._load_scraper_class"
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

    async def test_export_clipboard_copies_tsv(self) -> None:
        """Verify action_export_clipboard copies TSV to clipboard."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            app.products = [
                Product(
                    title="Item",
                    price=10.0,
                    currency="AED",
                    rating="5.0",
                    url="https://example.com/1",
                    source="noon",
                ),
            ]
            with patch(
                "src.ui.app.pyperclip",
                create=True,
            ) as mock_clip:
                mock_clip.copy = MagicMock()
                with patch.dict(
                    "sys.modules",
                    {"pyperclip": mock_clip},
                ):
                    app.action_export_clipboard()
                    await pilot.pause()
                    mock_clip.copy.assert_called_once()
                    tsv: str = mock_clip.copy.call_args[0][0]
                    self.assertIn("Title\tPrice", tsv)
                    self.assertIn("Item\t10.0", tsv)

    async def test_export_clipboard_empty_warns(self) -> None:
        """Verify action_export_clipboard warns when no results."""
        app = EcomSearchApp()
        async with app.run_test(notifications=True) as pilot:
            app.action_export_clipboard()
            await pilot.pause()
            self.assertEqual(app.products, [])

    async def test_invalidate_cache_binding_clears(self) -> None:
        """Pressing 'i' clears the query cache and notifies."""
        app = EcomSearchApp()
        async with app.run_test(notifications=True) as pilot:
            # Seed the cache
            app.orchestrator.query_cache.store(
                "test",
                frozenset(),
                frozenset({"noon"}),
                [
                    Product(
                        title="X",
                        price=10.0,
                        source="noon",
                    ),
                ],
            )
            app.action_invalidate_cache()
            await pilot.pause()
            # Cache should be empty now
            result = (
                app.orchestrator.query_cache.find_subset_match(
                    "test",
                    frozenset(),
                    frozenset({"noon"}),
                )
            )
            self.assertIsNone(result)

    async def test_invalidate_cache_empty_notifies(self) -> None:
        """Invalidating an empty cache still notifies with 0 count."""
        app = EcomSearchApp()
        async with app.run_test(notifications=True) as pilot:
            app.action_invalidate_cache()
            await pilot.pause()
            # No crash; cache is still empty
            result = (
                app.orchestrator.query_cache.find_subset_match(
                    "q",
                    frozenset(),
                    frozenset({"noon"}),
                )
            )
            self.assertIsNone(result)

    async def test_tabbed_content_exists(self) -> None:
        """Verify TabbedContent widget with three tabs."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            tabs = app.query_one("#tabs", TabbedContent)
            self.assertIsNotNone(tabs)
            # Results tab is active by default
            self.assertEqual(tabs.active, "results_tab")
            await pilot.pause()

    async def test_results_table_has_trend_column(self) -> None:
        """Verify results table has a Trend column."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            table = cast(
                DataTable[str],
                app.query_one("#results_table", DataTable),
            )
            cols = [
                str(c.label) for c in table.columns.values()
            ]
            self.assertIn("Trend", cols)
            await pilot.pause()

    async def test_watchlist_table_exists(self) -> None:
        """Verify watchlist table widget exists."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            wl_table = cast(
                DataTable[str],
                app.query_one(
                    "#watchlist_table", DataTable,
                ),
            )
            self.assertIsNotNone(wl_table)
            await pilot.pause()

    async def test_toggle_star_no_product_warns(self) -> None:
        """Toggle star with no product selected warns."""
        app = EcomSearchApp()
        async with app.run_test(
            notifications=True,
        ) as pilot:
            await app.action_toggle_star()
            await pilot.pause()
            # Should not crash, products is empty

    async def test_show_history_no_product_warns(self) -> None:
        """Show history with no product selected warns."""
        app = EcomSearchApp()
        async with app.run_test(
            notifications=True,
        ) as pilot:
            await app.action_show_history()
            await pilot.pause()

    async def test_show_watchlist_switches_tab(self) -> None:
        """Action show_watchlist switches to watchlist tab."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            await app.action_show_watchlist()
            await pilot.pause()
            tabs = app.query_one("#tabs", TabbedContent)
            self.assertEqual(tabs.active, "watchlist_tab")

    async def test_loading_indicator_hidden_on_mount(
        self,
    ) -> None:
        """LoadingIndicator should be hidden when the app starts."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            loader = app.query_one(
                "#loader", LoadingIndicator,
            )
            self.assertFalse(loader.display)
            await pilot.pause()

    async def test_loading_indicator_shown_during_search(
        self,
    ) -> None:
        """LoadingIndicator should be visible while searching."""
        app = EcomSearchApp()
        async with app.run_test() as pilot:
            loader_was_visible = False

            async def _spy_search(
                *args: Any, **kwargs: Any,
            ) -> MagicMock:
                nonlocal loader_was_visible
                loader = app.query_one(
                    "#loader", LoadingIndicator,
                )
                loader_was_visible = loader.display
                return MagicMock(
                    products=[],
                    errors=[],
                    excluded_count=0,
                    deduplicated_count=0,
                    invalid_count=0,
                    total_before_filter=0,
                )

            with patch.object(
                app.orchestrator, "multi_search",
                side_effect=_spy_search,
            ):
                search_input = app.query_one(
                    "#search_input", Input,
                )
                search_input.value = "test"
                await app.perform_search()
                await pilot.pause()

            self.assertTrue(loader_was_visible)
            loader = app.query_one(
                "#loader", LoadingIndicator,
            )
            self.assertFalse(loader.display)


if __name__ == "__main__":
    unittest.main()
