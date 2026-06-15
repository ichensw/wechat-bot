"""Thread-safe message sender with concurrency protection.

All message sends from the bot (handler pipeline, webhook, scheduler, admin)
go through this single sender, which serializes send operations with a lock
to prevent race conditions when multiple threads call send simultaneously.

WeChatFerry SDK itself is not thread-safe for concurrent send calls —
this wrapper ensures only one send is in-flight at a time.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from bot.wcf.client import WcfClient

logger = logging.getLogger("WeChatBot.Sender")

# Rate limit: minimum interval between sends (seconds)
_SEND_INTERVAL = 0.3


class ThreadSafeSender:
    """Thread-safe wrapper around WcfClient send operations.

    Guarantees:
      - Only one send operation runs at a time (via Lock)
      - Minimum interval between sends to avoid rate-limiting
      - All send failures are logged and return error codes

    Usage:
        sender = ThreadSafeSender(wcf_client)
        sender.send_text("hello", "wxid_xxx")
        sender.send_text("@user reply", "room@chatroom", at_list=["wxid_user"])
    """

    def __init__(self, wcf_client: "WcfClient") -> None:
        self._wcf = wcf_client
        self._lock = threading.Lock()
        self._last_send_time: float = 0.0

    def send_text(self, msg: str, receiver: str, at_list: Optional[List[str]] = None) -> int:
        """Send a text message (thread-safe).

        Args:
            msg: Message content.
            receiver: Receiver wxid or roomid.
            at_list: Optional wxids to @mention.

        Returns:
            Result code (0 = success).
        """
        with self._lock:
            self._rate_limit()
            try:
                result = self._wcf.send_text(msg, receiver, at_list=at_list)
                self._last_send_time = time.time()
                if result != 0:
                    logger.warning("send_text failed: code=%s to=%s", result, receiver)
                return result
            except Exception as e:
                logger.error("send_text exception: %s to=%s", e, receiver)
                return -1

    def send_image(self, path: str, receiver: str) -> int:
        """Send an image message (thread-safe)."""
        with self._lock:
            self._rate_limit()
            try:
                result = self._wcf.send_image(path, receiver)
                self._last_send_time = time.time()
                return result
            except Exception as e:
                logger.error("send_image exception: %s to=%s", e, receiver)
                return -1

    def send_file(self, path: str, receiver: str) -> int:
        """Send a file message (thread-safe)."""
        with self._lock:
            self._rate_limit()
            try:
                result = self._wcf.send_file(path, receiver)
                self._last_send_time = time.time()
                return result
            except Exception as e:
                logger.error("send_file exception: %s to=%s", e, receiver)
                return -1

    def _rate_limit(self) -> None:
        """Enforce minimum interval between sends (called inside lock)."""
        elapsed = time.time() - self._last_send_time
        if elapsed < _SEND_INTERVAL:
            time.sleep(_SEND_INTERVAL - elapsed)
