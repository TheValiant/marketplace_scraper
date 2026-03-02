# src/ui/app.py

"""Terminal UI for the ecom_search price comparison engine."""

import asyncio
import logging
import webbrowser
from collections.abc import Mapping, Sequence
from typing import cast

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
)
from textual_plotext import PlotextPlot

from src.config.settings import Settings
from src.models.product import Product
from src.services.search_orchestrator import SearchOrchestrator
from src.storage.file_manager import FileManager
from src.storage.price_history_db import PriceHistoryDB

logger = logging.getLogger("ecom_search.ui")


class EcomSearchApp(App[object]):
    """Terminal UI for the ecom_search price comparison engine."""

    CSS_PATH = "styles.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "save", "Save"),
        Binding("e", "export", "Export CSV"),
        Binding("p", "sort_price", "Price Sort"),
        Binding("r", "sort_rating", "Rating Sort"),
        Binding("c", "copy_url", "Copy URL"),
        Binding("x", "export_clipboard", "Copy All"),
        Binding("i", "invalidate_cache", "Clear Cache"),
        Binding("h", "show_history", "History"),
        Binding("t", "toggle_star", "Star"),
        Binding("w", "show_watchlist", "Watchlist"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.products: list[Product] = []
        self.current_query: str = ""
        self.file_manager = FileManager()
        self.settings = Settings()
        self.orchestrator = SearchOrchestrator()
        self.price_db = PriceHistoryDB()

    def compose(self) -> ComposeResult:
        """Build the widget tree for the TUI."""
        sources = self.settings.AVAILABLE_SOURCES
        source_checkboxes = [
            Checkbox(
                src["label"], value=True,
                id=f"check_{src['id']}",
            )
            for src in sources
        ]
        source_names = ", ".join(
            s["label"] for s in sources
        )

        # Arrange checkboxes in rows of 3
        row_size = 3
        checkbox_rows: list[Horizontal] = [
            Horizontal(
                *source_checkboxes[i:i + row_size],
                classes="checkbox-row",
            )
            for i in range(
                0, len(source_checkboxes), row_size,
            )
        ]

        yield Header()
        with Container(id="main_container"):
            yield Static(
                f"🛒 E-commerce Search ({source_names})",
                id="title",
            )

            # Search Bar
            with Horizontal(id="search_bar"):
                yield Input(
                    placeholder=(
                        "Search products"
                        " (use ; for multiple queries)..."
                    ),
                    id="search_input",
                )
                yield Button(
                    "Search", variant="primary",
                    id="search_btn",
                )

            # Negative Keyword Filter
            yield Input(
                placeholder=(
                    "Exclude keywords (comma-separated),"
                    " e.g. serum, cream, mask..."
                ),
                id="filter_input",
            )

            # Source Selection Checkboxes
            yield Collapsible(
                *checkbox_rows,
                title="Sources",
                id="source_toggles",
                collapsed=False,
            )

            yield Static("Ready", id="status")

            # Tabbed view
            with TabbedContent(id="tabs"):
                with TabPane("Results", id="results_tab"):
                    yield cast(
                        DataTable[str | Text],
                        DataTable(
                            id="results_table",
                            zebra_stripes=True,
                            cursor_type="row",
                        ),
                    )
                with TabPane(
                    "Price History",
                    id="history_tab",
                ):
                    with Vertical(
                        id="history_container",
                    ):
                        yield Static(
                            "Select a product and press"
                            " [bold]h[/bold] to view "
                            "price history",
                            id="history_label",
                        )
                        yield Static(
                            "", id="history_stats",
                        )
                        yield PlotextPlot(
                            id="history_chart",
                        )
                with TabPane(
                    "Watchlist", id="watchlist_tab",
                ):
                    with Vertical(
                        id="watchlist_container",
                    ):
                        yield Static(
                            "Press [bold]t[/bold] to star"
                            " a product,"
                            " [bold]w[/bold] to view "
                            "watchlist",
                            id="watchlist_label",
                        )
                        yield cast(
                            DataTable[str | Text],
                            DataTable(
                                id="watchlist_table",
                                zebra_stripes=True,
                                cursor_type="row",
                            ),
                        )
        yield Footer()

    def on_mount(self) -> None:
        """Configure table columns on startup."""
        table = cast(
            DataTable[str | Text],
            self.query_one("#results_table", DataTable),
        )
        table.add_columns(
            "Title", "Price", "Rating", "Source", "Trend",
        )
        watchlist = cast(
            DataTable[str | Text],
            self.query_one("#watchlist_table", DataTable),
        )
        watchlist.add_columns(
            "Title", "Latest", "Min", "Max",
            "Avg", "Source", "Snapshots",
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button click events."""
        if event.button.id == "search_btn":
            await self.perform_search()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in the search input."""
        if event.input.id == "search_input":
            await self.perform_search()

    def _get_selected_sources(self) -> list[dict[str, str]]:
        """Return the list of sources whose checkboxes are checked."""
        selected: list[dict[str, str]] = []
        for src in self.settings.AVAILABLE_SOURCES:
            checkbox = self.query_one(
                f"#check_{src['id']}", Checkbox
            )
            if checkbox.value:
                selected.append(src)
        return selected

    def _parse_negative_keywords(self) -> list[str]:
        """Parse comma-separated negative keywords from the filter input."""
        filter_input = self.query_one("#filter_input", Input)
        return [
            kw.strip()
            for kw in filter_input.value.split(",")
            if kw.strip()
        ]

    async def perform_search(self) -> None:
        """Execute a search against the selected sources."""
        search_input = self.query_one(
            "#search_input", Input
        )
        query = search_input.value.strip()
        if not query:
            self.notify(
                "Please enter a search term", severity="warning"
            )
            return

        selected_sources = self._get_selected_sources()
        if not selected_sources:
            self.notify("Select at least one source!", severity="error")
            return

        negative_keywords = self._parse_negative_keywords()

        self.current_query = query
        self.products = []
        table = cast(
            DataTable[str | Text],
            self.query_one("#results_table", DataTable),
        )
        status = self.query_one("#status", Static)
        table.clear()
        status.update(f"🔍 Searching '{query}'...")

        result = await self.orchestrator.multi_search(
            query, selected_sources, negative_keywords
        )

        for error_msg in result.errors:
            self.notify(f"Error: {error_msg}", severity="error")

        self.products = result.products
        self.populate_table()

        if not self.products:
            status.update("❌ No products found")
        else:
            self._auto_save_results()
            removed = (
                result.excluded_count
                + result.deduplicated_count
                + result.invalid_count
            )
            if removed:
                parts: list[str] = []
                if result.excluded_count:
                    parts.append(
                        f"{result.excluded_count} filtered"
                    )
                if result.deduplicated_count:
                    parts.append(
                        f"{result.deduplicated_count} deduped"
                    )
                if result.invalid_count:
                    parts.append(
                        f"{result.invalid_count} invalid"
                    )
                detail = ", ".join(parts)
                status.update(
                    f"✅ Showing {len(self.products)} of"
                    f" {result.total_before_filter} products"
                    f" ({detail}, saved)"
                )
            else:
                status.update(
                    f"✅ Found {len(self.products)}"
                    f" products (saved)"
                )

    def _auto_save_results(self) -> None:
        """Automatically save search results after every successful search."""
        try:
            # Save combined results
            path = self.file_manager.save_results(
                self.current_query, self.products, "combined"
            )
            logger.info("Auto-saved combined results to %s", path)

            # Save per-source results
            sources = {p.source for p in self.products}
            for source in sources:
                source_products = [
                    p for p in self.products if p.source == source
                ]
                self.file_manager.save_results(
                    self.current_query, source_products, source
                )
        except Exception as e:
            logger.error("Auto-save failed: %s", e, exc_info=True)
            self.notify(f"Auto-save failed: {e}", severity="error")

    def populate_table(self) -> None:
        """Fill the DataTable with current product results."""
        table = cast(
            DataTable[str | Text],
            self.query_one("#results_table", DataTable),
        )
        table.clear()
        if not self.products:
            return

        # Batch-fetch trend data from DB
        urls = [p.url for p in self.products]
        trends = self.price_db.get_price_trends(urls)

        min_price = min(
            (p.price for p in self.products if p.price > 0),
            default=0,
        )

        for p in self.products:
            is_cheapest = (
                p.price == min_price and p.price > 0
            )
            price_style = (
                "bold green" if is_cheapest else ""
            )
            starred = self.price_db.is_starred(p.url)
            star = "★ " if starred else ""
            trend = self._trend_indicator(p.url, trends)
            table.add_row(
                f"{star}{p.title[:58]}",
                Text(
                    f"{p.price} {p.currency}",
                    style=price_style,
                ),
                f"⭐ {p.rating}" if p.rating else "",
                p.source.upper(),
                trend,
            )

    def _trend_indicator(
        self,
        url: str,
        trends: Mapping[str, Sequence[object]],
    ) -> str:
        """Return a mini trend arrow from historical data."""
        from src.storage.price_history_db import normalize_url

        norm = normalize_url(url)
        snapshots = trends.get(norm, [])
        if len(snapshots) < 2:
            return "·"
        first_price = getattr(snapshots[0], "price", 0.0)
        last_price = getattr(snapshots[-1], "price", 0.0)
        if first_price == 0:
            return "·"
        change = (last_price - first_price) / first_price
        if change < -0.05:
            return "↓"
        if change > 0.05:
            return "↑"
        return "→"

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        """Open the selected product's URL in the default browser."""
        if 0 <= event.cursor_row < len(self.products):
            webbrowser.open(
                self.products[event.cursor_row].url
            )

    def action_sort_price(self) -> None:
        """Sort products by price, ascending."""
        self.products.sort(
            key=lambda p: p.price if p.price > 0 else float("inf")
        )
        self.populate_table()

    def action_sort_rating(self) -> None:
        """Sort products by rating, descending."""
        self.products.sort(key=lambda p: p.rating or "", reverse=True)
        self.populate_table()

    def action_save(self) -> None:
        """Save current results to a JSON file."""
        if not self.products:
            self.notify("No results to save", severity="warning")
            return
        try:
            path = self.file_manager.save_results(
                self.current_query, self.products, "combined"
            )
            logger.info("Results saved to %s", path)
            self.notify(f"Saved to {path}")
        except Exception as e:
            logger.error("Failed to save results", exc_info=True)
            self.notify(f"Save failed: {e}", severity="error")

    def action_export(self) -> None:
        """Export current results to a CSV file."""
        if not self.products:
            self.notify("No results to export", severity="warning")
            return
        try:
            path = self.file_manager.export_csv(
                self.current_query, self.products, "combined"
            )
            logger.info("Exported results to %s", path)
            self.notify(f"Exported to {path}")
        except Exception as e:
            logger.error("Failed to export results", exc_info=True)
            self.notify(f"Export failed: {e}", severity="error")

    def action_copy_url(self) -> None:
        """Copy the selected product's URL to the clipboard."""
        try:
            import pyperclip  # type: ignore[import-untyped]

            table = cast(
                DataTable[str | Text],
                self.query_one("#results_table", DataTable),
            )
            row = table.cursor_row
            pyperclip.copy(self.products[row].url)
            self.notify("URL Copied")
        except Exception:
            logger.error(
                "Failed to copy URL to clipboard",
                exc_info=True,
            )
            self.notify(
                "Install pyperclip", severity="warning"
            )

    def action_export_clipboard(self) -> None:
        """Copy all results as tab-separated text to the clipboard."""
        if not self.products:
            self.notify("No results to copy", severity="warning")
            return
        try:
            import pyperclip  # type: ignore[import-untyped]

            tsv_text = self.file_manager.format_tsv(self.products)
            pyperclip.copy(tsv_text)
            self.notify(f"Copied {len(self.products)} products")
        except Exception:
            logger.error(
                "Failed to copy results to clipboard",
                exc_info=True,
            )
            self.notify(
                "Install pyperclip", severity="warning"
            )

    def action_invalidate_cache(self) -> None:
        """Purge the in-memory query result cache."""
        count = self.orchestrator.query_cache.clear()
        self.notify(
            f"Cache cleared ({count} entries purged)"
        )

    # ── Price history / star / watchlist actions ─────

    def _get_selected_product(self) -> Product | None:
        """Return the product under the DataTable cursor."""
        table = cast(
            DataTable[str | Text],
            self.query_one("#results_table", DataTable),
        )
        row = table.cursor_row
        if 0 <= row < len(self.products):
            return self.products[row]
        return None

    async def action_show_history(self) -> None:
        """Show price history chart for the selected product."""
        product = self._get_selected_product()
        if product is None:
            self.notify(
                "Select a product first",
                severity="warning",
            )
            return

        snapshots = await asyncio.to_thread(
            self.price_db.get_price_history, product.url,
        )
        summary = await asyncio.to_thread(
            self.price_db.get_trend_summary, product.url,
        )

        # Switch to history tab
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = "history_tab"

        # Update label
        label = self.query_one("#history_label", Static)
        label.update(
            f"[bold]{product.title[:60]}[/bold]"
            f"  ({product.source.upper()})"
        )

        # Update stats
        stats_widget = self.query_one(
            "#history_stats", Static,
        )
        if summary:
            stats_widget.update(
                f"Min: {summary['min']}  "
                f"Max: {summary['max']}  "
                f"Avg: {summary['avg']}  "
                f"Latest: {summary['latest']}  "
                f"Points: {summary['count']}"
            )
        else:
            stats_widget.update("No price history yet")

        # Draw chart
        chart = self.query_one(
            "#history_chart", PlotextPlot,
        )
        plt = chart.plt
        plt.clear_figure()

        if len(snapshots) >= 2:
            dates = [s.scraped_at.timestamp() for s in snapshots]
            prices = [s.price for s in snapshots]
            labels = [
                s.scraped_at.strftime("%m/%d")
                for s in snapshots
            ]
            plt.plot(
                dates, prices,
                marker="braille",
            )
            # Show date labels on x-axis
            step = max(1, len(labels) // 8)
            xtick_idx = list(range(0, len(labels), step))
            plt.xticks(
                [dates[i] for i in xtick_idx],
                [labels[i] for i in xtick_idx],
            )
            plt.title(f"Price History — {product.title[:40]}")
            plt.ylabel("Price")
        else:
            plt.title("Not enough data points")

        chart.refresh()

    async def action_toggle_star(self) -> None:
        """Toggle star status for the selected product."""
        product = self._get_selected_product()
        if product is None:
            self.notify(
                "Select a product first",
                severity="warning",
            )
            return

        new_state = await asyncio.to_thread(
            self.price_db.toggle_star, product.url,
        )
        icon = "★" if new_state else "☆"
        self.notify(
            f"{icon} {product.title[:40]}",
        )
        self.populate_table()

    async def action_show_watchlist(self) -> None:
        """Show all starred products in the watchlist tab."""
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = "watchlist_tab"

        starred = await asyncio.to_thread(
            self.price_db.get_starred_products,
        )

        label = self.query_one(
            "#watchlist_label", Static,
        )
        label.update(
            f"Starred products: {len(starred)}"
        )

        table = cast(
            DataTable[str | Text],
            self.query_one("#watchlist_table", DataTable),
        )
        table.clear()

        for item in starred:
            table.add_row(
                str(item["title"])[:50],
                str(item["latest_price"]),
                str(item["min_price"]),
                str(item["max_price"]),
                str(item["avg_price"]),
                str(item["source"]).upper(),
                str(item["snapshot_count"]),
            )
