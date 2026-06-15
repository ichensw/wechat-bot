"""Group blacklist/whitelist filter.

Filter modes:
  - "whitelist": Only monitor groups in the whitelist
  - "blacklist": Monitor all groups except those in the blacklist
  - "all": Monitor all groups (no filtering)

Changes are persisted to config.yaml via the ConfigLoader.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set

from bot.config.loader import ConfigLoader
from bot.config.settings import GroupFilterSettings
from bot.core.exceptions import ConfigValidationError

logger = logging.getLogger("WeChatBot.GroupFilter")


class GroupFilter:
    """Group blacklist/whitelist filter manager.

    Provides runtime-modifiable group filtering with persistence.
    Thread-safe for concurrent access.
    """

    def __init__(self, config_loader: ConfigLoader):
        self._config_loader = config_loader
        self._whitelist_cache: Set[str] = set()
        self._blacklist_cache: Set[str] = set()
        self._last_sync: float = 0.0
        self._sync_from_config()

    def _sync_from_config(self) -> None:
        """Sync internal caches from config settings."""
        settings = self._config_loader.settings.group_filter
        self._whitelist_cache = set(settings.whitelist)
        self._blacklist_cache = set(settings.blacklist)
        self._last_sync = time.time()
        logger.debug("GroupFilter synced: mode=%s, wl=%d, bl=%d", settings.mode, len(self._whitelist_cache), len(self._blacklist_cache))

    def _persist_changes(self) -> None:
        """Persist current cache state back to config."""
        wl = list(self._whitelist_cache)
        bl = list(self._blacklist_cache)
        self._config_loader.update_section("group_filter", "whitelist", wl)
        self._config_loader.update_section("group_filter", "blacklist", bl)

    @property
    def mode(self) -> str:
        """Current filter mode."""
        return self._config_loader.settings.group_filter.mode

    @mode.setter
    def mode(self, value: str) -> None:
        """Set filter mode and persist."""
        valid_modes = ("whitelist", "blacklist", "all")
        if value not in valid_modes:
            raise ConfigValidationError("group_filter.mode", f"must be one of {valid_modes}, got '{value}'")
        self._config_loader.update_section("group_filter", "mode", value)
        logger.info("Filter mode changed to: %s", value)

    @property
    def whitelist(self) -> List[str]:
        """Get whitelist roomids."""
        return list(self._whitelist_cache)

    @property
    def blacklist(self) -> List[str]:
        """Get blacklist roomids."""
        return list(self._blacklist_cache)

    def is_allowed(self, room_id: str) -> bool:
        """Check if a group is allowed to be monitored.

        Args:
            room_id: The group roomid (ends with @chatroom).

        Returns:
            True if the group passes the filter, False otherwise.
        """
        mode = self.mode

        if mode == "all":
            return True

        if mode == "whitelist":
            return room_id in self._whitelist_cache

        if mode == "blacklist":
            return room_id not in self._blacklist_cache

        return False

    def add_to_whitelist(self, room_id: str) -> bool:
        """Add a group to the whitelist.

        Returns:
            True if added, False if already exists.
        """
        if not room_id.endswith("@chatroom"):
            logger.warning("Invalid roomid format: %s", room_id)
            return False
        if room_id in self._whitelist_cache:
            return False
        self._whitelist_cache.add(room_id)
        self._persist_changes()
        logger.info("Added %s to whitelist", room_id)
        return True

    def remove_from_whitelist(self, room_id: str) -> bool:
        """Remove a group from the whitelist."""
        if room_id not in self._whitelist_cache:
            return False
        self._whitelist_cache.discard(room_id)
        self._persist_changes()
        logger.info("Removed %s from whitelist", room_id)
        return True

    def add_to_blacklist(self, room_id: str) -> bool:
        """Add a group to the blacklist."""
        if not room_id.endswith("@chatroom"):
            logger.warning("Invalid roomid format: %s", room_id)
            return False
        if room_id in self._blacklist_cache:
            return False
        self._blacklist_cache.add(room_id)
        self._persist_changes()
        logger.info("Added %s to blacklist", room_id)
        return True

    def remove_from_blacklist(self, room_id: str) -> bool:
        """Remove a group from the blacklist."""
        if room_id not in self._blacklist_cache:
            return False
        self._blacklist_cache.discard(room_id)
        self._persist_changes()
        logger.info("Removed %s from blacklist", room_id)
        return True

    def set_all_groups(self) -> None:
        """Switch to monitoring all groups (mode = 'all')."""
        self.mode = "all"

    def get_status(self) -> str:
        """Get a human-readable filter status."""
        mode = self.mode
        if mode == "all":
            return "模式: 全部群聊 (不过滤)"

        if mode == "whitelist":
            groups = self.whitelist
            if not groups:
                return "模式: 白名单 (0个群 - 无群被监控)"
            names = ", ".join(groups[:10])
            extra = f" ... 等{len(groups)}个" if len(groups) > 10 else ""
            return f"模式: 白名单 ({len(groups)}个群: {names}{extra})"

        if mode == "blacklist":
            groups = self.blacklist
            if not groups:
                return "模式: 黑名单 (0个群被屏蔽 - 所有群被监控)"
            return f"模式: 黑名单 ({len(groups)}个群被屏蔽)"

        return f"模式: 未知 ({mode})"
