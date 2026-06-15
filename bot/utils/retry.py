"""Retry utilities for resilient operations.

Usage:
    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def fetch_data():
        ...

    # Or with a policy object
    policy = RetryPolicy(max_attempts=5, delay=0.5, backoff=2.0, jitter=True)
    retry_with_policy(policy, my_func, arg1, arg2)
"""

from __future__ import annotations

import functools
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, Type

from bot.utils.logger import get_logger

logger = get_logger("Retry")


@dataclass
class RetryPolicy:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including first call).
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each failure.
        jitter: Add random jitter to delay (prevents thundering herd).
        retryable_exceptions: Tuple of exception types that should trigger retry.
    """

    max_attempts: int = 3
    delay: float = 1.0
    backoff: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator for automatic retry on failure.

    Args:
        max_attempts: Maximum number of attempts.
        delay: Initial delay between retries.
        backoff: Exponential backoff multiplier.
        jitter: Add random jitter to delay.
        retryable_exceptions: Exception types that should trigger retry.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            policy = RetryPolicy(
                max_attempts=max_attempts,
                delay=delay,
                backoff=backoff,
                jitter=jitter,
                retryable_exceptions=retryable_exceptions,
            )
            return retry_with_policy(policy, func, *args, **kwargs)

        return wrapper

    return decorator


def retry_with_policy(policy: RetryPolicy, func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a function with the given retry policy.

    Args:
        policy: Retry configuration.
        func: Function to execute.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        The result of the function call.

    Raises:
        The last exception if all attempts fail.
    """
    last_exception: Optional[Exception] = None
    current_delay = policy.delay

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except policy.retryable_exceptions as e:
            last_exception = e
            if attempt < policy.max_attempts:
                wait = current_delay
                if policy.jitter:
                    wait *= random.uniform(0.5, 1.5)
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                    attempt,
                    policy.max_attempts,
                    func.__name__,
                    str(e)[:100],
                    wait,
                )
                time.sleep(wait)
                current_delay *= policy.backoff
            else:
                logger.error(
                    "All %d attempts failed for %s: %s",
                    policy.max_attempts,
                    func.__name__,
                    str(e)[:200],
                )

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Unexpected retry state for {func.__name__}")
