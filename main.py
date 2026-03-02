# main.py

"""Entry point for the ecom_search application (TUI or headless CLI)."""

import argparse
import asyncio
import logging
import sys

from src.config.logging_config import setup_logging
from src.config.settings import Settings

logger = logging.getLogger("ecom_search.main")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    valid_ids = ", ".join(s["id"] for s in Settings.AVAILABLE_SOURCES)

    parser = argparse.ArgumentParser(
        prog="ecom_search",
        description="UAE e-commerce price comparison engine.",
        epilog=f"Available sources: {valid_ids}",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query. Omit to launch the interactive TUI.",
    )
    parser.add_argument(
        "-s",
        "--sources",
        default=None,
        help="Comma-separated source IDs (default: all).",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        default=None,
        help="Comma-separated negative keywords to filter out.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "table"],
        default="json",
        dest="output_format",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        dest="output_dir",
        help="Custom output directory (default: results/).",
    )
    parser.add_argument(
        "--import-history",
        action="store_true",
        default=False,
        dest="import_history",
        help="Import existing JSON results into price history DB.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        default=False,
        help="Run a connectivity health check on all sources.",
    )
    return parser


def _run_tui() -> None:
    """Launch the interactive Textual TUI."""
    from src.ui.app import EcomSearchApp

    try:
        app = EcomSearchApp()
        app.run()
    except Exception:
        logger.critical("Fatal error during TUI run", exc_info=True)
        raise
    finally:
        logger.info("ecom_search TUI shutting down")


def _run_cli(args: argparse.Namespace) -> None:
    """Run headless CLI search and exit."""
    from src.cli.runner import cli_search

    exit_code = asyncio.run(
        cli_search(
            query=args.query,
            source_csv=args.sources,
            exclude_csv=args.exclude,
            output_format=args.output_format,
            output_dir=args.output_dir,
        )
    )
    sys.exit(exit_code)


def _run_import_history() -> None:
    """Import legacy JSON results into the price history database."""
    from src.cli.runner import run_import_history

    exit_code = run_import_history()
    sys.exit(exit_code)


def _run_health_check() -> None:
    """Run scraper connectivity health check."""
    from src.cli.runner import run_health_check

    exit_code = asyncio.run(run_health_check())
    sys.exit(exit_code)


def main() -> None:
    """Route to TUI (no args) or headless CLI (query provided)."""
    log_file = setup_logging()
    logger.info("ecom_search starting — log file: %s", log_file)

    parser = _build_parser()
    args = parser.parse_args()

    if args.import_history:
        _run_import_history()
    elif args.health:
        _run_health_check()
    elif args.query is None:
        _run_tui()
    else:
        _run_cli(args)


if __name__ == "__main__":
    main()
