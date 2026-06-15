"""Base handler abstract class and result type.

All message handlers must extend BaseHandler and implement handle().
The handler pipeline processes messages through registered handlers
in priority order until a handler returns HANDLED.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Optional

from bot.wcf.models import WxMessage


class HandlerPriority(IntEnum):
    """Handler execution priority (lower = earlier).

    Use these to control the order of handler execution.
    """

    HIGHEST = 0
    HIGH = 100
    NORMAL = 500
    LOW = 1000
    LOWEST = 9999


@dataclass
class HandlerResult:
    """Result returned by a handler after processing a message.

    Controls the pipeline flow:
      - HANDLED: Message was handled, stop pipeline
      - CONTINUE: Message not handled, continue to next handler
      - REJECTED: Message should be rejected, stop pipeline
    """

    action: str = "continue"  # "handled", "continue", "rejected"
    data: Optional[Dict[str, Any]] = None
    response: Optional[str] = None  # Reply message to send back

    @classmethod
    def handled(cls, response: Optional[str] = None, **data: Any) -> "HandlerResult":
        """Create a HANDLED result (stop pipeline)."""
        return cls(action="handled", response=response, data=dict(data) if data else None)

    @classmethod
    def continue_(cls, **data: Any) -> "HandlerResult":
        """Create a CONTINUE result (proceed to next handler)."""
        return cls(action="continue", data=dict(data) if data else None)

    @classmethod
    def rejected(cls, reason: str = "") -> "HandlerResult":
        """Create a REJECTED result (reject message, stop pipeline)."""
        return cls(action="rejected", data={"reason": reason})


class BaseHandler(abc.ABC):
    """Abstract base class for all message handlers.

    Subclasses must implement:
      - name: Unique handler identifier
      - handle(): Process a message and return a HandlerResult

    Optional overrides:
      - priority: Handler execution priority
      - enabled: Whether the handler is active
      - can_handle(): Pre-check if this handler should process the message
    """

    @property
    def name(self) -> str:
        """Unique handler name. Defaults to class name."""
        return self.__class__.__name__

    @property
    def priority(self) -> HandlerPriority:
        """Handler priority (lower = runs earlier)."""
        return HandlerPriority.NORMAL

    @property
    def enabled(self) -> bool:
        """Whether this handler is currently active."""
        return True

    def can_handle(self, msg: WxMessage) -> bool:
        """Pre-check if this handler should process the message.

        Override for fast filtering (e.g., check message type).
        Return False to skip this handler entirely.

        Default: True (all messages).
        """
        return True

    @abc.abstractmethod
    def handle(self, msg: WxMessage) -> HandlerResult:
        """Process a message and return a result.

        Args:
            msg: The WeChat message to process.

        Returns:
            HandlerResult controlling pipeline flow.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} priority={self.priority} enabled={self.enabled}>"
