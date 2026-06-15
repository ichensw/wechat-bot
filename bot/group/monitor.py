"""Group monitor - tracks member counts, stores messages, generates stats.

Uses the event bus for decoupled notification and the database for persistence.
Periodic member count checks are scheduled via the scheduler.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set

from bot.config.settings import MonitorSettings
from bot.core.event_bus import EventBus, EventTypes
from bot.db.repository import Repository
from bot.group.cache import GroupCache
from bot.group.filter import GroupFilter
from bot.wcf.models import WxMessage

if TYPE_CHECKING:
    from bot.wcf.client import WcfClient

logger = logging.getLogger("WeChatBot.GroupMonitor")


class GroupMonitor:
    """Group monitoring manager.

    Responsibilities:
      - Store monitored group messages to database
      - Periodically check member count changes
      - Alert admin on significant member count changes
      - Provide group statistics
    """

    def __init__(
        self,
        settings: MonitorSettings,
        db: Repository,
        group_filter: GroupFilter,
        group_cache: GroupCache,
        wcf_client: "WcfClient",
        event_bus: EventBus,
        send_msg_func: Callable[[str, str], int],
    ):
        self._settings = settings
        self._db = db
        self._group_filter = group_filter
        self._group_cache = group_cache
        self._wcf = wcf_client
        self._event_bus = event_bus
        self._send_msg = send_msg_func
        self._monitored_groups: Set[str] = set()
        self._member_counts: Dict[str, int] = {}

    def process_message(
        self,
        msg_id: str,
        room_id: str,
        sender_wxid: str,
        sender_name: str,
        msg_type: int,
        content: str,
        xml_content: str = "",
    ) -> None:
        """Process and store a monitored group message."""
        if not self._settings.message:
            return

        # Filter by message type if configured
        allowed_types = self._settings.message_types
        if allowed_types and msg_type not in allowed_types:
            return

        # Store the message
        self._db.save_message(
            msg_id=msg_id,
            room_id=room_id,
            sender_wxid=sender_wxid,
            sender_name=sender_name,
            msg_type=msg_type,
            content=content,
            xml_content=xml_content,
        )
        self._monitored_groups.add(room_id)

        # Publish event
        self._event_bus.publish(
            EventTypes.GROUP_MESSAGE_STORED,
            data={"msg_id": msg_id, "room_id": room_id, "sender": sender_wxid},
            source="GroupMonitor",
        )

    def check_member_counts(self) -> None:
        """Check member counts for all monitored groups and alert on changes.

        This method is called by the scheduler periodically.
        """
        if not self._settings.member_count:
            return

        alert_threshold = self._settings.member_change_threshold
        should_alert = self._settings.alert_member_change

        for room_id in list(self._monitored_groups):
            try:
                members = self._wcf.get_chatroom_members(room_id)
                if not members:
                    continue

                current_count = len(members)
                previous_count = self._member_counts.get(room_id)

                # Compute hash for composition change detection
                member_wxids = sorted(members.keys()) if isinstance(members, dict) else sorted(members)
                members_hash = hashlib.md5(",".join(member_wxids).encode()).hexdigest()

                # Save snapshot
                self._db.save_member_snapshot(
                    room_id=room_id,
                    member_count=current_count,
                    members_hash=members_hash,
                )

                # Detect changes
                if previous_count is not None and previous_count != current_count:
                    diff = current_count - previous_count
                    direction = "增加" if diff > 0 else "减少"

                    logger.info(
                        "Group %s: %d -> %d (%s%d)",
                        room_id, previous_count, current_count, direction, abs(diff),
                    )

                    # Publish event
                    self._event_bus.publish(
                        EventTypes.GROUP_MEMBER_CHANGE,
                        data={
                            "room_id": room_id,
                            "previous": previous_count,
                            "current": current_count,
                            "diff": diff,
                        },
                        source="GroupMonitor",
                    )

                    # Alert admin if threshold exceeded
                    if should_alert and abs(diff) >= alert_threshold:
                        admin_wxid = self._get_admin_wxid()
                        if admin_wxid:
                            alert_msg = (
                                f"⚠️ 群聊成员变动\n"
                                f"群: {self._get_group_name(room_id)}\n"
                                f"ID: {room_id}\n"
                                f"人数: {previous_count} → {current_count} ({direction}{abs(diff)}人)"
                            )
                            self._send_msg(alert_msg, admin_wxid)

                # Update cache
                self._member_counts[room_id] = current_count
                self._group_cache.update_member_count(room_id, current_count)

                # Update group info in DB
                self._db.upsert_group_info(room_id=room_id, member_count=current_count)

            except Exception as e:
                logger.error("Error checking members for %s: %s", room_id, e)

    def refresh_groups(self) -> List[Dict]:
        """Refresh group info from WeChat contacts and sync to database/cache.

        Returns:
            List of all group info dicts.
        """
        contacts = self._wcf.get_contacts()
        groups = [c for c in contacts if c.is_group]

        # Update cache
        self._group_cache.refresh_from_contacts(groups)

        # Upsert to DB
        for g in groups:
            self._db.upsert_group_info(room_id=g.wxid, room_name=g.name)

        # Publish event
        self._event_bus.publish(
            EventTypes.GROUP_CACHE_REFRESHED,
            data={"count": len(groups)},
            source="GroupMonitor",
        )

        logger.info("Refreshed %d groups", len(groups))
        return [{"room_id": g.wxid, "name": g.name} for g in groups]

    def get_group_summary(self, room_id: str) -> str:
        """Get a summary string for a group."""
        info = self._db.get_group_info(room_id)
        stats = self._db.get_group_stats(room_id)
        member_count = self._member_counts.get(room_id, 0)
        cached = self._group_cache.get(room_id)
        name = cached.room_name if cached else (info.get("room_name", "Unknown") if info else "Unknown")

        lines = [
            f"📋 群聊概要",
            f"  群名: {name}",
            f"  群ID: {room_id}",
            f"  成员数: {member_count}",
            f"  近24h消息: {stats.get('message_count', 0)}条",
            f"  近24h活跃: {stats.get('active_senders', 0)}人",
        ]

        top_senders = stats.get("top_senders", [])
        if top_senders:
            lines.append("  📊 发言排行:")
            for i, s in enumerate(top_senders[:5], 1):
                lines.append(f"    {i}. {s['name'] or s['wxid']}: {s['count']}条")

        return "\n".join(lines)

    def get_all_groups_summary(self) -> str:
        """Get a summary of all groups."""
        groups = self._group_cache.get_all_cached_unchecked()
        if not groups:
            return "暂无群聊数据"

        lines = [f"📂 共 {len(groups)} 个群:"]
        for g in groups:
            monitored = "✅" if self._group_filter.is_allowed(g.room_id) else "❌"
            lines.append(f"  {monitored} {g.room_name or g.room_id} ({g.member_count}人)")

        return "\n".join(lines)

    def _get_admin_wxid(self) -> Optional[str]:
        """Get admin wxid from config."""
        return self._config_loader.settings.bot.admin_wxid if hasattr(self, "_config_loader") else None

    def _get_group_name(self, room_id: str) -> str:
        """Get group name from cache or DB."""
        cached = self._group_cache.get(room_id)
        if cached and cached.room_name:
            return cached.room_name
        info = self._db.get_group_info(room_id)
        return info.get("room_name", room_id) if info else room_id
