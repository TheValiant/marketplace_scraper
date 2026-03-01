# src/cli/runner.py

"""Headless CLI search runner — reuses the async orchestrator."""

import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.config.settings import Settings
from src.models.product import Product
from src.services.search_orchestrator import SearchOrchestrator
from src.storage.file_manager import FileManager

logger = logging.getLogger("ecom_search.cli")

# Stderr console for status messages so stdout stays clean for JSON
_err = Console(stderr=True)


def resolve_sources(
    source_csv: str | None,
) -> list[dict[str, str]]:
    """Map a comma-separated list of source IDs to their config dicts.

    Returns all sources when *source_csv* is ``None``.
    Raises ``SystemExit`` on unknown IDs.
    """
    available = {
        s["id"]: s for s in Settings.AVAILABLE_SOURCES
    }
    if source_csv is None:
        return Settings.AVAILABLE_SOURCES

    requested = [
        s.strip() for s in source_csv.split(",") if s.strip()
    ]
    unknown = [r for r in requested if r not in available]
    if unknown:
        valid = ", ".join(sorted(available))
        _err.print(
            f"[red]Unknown source(s): {', '.join(unknown)}[/red]"
        )
        _err.print(f"[dim]Available: {valid}[/dim]")
        raise SystemExit(1)

    return [available[r] for r in requested]


def _products_to_dicts(products: list[Product]) -> list[dict[str, object]]:
    """Serialise a product list to plain dicts for JSON output."""
    return [
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


def _print_table(products: list[Product]) -> None:
    """Render a Rich table of products to stdout."""
    sorted_products = sorted(
        products,
        key=lambda p: p.price if p.price > 0 else float("inf"),
    )
    table = Table(
        title="Search Results",
        show_lines=True,
        title_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", max_width=60)
    table.add_column("Price", justify="right", style="green")
    table.add_column("Rating", justify="center")
    table.add_column("Source", style="magenta")
    table.add_column("URL", overflow="fold", style="dim")

    for idx, p in enumerate(sorted_products, 1):
        price_str = (
            f"{p.currency} {p.price:,.2f}"
            if p.price > 0
            else "N/A"
        )
        table.add_row(
            str(idx),
            p.title[:60],
            price_str,
            p.rating or "—",
            p.source,
            p.url,
        )

    Console().print(table)


def _save_results(
    file_manager: FileManager,
    query: str,
    products: list[Product],
) -> None:
    """Auto-save combined + per-source JSON (mirrors TUI behaviour)."""
    try:
        path = file_manager.save_results(query, products, "combined")
        _err.print(f"[dim]Saved combined → {path}[/dim]")
        sources = {p.source for p in products}
        for source in sorted(sources):
            source_products = [
                p for p in products if p.source == source
            ]
            sp = file_manager.save_results(query, source_products, source)
            _err.print(f"[dim]Saved {source} → {sp}[/dim]")
    except Exception as exc:
        logger.error("Save failed: %s", exc, exc_info=True)
        _err.print(f"[red]Save failed: {exc}[/red]")


async def cli_search(
    query: str,
    source_csv: str | None,
    exclude_csv: str | None,
    output_format: str,
    output_dir: str | None,
) -> int:
    """Run a headless search and return an exit code (0=ok, 1=fail)."""
    sources = resolve_sources(source_csv)
    negative_keywords = (
        [k.strip() for k in exclude_csv.split(",") if k.strip()]
        if exclude_csv
        else []
    )

    # Optional custom output directory
    if output_dir is not None:
        Settings.RESULTS_DIR = Path(output_dir)

    file_manager = FileManager()
    orchestrator = SearchOrchestrator()

    source_labels = ", ".join(s["label"] for s in sources)
    _err.print(
        f"[bold]Searching:[/bold] {query}  "
        f"[dim]sources={source_labels}[/dim]"
    )
    if negative_keywords:
        _err.print(
            f"[dim]Excluding: {', '.join(negative_keywords)}[/dim]"
        )

    result = await orchestrator.multi_search(
        query, sources, negative_keywords
    )

    for error_msg in result.errors:
        _err.print(f"[red]Error: {error_msg}[/red]")

    if not result.products:
        _err.print("[yellow]No products found.[/yellow]")
        return 1

    # Summary to stderr
    parts: list[str] = []
    if result.excluded_count:
        parts.append(f"{result.excluded_count} filtered")
    if result.deduplicated_count:
        parts.append(f"{result.deduplicated_count} deduped")
    if result.invalid_count:
        parts.append(f"{result.invalid_count} invalid")
    detail = f" ({', '.join(parts)})" if parts else ""
    _err.print(
        f"[green]✓ {len(result.products)} products"
        f" of {result.total_before_filter}{detail}[/green]"
    )

    # Save to disk
    _save_results(file_manager, query, result.products)

    # Output to stdout
    if output_format == "table":
        _print_table(result.products)
    else:
        json.dump(
            _products_to_dicts(result.products),
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")

    return 0
