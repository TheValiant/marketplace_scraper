# src/storage/file_manager.py

"""Handles saving search results to disk."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from src.config.settings import Settings
from src.models.product import Product

logger = logging.getLogger("ecom_search.storage")


class FileManager:
    """Handles saving search results to disk."""

    def __init__(self) -> None:
        self.results_dir: Path = Settings.RESULTS_DIR
        self.results_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("FileManager initialised — results_dir=%s", self.results_dir)

    def save_results(
        self, query: str, products: list[Product], source: str
    ) -> Path:
        """Save a list of products to a timestamped JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source}_{query.replace(' ', '_')}_{timestamp}.json"
        filepath = self.results_dir / filename

        data = [
            {
                "title": p.title,
                "price": p.price,
                "currency": p.currency,
                "rating": p.rating,
                "url": p.url,
                "source": p.source,
            }
            for p in products
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            "Saved %d products for query '%s' to %s",
            len(products),
            query,
            filepath,
        )
        return filepath

    def export_csv(
        self, query: str, products: list[Product], source: str
    ) -> Path:
        """Export products to a human-readable CSV file sorted by price."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{source}_{query.replace(' ', '_')}_{timestamp}.csv"
        filepath = self.results_dir / filename

        sorted_products = sorted(
            products,
            key=lambda p: p.price if p.price > 0 else float("inf"),
        )

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Title", "Price", "Currency", "Rating", "Source", "URL"]
            )
            for p in sorted_products:
                writer.writerow(
                    [p.title, p.price, p.currency, p.rating, p.source, p.url]
                )

        logger.info(
            "Exported %d products for query '%s' to %s",
            len(products),
            query,
            filepath,
        )
        return filepath

    def format_tsv(self, products: list[Product]) -> str:
        """Format products as tab-separated text sorted by price."""
        sorted_products = sorted(
            products,
            key=lambda p: p.price if p.price > 0 else float("inf"),
        )

        lines: list[str] = [
            "Title\tPrice\tCurrency\tRating\tSource\tURL",
        ]
        for p in sorted_products:
            lines.append(
                f"{p.title}\t{p.price}\t{p.currency}"
                f"\t{p.rating}\t{p.source}\t{p.url}"
            )

        return "\n".join(lines)
