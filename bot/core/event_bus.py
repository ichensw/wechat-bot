"""Event bus for decoupled inter-component communication.

Components publish events; other components subscribe to event types.
This eliminates direct dependencies between modules.

Usage:
    bus = EventBus()

    # Subscribe
    bus.subscribe("group.message", my_handler)

    # Publish
    bus.publish("group.message", WxMessage(...))

    # Async subscription (runs in thread pool)
    bus.subscribe_async("group.member_change", send_alert)
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("WeChatBot.EventBus")


@dataclass
class Event:
    """An event object passed through the event bus."""

    type: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # Component that published the event

    @property
    def is_group_event(self) -> bool:
        """Check if this is a group-related event."""
        return self.type.startswith("group.")


# Event type constants
class EventTypes:
    """Standard event type names."""

    # Message events
    MSG_RECEIVED = "msg.received"
    MSG_GROUP = "msg.group"
    MSG_PRIVATE = "msg.private"
    MSG_SYSTEM = "msg.system"

    # Group events
    GROUP_MEMBER_CHANGE = "group.member_change"
    GROUP_MESSAGE_STORED = "group.message_stored"
    GROUP_INFO_UPDATED = "group.info_updated"
    GROUP_CACHE_REFRESHED = "group.cache_refreshed"

    # Admin events
    ADMIN_BOUND = "admin.bound"
    ADMIN_UNBOUND = "admin.unbound"
    ADMIN_COMMAND = "admin.command"

    # Bot lifecycle events
    BOT_STARTING = "bot.starting"
    BOT_STARTED = "bot.started"
    BOT_STOPPING = "bot.stopping"
    BOT_STOPPED = "bot.stopped"
    BOT_ERROR = "bot.error"
    BOT_WCF_CONNECTED = "bot.wcf_connected"
    BOT_WCF_DISCONNECTED = "bot.wcf_disconnected"

    # Config events
    CONFIG_CHANGED = "config.changed"
    CONFIG_RELOADED = "config.reloaded"


# Type aliases
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], None]


class EventBus:
    """Synchronous publish-subscribe event bus with optional async dispatch.

    Features:
      - Synchronous event dispatch (default)
      - Async event dispatch (via thread pool)
      - Event history (for debugging)
      - Subscriber filtering by event type prefix
    """

    def __init__(self, max_history: int = 1000, max_workers: int = 4):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._async_subscribers: Dict[str, List[AsyncEventHandler]] = {}
        self._history: List[Event] = []
        self._max_history = max_history
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EventBus")
        self._lock = Lock()
        self._enabled = True

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a synchronous handler to an event type.

        Args:
            event_type: Event type string (supports prefix matching, e.g., "group." matches all group events).
            handler: Callback function that receives an Event.
        """
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)
        logger.debug("Subscribed %s to event '%s'", handler.__name__, event_type)

    def subscribe_async(self, event_type: str, handler: AsyncEventHandler) -> None:
        """Subscribe an async handler (runs in thread pool).

        Use this for handlers that may block (e.g., sending messages, network calls).
        """
        with self._lock:
            self._async_subscribers.setdefault(event_type, []).append(handler)
        logger.debug("Subscribed async %s to event '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [h for h in self._subscribers[event_type] if h != handler]
            if event_type in self._async_subscribers:
                self._async_subscribers[event_type] = [h for h in self._async_subscribers[event_type] if h != handler]

    def publish(self, event_type: str, data: Any = None, source: str = "") -> Event:
        """Publish an event synchronously.

        Synchronous handlers are called immediately. Async handlers are dispatched
        to the thread pool.

        Args:
            event_type: Event type string.
            data: Event payload.
            source: Name of the publishing component.

        Returns:
            The published Event object.
        """
        if not self._enabled:
            return Event(type=event_type, data=data, source=source)

        event = Event(type=event_type, data=data, timestamp=time.time(), source=source)

        # Record in history
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        # Dispatch to synchronous subscribers
        self._dispatch_sync(event)

        # Dispatch to async subscribers
        self._dispatch_async(event)

        return event

    def _dispatch_sync(self, event: Event) -> None:
        """Dispatch event to all matching synchronous subscribers."""
        with self._lock:
            subscribers = dict(self._subscribers)

        # Match exact type and prefix types
        handlers: List[EventHandler] = []
        for event_type, handler_list in subscribers.items():
            if event.type == event_type or event.type.startswith(event_type.rstrip(".") + "."):
                handlers.extend(handler_list)

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Error in sync handler %s for event '%s': %s", handler.__name__, event.type, e)

    def _dispatch_async(self, event: Event) -> None:
        """Dispatch event to all matching async subscribers via thread pool."""
        with self._lock:
            async_subscribers = dict(self._async_subscribers)

        handlers: List[AsyncEventHandler] = []
        for event_type, handler_list in async_subscribers.items():
            if event.type == event_type or event.type.startswith(event_type.rstrip(".") + "."):
                handlers.extend(handler_list)

        for handler in handlers:
            try:
                self._executor.submit(self._safe_async_call, handler, event)
            except Exception as e:
                logger.error("Error dispatching async handler %s: %s", handler.__name__, e)

    def _safe_async_call(self, handler: AsyncEventHandler, event: Event) -> None:
        """Execute an async handler with error handling."""
        try:
            handler(event)
        except Exception as e:
            logger.error("Error in async handler %s for event '%s': %s", handler.__name__, event.type, e)

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> List[Event]:
        """Get recent event history, optionally filtered by type prefix."""
        with self._lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if e.type.startswith(event_type)]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()

    def shutdown(self) -> None:
        """Shutdown the event bus and thread pool."""
        self._enabled = False
        self._executor.shutdown(wait=False)
        logger.info("Event bus shutdown")
