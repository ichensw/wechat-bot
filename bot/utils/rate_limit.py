"""Rate limiting utilities.

Provides two rate limiting algorithms:
  - TokenBucket: Smooth rate limiting with burst support
  - RateLimiter: Simple sliding window rate limiter

Usage:
    bucket = TokenBucket(rate=10, capacity=20)
    if bucket.consume():
        # Request allowed
    else:
        # Rate limit exceeded

    limiter = RateLimiter(max_requests=60, window_seconds=60)
    limiter.check("client_ip_1")
    limiter.check("client_ip_2")
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bot.core.exceptions import WebHookRateLimitError


class TokenBucket:
    """Token bucket rate limiter.

    Allows burst traffic up to capacity, then enforces a steady rate.
    Thread-safe implementation.

    Args:
        rate: Tokens added per second.
        capacity: Maximum tokens that can accumulate.
    """

    def __init__(self, rate: float, capacity: float):
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if tokens were available and consumed, False otherwise.
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            return min(self._capacity, self._tokens + elapsed * self._rate)

    @property
    def rate(self) -> float:
        """Token refill rate per second."""
        return self._rate

    @property
    def capacity(self) -> float:
        """Maximum burst capacity."""
        return self._capacity


class RateLimiter:
    """Sliding window rate limiter with per-key tracking.

    Tracks request counts per key within a sliding time window.
    Thread-safe implementation.

    Args:
        max_requests: Maximum requests allowed per window.
        window_seconds: Time window in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Check if a request from the given key is allowed.

        Args:
            key: Identifier for the client (e.g., IP address).

        Returns:
            True if the request is allowed, False if rate limit exceeded.
        """
        now = time.time()
        window_start = now - self._window_seconds

        with self._lock:
            # Remove expired entries
            self._requests[key] = [t for t in self._requests[key] if t > window_start]

            # Check if limit exceeded
            if len(self._requests[key]) >= self._max_requests:
                return False

            # Record this request
            self._requests[key].append(now)
            return True

    def check_or_raise(self, key: str) -> None:
        """Check rate limit and raise if exceeded.

        Raises:
            WebHookRateLimitError: If rate limit is exceeded.
        """
        if not self.check(key):
            raise WebHookRateLimitError(retry_after=self._window_seconds)

    def remaining(self, key: str) -> int:
        """Get remaining requests for a key in the current window."""
        now = time.time()
        window_start = now - self._window_seconds

        with self._lock:
            active = [t for t in self._requests[key] if t > window_start]
            return max(0, self._max_requests - len(active))

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limit for a specific key or all keys."""
        with self._lock:
            if key:
                self._requests.pop(key, None)
            else:
                self._requests.clear()

    @property
    def max_requests(self) -> int:
        """Maximum requests per window."""
        return self._max_requests

    @property
    def window_seconds(self) -> int:
        """Time window in seconds."""
        return self._window_seconds
