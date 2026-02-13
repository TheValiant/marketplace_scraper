# src/models/product.py

"""Product data model for inter-module data flow."""

from dataclasses import dataclass


@dataclass
class Product:
    """Represents a single product listing from any marketplace."""

    title: str
    price: float
    currency: str = "AED"
    rating: str = ""
    url: str = ""
    source: str = ""
    image_url: str = ""
