#!/usr/bin/env python3
"""Live search matrix test runner for all scrapers.

Exercises each scraper with a set of queries and validates:
- No crashes (graceful empty returns)
- Product data quality (titles, prices, URLs, sources)
- Special character handling
- Edge case resilience

Usage:
    python -m tests.run_search_matrix [--phase N]

Phases:
    1 = Edge cases (nonexistent, single char, special chars)
    2 = Health supplements (collagen peptides, vitamin D3)
    3 = Personal care (sunscreen SPF 50, shampoo)
    4 = Electronics (wireless headphones, USB-C charger)
    5 = Stress + CAPTCHA (collagen broad, krill oil)
    (no flag = run all phases sequentially)
"""

import argparse
import importlib
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.logging_config import setup_logging  # noqa: E402
from src.config.settings import Settings  # noqa: E402
from src.models.product import Product  # noqa: E402
from src.scrapers.base_scraper import BaseScraper  # noqa: E402

logger = logging.getLogger("ecom_search.test_matrix")

# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------

SCRAPER_REGISTRY: list[dict[str, str]] = Settings.AVAILABLE_SOURCES

# Phase -> list of (test_id, query, expected_behaviour_notes, scraper_ids|None)
# scraper_ids=None means all scrapers
PHASES: dict[int, list[tuple[str, str, str, list[str] | None]]] = {
    1: [
        ("T8", "xyznonexistentproduct123", "all return empty []", None),
        ("T9", "a", "single char; no infinite loop", None),
        ("T10", "Doctor's Best Glucosamine",
         "special chars (apostrophe); URL encoding", None),
    ],
    2: [
        ("T1", "collagen peptides",
         "health; all scrapers return results", None),
        ("T3", "vitamin D3",
         "common supplement; universal coverage", None),
    ],
    3: [
        ("T6", "sunscreen SPF 50",
         "pharmacy sites strong; Amazon/Noon moderate", None),
        ("T7", "shampoo",
         "broad query; all sources should return", None),
    ],
    4: [
        ("T4", "wireless headphones",
         "Amazon/Noon strong; pharmacy sites sparse", None),
        ("T5", "USB-C charger",
         "Amazon/Noon strong; others empty", None),
    ],
    5: [
        ("T11", "collagen",
         "pagination stress; high volume",
         ["noon", "amazon"]),
        ("T2", "krill oil",
         "iHerb CAPTCHA risk; run last", None),
    ],
}


@dataclass
class TestResult:
    """Outcome of a single scraper+query test."""

    test_id: str
    query: str
    scraper_id: str
    product_count: int
    sample_title: str
    sample_price: float
    sample_url: str
    empty_titles: int
    zero_prices: int
    missing_urls: int
    missing_source: int
    elapsed_secs: float
    error: str


def _load_scraper(dotted_path: str) -> BaseScraper:
    """Dynamically import and instantiate a scraper class."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: Any = getattr(module, class_name)
    instance: BaseScraper = cls()
    return instance


def _validate_products(
    products: list[Product], scraper_id: str,
) -> dict[str, int]:
    """Check data quality of returned products."""
    empty_titles = sum(1 for p in products if not p.title.strip())
    zero_prices = sum(1 for p in products if p.price <= 0)
    missing_urls = sum(1 for p in products if not p.url)
    missing_source = sum(1 for p in products if not p.source)
    return {
        "empty_titles": empty_titles,
        "zero_prices": zero_prices,
        "missing_urls": missing_urls,
        "missing_source": missing_source,
    }


def run_single_test(
    test_id: str,
    query: str,
    scraper_id: str,
    scraper_path: str,
) -> TestResult:
    """Run a single scraper against a query and return results."""
    logger.info(
        "=== %s | %-10s | query='%s' ===", test_id, scraper_id, query,
    )

    error_msg = ""
    products: list[Product] = []
    start = time.monotonic()

    try:
        scraper = _load_scraper(scraper_path)
        products = scraper.search(query)
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error(
            "%s | %s CRASHED: %s", test_id, scraper_id, error_msg,
            exc_info=True,
        )

    elapsed = time.monotonic() - start

    quality = _validate_products(products, scraper_id)

    sample_title = products[0].title[:60] if products else ""
    sample_price = products[0].price if products else 0.0
    sample_url = products[0].url if products else ""

    result = TestResult(
        test_id=test_id,
        query=query,
        scraper_id=scraper_id,
        product_count=len(products),
        sample_title=sample_title,
        sample_price=sample_price,
        sample_url=sample_url,
        empty_titles=quality["empty_titles"],
        zero_prices=quality["zero_prices"],
        missing_urls=quality["missing_urls"],
        missing_source=quality["missing_source"],
        elapsed_secs=round(elapsed, 2),
        error=error_msg,
    )

    status = "PASS" if not error_msg else "FAIL"
    logger.info(
        "%s | %s | %s | %d products | %.1fs | titles_empty=%d "
        "prices_zero=%d urls_missing=%d",
        test_id, scraper_id, status, len(products), elapsed,
        quality["empty_titles"], quality["zero_prices"],
        quality["missing_urls"],
    )

    return result


def run_phase(phase_num: int) -> list[TestResult]:
    """Execute all tests in a phase and return results."""
    tests = PHASES.get(phase_num, [])
    if not tests:
        logger.warning("Phase %d has no tests defined", phase_num)
        return []

    results: list[TestResult] = []
    scraper_map = {s["id"]: s["scraper"] for s in SCRAPER_REGISTRY}

    for test_id, query, _notes, scraper_ids in tests:
        target_ids = scraper_ids or list(scraper_map.keys())
        for sid in target_ids:
            spath = scraper_map[sid]
            result = run_single_test(test_id, query, sid, spath)
            results.append(result)

    return results


def print_phase_summary(
    phase_num: int, results: list[TestResult],
) -> None:
    """Print a compact summary table for a phase."""
    print(f"\n{'=' * 80}")
    print(f"  PHASE {phase_num} SUMMARY")
    print(f"{'=' * 80}")
    print(
        f"{'Test':<5} {'Scraper':<14} {'Count':>6} "
        f"{'Time':>6} {'Empty':>6} {'$0':>4} "
        f"{'NoURL':>6} {'Status':<6} {'Error'}"
    )
    print("-" * 80)

    for r in results:
        has_quality_issue = (
            r.empty_titles > 0
            or r.missing_urls > 0
            or r.missing_source > 0
        )
        status = "FAIL" if r.error else ("WARN" if has_quality_issue else "OK")
        print(
            f"{r.test_id:<5} {r.scraper_id:<14} {r.product_count:>6} "
            f"{r.elapsed_secs:>5.1f}s {r.empty_titles:>6} "
            f"{r.zero_prices:>4} {r.missing_urls:>6} "
            f"{status:<6} {r.error[:40]}"
        )

    total = len(results)
    passed = sum(1 for r in results if not r.error)
    warned = sum(
        1 for r in results
        if not r.error and (
            r.empty_titles > 0 or r.missing_urls > 0 or r.missing_source > 0
        )
    )
    failed = sum(1 for r in results if r.error)
    print("-" * 80)
    print(
        f"  Total: {total} | OK: {passed - warned} | "
        f"WARN: {warned} | FAIL: {failed}"
    )


def save_results(
    all_results: list[TestResult], output_path: Path,
) -> None:
    """Save all test results to a JSON report."""
    data: list[dict[str, Any]] = []
    for r in all_results:
        data.append({
            "test_id": r.test_id,
            "query": r.query,
            "scraper_id": r.scraper_id,
            "product_count": r.product_count,
            "sample_title": r.sample_title,
            "sample_price": r.sample_price,
            "sample_url": r.sample_url,
            "empty_titles": r.empty_titles,
            "zero_prices": r.zero_prices,
            "missing_urls": r.missing_urls,
            "missing_source": r.missing_source,
            "elapsed_secs": r.elapsed_secs,
            "error": r.error,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Test results saved to %s", output_path)
    print(f"\nResults saved to {output_path}")


def main() -> None:
    """Parse args and run the test matrix."""
    parser = argparse.ArgumentParser(
        description="Live search matrix test runner",
    )
    parser.add_argument(
        "--phase", type=int, default=0,
        help="Run a specific phase (1-5). 0 = all phases.",
    )
    args = parser.parse_args()

    log_file = setup_logging()
    print(f"Log file: {log_file}")

    all_results: list[TestResult] = []

    phases_to_run = (
        [args.phase] if args.phase > 0
        else list(PHASES.keys())
    )

    for phase_num in phases_to_run:
        print(f"\n>>> Starting Phase {phase_num} ...")
        results = run_phase(phase_num)
        all_results.extend(results)
        print_phase_summary(phase_num, results)

    # Final report
    report_path = Settings.RESULTS_DIR / "test_matrix_report.json"
    save_results(all_results, report_path)

    # Grand summary
    total = len(all_results)
    failed = sum(1 for r in all_results if r.error)
    print(f"\n{'=' * 80}")
    print(f"  GRAND TOTAL: {total} tests | {total - failed} passed | {failed} failed")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
