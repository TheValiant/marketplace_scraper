# `ecom_search` — Project Design Document

> **Version**: 2.0
> **Last Updated**: 2026-03-01
> **Core Philosophy**: *"Resilience over Speed."*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Configuration Layer](#4-configuration-layer)
5. [Data Models](#5-data-models)
6. [Scraping Engine](#6-scraping-engine)
7. [Search Orchestration & Filtering Pipeline](#7-search-orchestration--filtering-pipeline)
8. [Price History & Tracking](#8-price-history--tracking)
9. [TUI Application](#9-tui-application)
10. [CLI Mode](#10-cli-mode)
11. [Charts & Visualization](#11-charts--visualization)
12. [Storage & Export](#12-storage--export)
13. [Anti-Detection Strategy](#13-anti-detection-strategy)
14. [Testing Strategy](#14-testing-strategy)

---

## 1. Overview

`ecom_search` is a **modular, local e-commerce price comparison engine** for UAE markets. It scrapes product listings from **6 sources** (Noon, Amazon.ae, BinSina, Life Pharmacy, Aster, iHerb), presents them in a rich Terminal User Interface (TUI), tracks price history in SQLite, and generates interactive charts — all from the terminal.

### Key Capabilities

| Feature | Description |
|---|---|
| **Multi-source search** | Scrapes 6 UAE marketplaces concurrently |
| **Source selection** | Checkboxes to toggle individual sources on/off |
| **Boolean query syntax** | Supports `OR`, `AND`, parentheses, `-exclusion` |
| **Multi-query** | Semicolon-separated queries executed in parallel |
| **Price tracking** | SQLite database auto-records every search result |
| **Star/watchlist** | Pin products for focused tracking |
| **In-TUI charts** | ASCII price history charts via textual-plotext |
| **Browser charts** | Interactive Plotly HTML charts opened in browser |
| **Sorting** | Sort by price or rating with a single keypress |
| **Export** | Save results to JSON/CSV, copy to clipboard |
| **Query cache** | Avoids duplicate requests within a session |
| **Health check** | Verifies scraper connectivity across all sources |
| **Loading indicator** | Visual feedback during multi-source searches |
| **Anti-detection** | Browser-impersonating HTTP via `curl_cffi` |
| **Legacy import** | One-time migration of existing JSON result files |

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        main.py (Entry Point)                         │
│         Routes: TUI (default) │ CLI (query) │ Utilities              │
└──────────┬──────────┬─────────┬──────────┬──────────┬────────────────┘
           │          │         │          │          │
     No args     query arg   --health  --chart   --import-history
           │          │         │          │          │
           ▼          ▼         ▼          ▼          ▼
      ┌────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌────────┐
      │  TUI   │ │  CLI   │ │Health│ │ Chart  │ │ Import │
      │app.py  │ │runner  │ │Check │ │Exporter│ │Legacy  │
      └───┬────┘ └───┬────┘ └──────┘ └────────┘ └────────┘
          │          │
          ▼          ▼
    ┌─────────────────────────┐
    │   SearchOrchestrator    │     Concurrent scraping + filtering
    │   (multi_search)        │
    └──────────┬──────────────┘
               │
    ┌──────────▼──────────────┐
    │   Filtering Pipeline     │
    │  QueryParser → Enhancer  │
    │  → Validator → Filter    │
    │  → Deduplicator          │
    └──────────┬──────────────┘
               │
    ┌──────────▼──────────────┐     ┌──────────────────────┐
    │   6 Scrapers             │     │  Storage Layer        │
    │   noon, amazon, binsina  │     │  ├ PriceHistoryDB     │
    │   life_pharmacy, aster   │     │  ├ FileManager        │
    │   iherb                  │     │  ├ ChartExporter      │
    └──────────────────────────┘     │  └ QueryCache         │
                                     └──────────────────────┘
```

### Data Flow

1. User types a query and presses **Search** (or `Enter`).
2. `LoadingIndicator` appears while search runs.
3. `SearchOrchestrator.multi_search()` dispatches scrapers concurrently via `asyncio.gather()`.
4. Results pass through the filtering pipeline: validation → enhancement → keyword filtering → deduplication.
5. Valid products are auto-recorded in the SQLite price history database.
6. Results populate the `DataTable` with trend indicators (↑↓→).
7. `LoadingIndicator` hides, status bar shows result summary.

---

## 3. Directory Structure

```
marketplace_scraper/
├── main.py                        # Entry point: TUI, CLI, utilities
├── pylance.sh                     # Linter gate (flake8 + pyright strict)
├── requirements.txt               # Pin-locked dependencies
├── project_design.md              # This document
├── .env                           # Secrets (not committed)
├── .gitignore
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── settings.py            # All constants (delays, retries, paths, sources)
│   │   ├── selectors.json         # CSS selectors for each marketplace
│   │   └── logging_config.py      # Structured logging setup
│   │
│   ├── models/
│   │   ├── product.py             # Product dataclass
│   │   └── price_snapshot.py      # PriceSnapshot dataclass (temporal)
│   │
│   ├── scrapers/
│   │   ├── base_scraper.py        # Abstract base: session, extract_price, headers
│   │   ├── noon_scraper.py        # Noon.com scraper
│   │   ├── amazon_scraper.py      # Amazon.ae scraper
│   │   ├── binsina_scraper.py     # BinSina Pharmacy scraper
│   │   ├── life_pharmacy_scraper.py  # Life Pharmacy scraper
│   │   ├── aster_scraper.py       # Aster Pharmacy scraper
│   │   └── iherb_scraper.py       # iHerb scraper
│   │
│   ├── filters/
│   │   ├── query_parser.py        # Boolean query parsing (AND/OR/NOT)
│   │   ├── query_enhancer.py      # Query expansion & synonym handling
│   │   ├── product_validator.py   # Validates scraped Product fields
│   │   ├── product_filter.py      # Negative keyword filtering
│   │   └── deduplicator.py        # URL-based deduplication
│   │
│   ├── services/
│   │   ├── search_orchestrator.py # Concurrent search + pipeline orchestration
│   │   └── health_checker.py      # Source connectivity probe
│   │
│   ├── storage/
│   │   ├── file_manager.py        # JSON/CSV export
│   │   ├── price_history_db.py    # SQLite price history CRUD
│   │   ├── chart_exporter.py      # Plotly HTML chart generation
│   │   └── query_cache.py         # In-memory query deduplication cache
│   │
│   ├── cli/
│   │   └── runner.py              # Headless CLI search + utility commands
│   │
│   └── ui/
│       ├── app.py                 # EcomSearchApp (Textual TUI)
│       └── styles.css             # Textual CSS styles
│
├── data/                          # (gitignored) Runtime data
│   ├── price_history.db           # SQLite database
│   └── charts/                    # Generated HTML charts
│
├── results/                       # Saved search results (JSON)
├── logs/                          # Application logs
│
└── tests/
    ├── conftest.py                # Shared fixtures, sleep patch
    ├── test_noon_scraper.py
    ├── test_amazon_scraper.py
    ├── test_binsina_scraper.py
    ├── test_life_pharmacy_scraper.py
    ├── test_aster_scraper.py
    ├── test_iherb_scraper.py
    ├── test_base_scraper.py
    ├── test_search_orchestrator.py
    ├── test_product_filter.py
    ├── test_product_validator.py
    ├── test_query_parser.py
    ├── test_deduplicator.py
    ├── test_file_manager.py
    ├── test_query_cache.py
    ├── test_settings.py
    ├── test_app.py
    ├── test_cli.py
    ├── test_price_history_db.py
    ├── test_health_checker.py
    └── test_chart_exporter.py
```

---

## 4. Configuration Layer

### `src/config/settings.py`

All tuneable constants live here. **No magic numbers** in scraper or UI code.

Key settings include:
- `REQUEST_DELAY`, `REQUEST_TIMEOUT`, `MAX_RETRIES`, `MAX_PAGES`
- `IMPERSONATE_BROWSER = "chrome124"`
- `BASE_DIR`, `SELECTORS_PATH`, `RESULTS_DIR`, `DATA_DIR`, `PRICE_DB_PATH`
- `AVAILABLE_SOURCES` — Registry of all 6 scrapers with dotted import paths and optional timeouts

### `src/config/selectors.json`

CSS selectors are **never hardcoded** in Python. If a site changes its layout, only this file is updated. Contains selectors for: `product_card`, `title`, `price`, `currency`, `rating`, `url`, `next_page` per source.

---

## 5. Data Models

### `Product` (`src/models/product.py`)

Core data transfer object for scraped results:

| Field | Type | Description |
|---|---|---|
| `title` | `str` | Product name |
| `price` | `float` | Extracted numeric price |
| `currency` | `str` | Currency code (AED, USD) |
| `rating` | `str` | Star rating or review text |
| `url` | `str` | Product page URL |
| `source` | `str` | Source identifier (noon, amazon, etc.) |

### `PriceSnapshot` (`src/models/price_snapshot.py`)

Temporal price observation for history tracking:

| Field | Type | Description |
|---|---|---|
| `product_url` | `str` | Normalized canonical URL |
| `title` | `str` | Product name at scrape time |
| `price` | `float` | Price at scrape time |
| `currency` | `str` | Currency code |
| `source` | `str` | Source identifier |
| `scraped_at` | `datetime` | Timestamp of observation |

---

## 6. Scraping Engine

### Base Scraper (`src/scrapers/base_scraper.py`)

All scrapers inherit from `BaseScraper` which provides:
- `curl_cffi` session with `impersonate="chrome124"` and anti-detection headers
- `extract_price()` static method for consistent price parsing
- `Referer` header set to target site's homepage
- Rate limiting via `Settings.REQUEST_DELAY`

### Active Scrapers

| Source | Module | Strategy |
|---|---|---|
| **Noon** | `noon_scraper.py` | HTML scraping via CSS selectors |
| **Amazon.ae** | `amazon_scraper.py` | HTML scraping with pagination |
| **BinSina** | `binsina_scraper.py` | Pharmacy product scraping |
| **Life Pharmacy** | `life_pharmacy_scraper.py` | Pharmacy product scraping |
| **Aster** | `aster_scraper.py` | Pharmacy product scraping |
| **iHerb** | `iherb_scraper.py` | Supplement marketplace scraping |

All scrapers wrap operations in `try/except`, returning `[]` on failure rather than crashing.

---

## 7. Search Orchestration & Filtering Pipeline

### `SearchOrchestrator` (`src/services/search_orchestrator.py`)

Coordinates the full search lifecycle:

1. **Query Parsing** — `QueryParser` handles boolean syntax (`OR`, `AND`, `-exclusion`, parentheses)
2. **Query Enhancement** — `QueryEnhancer` expands synonyms/variants
3. **Concurrent Scraping** — Dispatches selected scrapers via `asyncio.gather()` with per-source timeouts
4. **Validation** — `ProductValidator` checks required fields, price > 0, valid URLs
5. **Keyword Filtering** — `ProductFilter` applies negative keywords from user input
6. **Deduplication** — `Deduplicator` removes URL-based duplicates
7. **Auto-Recording** — Saves all valid products to SQLite price history

Returns a `SearchResult` dataclass with products, error messages, and pipeline statistics (filtered count, deduped count, invalid count, total before filter).

### Multi-Query Support

Semicolon-separated queries (e.g., `"collagen; vitamin c"`) are executed as independent parallel searches and merged.

---

## 8. Price History & Tracking

### `PriceHistoryDB` (`src/storage/price_history_db.py`)

SQLite-based persistent price tracking:

**Schema:**
- `products` table: `id`, `url` (unique, normalized), `title`, `source`, `first_seen`, `is_starred`
- `price_snapshots` table: `id`, `product_id` (FK), `price`, `currency`, `scraped_at`
- Index on `(product_id, scraped_at)` for fast trend queries

**Key Methods:**
| Method | Description |
|---|---|
| `record_snapshots()` | Upsert products + insert price snapshots |
| `get_price_history()` | All snapshots for a URL, ordered by date |
| `get_price_trends()` | Multi-product trend data for charting |
| `get_trend_summary()` | Min/max/avg/direction for trend indicators |
| `toggle_star()` | Pin/unpin a product for watchlist |
| `is_starred()` | Check star status |
| `get_starred_products()` | All starred products with stats |
| `search_products_by_title()` | Find products by title substring |
| `import_single_file()` | Import one legacy JSON result file |
| `import_legacy_results()` | Bulk import all files from results/ dir |

**URL Normalization:** Strips query parameters (tracking params like `ref=`, `dib=`, `qid=`) and Amazon path-based `/ref=...` segments to match the same product across searches.

**Auto-Recording:** Every search automatically records snapshots via `SearchOrchestrator`, building history over time without user intervention.

---

## 9. TUI Application

### `EcomSearchApp` (`src/ui/app.py`)

Built with [Textual](https://textual.textualize.io/) — a modern Python TUI framework.

### Layout

```
┌─────────────────────── Header ───────────────────────┐
│  🛒 E-commerce Search (Noon, Amazon, BinSina, ...)   │
├──────────────────────────────────────────────────────┤
│  [Search Input                          ] [Search]   │
│  [Exclude keywords: serum, cream, mask...]           │
│  ▼ Sources                                           │
│    [x] Noon  [x] Amazon  [x] BinSina                │
│    [x] Life  [x] Aster   [x] iHerb                  │
│  Status: ✅ Found 42 products (3 filtered, saved)    │
│  [LoadingIndicator — visible during search]          │
├──────────────────────────────────────────────────────┤
│  ┌─Results─┐ ┌─Price History─┐ ┌─Watchlist─┐        │
│  │ Title      │ Price │ Rating │ Source │ Trend │    │
│  │ Product A  │ 45.00 │ 4.5    │ amazon │  ↓   │    │
│  │ ★ Product B│ 52.00 │ 4.8    │ noon   │  ↑   │    │
│  └───────────────────────────────────────────────┘   │
├──────────────────────── Footer ──────────────────────┤
│  q:Quit s:Save e:CSV p:Price r:Rating c:URL         │
│  x:CopyAll i:Cache h:History t:Star w:Watch o:Chart  │
└──────────────────────────────────────────────────────┘
```

### Tabs

| Tab | Content |
|---|---|
| **Results** | DataTable with Title, Price, Rating, Source, Trend columns |
| **Price History** | PlotextPlot ASCII chart + stats for selected product |
| **Watchlist** | DataTable of starred products with min/max/avg/latest prices |

### Key Bindings

| Key | Action | Description |
|---|---|---|
| `q` | Quit | Exit the application |
| `s` | Save | Save results to JSON |
| `e` | Export CSV | Export results as CSV |
| `p` | Price Sort | Toggle price sort asc/desc |
| `r` | Rating Sort | Toggle rating sort asc/desc |
| `c` | Copy URL | Copy selected product URL to clipboard |
| `x` | Copy All | Copy all results as TSV to clipboard |
| `i` | Clear Cache | Invalidate the query cache |
| `h` | History | Show price history chart for selected product |
| `t` | Star | Toggle star/pin on selected product |
| `w` | Watchlist | Switch to watchlist tab |
| `o` | Browser Chart | Open interactive Plotly chart in browser |

### Trend Indicators

The Trend column shows directional arrows based on price history:
- **↑** (green) — Price trending up
- **↓** (red) — Price trending down
- **→** (dim) — Price stable
- Starred products show ★ prefix on title

---

## 10. CLI Mode

Run headless searches without the TUI:

```bash
# Basic search
python main.py "collagen peptides"

# Filter sources and exclude keywords
python main.py "vitamin c" -s noon,amazon -e "serum,cream"

# Output as table instead of JSON
python main.py "krill oil" -f table

# Custom output directory
python main.py "collagen" -o ./my_results

# Health check all sources
python main.py --health

# Import legacy JSON results into SQLite
python main.py --import-history

# Generate browser chart for matching products
python main.py --chart "collagen"

# Generate watchlist dashboard chart
python main.py --watchlist
```

---

## 11. Charts & Visualization

### In-TUI Charts (textual-plotext)

Press `h` on a product to view an ASCII price history chart directly in the terminal. Uses `PlotextPlot` widget from `textual-plotext`. Shows min/max/average statistics alongside the chart.

### Browser Charts (Plotly HTML)

`ChartExporter` (`src/storage/chart_exporter.py`) generates standalone interactive HTML charts:

| Function | Description |
|---|---|
| `export_price_chart()` | Single product line chart with min/max annotations |
| `export_comparison_chart()` | Multi-product overlay for comparison |
| `export_watchlist_dashboard()` | Dashboard for all starred products |

Charts are saved to `data/charts/` and auto-opened in the default browser. Features: hover tooltips, source color-coding, min/max annotations, responsive layout.

---

## 12. Storage & Export

| Component | Purpose | Location |
|---|---|---|
| `FileManager` | JSON/CSV result export | `results/` |
| `PriceHistoryDB` | SQLite price tracking | `data/price_history.db` |
| `ChartExporter` | Plotly HTML charts | `data/charts/` |
| `QueryCache` | In-memory query dedup | (runtime only) |

---

## 13. Anti-Detection Strategy

| Technique | Implementation |
|---|---|
| **Browser impersonation** | `curl_cffi` with `impersonate="chrome124"` |
| **Realistic headers** | `Accept-Language`, `Referer` to target homepage |
| **Rate limiting** | `Settings.REQUEST_DELAY` between requests |
| **Fallback client** | `cloudscraper` if `curl_cffi` fails |
| **Selector separation** | CSS selectors in JSON, not hardcoded |
| **Graceful failure** | Scrapers return `[]` on error, never crash |

---

## 14. Testing Strategy

- **Framework**: `unittest` (TestCase + IsolatedAsyncioTestCase) run via `pytest`
- **Coverage**: 324+ tests across all modules
- **Mocking**: All HTTP calls mocked — never hits live sites during tests
- **Linter gate**: `pylance.sh` enforces flake8 (88-char lines, max-complexity 10) + pyright strict mode
- **Zero tolerance**: No `# type: ignore`, no `# noqa` — all checks must pass clean
- **Deterministic**: Fixed data, no randomness in tests
