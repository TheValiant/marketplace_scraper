# src/models/price_snapshot.py

"""Temporal price snapshot model for price history tracking."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceSnapshot:
    """A single price observation for a product at a point in time."""

    product_url: str
    title: str
    price: float
    currency: str
    source: str
    scraped_at: datetime
