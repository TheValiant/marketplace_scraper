# src/config/settings.py

"""Central configuration for the ecom_search engine."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration for the ecom_search engine."""

    # --- Scraping ---
    REQUEST_DELAY: float = 2.0          # Seconds between requests
    REQUEST_TIMEOUT: int = 15           # Seconds before a request times out
    MAX_RETRIES: int = 3                # Retry count on transient failures
    MAX_PAGES: int = 10                 # Max pagination depth per source

    # --- Browser Impersonation ---
    IMPERSONATE_BROWSER: str = "chrome124"
    DEFAULT_HEADERS: dict = {
        "Accept-Language": "en-US,en;q=0.9",
    }

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    SELECTORS_PATH: Path = BASE_DIR / "src" / "config" / "selectors.json"
    RESULTS_DIR: Path = BASE_DIR / "results"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # --- Sources (registry for future extensibility) ---
    AVAILABLE_SOURCES: list[dict] = [
        {
            "id": "noon",
            "label": "Noon",
            "scraper": "src.scrapers.noon_scraper.NoonScraper",
        },
        {
            "id": "amazon",
            "label": "Amazon",
            "scraper": "src.scrapers.amazon_scraper.AmazonScraper",
        },
        {
            "id": "binsina",
            "label": "BinSina",
            "scraper": "src.scrapers.binsina_scraper.BinSinaScraper",
        },
        {
            "id": "life_pharmacy",
            "label": "Life Pharmacy",
            "scraper": "src.scrapers.life_pharmacy_scraper.LifePharmacyScraper",
        },
        {
            "id": "aster",
            "label": "Aster",
            "scraper": "src.scrapers.aster_scraper.AsterScraper",
        },
    ]
