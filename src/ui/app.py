# src/ui/app.py

"""Terminal UI for the ecom_search price comparison engine."""

import asyncio
import webbrowser

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

from src.scrapers.amazon_scraper import AmazonScraper
from src.scrapers.noon_scraper import NoonScraper
from src.storage.file_manager import FileManager


class EcomSearchApp(App):
    """Terminal UI for the ecom_search price comparison engine."""

    CSS_PATH = "styles.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "save", "Save"),
        Binding("p", "sort_price", "Price Sort"),
        Binding("r", "sort_rating", "Rating Sort"),
        Binding("c", "copy_url", "Copy URL"),
    ]

    def __init__(self):
        super().__init__()
        self.products: list = []
        self.current_query: str = ""
        self.file_manager = FileManager()

    def compose(self) -> ComposeResult:
        """Build the widget tree for the TUI."""
        yield Header()
        yield Container(
            Static("🛒 E-commerce Search (Noon & Amazon)", id="title"),

            # Search Bar
            Horizontal(
                Input(
                    placeholder="Search products...", id="search_input"
                ),
                Button("Search", variant="primary", id="search_btn"),
                id="search_bar",
            ),

            # Source Selection Checkboxes
            Horizontal(
                Checkbox("Noon", value=True, id="check_noon"),
                Checkbox("Amazon", value=True, id="check_amazon"),
                id="source_toggles",
            ),

            Static("Ready", id="status"),
            DataTable(
                id="results_table", zebra_stripes=True, cursor_type="row"
            ),
            id="main_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Configure the results table columns on startup."""
        self.query_one("#results_table").add_columns(
            "Title", "Price", "Rating", "Source"
        )

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
        query = self.query_one("#search_input").value.strip()
        if not query:
            self.notify("Please enter a search term", severity="warning")
            return

        # --- Check Source Selection ---
        use_noon = self.query_one("#check_noon").value
        use_amazon = self.query_one("#check_amazon").value

        if not use_noon and not use_amazon:
            self.notify("Select at least one source!", severity="error")
            return

        self.current_query = query
        self.products = []
        self.query_one("#results_table").clear()
        self.query_one("#status").update(f"🔍 Searching '{query}'...")

        # Build task list from checked sources only
        tasks = []

        async def run_scraper(scraper_cls):
            """Run a blocking scraper in a thread to keep UI responsive."""
            return await asyncio.to_thread(scraper_cls().search, query)

        if use_noon:
            tasks.append(run_scraper(NoonScraper))
        if use_amazon:
            tasks.append(run_scraper(AmazonScraper))

        # Execute selected tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for batch in results:
            if isinstance(batch, list):
                self.products.extend(batch)
            elif isinstance(batch, Exception):
                self.notify(f"Error: {batch}", severity="error")

        self.populate_table()

        if not self.products:
            self.query_one("#status").update("❌ No products found")
        else:
            self.query_one("#status").update(
                f"✅ Found {len(self.products)} products"
            )

    def populate_table(self) -> None:
        """Fill the DataTable with current product results."""
        table = self.query_one("#results_table")
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the selected product's URL in the default browser."""
        if 0 <= event.cursor_row < len(self.products):
            webbrowser.open(self.products[event.cursor_row].url)

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
        if self.products:
            path = self.file_manager.save_results(
                self.current_query, self.products, "combined"
            )
            self.notify(f"Saved to {path}")

    def action_copy_url(self) -> None:
        """Copy the selected product's URL to the clipboard."""
        try:
            import pyperclip

            row = self.query_one("#results_table").cursor_row
            pyperclip.copy(self.products[row].url)
            self.notify("URL Copied")
        except Exception:
            self.notify("Install pyperclip", severity="warning")
