# src/config/settings.py

"""Central configuration for the ecom_search engine."""

from pathlib import Path

from curl_cffi.requests import BrowserTypeLiteral
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration for the ecom_search engine."""

    # --- Scraping ---
    REQUEST_DELAY: float = 2.0          # Seconds between requests
    REQUEST_TIMEOUT: int = 15           # Seconds before a request times out
    MAX_RETRIES: int = 3                # Retry count on transient failures
    MAX_PAGES: int = 10                 # Max pagination depth per source

    # --- Resilience ---
    CIRCUIT_BREAKER_THRESHOLD: int = 3  # Consecutive failures to trip
    MAX_DELAY_MULTIPLIER: int = 8       # Cap for adaptive backoff
    CAPTCHA_KEYWORDS: list[str] = [
        "captcha",
        "verify you are human",
        "unusual traffic",
        "automated requests",
    ]
    API_KEY_CACHE_TTL: float = 600.0    # BinSina key cache (secs)

    # --- Filtering ---
    QUERY_ENHANCED_PLATFORMS: list[str] = ["amazon", "iherb"]

    # --- Browser Impersonation ---
    IMPERSONATE_BROWSER: BrowserTypeLiteral = "chrome131"
    DEFAULT_HEADERS: dict[str, str] = {
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": (
            '"Google Chrome";v="131", '
            '"Chromium";v="131", '
            '"Not_A Brand";v="24"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    SELECTORS_PATH: Path = BASE_DIR / "src" / "config" / "selectors.json"
    RESULTS_DIR: Path = BASE_DIR / "results"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # --- Sources (registry for future extensibility) ---
    AVAILABLE_SOURCES: list[dict[str, str]] = [
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
        {
            "id": "iherb",
            "label": "iHerb",
            "scraper": "src.scrapers.iherb_scraper.IherbScraper",
        },
    ]
