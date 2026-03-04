# src/config/settings.py

"""Central configuration for the ecom_search engine."""

import os
import random
from pathlib import Path
from typing import Any

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
    CIRCUIT_BREAKER_COOLDOWN: float = 60.0  # Seconds before half-open retry
    MAX_DELAY_MULTIPLIER: int = 8       # Cap for adaptive backoff
    CAPTCHA_KEYWORDS: list[str] = [
        "captcha",
        "verify you are human",
        "unusual traffic",
        "automated requests",
    ]
    API_KEY_CACHE_TTL: float = 600.0    # BinSina key cache (secs)
    QUERY_CACHE_TTL: float = 3600.0     # In-memory result cache (secs)

    # --- Query parsing ---
    MAX_BASE_QUERIES: int = 10           # DNF explosion cap

    # --- Filtering ---
    QUERY_ENHANCED_PLATFORMS: list[str] = [
        "amazon", "iherb", "carrefour", "sephora",
        "lulu",
    ]

    # --- Deduplication ---
    FUZZY_MATCH_THRESHOLD: int = 85      # rapidfuzz token_set_ratio
    FUZZY_PRICE_TOLERANCE: float = 0.05  # 5 % price proximity

    # --- Browser Impersonation ---
    IMPERSONATE_BROWSER: str = os.getenv(
        "IMPERSONATE_BROWSER", "chrome124"
    )

    SUPPORTED_IMPERSONATION_BROWSERS: tuple[
        BrowserTypeLiteral, ...
    ] = (
        "chrome124",
        "chrome131",
    )

    # Pool of browser fingerprints to randomise per session
    _IMPERSONATION_POOL: list[
        dict[str, Any]
    ] = [
        {
            "browser": "chrome124",
            "sec-ch-ua": (
                '"Chromium";v="124", '
                '"Google Chrome";v="124", '
                '"Not-A.Brand";v="99"'
            ),
        },
        {
            "browser": "chrome131",
            "sec-ch-ua": (
                '"Google Chrome";v="131", '
                '"Chromium";v="131", '
                '"Not_A Brand";v="24"'
            ),
        },
    ]

    @classmethod
    def get_valid_impersonation_browser(
        cls, requested: str | None = None,
    ) -> BrowserTypeLiteral:
        """Return a supported browser or fall back to a safe default."""
        candidate = (requested or cls.IMPERSONATE_BROWSER).strip()
        if candidate in cls.SUPPORTED_IMPERSONATION_BROWSERS:
            return candidate
        return "chrome124"

    @classmethod
    def get_impersonation_headers(
        cls, browser: BrowserTypeLiteral,
    ) -> dict[str, str]:
        """Return default headers aligned with the selected browser."""
        headers = dict(cls.DEFAULT_HEADERS)
        for entry in cls._IMPERSONATION_POOL:
            entry_browser = entry["browser"]
            if entry_browser != browser:
                continue
            ua: str = entry["sec-ch-ua"]
            headers["sec-ch-ua"] = ua
            return headers
        return headers

    @classmethod
    def random_impersonation(
        cls,
    ) -> tuple[BrowserTypeLiteral, dict[str, str]]:
        """Pick a random browser identity and matching headers."""
        entry = random.choice(cls._IMPERSONATION_POOL)
        browser: BrowserTypeLiteral = cls.get_valid_impersonation_browser(
            entry["browser"]
        )
        return browser, cls.get_impersonation_headers(browser)

    @classmethod
    def default_impersonation(
        cls,
    ) -> tuple[BrowserTypeLiteral, dict[str, str]]:
        """Return the deterministic browser identity for stable scraping."""
        browser = cls.get_valid_impersonation_browser()
        return browser, cls.get_impersonation_headers(browser)

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
    DATA_DIR: Path = BASE_DIR / "data"
    PRICE_DB_PATH: Path = DATA_DIR / "price_history.db"

    # --- Price Tracking ---
    PRICE_HISTORY_RETENTION_DAYS: int = 365

    # --- Sources (registry for future extensibility) ---
    AVAILABLE_SOURCES: list[dict[str, str]] = [
        {
            "id": "noon",
            "label": "Noon",
            "scraper": "src.scrapers.noon_scraper.NoonScraper",
            "timeout": "10",
        },
        {
            "id": "amazon",
            "label": "Amazon",
            "scraper": "src.scrapers.amazon_scraper.AmazonScraper",
            "timeout": "20",
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
            "timeout": "10",
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
            "timeout": "20",
        },
        {
            "id": "carrefour",
            "label": "Carrefour",
            "scraper": "src.scrapers.carrefour_scraper.CarrefourScraper",
            "timeout": "25",
        },
        {
            "id": "sephora",
            "label": "Sephora",
            "scraper": "src.scrapers.sephora_scraper.SephoraScraper",
            "timeout": "20",
        },
        {
            "id": "lulu",
            "label": "LuLu Hypermarket",
            "scraper": "src.scrapers.lulu_scraper.LuluScraper",
            "timeout": "25",
        },
    ]
