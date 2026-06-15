"""Message processing pipeline.

The pipeline processes messages through registered handlers in priority order.
Handlers are invoked until one returns HANDLED or REJECTED.

Pipeline flow:
  1. Find candidate handlers (can_handle() == True)
  2. Execute each handler in priority order
  3. Stop on first HANDLED or REJECTED result
  4. Collect and return the pipeline result

Supports pre/post hooks for cross-cutting concerns (logging, metrics, etc.).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from bot.core.event_bus import EventBus, EventTypes
from bot.handlers.base import BaseHandler, HandlerResult
from bot.handlers.registry import HandlerRegistry
from bot.wcf.models import WxMessage

logger = logging.getLogger("WeChatBot.Pipeline")


# Type aliases for hooks
PreHook = Callable[[WxMessage], Optional[HandlerResult]]  # Can short-circuit
PostHook = Callable[[WxMessage, HandlerResult], None]


@dataclass
class PipelineStats:
    """Pipeline execution statistics."""

    total_processed: int = 0
    total_handled: int = 0
    total_rejected: int = 0
    total_passed: int = 0
    total_errors: int = 0
    handler_times: Dict[str, List[float]] = field(default_factory=dict)

    def record(self, handler_name: str, elapsed: float, result_action: str) -> None:
        """Record a handler execution result."""
        self.total_processed += 1
        if result_action == "handled":
            self.total_handled += 1
        elif result_action == "rejected":
            self.total_rejected += 1
        else:
            self.total_passed += 1

        self.handler_times.setdefault(handler_name, []).append(elapsed)
        # Keep only last 1000 measurements per handler
        if len(self.handler_times[handler_name]) > 1000:
            self.handler_times[handler_name] = self.handler_times[handler_name][-1000:]


class HandlerPipeline:
    """Message processing pipeline with hooks and metrics.

    The pipeline orchestrates the flow of a message through registered handlers.
    It supports pre/post hooks for cross-cutting concerns and tracks execution metrics.
    """

    def __init__(self, registry: HandlerRegistry, event_bus: Optional[EventBus] = None):
        self._registry = registry
        self._event_bus = event_bus
        self._pre_hooks: List[PreHook] = []
        self._post_hooks: List[PostHook] = []
        self._stats = PipelineStats()

    def add_pre_hook(self, hook: PreHook) -> None:
        """Add a pre-processing hook.

        Pre-hooks run before the handler chain. If a pre-hook returns a
        non-None HandlerResult, the pipeline short-circuits.
        """
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: PostHook) -> None:
        """Add a post-processing hook.

        Post-hooks run after the pipeline completes (regardless of outcome).
        They cannot modify the result.
        """
        self._post_hooks.append(hook)

    def process(self, msg: WxMessage) -> HandlerResult:
        """Process a message through the handler pipeline.

        Flow:
          1. Run pre-hooks (any can short-circuit)
          2. Find candidate handlers
          3. Execute handlers in priority order
          4. Stop on first HANDLED or REJECTED
          5. Run post-hooks
          6. Return the final result

        Args:
            msg: The WeChat message to process.

        Returns:
            HandlerResult from the pipeline execution.
        """
        start_time = time.monotonic()

        # Run pre-hooks
        for hook in self._pre_hooks:
            try:
                result = hook(msg)
                if result is not None:
                    self._run_post_hooks(msg, result)
                    return result
            except Exception as e:
                logger.error("Pre-hook error: %s", e)

        # Find candidates
        candidates = self._registry.find_candidates(msg)
        if not candidates:
            result = HandlerResult.continue_()
            self._run_post_hooks(msg, result)
            return result

        # Execute handler chain
        final_result = HandlerResult.continue_()
        for handler in candidates:
            handler_start = time.monotonic()
            try:
                result = handler.handle(msg)
                elapsed = time.monotonic() - handler_start
                self._stats.record(handler.name, elapsed, result.action)

                logger.debug(
                    "Handler %s -> %s (%.3fms)",
                    handler.name,
                    result.action,
                    elapsed * 1000,
                )

                if result.action in ("handled", "rejected"):
                    final_result = result
                    break

            except Exception as e:
                elapsed = time.monotonic() - handler_start
                self._stats.record(handler.name, elapsed, "error")
                self._stats.total_errors += 1
                logger.error("Handler %s error: %s", handler.name, e, exc_info=True)

        # Run post-hooks
        self._run_post_hooks(msg, final_result)

        # Publish event
        if self._event_bus:
            event_type = EventTypes.MSG_GROUP if msg.is_group else EventTypes.MSG_PRIVATE
            self._event_bus.publish(event_type, data={"msg": msg, "result": final_result})

        total_elapsed = time.monotonic() - start_time
        logger.debug("Pipeline completed in %.3fms", total_elapsed * 1000)

        return final_result

    def _run_post_hooks(self, msg: WxMessage, result: HandlerResult) -> None:
        """Run all post-hooks."""
        for hook in self._post_hooks:
            try:
                hook(msg, result)
            except Exception as e:
                logger.error("Post-hook error: %s", e)

    @property
    def stats(self) -> PipelineStats:
        """Get pipeline execution statistics."""
        return self._stats

    def get_handler_avg_time(self, handler_name: str) -> Optional[float]:
        """Get average execution time for a handler."""
        times = self._stats.handler_times.get(handler_name, [])
        if not times:
            return None
        return sum(times) / len(times)
