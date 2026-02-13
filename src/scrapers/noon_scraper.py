# src/scrapers/noon_scraper.py

"""Scraper for noon.com (UAE)."""

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class NoonScraper(BaseScraper):
    """Scraper for noon.com (UAE)."""

    def __init__(self):
        super().__init__("noon")

    def _get_homepage(self) -> str:
        """Return the Noon homepage URL."""
        return "https://www.noon.com/"

    def search(self, query: str) -> list[Product]:
        """Search Noon for products matching the query."""
        try:
            products = []
            url = f"https://www.noon.com/uae-en/search/?q={query}"

            for page in range(1, self.settings.MAX_PAGES + 1):
                soup = self._get_page(url)
                if not soup:
                    break

                cards = soup.select(self.selectors["product_card"])
                for card in cards:
                    title_el = card.select_one(self.selectors["title"])
                    price_el = card.select_one(self.selectors["price"])
                    rating_el = card.select_one(
                        self.selectors.get("rating", "")
                    )
                    url_el = card.select_one(self.selectors["url"])

                    products.append(
                        Product(
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
                                f"https://www.noon.com{url_el['href']}"
                                if url_el
                                else ""
                            ),
                            source="noon",
                        )
                    )

                next_btn = soup.select_one(
                    self.selectors.get("next_page", "")
                )
                if next_btn and next_btn.get("href"):
                    url = f"https://www.noon.com{next_btn['href']}"
                else:
                    break

            return products
        except Exception as e:
            self.logger.error("[noon] Search failed: %s", e)
            return []
