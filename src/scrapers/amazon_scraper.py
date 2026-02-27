# src/scrapers/amazon_scraper.py

"""Scraper for amazon.ae (UAE)."""

from bs4 import Tag

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class AmazonScraper(BaseScraper):
    """Scraper for amazon.ae (UAE)."""

    def __init__(self) -> None:
        super().__init__("amazon")

    def _get_homepage(self) -> str:
        """Return the Amazon.ae homepage URL."""
        return "https://www.amazon.ae/"

    def _parse_card(self, card: Tag) -> Product:
        """Parse a single product card into a Product."""
        title_el = card.select_one(self.selectors["title"])
        price_el = card.select_one(self.selectors["price"])
        rating_el = card.select_one(
            self.selectors.get("rating", "")
        )
        url_el = card.select_one(self.selectors["url"])

        return Product(
            title=(
                title_el.get_text(strip=True)
                if title_el
                else "N/A"
            ),
            price=self.extract_price(
                price_el.get_text() if price_el else ""
            ),
            currency="AED",
            rating=(
                rating_el.get_text(strip=True)
                if rating_el
                else ""
            ),
            url=(
                f"https://www.amazon.ae{url_el['href']}"
                if url_el
                else ""
            ),
            source="amazon",
        )

    def search(self, query: str) -> list[Product]:
        """Search Amazon.ae for products matching the query."""
        try:
            products: list[Product] = []
            url = f"https://www.amazon.ae/s?k={query}"

            for page in range(1, self.settings.MAX_PAGES + 1):
                self.logger.info(
                    "[amazon] Fetching page %d (%d so far)",
                    page,
                    len(products),
                )
                soup = self._get_page(url)
                if not soup:
                    break

                selector = self.selectors["product_card"]
                cards = soup.select(selector)
                for card in cards:
                    products.append(self._parse_card(card))

                next_sel = self.selectors.get("next_page", "")
                next_btn = soup.select_one(next_sel)
                if next_btn and next_btn.get("href"):
                    url = (
                        "https://www.amazon.ae"
                        f"{next_btn['href']}"
                    )
                else:
                    break

            return products
        except Exception as e:
            self.logger.error(
                "[amazon] Search failed: %s", e, exc_info=True
            )
            return []
