# ecom_search

A modular, local e-commerce price comparison engine for UAE markets. Search across multiple marketplaces simultaneously, filter out noise, compare prices, and export results — all from a rich Terminal User Interface.

> **Core Philosophy**: *"Resilience over Speed."* The engine prioritizes anti-detection and stability over raw scraping throughput.

## Supported Marketplaces

| Marketplace | Method | Region |
|---|---|---|
| **Amazon.ae** | HTML scraping | UAE |
| **Noon** | JSON API | UAE |
| **BinSina** | Algolia API | UAE |
| **Life Pharmacy** | REST API | UAE |
| **Aster** | Elasticsearch API | UAE |
| **iHerb** | HTML scraping + JSON fallback | UAE |

## Features

- **Multi-source concurrent search** — scrape all 6 marketplaces in parallel with a single query
- **Multi-query support** — search multiple terms at once using `;` as separator (e.g., `collagen;vitamin d;krill oil`)
- **Source selection** — toggle individual marketplaces on/off via checkboxes
- **Negative keyword filtering** — exclude irrelevant products using comma-separated exclusion keywords (dual-layer: pre-scrape query enhancement + post-scrape title filtering)
- **Product validation** — automatically drops products with empty titles or zero/negative prices
- **Deduplication** — removes duplicate products across sources via URL normalisation and same-source title matching, keeping the cheapest per group
- **Price comparison** — lowest price highlighted in bold green across all results
- **Sorting** — sort by price or rating with a single keypress
- **Export** — save results to JSON or CSV, copy to clipboard as TSV
- **Anti-detection** — browser-impersonating HTTP via `curl_cffi`, adaptive rate limiting, circuit breaker with auto-reset, CAPTCHA detection
- **Per-source timeout** — configurable request timeout per marketplace (HTML scrapers get longer timeouts than API scrapers)
- **Auto-save** — results automatically saved to `results/` after every search

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd marketplace_scraper

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---|---|
| `curl_cffi` | Browser-impersonating HTTP client (primary) |
| `cloudscraper` | Cloudflare bypass (fallback) |
| `beautifulsoup4` | HTML parsing |
| `lxml` | Fast HTML parser backend |
| `textual` | Terminal User Interface framework |
| `python-dotenv` | Environment variable loading |
| `pyperclip` | Clipboard operations (optional) |
| `rich` | Rich text formatting |

### Environment Variables

Create a `.env` file in the project root for any secrets or proxy configuration:

```bash
# .env (optional)
# Add proxy or API key configuration here if needed
```

## Usage

### Launch the TUI

```bash
python main.py
```

### TUI Layout

```
┌──────────────────────────────────────────────────────┐
│                    Header                             │
├──────────────────────────────────────────────────────┤
│  🛒 E-commerce Search (Noon, Amazon, BinSina, ...)   │
├──────────────────────────────────────────────────────┤
│  [ Search products (use ; for multiple queries)... ] │
│  [ Search ] │
│  [ Exclude keywords (comma-separated)... ]           │
├──────────────────────────────────────────────────────┤
│  Sources:                                            │
│  [x] Noon    [x] Amazon    [x] BinSina              │
│  [x] Life    [x] Aster     [x] iHerb                │
├──────────────────────────────────────────────────────┤
│  ✅ Showing 42 of 78 products (36 filtered, 5 deduped, 2 invalid, saved) │
├──────────────────────────────────────────────────────┤
│  Title              │ Price      │ Rating │ Source   │
│  Multi Collagen ... │ 89.00 AED  │ ⭐ 4.5 │ AMAZON  │
│  Collagen Peptid... │ 95.50 AED  │ ⭐ 4.3 │ NOON    │
│  ...                │            │        │          │
├──────────────────────────────────────────────────────┤
│                    Footer (keybindings)               │
└──────────────────────────────────────────────────────┘
```

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Enter` | Execute search (when in search input) |
| `q` | Quit the application |
| `p` | Sort results by price (ascending) |
| `r` | Sort results by rating (descending) |
| `s` | Save results to JSON |
| `e` | Export results to CSV |
| `c` | Copy selected product URL to clipboard |
| `x` | Copy all results to clipboard (TSV format) |
| Click row | Open product URL in default browser |

### Search Workflow

1. **Type your search query** in the search input (e.g., `multi collagen peptides hyaluronic`)
   - Use `;` to search multiple terms at once: `collagen;vitamin d;krill oil`
2. **Add exclusion keywords** (optional) in the filter input, comma-separated (e.g., `serum, cream, mask, lotion, shampoo`)
3. **Toggle sources** — uncheck any marketplaces you want to skip
4. **Press Enter or click Search** — scrapers run concurrently
5. **Browse results** — sorted table with cheapest product highlighted; duplicates auto-removed, invalid products auto-dropped
6. **Export** — press `s` for JSON, `e` for CSV, `x` for clipboard

### Negative Keyword Filtering

The filter input below the search bar accepts comma-separated keywords to exclude irrelevant products. Filtering works at two levels:

**Pre-scrape (query enhancement)**
For platforms that support boolean exclusion in their search syntax (Amazon, iHerb), negative keywords are appended directly to the search query as `-keyword` terms. This reduces noise at the source and returns cleaner results.

Example: searching `collagen powder` with exclusions `serum, cream` sends `collagen powder -serum -cream` to Amazon.

**Post-scrape (title filtering)**
After results are collected from all sources, products whose titles contain any of the exclusion keywords are removed. This catches noise from API-based platforms (Noon, BinSina, Aster, Life Pharmacy) that don't support `-keyword` syntax.

The filter is case-insensitive and uses substring matching. The status bar shows how many products were filtered: `Showing X of Y products (Z filtered out)`.

**Examples by product category:**

| Searching for | Suggested exclusions |
|---|---|
| Supplements/powders | `serum, cream, mask, lotion, shampoo, conditioner, lip, gloss, balm, wash, cleanser` |
| Electronics/laptops | `case, sleeve, screen protector, sticker, skin, stand` |
| Books | `kindle, audiobook, summary, workbook` |
| Shoes | `laces, insole, cleaner, polish, tree` |

## Project Structure

```
marketplace_scraper/
├── main.py                          # Entry point — launches the TUI
├── requirements.txt                 # Python dependencies
├── .env                             # Secrets & environment config
├── pylance.sh                       # Linter gate (Flake8 + Pyright strict)
├── project_design.md                # Detailed design document
│
├── src/
│   ├── config/
│   │   ├── settings.py              # All constants (delays, retries, timeouts, sources)
│   │   ├── selectors.json           # CSS selectors for HTML-based scrapers
│   │   └── logging_config.py        # Logging setup
│   │
│   ├── models/
│   │   └── product.py               # Product dataclass
│   │
│   ├── scrapers/
│   │   ├── base_scraper.py          # Abstract base: session, retries, circuit breaker
│   │   ├── amazon_scraper.py        # Amazon.ae (HTML)
│   │   ├── noon_scraper.py          # Noon (JSON API)
│   │   ├── binsina_scraper.py       # BinSina (Algolia API)
│   │   ├── life_pharmacy_scraper.py # Life Pharmacy (REST API)
│   │   ├── aster_scraper.py         # Aster (Elasticsearch API)
│   │   └── iherb_scraper.py         # iHerb (HTML + JSON fallback)
│   │
│   ├── services/
│   │   └── search_orchestrator.py   # SearchOrchestrator — coordinates multi-source search
│   │
│   ├── filters/
│   │   ├── product_filter.py        # Post-scrape filtering by negative keywords
│   │   ├── query_enhancer.py        # Pre-scrape query enhancement
│   │   ├── deduplicator.py          # URL + same-source title deduplication
│   │   └── product_validator.py     # Drop products with empty titles / zero prices
│   │
│   ├── storage/
│   │   └── file_manager.py          # JSON/CSV export, clipboard formatting
│   │
│   └── ui/
│       ├── app.py                   # EcomSearchApp (Textual TUI)
│       └── styles.css               # TUI styles
│
├── results/                         # Auto-saved search results (JSON)
├── logs/                            # Application logs
└── tests/                           # Unit tests
```

## Architecture

### Data Flow

```
User Input (query + exclusion keywords)
         │
         ▼
┌─────────────────────────┐
│  SearchOrchestrator     │──▶ Coordinates entire pipeline
│  (multi_search /        │
│   search)               │
└─────────────────────────┘
         │
         ▼
┌─────────────────────┐
│   QueryEnhancer     │──▶ Appends -keywords for Amazon/iHerb
└─────────────────────┘
         │
         ▼
┌─────────────────────┐    ┌──────────────┐
│  Scraper (async)    │───▶│ BaseScraper  │
│  ├── Amazon (20s)   │    │  curl_cffi   │
│  ├── Noon (10s)     │    │  cloudscraper│
│  ├── BinSina (15s)  │    │  rate limit  │
│  ├── Life (10s)     │    │  circuit     │
│  ├── Aster (15s)    │    │  breaker +   │
│  └── iHerb (20s)    │    │  cooldown    │
└─────────────────────┘    └──────────────┘
         │
         ▼ list[Product]
┌─────────────────────┐
│  ProductValidator   │──▶ Drops empty titles / zero prices
└─────────────────────┘
         │
         ▼ validated list[Product]
┌─────────────────────┐
│   ProductFilter     │──▶ Removes products matching exclusion keywords
└─────────────────────┘
         │
         ▼ filtered list[Product]
┌─────────────────────┐
│ ProductDeduplicator │──▶ URL + same-source title dedup (keeps cheapest)
└─────────────────────┘
         │
         ▼ deduplicated list[Product]
┌─────────────────────┐
│   TUI (DataTable)   │──▶ Display, sort, highlight cheapest
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   FileManager       │──▶ Auto-save JSON, export CSV/TSV
└─────────────────────┘
```

### Scraper Types

| Type | Scrapers | How it works |
|---|---|---|
| **HTML** | Amazon, iHerb | Fetch HTML pages, parse with BeautifulSoup + CSS selectors from `selectors.json` |
| **JSON API** | Noon, BinSina, Aster, Life Pharmacy | Call marketplace APIs directly, parse JSON responses |

### Anti-Detection Strategy

| Mechanism | Description |
|---|---|
| **Browser impersonation** | `curl_cffi` with `impersonate="chrome131"` mimics real Chrome TLS fingerprint |
| **Realistic headers** | Full set of `sec-ch-ua`, `Accept-Language`, `Referer` headers |
| **Adaptive rate limiting** | Configurable `REQUEST_DELAY` between requests, exponential backoff on failures |
| **Circuit breaker** | After `CIRCUIT_BREAKER_THRESHOLD` consecutive failures, stops hitting the source; auto-resets after `CIRCUIT_BREAKER_COOLDOWN` (60s) via half-open probe |
| **CAPTCHA detection** | Scans response HTML for CAPTCHA keywords, triggers backoff |
| **Fallback HTTP client** | If `curl_cffi` fails, falls back to `cloudscraper` |

## Configuration

All tuneable constants live in `src/config/settings.py`. No magic numbers in scraper or UI code.

| Setting | Default | Description |
|---|---|---|
| `REQUEST_DELAY` | `2.0` | Seconds between HTTP requests |
| `REQUEST_TIMEOUT` | `15` | Seconds before a request times out |
| `MAX_RETRIES` | `3` | Retry count on transient failures |
| `MAX_PAGES` | `10` | Maximum pagination depth per source |
| `CIRCUIT_BREAKER_THRESHOLD` | `3` | Consecutive failures to trip the circuit breaker |
| `CIRCUIT_BREAKER_COOLDOWN` | `60.0` | Seconds before the circuit breaker auto-resets (half-open) |
| `MAX_DELAY_MULTIPLIER` | `8` | Cap for adaptive backoff multiplier |
| `IMPERSONATE_BROWSER` | `chrome131` | Browser to impersonate in curl_cffi |
| `QUERY_ENHANCED_PLATFORMS` | `["amazon", "iherb"]` | Platforms supporting `-keyword` query syntax |

### Per-Source Timeout

Each source in `AVAILABLE_SOURCES` can optionally include a `"timeout"` key to override the global `REQUEST_TIMEOUT`. This is useful because HTML scrapers (Amazon, iHerb) need longer timeouts for page rendering, while fast REST APIs (Noon, Life Pharmacy) can use shorter timeouts:

| Source | Timeout | Reason |
|---|---|---|
| Amazon | 20s | HTML page scraping |
| iHerb | 20s | HTML + JSON hybrid |
| Noon | 10s | Fast JSON API |
| Life Pharmacy | 10s | Fast REST API |
| BinSina | 15s (default) | Algolia API |
| Aster | 15s (default) | Elasticsearch API |

### CSS Selectors

HTML-based scrapers (Amazon, iHerb) use CSS selectors defined in `src/config/selectors.json`. If a marketplace changes its layout, update the selectors file — not the scraper code.

```json
{
    "amazon": {
        "product_card": "div[data-component-type='s-search-result']",
        "title": "h2 span",
        "price": "span.a-price span.a-offscreen",
        "rating": "span.a-icon-alt",
        "url": "a.a-link-normal.s-line-clamp-4"
    }
}
```

## Data Model

All scrapers return a `list[Product]`. The `Product` dataclass is the single data exchange format across all modules:

```python
@dataclass
class Product:
    title: str           # Product name
    price: float         # Numeric price
    currency: str        # Default: "AED"
    rating: str          # Rating as string (e.g., "4.5 out of 5 stars")
    url: str             # Full product page URL
    source: str          # Marketplace identifier (e.g., "amazon", "noon")
    image_url: str       # Product image URL
```

## Output Formats

### JSON (auto-saved)

Results are automatically saved after every search to `results/`:

```
results/
├── combined_multi_collagen_20260228_141532.json
├── amazon_multi_collagen_20260228_141532.json
├── noon_multi_collagen_20260228_141532.json
└── ...
```

Each file contains an array of product objects:

```json
[
    {
        "title": "Multi Collagen Peptides Powder with Hyaluronic Acid",
        "price": 89.0,
        "currency": "AED",
        "rating": "4.5 out of 5 stars",
        "url": "https://www.amazon.ae/...",
        "source": "amazon"
    }
]
```

### CSV (on demand)

Press `e` to export a price-sorted CSV:

```csv
Title,Price,Currency,Rating,Source,URL
Multi Collagen Peptides...,89.0,AED,4.5 out of 5 stars,amazon,https://...
```

### Clipboard (on demand)

Press `x` to copy all results as tab-separated text.

## Development

### Linting

The project enforces strict code quality via `pylance.sh`:

```bash
./pylance.sh
```

This runs:
1. **Flake8** — style checking, max complexity 10, 88-char line limit
2. **Pyright** — strict mode type checking

Both must pass with zero errors before any change is considered complete.

### Adding a New Marketplace

1. Create `src/scrapers/new_scraper.py` extending `BaseScraper`
2. Implement `_get_homepage()` and `search(query: str) -> list[Product]`
3. For HTML scrapers: add CSS selectors to `src/config/selectors.json`
4. Register the source in `Settings.AVAILABLE_SOURCES`:
   ```python
   {"id": "new_source", "label": "New Source", "scraper": "src.scrapers.new_scraper.NewScraper"}
   ```
5. If the platform supports `-keyword` exclusion syntax, add its `id` to `Settings.QUERY_ENHANCED_PLATFORMS`

The TUI automatically picks up new sources — no UI code changes needed.

### Testing

```bash
python -m pytest tests/
```

Tests mock HTTP sessions (`curl_cffi.Session`) and never hit live marketplace URLs.

## License

Private project — not for redistribution.
