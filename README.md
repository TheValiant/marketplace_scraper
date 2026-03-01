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
- **Advanced boolean search** — combine terms with `AND`, `OR`, quoted phrases, parentheses, and inline negations (e.g., `("multi collagen" OR "types I II III") AND powder -serum -cream`)
- **Deterministic subset caching** — in-memory result cache with set-theoretic subset matching; repeat / narrower searches return instantly with zero network calls
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
| `i` | Invalidate (clear) the in-memory query cache |
| Click row | Open product URL in default browser |

### Search Workflow

1. **Type your search query** in the search input — three modes are supported:
   - **Simple**: `multi collagen peptides hyaluronic`
   - **Multi-query** (semicolons): `collagen;vitamin d;krill oil`
   - **Boolean** (auto-detected): `("multi collagen" OR "types I II III") AND powder -serum -cream`
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

### Advanced Boolean Search

The search input supports full boolean query syntax. When the engine detects boolean operators (`AND`, `OR`, parentheses, or quoted phrases), it automatically activates the advanced pipeline.

#### Syntax Reference

| Element | Syntax | Example | Meaning |
|---|---|---|---|
| **Term** | bare word | `collagen` | Match products containing "collagen" |
| **Phrase** | `"quoted words"` | `"multi collagen"` | Match the exact phrase "multi collagen" |
| **AND** | `AND` or adjacent terms | `collagen AND powder` | Both terms must appear |
| **Implicit AND** | space-separated | `collagen powder` | Same as `collagen AND powder` |
| **OR** | `OR` | `collagen OR peptides` | Either term may appear |
| **Grouping** | `( )` | `(A OR B) AND C` | Override default precedence |
| **Negation** | `-keyword` | `-serum -cream` | Exclude products containing these words (**boolean mode only** — requires quotes, `AND`, `OR`, or parentheses elsewhere in the query) |

**Operator precedence** (highest to lowest): Grouping `()` > `AND` / implicit AND > `OR`

#### How It Works

1. **Parse**: The query is tokenized and parsed into an Abstract Syntax Tree (AST) using a recursive-descent parser.
2. **Extract negatives**: Trailing `-keyword` tokens are pulled out as global exclusions.
3. **DNF expansion**: The AST is converted to [Disjunctive Normal Form](https://en.wikipedia.org/wiki/Disjunctive_normal_form) (OR of ANDs). Each conjunction becomes an independent base query dispatched to the scrapers in parallel.
4. **AST verification**: After scraping, every product title is evaluated against the original AST. Products that don't logically satisfy the boolean expression are removed — this catches fuzzy/irrelevant results from search engines that ignore quotes or boolean operators.
5. **Negative filtering**: Products matching any `-keyword` are excluded.
6. **Deduplication**: Cross-query and cross-source duplicates are merged, keeping the cheapest.

#### Examples

**Simple OR expansion:**

```
"multi collagen" OR "hydrolyzed collagen"
```

Dispatches 2 base queries → `multi collagen` and `hydrolyzed collagen` → merges and deduplicates results.

**Complex boolean with negations:**

```
("multi collagen" OR "types I II III V X") AND "hyaluronic" AND powder -serum -cream -mask -gummies
```

Dispatches 2 base queries:
- `multi collagen hyaluronic powder`
- `types I II III V X hyaluronic powder`

Then locally verifies every result title contains the required phrases, and excludes any product matching `serum`, `cream`, `mask`, or `gummies`.

**Mixing with the filter input:**

In **boolean mode** (queries containing quotes, `AND`, `OR`, or parentheses), negations can appear in both places. `-keywords` embedded in the search query and comma-separated keywords in the filter input are merged. These two are equivalent:

- Search: `"multi collagen" -serum`, Filter: `cream, mask`
- Search: `"multi collagen" -serum -cream -mask`, Filter: *(empty)*

> **Note:** In simple (non-boolean) mode, `-keyword` in the search input is NOT parsed as an exclusion — it is sent as raw text to the search engine. Use the **filter input** for reliable exclusion on all platforms.

#### Auto-Detection

The engine auto-routes queries based on syntax:

| Query | Detected as | Pipeline |
|---|---|---|
| `collagen` | Simple | Standard `search()` |
| `collagen;vitamin d` | Multi-query | Sequential `search()` + cross-query dedup |
| `collagen -serum` | Simple | Standard `search()` — the `-serum` is sent as raw text; works natively on Amazon/iHerb but is **not** parsed or applied as a local filter. Use the filter input for reliable cross-platform exclusion. |
| `"multi collagen"` | Boolean (quotes) | Advanced `execute_advanced_search()` |
| `collagen AND powder` | Boolean (AND) | Advanced `execute_advanced_search()` |
| `collagen OR peptides` | Boolean (OR) | Advanced `execute_advanced_search()` |
| `(collagen OR peptides) AND powder` | Boolean (parens + operators) | Advanced `execute_advanced_search()` |

### Deterministic Subset Caching

The engine maintains an in-memory result cache that exploits set-theoretic relationships between queries to avoid redundant network calls.

#### How It Works

Every search result is cached with three keys: **base query**, **negative terms**, and **source set**. On subsequent searches, the cache checks whether an existing entry can satisfy the new request:

- A cached entry with **fewer** (or equal) negative exclusions than the requested query means the cached data is a **superset** — it contains everything the new query needs, plus some extra items that can be filtered locally.
- The cached entry must have the **same base query** and the **same source set** (adding a new marketplace forces a fresh scrape).

#### Subset Matching Logic

```
Cache hit when:
  cached.base_query == requested.base_query
  AND cached.source_ids == requested.source_ids
  AND cached.negative_terms ⊆ requested.negative_terms
```

#### Examples

| Step | Search | Cache State | Result |
|---|---|---|---|
| 1 | `collagen` (Amazon, Noon) | Empty | **MISS** — scrapes both sources, caches raw results |
| 2 | `collagen` (Amazon, Noon) | Has entry from step 1 | **HIT** — returns cached results instantly |
| 3 | `collagen -mask` (Amazon, Noon) | Has entry from step 1 (no negatives) | **HIT** — cached `{}` ⊆ requested `{mask}` → filters "mask" locally |
| 4 | `collagen -mask -serum` (Amazon, Noon) | Has entry from step 1 (no negatives) | **HIT** — cached `{}` ⊆ `{mask, serum}` → filters both locally |
| 5 | `collagen` (Amazon, Noon, iHerb) | Has entry from step 1 (Amazon, Noon only) | **MISS** — source set changed, re-scrapes all 3 |
| 6 | `vitamin d` (Amazon, Noon) | Has entry for "collagen" only | **MISS** — different base query |

Cache entries expire after `QUERY_CACHE_TTL` seconds (default: 1 hour). The cache stores results **post-validation but pre-filtering** — validated data (no empty titles or zero prices) but with all products intact, so narrower searches can filter locally without re-scraping.

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
│   │   ├── query_parser.py          # Boolean query compiler (tokenizer, AST, DNF, evaluator)
│   │   ├── deduplicator.py          # URL + same-source title deduplication
│   │   └── product_validator.py     # Drop products with empty titles / zero prices
│   │
│   ├── storage/
│   │   ├── file_manager.py          # JSON/CSV export, clipboard formatting
│   │   └── query_cache.py           # In-memory deterministic subset cache
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

The engine supports two pipelines, selected automatically based on query syntax.

#### Standard Pipeline (simple queries, semicolon multi-queries)

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
│   QueryCache        │──▶ Check for subset cache hit
│   (subset match?)   │    HIT → skip scrapers, filter locally
└─────────────────────┘    MISS ↓
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
         ▼ validated → stored in QueryCache
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

#### Advanced Pipeline (boolean queries with AND, OR, quotes, parens)

```
User Input (boolean query + exclusion keywords)
         │
         ▼
┌─────────────────────────┐
│  QueryPlanner.parse()   │──▶ Tokenize → AST → DNF expansion
│  ├── AST                │    Extracts global negatives
│  ├── base_queries[]     │    Produces N flat base queries
│  └── global_negatives   │
└─────────────────────────┘
         │
    ┌────┴────┐  (for each base query)
    ▼         ▼
┌────────┐ ┌────────┐
│Cache?  │ │Cache?  │──▶ HIT → use cached results
│ MISS   │ │  HIT   │    MISS → scrape via _run_scrapers()
└───┬────┘ └────────┘
    ▼
┌─────────────────────┐    Results cached
│  _run_scrapers()    │──▶ post-validation
│  (QueryEnhancer +   │
│   concurrent scrape)│
└─────────────────────┘
         │
         ▼ merged list[Product]
┌─────────────────────┐
│  ProductValidator   │──▶ Drops empty titles / zero prices
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  AST Evaluator      │──▶ local_evaluate(title, AST)
│  (local_evaluate)   │    Removes products that don't satisfy
└─────────────────────┘    the boolean expression
         │
         ▼
┌─────────────────────┐
│   ProductFilter     │──▶ Removes products matching negatives
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ ProductDeduplicator │──▶ Cross-query + cross-source dedup
└─────────────────────┘
         │
         ▼ final list[Product]
┌─────────────────────┐
│   TUI (DataTable)   │──▶ Display, sort, highlight cheapest
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
| `QUERY_CACHE_TTL` | `3600.0` | In-memory result cache time-to-live (seconds) |

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
