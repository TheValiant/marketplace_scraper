# tests/test_logging_config.py

"""Tests for the per-run logging configuration."""

import logging
import unittest

from src.config.logging_config import setup_logging


class TestLoggingConfig(unittest.TestCase):
    """Verify logging setup behaviour."""

    def setUp(self) -> None:
        """Clean up the ecom_search logger before each test."""
        root_logger = logging.getLogger("ecom_search")
        root_logger.handlers.clear()

    def test_setup_creates_log_file(self) -> None:
        """setup_logging returns a path that exists on disk."""
        log_path = setup_logging()
        self.assertTrue(log_path.exists())

    def test_log_file_naming_convention(self) -> None:
        """Log file name matches run_YYYYMMDD_HHMMSS.log format."""
        log_path = setup_logging()
        pattern = r"^run_\d{8}_\d{6}\.log$"
        self.assertRegex(log_path.name, pattern)

    def test_root_logger_has_handlers(self) -> None:
        """After setup, the ecom_search logger has at least 2 handlers."""
        setup_logging()
        root_logger = logging.getLogger("ecom_search")
        self.assertGreaterEqual(len(root_logger.handlers), 2)

    def test_file_handler_level_debug(self) -> None:
        """File handler should be set to DEBUG level."""
        setup_logging()
        root_logger = logging.getLogger("ecom_search")
        file_handlers = [
            h
            for h in root_logger.handlers
            if isinstance(h, logging.FileHandler)
        ]
        self.assertTrue(len(file_handlers) >= 1)
        self.assertEqual(
            file_handlers[0].level, logging.DEBUG
        )

    def test_console_handler_level_warning(self) -> None:
        """Console handler should be set to WARNING level."""
        setup_logging()
        root_logger = logging.getLogger("ecom_search")
        stream_handlers: list[logging.Handler] = [
            h
            for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        self.assertTrue(len(stream_handlers) >= 1)
        self.assertEqual(
            stream_handlers[0].level, logging.WARNING
        )

    def test_repeated_calls_no_duplicate_handlers(self) -> None:
        """Calling setup_logging twice does not duplicate handlers."""
        setup_logging()
        root_logger = logging.getLogger("ecom_search")
        count_before = len(root_logger.handlers)
        setup_logging()
        count_after = len(root_logger.handlers)
        self.assertEqual(count_before, count_after)

    def test_root_logger_level_is_debug(self) -> None:
        """The root project logger is set to DEBUG."""
        setup_logging()
        root_logger = logging.getLogger("ecom_search")
        self.assertEqual(root_logger.level, logging.DEBUG)

    def test_log_file_inside_logs_dir(self) -> None:
        """Log file is created inside the logs/ directory."""
        log_path = setup_logging()
        self.assertEqual(log_path.parent.name, "logs")


if __name__ == "__main__":
    unittest.main()
