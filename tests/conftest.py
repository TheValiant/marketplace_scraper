# tests/conftest.py

"""Shared pytest fixtures for all scraper tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[None, None, None]:
    """Patch time.sleep globally so retry loops run instantly."""
    with patch("time.sleep"):
        yield
