"""Streaming response handler with metrics tracking."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any

from src.core.models import MetricsData, StreamChunk
from src.foundry.metrics import MetricsTracker, estimate_tokens

if TYPE_CHECKING:
    from openai import OpenAI
    from openai.types.chat import ChatCompletionChunk

logger = logging.getLogger(__name__)


class StreamingHandler:
    """Handle streaming responses from Foundry Local with metrics."""

    def __init__(
        self,
        client: "OpenAI",
        model_id: str,
        verbose: bool = True,
    ):
        """Initialize streaming handler.

        Args:
            client: OpenAI client instance.
            model_id: Model ID to use for completions.
            verbose: Enable metrics tracking.
        """
        self.client = client
        self.model_id = model_id
        self.verbose = verbose
        self.metrics = MetricsTracker()

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Generator[StreamChunk, None, None]:
        """Stream a chat completion response.

        Args:
            messages: List of chat messages in OpenAI format.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Yields:
            StreamChunk objects containing content and metrics.
        """
        # Estimate prompt tokens
        prompt_text = " ".join(m.get("content", "") for m in messages)
        prompt_tokens = estimate_tokens(prompt_text)

        if self.verbose:
            self.metrics.start(prompt_tokens=prompt_tokens)

        try:
            stream = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                content = self._extract_content(chunk)
                if content:
                    if self.verbose:
                        # Estimate tokens in this chunk
                        chunk_tokens = max(1, estimate_tokens(content))
                        self.metrics.add_tokens(chunk_tokens)

                    yield StreamChunk(
                        content=content,
                        done=False,
                        metrics=self.metrics.get_metrics() if self.verbose else None,
                    )

            # Final chunk with complete metrics
            final_metrics = self.metrics.stop() if self.verbose else None
            yield StreamChunk(content="", done=True, metrics=final_metrics)

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            if self.verbose:
                self.metrics.stop()
            raise

    async def stream_chat_async(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Async version of stream_chat.

        Args:
            messages: List of chat messages in OpenAI format.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Yields:
            StreamChunk objects containing content and metrics.
        """
        # Run sync streaming in thread pool
        loop = asyncio.get_event_loop()

        # Estimate prompt tokens
        prompt_text = " ".join(m.get("content", "") for m in messages)
        prompt_tokens = estimate_tokens(prompt_text)

        if self.verbose:
            self.metrics.start(prompt_tokens=prompt_tokens)

        try:
            # Create stream in executor
            stream = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                ),
            )

            # Process chunks
            for chunk in stream:
                content = self._extract_content(chunk)
                if content:
                    if self.verbose:
                        chunk_tokens = max(1, estimate_tokens(content))
                        self.metrics.add_tokens(chunk_tokens)

                    yield StreamChunk(
                        content=content,
                        done=False,
                        metrics=self.metrics.get_metrics() if self.verbose else None,
                    )

                # Yield control to allow other tasks
                await asyncio.sleep(0)

            # Final chunk
            final_metrics = self.metrics.stop() if self.verbose else None
            yield StreamChunk(content="", done=True, metrics=final_metrics)

        except Exception as e:
            logger.error(f"Async streaming error: {e}")
            if self.verbose:
                self.metrics.stop()
            raise

    def complete_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> tuple[str, MetricsData | None]:
        """Get a complete (non-streaming) chat response.

        Args:
            messages: List of chat messages in OpenAI format.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Tuple of (response_text, metrics).
        """
        prompt_text = " ".join(m.get("content", "") for m in messages)
        prompt_tokens = estimate_tokens(prompt_text)

        if self.verbose:
            self.metrics.start(prompt_tokens=prompt_tokens)

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

            content = response.choices[0].message.content or ""

            if self.verbose:
                # Use actual token count if available
                if response.usage:
                    self.metrics.add_tokens(response.usage.completion_tokens)
                else:
                    self.metrics.add_tokens(estimate_tokens(content))

            final_metrics = self.metrics.stop() if self.verbose else None
            return content, final_metrics

        except Exception as e:
            logger.error(f"Completion error: {e}")
            if self.verbose:
                self.metrics.stop()
            raise

    async def complete_chat_async(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> tuple[str, MetricsData | None]:
        """Async version of complete_chat."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.complete_chat(messages, temperature, max_tokens),
        )

    def _extract_content(self, chunk: "ChatCompletionChunk") -> str:
        """Extract content from a stream chunk."""
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                return delta.content
        return ""

    def get_current_metrics(self) -> MetricsData:
        """Get current metrics (useful during streaming)."""
        return self.metrics.get_metrics()
