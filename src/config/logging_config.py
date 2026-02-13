# src/config/logging_config.py

"""Per-run timestamped logging configuration for ecom_search.

Each application launch creates a dedicated log file inside ``logs/``,
named with the launch timestamp (e.g. ``logs/run_20260214_153045.log``).
All ``ecom_search.*`` loggers route through this file handler so that
every module's output lands in the same per-run log.

Error records include full tracebacks, thread names, and module paths
to make post-mortem debugging straightforward.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from src.config.settings import Settings

# Reusable format strings --------------------------------------------------

_DETAILED_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(funcName)s:%(lineno)d | "
    "%(message)s"
)

_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"

_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> Path:
    """Initialise the root ``ecom_search`` logger for the current run.

    Returns:
        The :class:`~pathlib.Path` to the log file created for this run.
    """
    logs_dir: Path = Settings.LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"run_{timestamp}.log"

    # --- Root project logger -----------------------------------------------
    root_logger = logging.getLogger("ecom_search")
    root_logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers on repeated calls (e.g. tests)
    if root_logger.handlers:
        return log_file

    # --- File handler (DEBUG+) – captures everything -----------------------
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(_DETAILED_FORMAT, datefmt=_DATE_FORMAT)
    )

    # --- Console handler (WARNING+) – only important messages --------------
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(
        logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT)
    )

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    root_logger.info(
        "Logging initialised — log file: %s", log_file
    )

    return log_file
