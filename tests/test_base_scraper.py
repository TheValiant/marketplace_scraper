# tests/test_base_scraper.py

"""Tests for BaseScraper resilience features."""

import time
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.models.product import Product
from src.scrapers.base_scraper import BaseScraper


class _StubScraper(BaseScraper):
    """Concrete scraper exposing protected members for testing."""

    def _get_homepage(self) -> str:
        return "https://example.com"

    def search(self, query: str) -> list[Product]:
        return []

    # --- Public accessors for protected state ---

    @property
    def circuit_open(self) -> bool:
        """Expose circuit breaker flag."""
        return self._circuit_open

    @circuit_open.setter
    def circuit_open(self, value: bool) -> None:
        self._circuit_open = value

    @property
    def circuit_opened_at(self) -> float:
        """Expose circuit breaker timestamp."""
        return self._circuit_opened_at

    @circuit_opened_at.setter
    def circuit_opened_at(self, value: float) -> None:
        self._circuit_opened_at = value

    @property
    def consecutive_failures(self) -> int:
        """Expose failure counter."""
        return self._consecutive_failures

    @consecutive_failures.setter
    def consecutive_failures(self, value: int) -> None:
        self._consecutive_failures = value

    @property
    def request_timeout(self) -> int:
        """Expose request timeout."""
        return self._request_timeout

    @request_timeout.setter
    def request_timeout(self, value: int) -> None:
        self._request_timeout = value

    @property
    def current_delay(self) -> float:
        """Expose adaptive delay."""
        return self._current_delay

    @current_delay.setter
    def current_delay(self, value: float) -> None:
        self._current_delay = value

    def fetch_get(
        self,
        url: str,
        headers: dict[str, str],
    ) -> curl_requests.Response | None:
        """Public wrapper for _fetch_get."""
        return self._fetch_get(url, headers)

    def fetch_post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> curl_requests.Response | None:
        """Public wrapper for _fetch_post."""
        return self._fetch_post(url, headers, payload)

    def get_page(
        self, url: str,
    ) -> BeautifulSoup | None:
        """Public wrapper for _get_page."""
        return self._get_page(url)

    def wait(self) -> None:
        """Public wrapper for _wait."""
        self._wait()

    def escalate_delay(self) -> None:
        """Public wrapper for _escalate_delay."""
        self._escalate_delay()


@patch("src.scrapers.base_scraper.curl_requests.Session")
class TestCircuitBreaker(unittest.TestCase):
    """Circuit breaker opens after consecutive failures."""

    def test_circuit_opens_after_threshold(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """After CIRCUIT_BREAKER_THRESHOLD failures, returns None."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_session.get.return_value = mock_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        threshold = scraper.settings.CIRCUIT_BREAKER_THRESHOLD

        for _ in range(threshold):
            result = scraper.fetch_get(
                "https://example.com", {}
            )
            self.assertIsNone(result)

        self.assertTrue(scraper.circuit_open)

        # Subsequent calls short-circuit immediately
        mock_session.get.reset_mock()
        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNone(result)
        mock_session.get.assert_not_called()

    def test_success_resets_counter(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """A successful fetch resets the failure counter."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"ok": true}'

        retries = 3
        side_effects: list[Any] = (
            [fail_resp] * retries + [ok_resp]
        )
        mock_session.get.side_effect = side_effects

        scraper = _StubScraper("test")
        scraper.session = mock_session
        # First call exhausts retries → 1 failure
        scraper.fetch_get("https://example.com", {})
        self.assertEqual(scraper.consecutive_failures, 1)

        # Second call succeeds on first try → reset
        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNotNone(result)
        self.assertEqual(scraper.consecutive_failures, 0)

    def test_circuit_affects_post(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Circuit breaker also blocks POST requests."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.circuit_open = True
        scraper.circuit_opened_at = time.time()

        result = scraper.fetch_post(
            "https://example.com", {}, {}
        )
        self.assertIsNone(result)
        mock_session.post.assert_not_called()

    def test_circuit_affects_get_page(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Circuit breaker skips _get_page entirely."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.circuit_open = True
        scraper.circuit_opened_at = time.time()

        result = scraper.get_page("https://example.com")
        self.assertIsNone(result)
        mock_session.get.assert_not_called()


@patch("src.scrapers.base_scraper.curl_requests.Session")
class TestCircuitBreakerCooldown(unittest.TestCase):
    """Circuit breaker half-open reset after cooldown."""

    def test_circuit_resets_after_cooldown(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """After cooldown period, breaker opens for a probe and resets on success."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"ok": true}'
        mock_session.get.return_value = ok_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.circuit_open = True
        cooldown = scraper.settings.CIRCUIT_BREAKER_COOLDOWN
        scraper.circuit_opened_at = time.time() - cooldown - 1

        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNotNone(result)
        mock_session.get.assert_called()
        self.assertFalse(scraper.circuit_open)
        self.assertEqual(scraper.consecutive_failures, 0)

    def test_circuit_blocks_before_cooldown(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Before cooldown elapses, breaker blocks all requests."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.circuit_open = True
        scraper.circuit_opened_at = time.time()

        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNone(result)
        mock_session.get.assert_not_called()

    def test_circuit_reopens_on_probe_failure(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """If the probe after cooldown fails, circuit re-opens."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        mock_session.get.return_value = fail_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.circuit_open = True
        cooldown = scraper.settings.CIRCUIT_BREAKER_COOLDOWN
        scraper.circuit_opened_at = time.time() - cooldown - 1

        # Ensure we're near threshold so probe failure re-opens
        threshold = scraper.settings.CIRCUIT_BREAKER_THRESHOLD
        scraper.consecutive_failures = threshold - 1

        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNone(result)
        self.assertTrue(scraper.circuit_open)


@patch("src.scrapers.base_scraper.curl_requests.Session")
class TestAdaptiveDelay(unittest.TestCase):
    """Rate-limiting detection escalates the delay."""

    def test_429_escalates_delay(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """A 429 response doubles the current delay."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp_429 = MagicMock()
        resp_429.status_code = 429
        mock_session.get.return_value = resp_429

        scraper = _StubScraper("test")
        scraper.session = mock_session
        original = scraper.current_delay

        scraper.fetch_get("https://example.com", {})

        self.assertGreater(scraper.current_delay, original)

    def test_403_escalates_delay(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """A 403 response triggers the same escalation."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp_403 = MagicMock()
        resp_403.status_code = 403
        mock_session.get.return_value = resp_403

        scraper = _StubScraper("test")
        scraper.session = mock_session
        original = scraper.current_delay

        scraper.fetch_get("https://example.com", {})

        self.assertGreater(scraper.current_delay, original)

    def test_success_resets_delay(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """A successful response resets delay to baseline."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"data": []}'
        mock_session.get.return_value = ok_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.current_delay = 16.0  # pre-escalated

        scraper.fetch_get("https://example.com", {})

        self.assertEqual(
            scraper.current_delay,
            scraper.settings.REQUEST_DELAY,
        )

    def test_delay_capped_at_max(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Delay never exceeds REQUEST_DELAY * MAX_DELAY_MULTIPLIER."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        scraper = _StubScraper("test")
        scraper.session = mock_session
        max_delay = (
            scraper.settings.REQUEST_DELAY
            * scraper.settings.MAX_DELAY_MULTIPLIER
        )

        for _ in range(20):
            scraper.escalate_delay()

        self.assertLessEqual(scraper.current_delay, max_delay)


@patch("src.scrapers.base_scraper.curl_requests.Session")
class TestCaptchaDetection(unittest.TestCase):
    """CAPTCHA detection in non-JSON responses."""

    def test_captcha_html_triggers_retry(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """An HTML response with 'captcha' fails validation."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        captcha_resp = MagicMock()
        captcha_resp.status_code = 200
        captcha_resp.text = (
            "<html>Please solve the captcha</html>"
        )
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"ok": true}'

        mock_session.get.side_effect = [captcha_resp, ok_resp]

        scraper = _StubScraper("test")
        scraper.session = mock_session
        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNotNone(result)
        self.assertEqual(mock_session.get.call_count, 2)

    def test_json_response_skips_captcha_check(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """JSON responses bypass CAPTCHA keyword check."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        json_resp = MagicMock()
        json_resp.status_code = 200
        json_resp.text = (
            '{"title": "CAPTCHA Puzzle Book", "price": 10}'
        )
        mock_session.get.return_value = json_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNotNone(result)

    def test_unusual_traffic_detected(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """'unusual traffic' keyword is caught."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        block_resp = MagicMock()
        block_resp.status_code = 200
        block_resp.text = (
            "<html>We detected unusual traffic</html>"
        )
        mock_session.get.return_value = block_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        result = scraper.fetch_get(
            "https://example.com", {}
        )
        self.assertIsNone(result)


@patch("src.scrapers.base_scraper.curl_requests.Session")
class TestWaitMethod(unittest.TestCase):
    """The _wait() method uses the adaptive delay."""

    @patch("src.scrapers.base_scraper.time.sleep")
    def test_wait_uses_current_delay(
        self,
        mock_sleep: MagicMock,
        mock_session_cls: MagicMock,
    ) -> None:
        """_wait() sleeps for _current_delay seconds."""
        mock_session_cls.return_value = MagicMock()
        scraper = _StubScraper("test")
        scraper.current_delay = 5.0
        scraper.wait()
        mock_sleep.assert_called_with(5.0)


@patch("src.scrapers.base_scraper.curl_requests.Session")
class TestRequestTimeout(unittest.TestCase):
    """Per-source timeout override on BaseScraper."""

    def test_timeout_defaults_to_settings(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Default request_timeout matches Settings.REQUEST_TIMEOUT."""
        mock_session_cls.return_value = MagicMock()
        scraper = _StubScraper("test")
        self.assertEqual(
            scraper.request_timeout,
            scraper.settings.REQUEST_TIMEOUT,
        )

    def test_timeout_override_applied(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """Setting request_timeout overrides the default."""
        mock_session_cls.return_value = MagicMock()
        scraper = _StubScraper("test")
        scraper.request_timeout = 20
        self.assertEqual(scraper.request_timeout, 20)

    def test_overridden_timeout_used_in_fetch(
        self, mock_session_cls: MagicMock,
    ) -> None:
        """fetch_get uses the overridden timeout value."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"ok": true}'
        mock_session.get.return_value = ok_resp

        scraper = _StubScraper("test")
        scraper.session = mock_session
        scraper.request_timeout = 25

        scraper.fetch_get("https://example.com", {})
        call_kwargs = mock_session.get.call_args
        self.assertEqual(call_kwargs.kwargs["timeout"], 25)
