# `ecom_search` — Project Design Document

> **Version**: 1.0  
> **Last Updated**: 2026-02-14  
> **Core Philosophy**: *"Resilience over Speed."*

---

## Table of Contents

1. [Overview](#1-overview)  
2. [Architecture](#2-architecture)  
3. [Directory Structure](#3-directory-structure)  
4. [Configuration Layer](#4-configuration-layer)  
5. [Data Models](#5-data-models)  
6. [Scraping Engine](#6-scraping-engine)  
7. [TUI Application](#7-tui-application)  
   - 7.1 [Layout & Composition](#71-layout--composition)  
   - 7.2 [Source Selection Checkboxes](#72-source-selection-checkboxes)  
   - 7.3 [Search Flow](#73-search-flow)  
   - 7.4 [Results Table](#74-results-table)  
   - 7.5 [Key Bindings & Actions](#75-key-bindings--actions)  
8. [Styling (CSS)](#8-styling-css)  
9. [Storage & Export](#9-storage--export)  
10. [Anti-Detection Strategy](#10-anti-detection-strategy)  
11. [Testing Strategy](#11-testing-strategy)  
12. [Implementation Checklist](#12-implementation-checklist)  

---

## 1. Overview

`ecom_search` is a **modular, local e-commerce price comparison engine** for UAE markets. It scrapes product listings from **Noon** and **Amazon.ae**, presents them in a rich Terminal User Interface (TUI), and lets users sort, compare, save, and open results — all from the terminal.

### Key Capabilities

| Feature | Description |
|---|---|
| **Multi-source search** | Scrapes Noon and Amazon concurrently |
| **Source selection** | Checkboxes to toggle individual sources on/off |
| **Price comparison** | Highlights the lowest price across all results |
| **Sorting** | Sort by price or rating with a single keypress |
| **Export** | Save results to JSON/CSV via `FileManager` |
| **Anti-detection** | Browser-impersonating HTTP via `curl_cffi` |

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        main.py (Entry Point)                       │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                     src/ui/app.py  (EcomSearchApp)                  │
│                                                                    │
│  ┌──────────┐  ┌──────────────────┐  ┌───────────────────────┐    │
│  │  Header   │  │   Search Bar     │  │   Results DataTable    │   │
│  └──────────┘  │  Input + Button   │  │   (sortable, clickable)│   │
│                │                    │  └───────────────────────┘    │
│                └──────────────────┘                                 │
│                ┌──────────────────┐                                 │
│                │ Source Toggles    │                                 │
│                │ [x] Noon          │                                 │
│                │ [x] Amazon        │                                 │
│                └──────────────────┘                                 │
│                ┌──────────────────┐                                 │
│                │   Status Bar     │                                 │
│                └──────────────────┘                                 │
└───────────┬────────────────────────────────────┬───────────────────┘
            │                                    │
            ▼                                    ▼
┌───────────────────────┐           ┌───────────────────────┐
│  src/scrapers/         │           │  src/storage/          │
│  ├─ base_scraper.py    │           │  └─ file_manager.py    │
│  ├─ noon_scraper.py    │           └───────────────────────┘
│  └─ amazon_scraper.py  │
└───────────┬────────────┘
            │
            ▼
┌───────────────────────┐
│  src/config/           │
│  ├─ settings.py        │
│  └─ selectors.json     │
└───────────────────────┘
```

### Data Flow

1. User types a query and presses **Search** (or `Enter`).
2. `EcomSearchApp.perform_search()` reads the **source selection checkboxes**.
3. Only the **checked** scrapers are dispatched via `asyncio.gather()`.
4. Each scraper returns a `list[Product]`.
5. Results are merged, the cheapest is highlighted, and the `DataTable` is populated.

---

## 3. Directory Structure

```
marketplace_scraper/
├── main.py                        # Entry point: runs EcomSearchApp
├── .env                           # Secrets (API keys, proxies)
├── .antigravity/
│   └── rules.md                   # Agent rules & project conventions
├── project_design.md              # This document
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # All constants (delays, retries, timeouts)
│   │   └── selectors.json         # CSS selectors for each marketplace
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── product.py             # Product dataclass
│   │
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base_scraper.py        # Abstract base: session, extract_price, headers
│   │   ├── noon_scraper.py        # Noon-specific scraper
│   │   └── amazon_scraper.py      # Amazon-specific scraper
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   └── file_manager.py        # JSON/CSV export
│   │
│   └── ui/
│       ├── __init__.py
│       ├── app.py                 # EcomSearchApp (Textual App)
│       └── styles.css             # Textual CSS styles
│
└── tests/
    ├── __init__.py
    ├── test_noon_scraper.py
    └── test_amazon_scraper.py
```

---

## 4. Configuration Layer

### `src/config/settings.py`

All tuneable constants live here. **No magic numbers** in scraper or UI code.

```python
# src/config/settings.py

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    """Central configuration for the ecom_search engine."""

    # --- Scraping ---
    REQUEST_DELAY: float = 2.0          # Seconds between requests
    REQUEST_TIMEOUT: int = 15           # Seconds before a request times out
    MAX_RETRIES: int = 3                # Retry count on transient failures
    MAX_PAGES: int = 3                  # Max pagination depth per source

    # --- Browser Impersonation ---
    IMPERSONATE_BROWSER: str = "chrome124"
    DEFAULT_HEADERS: dict = {
        "Accept-Language": "en-US,en;q=0.9",
    }

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    SELECTORS_PATH: Path = BASE_DIR / "src" / "config" / "selectors.json"
    RESULTS_DIR: Path = BASE_DIR / "results"

    # --- Sources (registry for future extensibility) ---
    AVAILABLE_SOURCES: list[dict] = [
        {"id": "noon",   "label": "Noon",   "scraper": "src.scrapers.noon_scraper.NoonScraper"},
        {"id": "amazon", "label": "Amazon", "scraper": "src.scrapers.amazon_scraper.AmazonScraper"},
    ]
```

### `src/config/selectors.json`

CSS selectors are **never hardcoded** in Python. If a site changes its layout, only this file is updated.

```json
{
  "noon": {
    "product_card": "div[data-qa='product-block']",
    "title": "span[data-qa='product-name']",
    "price": "strong[data-qa='product-price']",
    "currency": "span.currency",
    "rating": "div[data-qa='product-rating']",
    "url": "a[data-qa='product-link']",
    "next_page": "a[rel='next']"
  },
  "amazon": {
    "product_card": "div[data-component-type='s-search-result']",
    "title": "h2 a span",
    "price": "span.a-price > span.a-offscreen",
    "currency": "",
    "rating": "span.a-icon-alt",
    "url": "h2 a.a-link-normal",
    "next_page": "a.s-pagination-next"
  }
}
```

---

## 5. Data Models

### `src/models/product.py`

All inter-module data flows through this dataclass. **No raw dicts**.

```python
# src/models/product.py

from dataclasses import dataclass, field

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
```

---

## 6. Scraping Engine

### `src/scrapers/base_scraper.py`

```python
# src/scrapers/base_scraper.py

import json
import logging
import re
import time
from abc import ABC, abstractmethod

import cloudscraper
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.config.settings import Settings

class BaseScraper(ABC):
    """Abstract base class for all marketplace scrapers."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"ecom_search.{source_name}")
        self.settings = Settings()
        self.selectors = self._load_selectors()
        self.session = curl_requests.Session(
            impersonate=self.settings.IMPERSONATE_BROWSER
        )

    def _load_selectors(self) -> dict:
        """Load CSS selectors for this source from selectors.json."""
        with open(self.settings.SELECTORS_PATH) as f:
            all_selectors = json.load(f)
        return all_selectors.get(self.source_name, {})

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """Fetch a page with curl_cffi, falling back to cloudscraper on failure."""
        headers = {
            **self.settings.DEFAULT_HEADERS,
            "Referer": self._get_homepage(),
        }
        time.sleep(self.settings.REQUEST_DELAY)

        # Primary: curl_cffi (browser-impersonating TLS)
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                resp = self.session.get(
                    url, headers=headers, timeout=self.settings.REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "lxml")
                self.logger.warning(
                    "[%s] HTTP %d on attempt %d", self.source_name, resp.status_code, attempt + 1
                )
            except Exception as e:
                self.logger.warning(
                    "[%s] curl_cffi error on attempt %d: %s", self.source_name, attempt + 1, e
                )
                time.sleep(self.settings.REQUEST_DELAY * (attempt + 1))

        # Fallback: cloudscraper (JS challenge solver)
        self.logger.info("[%s] curl_cffi exhausted, falling back to cloudscraper", self.source_name)
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(url, headers=headers, timeout=self.settings.REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            self.logger.error("[%s] cloudscraper fallback also failed: %s", self.source_name, e)

        return None

    @staticmethod
    def extract_price(text: str) -> float:
        """Extract a numeric price from a string like 'AED 1,299.00'."""
        if not text:
            return 0.0
        numbers = re.findall(r"[\d,]+\.?\d*", text.replace(",", ""))
        return float(numbers[0]) if numbers else 0.0

    @abstractmethod
    def _get_homepage(self) -> str:
        """Return the homepage URL for the Referer header."""
        ...

    @abstractmethod
    def search(self, query: str) -> list:
        """Search for products and return a list of Product objects."""
        ...
```

### `src/scrapers/noon_scraper.py`

```python
# src/scrapers/noon_scraper.py

from src.scrapers.base_scraper import BaseScraper
from src.models.product import Product

class NoonScraper(BaseScraper):
    """Scraper for noon.com (UAE)."""

    def __init__(self):
        super().__init__("noon")

    def _get_homepage(self) -> str:
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
                    rating_el = card.select_one(self.selectors.get("rating", ""))
                    url_el = card.select_one(self.selectors["url"])

                    products.append(Product(
                        title=title_el.get_text(strip=True) if title_el else "N/A",
                        price=self.extract_price(price_el.get_text() if price_el else ""),
                        currency="AED",
                        rating=rating_el.get_text(strip=True) if rating_el else "",
                        url=f"https://www.noon.com{url_el['href']}" if url_el else "",
                        source="noon",
                    ))

                next_btn = soup.select_one(self.selectors.get("next_page", ""))
                if next_btn and next_btn.get("href"):
                    url = f"https://www.noon.com{next_btn['href']}"
                else:
                    break

            return products
        except Exception as e:
            self.logger.error("[noon] Search failed: %s", e)
            return []
```

### `src/scrapers/amazon_scraper.py`

```python
# src/scrapers/amazon_scraper.py

from src.scrapers.base_scraper import BaseScraper
from src.models.product import Product

class AmazonScraper(BaseScraper):
    """Scraper for amazon.ae (UAE)."""

    def __init__(self):
        super().__init__("amazon")

    def _get_homepage(self) -> str:
        return "https://www.amazon.ae/"

    def search(self, query: str) -> list[Product]:
        """Search Amazon.ae for products matching the query."""
        try:
            products = []
            url = f"https://www.amazon.ae/s?k={query}"

            for page in range(1, self.settings.MAX_PAGES + 1):
                soup = self._get_page(url)
                if not soup:
                    break

                cards = soup.select(self.selectors["product_card"])
                for card in cards:
                    title_el = card.select_one(self.selectors["title"])
                    price_el = card.select_one(self.selectors["price"])
                    rating_el = card.select_one(self.selectors.get("rating", ""))
                    url_el = card.select_one(self.selectors["url"])

                    products.append(Product(
                        title=title_el.get_text(strip=True) if title_el else "N/A",
                        price=self.extract_price(price_el.get_text() if price_el else ""),
                        currency="AED",
                        rating=rating_el.get_text(strip=True) if rating_el else "",
                        url=f"https://www.amazon.ae{url_el['href']}" if url_el else "",
                        source="amazon",
                    ))

                next_btn = soup.select_one(self.selectors.get("next_page", ""))
                if next_btn and next_btn.get("href"):
                    url = f"https://www.amazon.ae{next_btn['href']}"
                else:
                    break

            return products
        except Exception as e:
            self.logger.error("[amazon] Search failed: %s", e)
            return []
```

---

## 7. TUI Application

### 7.1 Layout & Composition

The TUI is built with `textual`. The `compose()` method defines the widget tree:

```
┌─ Header ──────────────────────────────────────────────┐
│ ecom_search                                            │
├────────────────────────────────────────────────────────┤
│  ┌─ #search_bar (Horizontal) ──────────────────────┐  │
│  │  [ Search products...              ] [ Search ] │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─ #source_toggles (Horizontal) ──────────────────┐  │
│  │        [x] Noon       [x] Amazon                │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─ #status ───────────────────────────────────────┐  │
│  │  Ready                                          │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─ #results_table (DataTable) ────────────────────┐  │
│  │  Title          │ Price      │ Rating │ Source   │  │
│  │  ───────────────┼────────────┼────────┼──────── │  │
│  │  Product A      │ 199 AED ✓  │ ⭐ 4.5 │ NOON    │  │
│  │  Product B      │ 249 AED    │ ⭐ 4.2 │ AMAZON  │  │
│  └─────────────────────────────────────────────────┘  │
├─ Footer ──────────────────────────────────────────────┤
│  q Quit │ s Save │ p Price Sort │ r Rating Sort       │
└────────────────────────────────────────────────────────┘
```

### 7.2 Source Selection Checkboxes

This is the **core feature** that makes source selection dynamic rather than hardcoded.

#### Design Rationale

| Concern | Decision |
|---|---|
| **Default state** | Both checkboxes are `value=True` (checked) so a fresh launch searches all sources. |
| **Zero-selection guard** | If no checkbox is checked, `perform_search()` shows an error notification and aborts. |
| **Extensibility** | Adding a new source (e.g., Carrefour) requires: adding a checkbox with `id="check_carrefour"`, adding its scraper class, and adding one `if` block. |
| **Widget IDs** | Each checkbox follows the pattern `check_{source_id}` (e.g., `check_noon`, `check_amazon`). |

#### Widget Definition (in `compose()`)

```python
# Inside EcomSearchApp.compose()
Horizontal(
    Checkbox("Noon", value=True, id="check_noon"),
    Checkbox("Amazon", value=True, id="check_amazon"),
    id="source_toggles"
)
```

#### Reading Checkbox State (in `perform_search()`)

```python
# Inside EcomSearchApp.perform_search()
use_noon = self.query_one("#check_noon").value      # bool
use_amazon = self.query_one("#check_amazon").value  # bool

if not use_noon and not use_amazon:
    self.notify("Select at least one source!", severity="error")
    return
```

#### Conditional Scraper Dispatch

Only scrapers whose checkboxes are checked get added to the `asyncio.gather()` call:

```python
tasks = []

async def run_scraper(scraper_cls):
    """Execute a scraper in a thread to avoid blocking the TUI."""
    return await asyncio.to_thread(scraper_cls().search, query)

if use_noon:
    tasks.append(run_scraper(NoonScraper))
if use_amazon:
    tasks.append(run_scraper(AmazonScraper))

results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 7.3 Search Flow

```
User presses Search / Enter
        │
        ▼
┌─ perform_search() ────────────────────────────────────────┐
│  1. Read query from #search_input                         │
│  2. Validate query is not empty                           │
│  3. ★ Read #check_noon.value and #check_amazon.value ★    │
│  4. Validate at least one source is selected              │
│  5. Clear previous results                                │
│  6. Build task list from checked sources only              │
│  7. await asyncio.gather(*tasks)                          │
│  8. Merge results into self.products                      │
│  9. Call populate_table()                                  │
│ 10. Update #status with count or "No products found"      │
└───────────────────────────────────────────────────────────┘
```

### 7.4 Results Table

| Column | Content | Notes |
|---|---|---|
| **Title** | `p.title[:60]` | Truncated to 60 chars |
| **Price** | `{p.price} {p.currency}` | **Bold green** if it's the lowest price |
| **Rating** | `⭐ {p.rating}` | Empty string if no rating |
| **Source** | `p.source.upper()` | `NOON` or `AMAZON` |

### 7.5 Key Bindings & Actions

| Key | Action | Description |
|---|---|---|
| `q` | `action_quit` | Exit the app |
| `s` | `action_save` | Save results to file via `FileManager` |
| `p` | `action_sort_price` | Sort products by price ascending |
| `r` | `action_sort_rating` | Sort products by rating descending |
| `c` | `action_copy_url` | Copy selected product URL to clipboard |
| `Enter` (on row) | `on_data_table_row_selected` | Open product URL in browser |

---

## 8. Styling (CSS)

### `src/ui/styles.css`

All TUI styles live in this file. **No inline styles** in Python unless computing dynamic values.

```css
/* src/ui/styles.css */

/* --- Title Banner --- */
#title {
    text-align: center;
    background: $primary;
    color: $text;
    padding: 1;
    text-style: bold;
}

/* --- Search Bar --- */
#search_bar {
    height: 3;
    padding: 1 1 0 1;
    background: $surface;
}

#search_input {
    width: 4fr;
}

#search_btn {
    width: 1fr;
    min-width: 10;
}

/* --- Source Selection Checkboxes --- */
#source_toggles {
    height: 3;
    padding: 0 1 1 1;
    background: $surface;
    align: center middle;
}

Checkbox {
    padding: 0 2;
}

/* --- Status Bar --- */
#status {
    height: 1;
    padding: 0 1;
    background: $panel;
    color: $text;
}

/* --- Results Table --- */
#results_table {
    height: 1fr;
    border: solid $primary;
}

DataTable > .datatable--cursor {
    background: $secondary 30%;
}
```

#### Key Styling Decisions

| Rule | Purpose |
|---|---|
| `#source_toggles` has `align: center middle` | Centers the checkboxes horizontally for a clean look |
| `#source_toggles` shares `background: $surface` with `#search_bar` | Creates a visually unified input area |
| `Checkbox { padding: 0 2 }` | Adds horizontal breathing room between checkbox labels |
| `#search_bar` uses `padding: 1 1 0 1` (no bottom) | The source toggles sit flush beneath the search bar |
| `#source_toggles` uses `padding: 0 1 1 1` (no top) | Completes the visual group with bottom padding |

---

## 9. Storage & Export

### `src/storage/file_manager.py`

```python
# src/storage/file_manager.py

import json
import csv
from pathlib import Path
from datetime import datetime
from src.config.settings import Settings
from src.models.product import Product

class FileManager:
    """Handles saving search results to disk."""

    def __init__(self):
        self.results_dir = Settings.RESULTS_DIR
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save_results(self, query: str, products: list[Product], source: str) -> Path:
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
```

---

## 10. Anti-Detection Strategy

| Layer | Mechanism |
|---|---|
| **HTTP Client** | `curl_cffi` with `impersonate="chrome124"` — mimics a real Chrome TLS fingerprint |
| **Headers** | `Accept-Language`, `Referer` (site homepage) sent on every request |
| **Rate Limiting** | `Settings.REQUEST_DELAY` (2s default) enforced between every request |
| **Retry Backoff** | Exponential: `delay * (attempt + 1)` on failure |
| **Fallback** | `cloudscraper` auto-triggers in `_get_page()` after `MAX_RETRIES` curl_cffi failures |
| **Selector Separation** | Selectors in JSON, not code — fast recovery when site layouts change |

### Fallback Mechanism

The `BaseScraper._get_page()` method implements a **two-tier fetching strategy**:

1. **Primary** — `curl_cffi` with `MAX_RETRIES` attempts and exponential backoff.
2. **Fallback** — If all `curl_cffi` attempts fail (blocked, timeout, network error), a single `cloudscraper` request is attempted as a last resort.

This ensures that even when a marketplace starts fingerprinting `curl_cffi`'s TLS signature, the scraper degrades gracefully to `cloudscraper`'s JS challenge solver rather than returning zero results.

---

## 11. Testing Strategy

### Principles

- **Never hit live URLs** in automated tests to avoid IP bans.
- **Mock `curl_requests.Session`** to return saved HTML fixtures.
- **Validate** against `selectors.json` keys (`product_card`, `title`, `price`, etc.).

### Example Test Structure

```python
# tests/test_noon_scraper.py

import unittest
from unittest.mock import patch, MagicMock
from src.scrapers.noon_scraper import NoonScraper

class TestNoonScraper(unittest.TestCase):
    """Tests for the Noon scraper using mocked HTTP responses."""

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_returns_products(self, mock_session_cls):
        """Verify that search() parses a fixture page into Product objects."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        with open("tests/fixtures/noon_search.html") as f:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = f.read()
            mock_session.get.return_value = mock_resp

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("iphone")

        self.assertGreater(len(products), 0)
        self.assertEqual(products[0].source, "noon")

    @patch("src.scrapers.base_scraper.curl_requests.Session")
    def test_search_handles_empty_page(self, mock_session_cls):
        """Verify graceful handling when no products are found."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body></body></html>"
        mock_session.get.return_value = mock_resp

        scraper = NoonScraper()
        scraper.session = mock_session
        products = scraper.search("nonexistent_product_xyz")

        self.assertEqual(products, [])
```

---

## 12. Implementation Checklist

### Phase 1: Foundation
- [ ] Create directory structure (`src/config/`, `src/models/`, `src/scrapers/`, `src/storage/`, `src/ui/`)
- [ ] Create `src/config/settings.py` with all constants
- [ ] Create `src/config/selectors.json` with Noon & Amazon selectors
- [ ] Create `src/models/product.py` with `Product` dataclass
- [ ] Create `.env` file (empty template)

### Phase 2: Scraping Engine
- [ ] Implement `src/scrapers/base_scraper.py`
- [ ] Implement `src/scrapers/noon_scraper.py`
- [ ] Implement `src/scrapers/amazon_scraper.py`
- [ ] Validate selectors against live pages (manual dry run)

### Phase 3: TUI Application
- [ ] Implement `src/ui/app.py` with full `compose()` layout
- [ ] **Add `Checkbox` imports and widgets for source selection**
- [ ] **Add `#source_toggles` container with `check_noon` and `check_amazon`**
- [ ] **Implement checkbox-aware `perform_search()` with zero-selection guard**
- [ ] Implement `populate_table()` with lowest-price highlighting
- [ ] Implement all key binding actions (`sort`, `save`, `copy_url`)
- [ ] Create `src/ui/styles.css` with `#source_toggles` and `Checkbox` rules

### Phase 4: Storage
- [ ] Implement `src/storage/file_manager.py`
- [ ] Create `results/` directory on first save

### Phase 5: Entry Point & Polish
- [ ] Create `main.py`
- [ ] End-to-end manual test with checkboxes toggled
- [ ] Verify TUI does not freeze during search (async correctness)

### Phase 6: Testing
- [ ] Create `tests/fixtures/` with saved HTML pages
- [ ] Write `test_noon_scraper.py` with mocked HTTP
- [ ] Write `test_amazon_scraper.py` with mocked HTTP
- [ ] Verify all `selectors.json` keys are used correctly

---

## Appendix A: Full `src/ui/app.py`

```python
# src/ui/app.py

import asyncio
import webbrowser

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, DataTable, Static, Checkbox

from src.scrapers.noon_scraper import NoonScraper
from src.scrapers.amazon_scraper import AmazonScraper
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
        self.products = []
        self.current_query = ""
        self.file_manager = FileManager()

    def compose(self) -> ComposeResult:
        """Build the widget tree for the TUI."""
        yield Header()
        yield Container(
            Static("🛒 E-commerce Search (Noon & Amazon)", id="title"),

            # Search Bar
            Horizontal(
                Input(placeholder="Search products...", id="search_input"),
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
            DataTable(id="results_table", zebra_stripes=True, cursor_type="row"),
            id="main_container",
        )
        yield Footer()

    def on_mount(self):
        """Configure the results table columns on startup."""
        self.query_one("#results_table").add_columns("Title", "Price", "Rating", "Source")

    async def on_button_pressed(self, event):
        """Handle button click events."""
        if event.button.id == "search_btn":
            await self.perform_search()

    async def on_input_submitted(self, event):
        """Handle Enter key in the search input."""
        if event.input.id == "search_input":
            await self.perform_search()

    async def perform_search(self):
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
            self.query_one("#status").update(f"✅ Found {len(self.products)} products")

    def populate_table(self):
        """Fill the DataTable with current product results."""
        table = self.query_one("#results_table")
        table.clear()
        if not self.products:
            return

        min_price = min((p.price for p in self.products if p.price > 0), default=0)

        for p in self.products:
            price_style = "bold green" if p.price == min_price and p.price > 0 else ""
            table.add_row(
                p.title[:60],
                Text(f"{p.price} {p.currency}", style=price_style),
                f"⭐ {p.rating}" if p.rating else "",
                p.source.upper(),
            )

    def on_data_table_row_selected(self, event):
        """Open the selected product's URL in the default browser."""
        if 0 <= event.cursor_row < len(self.products):
            webbrowser.open(self.products[event.cursor_row].url)

    def action_sort_price(self):
        """Sort products by price, ascending."""
        self.products.sort(key=lambda p: p.price if p.price > 0 else float("inf"))
        self.populate_table()

    def action_sort_rating(self):
        """Sort products by rating, descending."""
        self.products.sort(key=lambda p: p.rating or "", reverse=True)
        self.populate_table()

    def action_save(self):
        """Save current results to a JSON file."""
        if self.products:
            path = self.file_manager.save_results(self.current_query, self.products, "combined")
            self.notify(f"Saved to {path}")

    def action_copy_url(self):
        """Copy the selected product's URL to the clipboard."""
        try:
            import pyperclip

            row = self.query_one("#results_table").cursor_row
            pyperclip.copy(self.products[row].url)
            self.notify("URL Copied")
        except Exception:
            self.notify("Install pyperclip", severity="warning")
```

---

## Appendix B: `main.py`

```python
# main.py

from src.ui.app import EcomSearchApp

def main():
    """Launch the ecom_search TUI application."""
    app = EcomSearchApp()
    app.run()

if __name__ == "__main__":
    main()
```