# src/ui/app.py

"""Terminal UI for the ecom_search price comparison engine."""

import asyncio
import importlib
import logging
import webbrowser
from typing import Any, cast

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
)

from src.config.settings import Settings
from src.models.product import Product
from src.storage.file_manager import FileManager

logger = logging.getLogger("ecom_search.ui")


def _load_scraper_class(dotted_path: str) -> type[Any]:
    """Dynamically import a scraper class from its dotted module path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: type[Any] = getattr(module, class_name)
    return cls


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
    ]

    def __init__(self) -> None:
        super().__init__()
        self.products: list[Product] = []
        self.current_query: str = ""
        self.file_manager = FileManager()
        self.settings = Settings()

    def compose(self) -> ComposeResult:
        """Build the widget tree for the TUI."""
        source_checkboxes = [
            Checkbox(
                src["label"], value=True, id=f"check_{src['id']}"
            )
            for src in self.settings.AVAILABLE_SOURCES
        ]
        source_names = ", ".join(
            s["label"] for s in self.settings.AVAILABLE_SOURCES
        )

        yield Header()
        yield Container(
            Static(
                f"🛒 E-commerce Search ({source_names})", id="title"
            ),

            # Search Bar
            Horizontal(
                Input(
                    placeholder="Search products...", id="search_input"
                ),
                Button("Search", variant="primary", id="search_btn"),
                id="search_bar",
            ),

            # Source Selection Checkboxes
            Horizontal(*source_checkboxes, id="source_toggles"),

            Static("Ready", id="status"),
            cast(
                DataTable[str | Text],
                DataTable(
                    id="results_table",
                    zebra_stripes=True,
                    cursor_type="row",
                ),
            ),
            id="main_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Configure the results table columns on startup."""
        table = cast(
            DataTable[str | Text],
            self.query_one("#results_table", DataTable),
        )
        table.add_columns("Title", "Price", "Rating", "Source")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button click events."""
        if event.button.id == "search_btn":
            await self.perform_search()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in the search input."""
        if event.input.id == "search_input":
            await self.perform_search()

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

        # --- Collect selected sources from the registry ---
        selected_sources: list[dict[str, str]] = []
        for src in self.settings.AVAILABLE_SOURCES:
            checkbox_id = f"#check_{src['id']}"
            checkbox = self.query_one(checkbox_id, Checkbox)
            if checkbox.value:
                selected_sources.append(src)

        if not selected_sources:
            self.notify("Select at least one source!", severity="error")
            return

        self.current_query = query
        self.products = []
        table = cast(
            DataTable[str | Text],
            self.query_one("#results_table", DataTable),
        )
        status = self.query_one("#status", Static)
        table.clear()
        status.update(f"🔍 Searching '{query}'...")

        # Build task list from checked sources dynamically
        async def run_scraper(
            scraper_path: str,
        ) -> list[Product]:
            """Run a blocking scraper in a thread."""
            scraper_cls = _load_scraper_class(scraper_path)
            result: list[Product] = await asyncio.to_thread(
                scraper_cls().search, query
            )
            return result

        tasks = [
            run_scraper(src["scraper"]) for src in selected_sources
        ]

        # Execute selected tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for batch in results:
            if isinstance(batch, list):
                self.products.extend(batch)
            elif isinstance(batch, Exception):
                logger.error(
                    "Scraper returned exception for query '%s': %s",
                    query,
                    batch,
                    exc_info=batch,
                )
                self.notify(f"Error: {batch}", severity="error")

        self.populate_table()

        if not self.products:
            status.update("❌ No products found")
        else:
            # Auto-save results to disk
            self._auto_save_results()
            status.update(
                f"✅ Found {len(self.products)} products (saved)"
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

        min_price = min(
            (p.price for p in self.products if p.price > 0), default=0
        )

        for p in self.products:
            is_cheapest = p.price == min_price and p.price > 0
            price_style = "bold green" if is_cheapest else ""
            table.add_row(
                p.title[:60],
                Text(f"{p.price} {p.currency}", style=price_style),
                f"⭐ {p.rating}" if p.rating else "",
                p.source.upper(),
            )

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
