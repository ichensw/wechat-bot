"""Group message handler - filters, @mention check, commands, and message storage.

Logic flow:
  1. Check group filter (whitelist/blacklist/all)
  2. If at_me_required: only respond when @mentioned, EXCEPT for admin commands
  3. If message is a command (starts with prefix): delegate to AdminManager (no @ required)
  4. If message @s the bot: continue processing (future: AI response, etc.)
  5. Store the message for monitoring (regardless of @mention)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from bot.handlers.base import BaseHandler, HandlerPriority, HandlerResult
from bot.wcf.models import WxMessage, MessageType

if TYPE_CHECKING:
    from bot.group.filter import GroupFilter
    from bot.group.monitor import GroupMonitor
    from bot.admin.manager import AdminManager
    from bot.config.settings import BotSettings
    from bot.core.sender import ThreadSafeSender
    from bot.wcf.client import WcfClient

logger = logging.getLogger("WeChatBot.GroupMsgHandler")


def _extract_group_content(content: str) -> str:
    """Extract actual content from group message.

    WeChatFerry group text messages have format: 'sender_wxid:\\nactual content'
    We strip the sender prefix to get the clean content.
    """
    if ":\n" in content:
        _, _, actual = content.partition(":\n")
        return actual
    return content


class GroupMessageHandler(BaseHandler):
    """Handle group messages: filter + @mention check + command dispatch + storage.

    Priority: HIGH (runs early to filter out unwanted group messages).

    The handler enforces these rules:
      - Only allowed groups (per GroupFilter) are processed
      - When at_me_required=True: bot only responds when @mentioned
      - Admin commands in groups do NOT require @mention
      - All messages from allowed groups are stored for monitoring
    """

    def __init__(
        self,
        group_filter: "GroupFilter",
        group_monitor: "GroupMonitor",
        admin_manager: "AdminManager",
        bot_settings: "BotSettings",
        sender: "ThreadSafeSender",
    ):
        self._group_filter = group_filter
        self._group_monitor = group_monitor
        self._admin_manager = admin_manager
        self._bot_settings = bot_settings
        self._sender = sender

    @property
    def name(self) -> str:
        return "GroupMessageHandler"

    @property
    def priority(self) -> HandlerPriority:
        return HandlerPriority.HIGH

    def can_handle(self, msg: WxMessage) -> bool:
        """Only handle group text messages."""
        return msg.is_group and msg.is_text

    def handle(self, msg: WxMessage) -> HandlerResult:
        """Process group message with filter + @mention + command logic."""
        # Step 1: Group filter check
        if not self._group_filter.is_allowed(msg.room_id):
            return HandlerResult.rejected(f"Group {msg.room_id} filtered out")

        # Step 2: Always store the message for monitoring (regardless of @mention)
        actual_content = _extract_group_content(msg.content)
        self._group_monitor.process_message(
            msg_id=msg.msg_id,
            room_id=msg.room_id,
            sender_wxid=msg.sender,
            sender_name=msg.sender_name,
            msg_type=msg.type,
            content=actual_content,
            xml_content=msg.xml,
        )

        # Step 3: Check if this is a command (commands don't require @mention)
        prefix = self._bot_settings.command_prefix
        if prefix and actual_content.strip().startswith(prefix):
            response = self._admin_manager.handle_command(
                sender_wxid=msg.sender,
                content=actual_content.strip(),
                room_id=msg.room_id,
            )
            if response:
                # AdminManager already sent to group when room_id was provided
                # This branch handles the rare case where response is returned
                self._sender.send_text(response, msg.room_id)
            return HandlerResult.handled(response="Command executed")

        # Step 4: @mention check (only respond when @'d, if at_me_required)
        if self._bot_settings.at_me_required:
            # Get bot wxid from admin_manager's wcf client
            bot_wxid = self._admin_manager._wcf.get_user_info().wxid if self._admin_manager._wcf.is_connected() else ""
            if not msg.is_at(bot_wxid):
                return HandlerResult.continue_()

        # Step 5: Bot was @mentioned or at_me_required is False — continue pipeline
        return HandlerResult.continue_()


class PrivateMessageHandler(BaseHandler):
    """Handle private (1-on-1) messages - only for admin and private_whitelist.

    Priority: HIGH (runs early to filter unauthorized private messages).

    Access control:
      - Admin (admin_wxid): always allowed, commands processed
      - private_whitelist: allowed, commands processed
      - Everyone else: message is REJECTED (bot ignores)

    Private messages never require @mention.
    """

    def __init__(self, admin_manager: "AdminManager", bot_settings: "BotSettings", sender: "ThreadSafeSender"):
        self._admin_manager = admin_manager
        self._bot_settings = bot_settings
        self._sender = sender

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
        """Process private message with access control."""
        # Step 1: Access control — only admin + private_whitelist
        if not self._bot_settings.is_private_allowed(msg.sender):
            logger.debug("Private message from unauthorized wxid: %s", msg.sender)
            return HandlerResult.rejected(f"Private chat not allowed for {msg.sender}")

        # Step 2: Try as admin command
        response = self._admin_manager.handle_command(msg.sender, msg.content)
        if response:
            # Send response back to the user (thread-safe)
            self._sender.send_text(response, msg.sender)
            return HandlerResult.handled(response=response)

        # Step 3: Not a command, but authorized user — continue pipeline
        # (future: AI chat response, etc.)
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
