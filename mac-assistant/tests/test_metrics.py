"""Tests for metrics tracking."""

import time

import pytest

from src.core.models import MetricsData
from src.foundry.metrics import MetricsTracker, estimate_tokens, format_metrics


class TestMetricsTracker:
    """Test MetricsTracker functionality."""

    def test_basic_tracking(self):
        """Test basic token tracking."""
        tracker = MetricsTracker()
        tracker.start(prompt_tokens=10)

        for _ in range(5):
            tracker.add_token()
            time.sleep(0.01)  # Simulate generation time

        metrics = tracker.stop()

        assert metrics.tokens_generated == 5
        assert metrics.prompt_tokens == 10
        assert metrics.tokens_per_second > 0
        assert metrics.total_time > 0

    def test_time_to_first_token(self):
        """Test TTFT measurement."""
        tracker = MetricsTracker()
        tracker.start()

        time.sleep(0.05)  # Delay before first token
        tracker.add_token()

        metrics = tracker.get_metrics()

        assert metrics.time_to_first_token >= 0.04  # Allow some variance

    def test_not_started(self):
        """Test behavior when not started."""
        tracker = MetricsTracker()

        assert tracker.tokens_generated == 0
        assert tracker.tokens_per_second == 0.0
        assert not tracker.is_running

    def test_callback(self):
        """Test token callback."""
        tracker = MetricsTracker()
        callback_data = []

        def on_token(count: int, tps: float):
            callback_data.append((count, tps))

        tracker.set_token_callback(on_token)
        tracker.start()

        for _ in range(3):
            tracker.add_token()

        assert len(callback_data) == 3
        assert callback_data[0][0] == 1
        assert callback_data[2][0] == 3


class TestEstimateTokens:
    """Test token estimation."""

    def test_basic_estimate(self):
        """Test basic token estimation."""
        text = "Hello, how are you?"  # ~20 chars
        tokens = estimate_tokens(text)
        assert tokens >= 4  # ~4 chars per token

    def test_empty_string(self):
        """Test empty string."""
        assert estimate_tokens("") == 0


class TestFormatMetrics:
    """Test metrics formatting."""

    def test_basic_format(self):
        """Test basic formatting."""
        metrics = MetricsData(
            tokens_generated=100,
            tokens_per_second=42.5,
            time_to_first_token=0.123,
            total_time=2.5,
        )

        formatted = format_metrics(metrics)

        assert "100 tokens" in formatted
        assert "42.5 tok/s" in formatted
        assert "TTFT:" in formatted

    def test_non_verbose(self):
        """Test non-verbose format."""
        metrics = MetricsData(tokens_generated=50)
        formatted = format_metrics(metrics, verbose=False)

        assert formatted == "50 tokens"
