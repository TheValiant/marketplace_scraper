# main.py

"""Entry point for the ecom_search TUI application."""

import logging

from src.config.logging_config import setup_logging
from src.ui.app import EcomSearchApp

logger = logging.getLogger("ecom_search.main")


def main():
    """Launch the ecom_search TUI application."""
    log_file = setup_logging()
    logger.info("ecom_search starting — log file: %s", log_file)

    try:
        app = EcomSearchApp()
        app.run()
    except Exception:
        logger.critical("Fatal error during application run", exc_info=True)
        raise
    finally:
        logger.info("ecom_search shutting down")


if __name__ == "__main__":
    main()
