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

# Post-Edit Verification
- **Mandatory Linter Gate**: After **every** code edit, the agent **MUST** run `./pylance.sh` from the project root. This script runs Flake8 (style, max-complexity=10, 88-char lines) and Pyright in **strict** mode.
- **Zero Tolerance**: All Flake8 and Pyright errors reported by `pylance.sh` must be resolved before the edit is considered complete. If the script fails, fix every flagged issue and re-run until the output shows `✓ All checks passed!`.
- **No Bypass**: Never skip, silence, or weaken the checks (e.g., do not add `# type: ignore`, `# noqa`, or lower `typeCheckingMode`). If a check is wrong, fix the code — not the checker.

# Testing & Verification
- **Mocking**: When writing tests, mock `curl_requests.Session`. NEVER hit live Amazon/Noon URLs during automated tests to avoid IP bans.
- **Dry Run**: Before analyzing large changes, run the code mentally against the `selectors.json` file to ensure key names match `product_card`, `title`, etc.

coding_standards:
  metadata:
    name: "Python Clean Coding Standards for AI Agents"
    version: "1.0.0"
    source: "internal"
    applies_to: ["python"]
    last_updated: "2026-02-14"

  # Each rule:
  # - id: stable identifier
  # - section: main topic
  # - title: short description
  # - description: what the rule means
  # - rationale: why it matters
  # - severity: ["info", "minor", "major", "critical"]
  # - auto_check: whether a static tool can likely check it
  # - examples: optional code examples

  rules:

    # 1. General Principles
    - id: GEN-001
      section: General
      title: Prefer readability over cleverness
      description: "Choose clear, straightforward implementations instead of clever or overly compact code."
      rationale: "Readable code is easier to review, debug, and extend, especially for agents and multiple collaborators."
      severity: major
      auto_check: false

    - id: GEN-002
      section: General
      title: Follow PEP 8 and PEP 257 by default
      description: "Adhere to Python's PEP 8 style guide and PEP 257 docstring conventions unless explicitly overridden."
      rationale: "Consistent, widely recognized conventions reduce friction and tooling complexity."
      severity: major
      auto_check: true

    - id: GEN-003
      section: General
      title: Single responsibility per function or module
      description: "Functions and modules should each focus on one main responsibility."
      rationale: "Single-responsibility code is easier to test, reuse, and maintain."
      severity: major
      auto_check: partially

    - id: GEN-004
      section: General
      title: Fail fast in development, gracefully in production
      description: "In internal code, raise errors early; in user-facing layers, handle errors with clear and safe responses."
      rationale: "Fast failures help detect issues; graceful failures protect user experience and systems."
      severity: major
      auto_check: false

    # 2. Project Structure
    - id: STR-001
      section: ProjectStructure
      title: Organize packages by domain or feature
      description: "Group modules by domain or feature (e.g., data, models, agents, services), not exclusively by technical layer."
      rationale: "Domain-centered structure reflects how the system is understood and extended."
      severity: minor
      auto_check: false

    - id: STR-002
      section: ProjectStructure
      title: Keep entry points thin
      description: "main.py, CLI handlers, and API endpoints should orchestrate calls, not contain business logic."
      rationale: "Separating orchestration from logic improves testability and reuse."
      severity: major
      auto_check: partially

    - id: STR-003
      section: ProjectStructure
      title: Separate core logic from I/O and configuration
      description: "Isolate business logic from file/network/database I/O and from configuration sources."
      rationale: "Separation simplifies testing and allows reuse in different environments."
      severity: major
      auto_check: partially

    # 3. Naming Conventions
    - id: NAM-001
      section: Naming
      title: Use snake_case for functions and variables
      description: "Name functions, methods, and variables using snake_case."
      rationale: "Matches Python conventions and improves readability."
      severity: major
      auto_check: true

    - id: NAM-002
      section: Naming
      title: Use PascalCase for classes and exceptions
      description: "Name classes and exception types using PascalCase."
      rationale: "Aligns with standard Python style and makes types recognizable."
      severity: major
      auto_check: true

    - id: NAM-003
      section: Naming
      title: Use CAPS_SNAKE_CASE for constants
      description: "Name module-level constants in uppercase snake_case."
      rationale: "Signals immutability or configuration-like values."
      severity: minor
      auto_check: partially

    - id: NAM-004
      section: Naming
      title: Use descriptive names that reflect meaning
      description: "Variables and functions should be named by what they represent, not by vague terms or implementation details."
      rationale: "Good names reduce the need for comments and make code self-documenting."
      severity: major
      auto_check: partially

    - id: NAM-005
      section: Naming
      title: Use predicate-style names for booleans
      description: "Boolean variables and functions should read as predicates (e.g., is_valid, has_converged, use_gpu)."
      rationale: "Predicate names make control flow more understandable."
      severity: minor
      auto_check: partially

    - id: NAM-006
      section: Naming
      title: Use plural names for collections
      description: "Use plural names for lists, sets, and other collections (e.g., users, tool_responses)."
      rationale: "Signals that a variable represents multiple items."
      severity: minor
      auto_check: partially

    # 4. Code Formatting
    - id: FMT-001
      section: Formatting
      title: Use 4-space indentation, no tabs
      description: "Indent using 4 spaces per level and do not use tab characters."
      rationale: "Consistent indentation improves readability and avoids editor differences."
      severity: major
      auto_check: true

    - id: FMT-002
      section: Formatting
      title: Enforce maximum line length
      description: "Limit lines to at most 100 characters (or 88 if configured) and wrap longer code."
      rationale: "Shorter lines fit typical editors and review tools."
      severity: minor
      auto_check: true

    - id: FMT-003
      section: Formatting
      title: Use automatic formatter (e.g., black)
      description: "Format code with an automatic tool like black to enforce consistent style."
      rationale: "Automated formatting removes subjective style debates and speeds reviews."
      severity: major
      auto_check: true

    - id: FMT-004
      section: Formatting
      title: Use appropriate blank lines
      description: "Use two blank lines between top-level definitions and one blank line between methods in a class."
      rationale: "Visual separation improves code scanning and structure recognition."
      severity: minor
      auto_check: true

    - id: FMT-005
      section: Formatting
      title: Use spaces around operators and after commas
      description: "Write expressions with spaces around binary operators and after commas (e.g., a = b + c)."
      rationale: "Consistent spacing improves readability."
      severity: minor
      auto_check: true

    - id: FMT-006
      section: Formatting
      title: Avoid extraneous whitespace
      description: "Avoid trailing spaces and unnecessary spaces inside brackets or before newlines."
      rationale: "Reduces noise in diffs and keeps code clean."
      severity: minor
      auto_check: true

    # 5. Imports
    - id: IMP-001
      section: Imports
      title: Group imports by origin
      description: "Group imports as standard library, third-party, and local imports with blank lines between groups."
      rationale: "Import grouping clarifies dependencies and improves navigation."
      severity: minor
      auto_check: true

    - id: IMP-002
      section: Imports
      title: Avoid wildcard imports
      description: "Do not use 'from module import *'; import names explicitly or use module-qualified access."
      rationale: "Wildcard imports obscure dependencies and risk name collisions."
      severity: major
      auto_check: true

    - id: IMP-003
      section: Imports
      title: Prefer imports at top of file
      description: "Place imports at the top of the module unless late import is explicitly justified."
      rationale: "Centralized imports clarify dependencies and avoid surprises."
      severity: minor
      auto_check: partially

    # 6. Functions and Methods
    - id: FUN-001
      section: Functions
      title: Keep functions focused and small
      description: "Functions should generally do one thing and be limited to a reasonable length (roughly under 50 lines)."
      rationale: "Small, focused functions are easier to test and reason about."
      severity: major
      auto_check: partially

    - id: FUN-002
      section: Functions
      title: Limit number of parameters
      description: "If functions have more than 4–5 parameters, consider grouping them into a configuration object or splitting the function."
      rationale: "Too many parameters indicate unclear responsibilities and make calls error-prone."
      severity: minor
      auto_check: partially

    - id: FUN-003
      section: Functions
      title: Make side effects explicit
      description: "Functions that modify external state should be clearly named and documented to signal their effects."
      rationale: "Clear indication of side effects helps prevent subtle bugs."
      severity: major
      auto_check: partially

    # 7. Classes and Object Design
    - id: OOP-001
      section: Classes
      title: Use classes for cohesive state and behavior
      description: "Introduce classes when state and behavior belong together and multiple instances are needed."
      rationale: "Object grouping can express domain concepts and reduce duplication."
      severity: minor
      auto_check: false

    - id: OOP-002
      section: Classes
      title: Prefer composition over inheritance
      description: "Favor 'has-a' relationships and composed objects instead of deep inheritance hierarchies."
      rationale: "Composition reduces tight coupling and makes evolution easier."
      severity: major
      auto_check: partially

    - id: OOP-003
      section: Classes
      title: Use dataclasses for simple data containers
      description: "Use @dataclass for simple structured data types, and consider frozen dataclasses for configuration objects."
      rationale: "Dataclasses reduce boilerplate and clarify intent."
      severity: minor
      auto_check: partially

    # 8. Type Hints and Static Checking
    - id: TYP-001
      section: Types
      title: Use type hints consistently
      description: "Apply type annotations to function parameters, return values, and key variables where practical."
      rationale: "Type hints support static analysis, better tooling, and self-documentation."
      severity: major
      auto_check: true

    - id: TYP-002
      section: Types
      title: Use standard typing primitives
      description: "Use types from the typing module (e.g., List[str], Dict[str, Any], Optional[int])."
      rationale: "Consistent typing patterns improve static analysis and readability."
      severity: minor
      auto_check: true

    - id: TYP-003
      section: Types
      title: Minimize use of Any
      description: "Avoid unnecessary Any annotations; prefer more specific types when feasible."
      rationale: "Excessive Any weakens static checks and hides potential bugs."
      severity: major
      auto_check: partially

    # 9. Docstrings and Comments
    - id: DOC-001
      section: Documentation
      title: Docstring for public modules, classes, and functions
      description: "Provide docstrings for all public-facing modules, classes, and functions, describing purpose, arguments, returns, and side effects."
      rationale: "Docstrings communicate intended behavior and allow better tooling support."
      severity: major
      auto_check: partially

    - id: DOC-002
      section: Documentation
      title: Explain why, not what, in comments
      description: "Use comments to explain intent, reasoning, and domain context rather than restating obvious code."
      rationale: "Intent-focused comments remain valuable even as implementations change."
      severity: minor
      auto_check: false

    - id: DOC-003
      section: Documentation
      title: Keep comments and docs up-to-date
      description: "Update or remove stale comments and docstrings that no longer match the code."
      rationale: "Outdated documentation misleads readers and tools."
      severity: major
      auto_check: false

    # 10. Error Handling and Exceptions
    - id: ERR-001
      section: ErrorHandling
      title: Prefer exceptions over silent failures
      description: "Raise meaningful exceptions instead of silently returning None or incorrect values."
      rationale: "Explicit failures are easier to debug and safer in production."
      severity: critical
      auto_check: partially

    - id: ERR-002
      section: ErrorHandling
      title: Use specific exception types
      description: "Use built-in or custom exception classes that precisely describe the error condition."
      rationale: "Specific exceptions enable targeted handling and recovery."
      severity: major
      auto_check: partially

    - id: ERR-003
      section: ErrorHandling
      title: Avoid broad except Exception without handling
      description: "Do not catch Exception broadly unless you log with context and either re-raise or handle meaningfully."
      rationale: "Overbroad catches hide issues and complicate debugging."
      severity: critical
      auto_check: true

    # 11. Logging and Monitoring
    - id: LOG-001
      section: Logging
      title: Use logging module instead of print
      description: "Use the logging module for application logs; avoid print() for non-debug logging."
      rationale: "Logging allows levels, handlers, and structured output."
      severity: major
      auto_check: partially

    - id: LOG-002
      section: Logging
      title: Use module-level loggers
      description: "Create a logger per module (e.g., logger = logging.getLogger(__name__))."
      rationale: "Module-level loggers aid filtering and configuration."
      severity: minor
      auto_check: partially

    - id: LOG-003
      section: Logging
      title: Log key external calls and decisions
      description: "Log external service calls, major agent decisions, and failures with sufficient context but without secrets."
      rationale: "Logs help debug behavior and trace issues in production."
      severity: major
      auto_check: partially

    # 12. Configuration and Secrets
    - id: CFG-001
      section: Configuration
      title: Keep secrets out of code
      description: "Do not hard-code API keys, passwords, or other secrets in source files."
      rationale: "Hard-coded secrets are a major security risk and difficult to rotate."
      severity: critical
      auto_check: partially

    - id: CFG-002
      section: Configuration
      title: Use config files and environment variables
      description: "Load configuration from environment variables or config files instead of embedding it in code."
      rationale: "Externalized configuration enables environment-specific behavior without code changes."
      severity: major
      auto_check: partially

    # 13. Dependency Management
    - id: DEP-001
      section: Dependencies
      title: Pin dependencies sensibly
      description: "Specify dependency versions or ranges in requirements.txt or pyproject.toml."
      rationale: "Version control avoids unexpected breaking changes."
      severity: major
      auto_check: partially

    - id: DEP-002
      section: Dependencies
      title: Avoid unnecessary dependencies
      description: "Prefer standard library and small, focused libraries over large or redundant dependencies."
      rationale: "Reducing dependencies decreases attack surface and maintenance burden."
      severity: minor
      auto_check: false

    # 14. Testing and Quality
    - id: TST-001
      section: Testing
      title: Write unit tests for core logic
      description: "Cover core logic, utilities, and critical paths with unit tests."
      rationale: "Unit tests catch regressions and document intended behavior."
      severity: critical
      auto_check: partially

    - id: TST-002
      section: Testing
      title: Use pytest or equivalent
      description: "Use pytest (or a similar framework) and standard conventions (e.g., test_*.py)."
      rationale: "Consistent testing frameworks simplify setup and CI integration."
      severity: major
      auto_check: partially

    - id: TST-003
      section: Testing
      title: Ensure tests are deterministic
      description: "Control randomness in tests (e.g., seeds, fixed data) to avoid flaky behavior."
      rationale: "Deterministic tests provide reliable feedback."
      severity: major
      auto_check: partially

    # 15. Performance and Efficiency
    - id: PERF-001
      section: Performance
      title: Optimize only after measuring
      description: "Profile code before making performance optimizations."
      rationale: "Data-driven optimization prevents wasted effort and misdirected changes."
      severity: minor
      auto_check: false

    - id: PERF-002
      section: Performance
      title: Avoid unnecessary large data copies
      description: "Avoid copying large data structures when views or references suffice."
      rationale: "Reduces memory usage and execution time."
      severity: major
      auto_check: partially

    # 16. Concurrency and Async
    - id: CONC-001
      section: Concurrency
      title: Use a consistent concurrency model per component
      description: "Within a component, use a single main concurrency approach (e.g., asyncio for I/O-bound tasks)."
      rationale: "Mixed concurrency models increase complexity and risk subtle bugs."
      severity: major
      auto_check: false

    - id: CONC-002
      section: Concurrency
      title: Avoid blocking calls in async code
      description: "Do not call blocking functions inside async code without appropriate offloading."
      rationale: "Blocking in async contexts harms throughput and responsiveness."
      severity: critical
      auto_check: partially

    # 17. AI-/Agent-Specific
    - id: AI-001
      section: Agents
      title: Keep prompt construction explicit and readable
      description: "Structure prompts with clear templates and explicit separation of system, user, and tool messages."
      rationale: "Explicit prompts are easier to debug and adapt."
      severity: major
      auto_check: partially

    - id: AI-002
      section: Agents
      title: Centralize model access
      description: "Use a shared model client or service instead of scattering direct API calls across the codebase."
      rationale: "Centralization simplifies monitoring, changes, and security controls."
      severity: major
      auto_check: partially

    - id: AI-003
      section: Agents
      title: Make agent decisions transparent
      description: "Where permitted, log or store key agent decisions and reasoning steps in a structured format."
      rationale: "Transparency aids debugging, evaluation, and alignment."
      severity: major
      auto_check: partially

    - id: AI-004
      section: Agents
      title: Handle tool errors robustly
      description: "Validate tool inputs, implement retries with backoff, and define safe fallbacks when tools fail."
      rationale: "Robust error handling prevents cascading failures in agent workflows."
      severity: critical
      auto_check: partially

    - id: AI-005
      section: Agents
      title: Design for idempotent and retriable operations
      description: "Structure actions so they can be retried safely if partially completed."
      rationale: "Idempotency improves reliability in distributed and agent-based systems."
      severity: major
      auto_check: partially

    - id: AI-006
      section: Agents
      title: Control randomness and sampling parameters
      description: "Document and control model sampling parameters (e.g., temperature, top_p) and use fixed seeds where determinism is required."
      rationale: "Controlled randomness is essential for reproducibility and evaluation."
      severity: major
      auto_check: partially

    # 18. Data Handling, Privacy, and Safety
    - id: DATA-001
      section: Data
      title: Minimize logging of sensitive data
      description: "Avoid logging raw user inputs or sensitive payloads; redact or hash where necessary."
      rationale: "Protects user privacy and reduces compliance risk."
      severity: critical
      auto_check: partially

    - id: DATA-002
      section: Data
      title: Validate external inputs
      description: "Sanitize and validate all external inputs (text, filenames, URLs) before use."
      rationale: "Input validation mitigates injection and abuse risks."
      severity: critical
      auto_check: partially

    - id: DATA-003
      section: Data
      title: Respect data boundaries and usage
      description: "Separate training/evaluation data from live user data and clearly mark datasets and allowed uses."
      rationale: "Prevents misuse of data and clarifies compliance boundaries."
      severity: major
      auto_check: partially

    # 19. Documentation and Examples
    - id: DOC-004
      section: Documentation
      title: Provide README for major components
      description: "Each major package or service should have a README describing purpose, usage, and how to run/tests."
      rationale: "Introductory docs help new contributors and tools understand the system."
      severity: minor
      auto_check: partially

    - id: DOC-005
      section: Documentation
      title: Provide minimal runnable examples
      description: "Document minimal code examples for core flows (e.g., running an agent, adding a tool)."
      rationale: "Examples reduce onboarding time and ambiguity."
      severity: minor
      auto_check: false

    # 20. Version Control Practices
    - id: VCS-001
      section: VersionControl
      title: Make small, focused commits
      description: "Group related changes into small, coherent commits instead of large, mixed ones."
      rationale: "Focused commits simplify review and rollback."
      severity: minor
      auto_check: false

    - id: VCS-002
      section: VersionControl
      title: Use clear commit messages
      description: "Write imperative, descriptive commit messages (e.g., 'Add agent routing for X')."
      rationale: "Good commit messages aid history comprehension and debugging."
      severity: minor
      auto_check: false

    - id: VCS-003
      section: VersionControl
      title: Avoid committing generated artifacts and secrets
      description: "Do not commit build artifacts, large logs, model binaries, or secrets unless explicitly required and managed."
      rationale: "Reduces repository bloat and security risks."
      severity: critical
      auto_check: partially

add commit and push with proper description after every milestone