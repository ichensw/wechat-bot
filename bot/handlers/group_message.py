"""Group message handler - filters and stores group messages."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot.handlers.base import BaseHandler, HandlerPriority, HandlerResult
from bot.wcf.models import WxMessage, MessageType

if TYPE_CHECKING:
    from bot.group.filter import GroupFilter
    from bot.group.monitor import GroupMonitor

logger = logging.getLogger("WeChatBot.GroupMsgHandler")


class GroupMessageHandler(BaseHandler):
    """Handle group messages: filter by blacklist/whitelist, then store and monitor.

    Priority: HIGH (runs early to filter out unwanted group messages).
    """

    def __init__(self, group_filter: "GroupFilter", group_monitor: "GroupMonitor"):
        self._group_filter = group_filter
        self._group_monitor = group_monitor

    @property
    def name(self) -> str:
        return "GroupMessageHandler"

    @property
    def priority(self) -> HandlerPriority:
        return HandlerPriority.HIGH

    def can_handle(self, msg: WxMessage) -> bool:
        """Only handle group messages."""
        return msg.is_group

    def handle(self, msg: WxMessage) -> HandlerResult:
        """Filter and store group messages."""
        # Check if group is allowed by filter
        if not self._group_filter.is_allowed(msg.room_id):
            return HandlerResult.rejected(f"Group {msg.room_id} filtered out")

        # Store the message
        self._group_monitor.process_message(
            msg_id=msg.msg_id,
            room_id=msg.room_id,
            sender_wxid=msg.sender,
            sender_name=msg.sender_name,
            msg_type=msg.type,
            content=msg.content,
            xml_content=msg.xml,
        )

        return HandlerResult.continue_()


class PrivateMessageHandler(BaseHandler):
    """Handle private (1-on-1) messages - mainly for admin commands.

    Priority: HIGH (runs early to catch admin commands).
    """

    def __init__(self, admin_manager: "AdminManager"):
        self._admin_manager = admin_manager

    @property
    def name(self) -> str:
        return "PrivateMessageHandler"

    @property
    def priority(self) -> HandlerPriority:
        return HandlerPriority.HIGH

    def can_handle(self, msg: WxMessage) -> bool:
        """Only handle private text messages."""
        return msg.is_private and msg.is_text

    def handle(self, msg: WxMessage) -> HandlerResult:
        """Process admin commands from private messages."""
        response = self._admin_manager.handle_command(msg.sender, msg.content)
        if response:
            return HandlerResult.handled(response=response)
        return HandlerResult.continue_()


class SystemMessageHandler(BaseHandler):
    """Handle system messages (revoke, notifications, etc.).

    Priority: LOW (logging only, doesn't block other handlers).
    """

    @property
    def name(self) -> str:
        return "SystemMessageHandler"

    @property
    def priority(self) -> HandlerPriority:
        return HandlerPriority.LOW

    def can_handle(self, msg: WxMessage) -> bool:
        """Handle system messages."""
        return msg.is_system

    def handle(self, msg: WxMessage) -> HandlerResult:
        """Log system messages."""
        logger.info("System message: type=%s room=%s content=%s", msg.type_name, msg.room_id, msg.content[:100])
        return HandlerResult.continue_()


# Import at bottom to avoid circular imports
from bot.admin.manager import AdminManager  # noqa: E402
