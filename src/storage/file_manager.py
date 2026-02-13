# src/storage/file_manager.py

"""Handles saving search results to disk."""

import json
from datetime import datetime
from pathlib import Path

from src.config.settings import Settings
from src.models.product import Product


class FileManager:
    """Handles saving search results to disk."""

    def __init__(self):
        self.results_dir: Path = Settings.RESULTS_DIR
        self.results_dir.mkdir(parents=True, exist_ok=True)

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

        return filepath
