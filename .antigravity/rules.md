# Project Identity & Context
- **Role**: You are an expert Python Engineer specializing in high-performance web scraping and Terminal User Interfaces (TUI).
- **Project**: `ecom_search` - A modular, local e-commerce price comparison engine for UAE markets (Noon, Amazon).
- **Core Philosophy**: "Resilience over Speed." The bot must prioritize anti-detection and stability over raw scraping throughput.

# Tech Stack Enforcement
- **HTTP Client**: ALWAYS use `curl_cffi` (`curl_requests`) first to impersonate browsers (Chrome 124+). Fallback to `cloudscraper` only if `curl_cffi` fails. NEVER use standard `requests` or `urllib` for scraping.
- **HTML Parsing**: Use `BeautifulSoup` with `lxml` parser for speed.
- **UI Framework**: Use `textual` for the TUI. All UI components must be asynchronous (`async def`).
- **Configuration**: Strictly use `.env` for secrets and `src/config/selectors.json` for CSS selectors. **NEVER hardcode CSS selectors** in Python files.

# Architectural Guidelines
## 1. Scraping & Anti-Detection
- **Selector Separation**: If you need to fix a broken scraper, modify `src/config/selectors.json`, NOT the scraper code, unless the logic (e.g., JSON API extraction) has fundamentally changed.
- **Price Extraction**: Always use the `BaseScraper.extract_price` static method. Do not write custom regex for prices unless the format is unique (e.g., "50 AED/month").
- **Rate Limiting**: Respect `Settings.REQUEST_DELAY`. Never bypass delays in loops.
- **Browser Fingerprinting**: When initializing `curl_cffi`, always specify `impersonate="chrome124"` (or newer) and include headers:
  - `Accept-Language: en-US,en;q=0.9`
  - `Referer`: The target site's homepage.

## 2. Textual UI (TUI) Patterns
- **Async Handling**: All UI event handlers (e.g., `on_button_pressed`) must be `async`. Use `await asyncio.to_thread()` for blocking scraping operations to keep the UI responsive.
- **CSS Management**: Keep styles in `src/ui/styles.css`. Do not use inline styles in Python code (`.styles.background = ...`) unless calculating dynamic values (like gradients).
- **Notifications**: Use `self.notify()` for user feedback instead of `print()`. `print()` will break the TUI layout.

## 3. Data & Models
- **Typing**: Use the `Product` dataclass for all data passing. Do not pass raw dictionaries between modules.
- **Safety**: Start all scrapers with a `try/except` block that catches `Exception` and logs it, returning an empty list `[]` rather than crashing the app.

# Code Generation Rules
- **No Magic Numbers**: Move all timeouts, retries, and delay constants to `src/config/settings.py`.
- **Imports**: Group imports: Standard Library -> Third Party -> Local Application.
- **Docstrings**: Include a brief docstring for every method explaining *what* it does, not *how*.

# Testing & Verification
- **Mocking**: When writing tests, mock `curl_requests.get`. NEVER hit live Amazon/Noon URLs during automated tests to avoid IP bans.
- **Dry Run**: Before analyzing large changes, run the code mentally against the `selectors.json` file to ensure key names match `product_card`, `title`, etc.

Why these rules matter for this project

    Anti-Fragility (The "Antigravity"):

        Selector Separation: By forcing the agent to edit selectors.json instead of Python code, you prevent "spaghetti code" where logic and data are mixed. If Amazon changes their layout, the agent only updates the JSON.

        curl_cffi Enforcement: Standard Python requests get blocked immediately by Amazon/Noon. This rule forces the agent to use the browser-impersonating library, keeping your scraper "flying."

    UI Responsiveness:

        Async Rule: The most common bug in textual apps is a frozen UI during heavy tasks. The rule forcing asyncio.to_thread ensures your "Search" button doesn't freeze the app while waiting for a response.

    Governance:

        No print() in UI: A stray print statement destroys the TUI rendering. This rule prevents the agent from adding debug prints that ruin the user experience.

How to Apply

    Antigravity IDE / Cursor: Create a file named .antigravity/rules.md (or .cursorrules if using Cursor) in your project root.

    Paste: Copy the markdown block above into that file.
