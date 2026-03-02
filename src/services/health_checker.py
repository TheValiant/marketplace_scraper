# src/services/health_checker.py

"""Scraper connectivity health checker."""

import asyncio
import importlib
import logging
import time
from dataclasses import dataclass

from src.config.settings import Settings

logger = logging.getLogger("ecom_search.health")

_HEALTH_TIMEOUT = 10  # seconds per source


@dataclass
class HealthResult:
    """Result of a single source health check."""

    source_id: str
    status: str  # "ok", "slow", "down"
    latency_ms: float
    message: str


def probe_source(source: dict[str, str]) -> HealthResult:
    """Probe a single scraper source for connectivity."""
    source_id = source["id"]
    dotted_path = source["scraper"]

    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        scraper_cls = getattr(module, class_name)
        scraper = scraper_cls()
    except Exception as exc:
        return HealthResult(
            source_id=source_id,
            status="down",
            latency_ms=0.0,
            message=f"Failed to load scraper: {exc}",
        )

    start = time.monotonic()
    try:
        homepage = scraper._get_homepage()
        headers = {
            **scraper.settings.DEFAULT_HEADERS,
            "Referer": homepage,
        }
        resp = scraper.session.get(
            homepage,
            headers=headers,
            timeout=_HEALTH_TIMEOUT,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        if resp.status_code != 200:
            return HealthResult(
                source_id=source_id,
                status="down",
                latency_ms=elapsed_ms,
                message=f"HTTP {resp.status_code}",
            )

        if elapsed_ms > 5000:
            return HealthResult(
                source_id=source_id,
                status="slow",
                latency_ms=elapsed_ms,
                message="High latency",
            )

        return HealthResult(
            source_id=source_id,
            status="ok",
            latency_ms=elapsed_ms,
            message="",
        )

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return HealthResult(
            source_id=source_id,
            status="down",
            latency_ms=elapsed_ms,
            message=str(exc)[:80],
        )


class HealthChecker:
    """Runs concurrent health probes against all sources."""

    def __init__(self) -> None:
        self.sources = Settings.AVAILABLE_SOURCES

    async def check_all(self) -> list[HealthResult]:
        """Probe every registered source concurrently."""
        tasks = [
            asyncio.to_thread(probe_source, src)
            for src in self.sources
        ]
        results: list[HealthResult] = list(
            await asyncio.gather(*tasks)
        )
        for r in results:
            logger.info(
                "Health check %s: %s (%.0fms) %s",
                r.source_id,
                r.status,
                r.latency_ms,
                r.message,
            )
        return results
