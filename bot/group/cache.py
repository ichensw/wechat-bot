"""Group cache - in-memory cache for group info.

Caches contact data, member counts, and group metadata to reduce WCF API calls.
Supports TTL-based expiration and manual invalidation.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from bot.config.settings import MonitorSettings
from bot.wcf.models import Contact, GroupInfo

logger = logging.getLogger("WeChatBot.GroupCache")


class GroupCache:
    """Thread-safe in-memory cache for group information.

    Reduces WCF API calls by caching group data with TTL expiration.
    Automatically refreshes when entries expire.

    Args:
        settings: Monitor settings (for TTL configuration).
    """

    def __init__(self, settings: MonitorSettings):
        self._ttl = settings.group_cache_ttl
        self._groups: Dict[str, "_CacheEntry"] = {}
        self._lock = threading.RLock()
        self._last_full_refresh: float = 0.0

    def get(self, room_id: str) -> Optional[GroupInfo]:
        """Get cached group info if not expired.

        Returns:
            GroupInfo if cached and valid, None otherwise.
        """
        with self._lock:
            entry = self._groups.get(room_id)
            if entry and not entry.is_expired(self._ttl):
                return entry.data
            return None

    def put(self, group_info: GroupInfo) -> None:
        """Store group info in cache."""
        with self._lock:
            self._groups[group_info.room_id] = _CacheEntry(data=group_info, timestamp=time.time())

    def invalidate(self, room_id: str) -> None:
        """Invalidate a specific group's cache entry."""
        with self._lock:
            self._groups.pop(room_id, None)

    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        with self._lock:
            self._groups.clear()

    def get_all_cached(self) -> List[GroupInfo]:
        """Get all non-expired cached group info."""
        with self._lock:
            return [e.data for e in self._groups.values() if not e.is_expired(self._ttl)]

    def get_all_cached_unchecked(self) -> List[GroupInfo]:
        """Get all cached group info regardless of expiration."""
        with self._lock:
            return [e.data for e in self._groups.values()]

    def refresh_from_contacts(self, contacts: List[Contact]) -> int:
        """Populate cache from a list of contacts.

        Returns:
            Number of groups cached.
        """
        with self._lock:
            for contact in contacts:
                if contact.is_group:
                    info = GroupInfo.from_contact(contact)
                    self._groups[contact.wxid] = _CacheEntry(data=info, timestamp=time.time())
            self._last_full_refresh = time.time()

        count = len([c for c in contacts if c.is_group])
        logger.info("Cache refreshed: %d groups", count)
        return count

    def update_member_count(self, room_id: str, count: int) -> None:
        """Update member count for a cached group."""
        with self._lock:
            entry = self._groups.get(room_id)
            if entry:
                entry.data.member_count = count

    @property
    def size(self) -> int:
        """Number of cached entries."""
        with self._lock:
            return len(self._groups)

    @property
    def expired_count(self) -> int:
        """Number of expired entries."""
        with self._lock:
            return sum(1 for e in self._groups.values() if e.is_expired(self._ttl))

    @property
    def needs_refresh(self) -> bool:
        """Check if cache needs a full refresh based on TTL."""
        return (time.time() - self._last_full_refresh) > self._ttl


class _CacheEntry:
    """Internal cache entry with timestamp."""

    __slots__ = ("data", "timestamp")

    def __init__(self, data: GroupInfo, timestamp: float):
        self.data = data
        self.timestamp = timestamp

    def is_expired(self, ttl: float) -> bool:
        """Check if this entry has exceeded the TTL."""
        return (time.time() - self.timestamp) > ttl
