"""Performance metrics tracking for token generation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from src.core.models import MetricsData


@dataclass
class MetricsTracker:
    """Track performance metrics during inference."""

    # Timing
    _start_time: float = 0.0
    _first_token_time: float = 0.0
    _end_time: float = 0.0

    # Token counts
    _tokens_generated: int = 0
    _prompt_tokens: int = 0
    _context_tokens: int = 0

    # State
    _is_running: bool = False
    _first_token_received: bool = False

    # Optional callbacks
    _on_token: Callable[[int, float], None] | None = None

    def start(self, prompt_tokens: int = 0, context_tokens: int = 0) -> None:
        """Start tracking metrics."""
        self._start_time = time.perf_counter()
        self._first_token_time = 0.0
        self._end_time = 0.0
        self._tokens_generated = 0
        self._prompt_tokens = prompt_tokens
        self._context_tokens = context_tokens
        self._is_running = True
        self._first_token_received = False

    def add_token(self) -> None:
        """Record a token being generated."""
        if not self._is_running:
            return

        now = time.perf_counter()

        if not self._first_token_received:
            self._first_token_time = now
            self._first_token_received = True

        self._tokens_generated += 1

        if self._on_token:
            self._on_token(self._tokens_generated, self.tokens_per_second)

    def add_tokens(self, count: int) -> None:
        """Record multiple tokens being generated."""
        for _ in range(count):
            self.add_token()

    def stop(self) -> MetricsData:
        """Stop tracking and return final metrics."""
        self._end_time = time.perf_counter()
        self._is_running = False
        return self.get_metrics()

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if not self._start_time:
            return 0.0
        end = self._end_time if self._end_time else time.perf_counter()
        return end - self._start_time

    @property
    def time_to_first_token(self) -> float:
        """Get time to first token in seconds."""
        if not self._first_token_time or not self._start_time:
            return 0.0
        return self._first_token_time - self._start_time

    @property
    def tokens_per_second(self) -> float:
        """Calculate current tokens per second."""
        if self._tokens_generated == 0:
            return 0.0

        # Calculate from first token (more accurate for streaming)
        if self._first_token_time:
            end = self._end_time if self._end_time else time.perf_counter()
            generation_time = end - self._first_token_time
            if generation_time > 0:
                return self._tokens_generated / generation_time

        return 0.0

    @property
    def tokens_generated(self) -> int:
        """Get total tokens generated."""
        return self._tokens_generated

    @property
    def is_running(self) -> bool:
        """Check if tracking is active."""
        return self._is_running

    def get_metrics(self) -> MetricsData:
        """Get current metrics as a MetricsData object."""
        return MetricsData(
            tokens_generated=self._tokens_generated,
            tokens_per_second=round(self.tokens_per_second, 2),
            time_to_first_token=round(self.time_to_first_token, 3),
            total_time=round(self.elapsed_time, 3),
            prompt_tokens=self._prompt_tokens,
            context_tokens=self._context_tokens,
        )

    def set_token_callback(self, callback: Callable[[int, float], None]) -> None:
        """Set a callback for each token generated.

        Callback receives (token_count, current_tokens_per_second).
        """
        self._on_token = callback


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token on average.
    For more accurate counting, use tiktoken with the specific model.
    """
    return len(text) // 4


def format_metrics(metrics: MetricsData, verbose: bool = True) -> str:
    """Format metrics for display."""
    if not verbose:
        return f"{metrics.tokens_generated} tokens"

    parts = [
        f"{metrics.tokens_generated} tokens",
        f"{metrics.tokens_per_second:.1f} tok/s",
    ]

    if metrics.time_to_first_token > 0:
        parts.append(f"TTFT: {metrics.time_to_first_token*1000:.0f}ms")

    parts.append(f"total: {metrics.total_time:.2f}s")

    return " | ".join(parts)
