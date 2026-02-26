# Plan: Integrate 3 Pharmacy Scrapers + Dynamic Registry

## TL;DR
Add BinSina, Life Pharmacy, and myAster pharmacy retailer scrapers, then refactor the hardcoded UI to use a dynamic registry pattern driven by `Settings.AVAILABLE_SOURCES`. All scrapers follow the NoonScraper pattern (standalone JSON API, curl_cffi sessions).

---

## Phase 1: Create Pharmacy Scrapers

### Step 1 — BinSina Scraper (`src/scrapers/binsina_scraper.py`)
- **API**: Algolia via Magento 2. Two-step: (1) fetch `https://binsina.ae/en/` homepage to extract fresh time-limited API key from `window.algoliaConfig`, (2) POST to `https://FTRV4XOC74-dsn.algolia.net/1/indexes/magento2_en_products/query`
- **Auth**: App ID `FTRV4XOC74`, API key must be scraped from homepage each session (time-limited, encoded with `validUntil`)
- **Field mapping**: `hit["name"]`→title, `hit["price"]["AED"]["default"]`→price, `hit["url"]`→url (prepend `https://binsina.ae`), `hit["image_url"]`→image_url, `hit["rating_summary"]`→rating
- **Pagination**: Algolia `page` param (0-indexed), check `nbPages`
- **Pattern**: Follow NoonScraper structure (standalone class, curl_cffi session, try/except returning `[]`)

### Step 2 — Life Pharmacy Scraper (`src/scrapers/life_pharmacy_scraper.py`)
- **API**: REST GET endpoint `https://prodapp.lifepharmacy.com/api/v1/products/search/{query}?lang=ae-en`
- **Auth**: None required (public endpoint)
- **Field mapping**: `p["title"]`→title, `p["sale"]["offer_price"]`→price (final/discounted), `p["sale"]["currency"]`→currency, `p["rating"]`→rating, `https://www.lifepharmacy.com/product/{p["slug"]}`→url, `p["images"]["featured_image"]`→image_url
- **Pagination**: Currently returns all results in single response (27 for "panadol"). No pagination needed initially.
- **Response path**: `resp.json()["data"]["products"]`

### Step 3 — myAster Scraper (`src/scrapers/aster_scraper.py`)
- **API**: Elasticsearch-based REST GET `https://api.myaster.com/uae/ae/search/api/search?text={query}&productPageSize={size}&productPageFrom={page}`
- **Auth**: None required (public endpoint)
- **Field mapping**: `p["name"]`→title, `p["special_price"]` or `p["price"]`→price (prefer special_price as final price), `p["currency"]`→currency, `p["avgRating"]`→rating, `https://www.myaster.com/en/online-pharmacy{p["productUrl"]}`→url, `p["small_image"]`→image_url
- **Pagination**: `productPageFrom` (0-indexed page number), `productPageSize` (default 50), check `totalPages`
- **Response path**: `resp.json()["data"]`

### Step 4 — Test Fixtures
- Create `tests/fixtures/binsina_algolia.json` — mock Algolia response with 3-4 hits
- Create `tests/fixtures/life_pharmacy_search.json` — mock Life Pharmacy response
- Create `tests/fixtures/aster_search.json` — mock myAster response
- Also create `tests/fixtures/binsina_homepage.html` — mock snippet containing `window.algoliaConfig` with API key

### Step 5 — Test Files
- Create `tests/test_binsina_scraper.py` — mock `curl_requests.Session`, test API key extraction, product parsing, error handling
- Create `tests/test_life_pharmacy_scraper.py` — mock session, test product field mapping, empty results, HTTP errors
- Create `tests/test_aster_scraper.py` — mock session, test special_price fallback to price, pagination, error handling
- Follow existing `tests/test_noon_scraper.py` patterns (unittest, MagicMock, patch)

---

## Phase 2: Dynamic Registry Refactor

### Step 6 — Update `src/config/settings.py`
- Add 3 new entries to `AVAILABLE_SOURCES`:
  - `{"id": "binsina", "label": "BinSina", "scraper": "src.scrapers.binsina_scraper.BinSinaScraper"}`
  - `{"id": "life_pharmacy", "label": "Life Pharmacy", "scraper": "src.scrapers.life_pharmacy_scraper.LifePharmacyScraper"}`
  - `{"id": "aster", "label": "Aster", "scraper": "src.scrapers.aster_scraper.AsterScraper"}`

### Step 7 — Refactor `src/ui/app.py` (*depends on Step 6*)
- Remove hardcoded imports of `AmazonScraper`, `NoonScraper`
- Add `_load_scraper_class(dotted_path: str)` helper using `importlib.import_module` to dynamically load scraper classes from `Settings.AVAILABLE_SOURCES`
- Replace hardcoded `Checkbox("Noon"...)`, `Checkbox("Amazon"...)` in `compose()` with a loop over `Settings.AVAILABLE_SOURCES` generating `Checkbox(s["label"], value=True, id=f"check_{s['id']}")`
- Replace hardcoded `use_noon`/`use_amazon` checks in `perform_search()` with a loop: iterate `AVAILABLE_SOURCES`, check `self.query_one(f"#check_{s['id']}").value`, load scraper class dynamically, append to tasks list
- Update title string to reflect all sources (or make it generic)

### Step 8 — Update `src/ui/styles.css` (*parallel with Step 7*)
- Change `#source_toggles { height: 3; }` to `height: auto;` to accommodate 5 checkboxes dynamically

---

## Phase 3: Cleanup

### Step 9 — Delete temporary files
- Delete `_discover_apis.py` from project root

---

## Relevant Files

- `src/scrapers/noon_scraper.py` — **template** for all 3 new scrapers (standalone class pattern, curl_cffi session, retry loop, pagination)
- `src/config/settings.py` — add 3 entries to `AVAILABLE_SOURCES`
- `src/ui/app.py` — refactor to dynamic registry (remove hardcoded imports/checkboxes/dispatch)
- `src/ui/styles.css` — adjust `#source_toggles` height
- `src/models/product.py` — reuse `Product` dataclass (no changes needed)
- `tests/test_noon_scraper.py` — **reference** for test structure (unittest, mock patterns)
- `tests/fixtures/noon_search.json` — **reference** for fixture format

---

## Verification

1. **Unit tests**: `python -m pytest tests/ -v` — all existing + new tests pass
2. **Lint check**: `python -m py_compile src/scrapers/binsina_scraper.py src/scrapers/life_pharmacy_scraper.py src/scrapers/aster_scraper.py`
3. **Dynamic loading**: Launch the TUI (`python main.py`) and verify all 5 checkboxes appear
4. **Live search** (manual): Search "panadol" with each pharmacy source enabled individually, confirm results populate and auto-save to `results/`
5. **Error resilience**: Disable network and verify scrapers return `[]` without crashing the TUI

---

## Decisions
- **BinSina API key**: Must be scraped fresh from homepage each session (time-limited Algolia key with `validUntil`). The scraper will call `_refresh_api_key()` before first search and cache it for the session.
- **myAster parameter**: The search parameter is `text` (not `q` or `query`). Pagination uses `productPageFrom` (0-indexed) and `productPageSize`.
- **Life Pharmacy pagination**: Not needed initially — single response returns all matching products.
- **No `BaseScraper` inheritance**: Pharmacy scrapers use JSON APIs, not HTML/CSS selectors. They follow the NoonScraper standalone pattern.
- **Scope exclusion**: No changes to `selectors.json` (pharmacy scrapers don't use CSS selectors). No changes to `Product` dataclass. No changes to `FileManager`.
