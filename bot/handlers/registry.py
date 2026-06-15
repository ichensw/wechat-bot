"""Handler registry - manages all registered message handlers.

Handlers are registered with priorities and can be dynamically added/removed.
Supports both class-based and function-based handler registration.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from bot.handlers.base import BaseHandler, HandlerPriority
from bot.wcf.models import WxMessage

logger = logging.getLogger("WeChatBot.HandlerRegistry")


class HandlerRegistry:
    """Central registry for message handlers.

    Features:
      - Priority-based ordering
      - Dynamic registration/deregistration
      - Enable/disable individual handlers
      - Query handlers by name or type
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, BaseHandler] = {}

    def register(self, handler: BaseHandler) -> None:
        """Register a handler.

        If a handler with the same name exists, it will be replaced.

        Args:
            handler: A BaseHandler instance.
        """
        if handler.name in self._handlers:
            logger.warning("Replacing existing handler: %s", handler.name)
        self._handlers[handler.name] = handler
        logger.info(
            "Registered handler: %s (priority=%d)",
            handler.name,
            handler.priority,
        )

    def unregister(self, name: str) -> Optional[BaseHandler]:
        """Unregister a handler by name.

        Returns:
            The removed handler, or None if not found.
        """
        handler = self._handlers.pop(name, None)
        if handler:
            logger.info("Unregistered handler: %s", name)
        return handler

    def get(self, name: str) -> Optional[BaseHandler]:
        """Get a handler by name."""
        return self._handlers.get(name)

    def get_all(self) -> List[BaseHandler]:
        """Get all handlers sorted by priority (ascending)."""
        return sorted(self._handlers.values(), key=lambda h: h.priority)

    def get_enabled(self) -> List[BaseHandler]:
        """Get all enabled handlers sorted by priority."""
        return sorted(
            [h for h in self._handlers.values() if h.enabled],
            key=lambda h: h.priority,
        )

    def enable(self, name: str) -> bool:
        """Enable a handler by name."""
        handler = self._handlers.get(name)
        if handler:
            # Use a flag to track enabled state
            handler._enabled = True  # noqa: SLF001
            logger.info("Enabled handler: %s", name)
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a handler by name."""
        handler = self._handlers.get(name)
        if handler:
            handler._enabled = False  # noqa: SLF001
            logger.info("Disabled handler: %s", name)
            return True
        return False

    def find_candidates(self, msg: WxMessage) -> List[BaseHandler]:
        """Find handlers that can handle a message, sorted by priority.

        Runs can_handle() pre-check on each enabled handler.
        """
        candidates = []
        for handler in self.get_enabled():
            try:
                if handler.can_handle(msg):
                    candidates.append(handler)
            except Exception as e:
                logger.error("Error in can_handle() for %s: %s", handler.name, e)
        return candidates

    @property
    def count(self) -> int:
        """Total number of registered handlers."""
        return len(self._handlers)

    @property
    def enabled_count(self) -> int:
        """Number of enabled handlers."""
        return sum(1 for h in self._handlers.values() if h.enabled)

    def describe(self) -> str:
        """Generate a human-readable description of all registered handlers."""
        handlers = self.get_all()
        lines = [f"Handler Registry ({len(handlers)} handlers):"]
        for h in handlers:
            status = "✅" if h.enabled else "❌"
            lines.append(f"  {status} {h.name} (priority={h.priority})")
        return "\n".join(lines)
